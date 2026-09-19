"""Single-replica WSGI deployment: isolated durable sessions and bounded jobs.

Run behind an HTTPS reverse proxy; use --local for loopback verification only.
The scheduling model remains in Workspace. This module owns transport/storage.
"""
import argparse
import base64
from contextlib import contextmanager
import hashlib
import hmac
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import subprocess
import sys
import sysconfig
import threading
import time
from urllib.parse import urlsplit
import uuid

from .workspace import Workspace, RunError, INPUT_SCHEMAS, OUTPUT_SCHEMAS, decode_upload, ROOT
from .webapp import WEB, MAX_REQUEST

ID = re.compile(r'^[a-f0-9]{32}$')
MUTATIONS = {'/api/sample','/api/import','/api/generate','/api/optimise','/api/alternative','/api/replan','/api/review'}


def atomic_json(path, value):
    pending = path.with_suffix('.pending')
    pending.write_text(json.dumps(value),encoding='utf-8')
    pending.replace(path)


def remove_owned_directory(path, parent):
    if not ID.fullmatch(path.name) or path.is_symlink() or path.resolve().parent != parent.resolve():
        raise ValueError('Refusing to remove a directory outside the owned store.')
    shutil.rmtree(path)


class DurableWorkspace(Workspace):
    def __init__(self, root):
        super().__init__()
        self.temp.cleanup(); self.temp = None
        self.root = Path(root).resolve(); self.root.mkdir(parents=True,exist_ok=True)
        state = self.root/'state.json'
        if state.exists():
            stored = json.loads(state.read_text(encoding='utf-8'))
            self.sources = stored['sources']
            for id, view in stored['views'].items():
                if not ID.fullmatch(id):raise RunError('Invalid stored run identity.')
                folder = self.root/id
                files = {n:(folder/'inputs'/n).read_bytes() for n in INPUT_SCHEMAS}
                files.update({n:(folder/'schedule'/n).read_bytes() for n in OUTPUT_SCHEMAS if (folder/'schedule'/n).exists()})
                self.runs[id] = {'view':view,'files':files,'folder':folder}
            self.check_sources()

    def checkpoint(self, job_id):
        return {'sources':self.sources,'last_job_id':job_id,'views':{id:r['view'] for id,r in self.runs.items()}}

    def close(self):
        pass  # Owned by the deployment store and its explicit expiry policy.


def dispatch(workspace, route, body):
    id = body.get('id','')
    if route == '/api/runs':return workspace.summaries()
    if route == '/api/run':return workspace.get(id)['view']
    if route == '/api/sample':return workspace.sample()
    if route == '/api/import':return workspace.create(decode_upload(body.get('files')),body.get('scenario','A'),'Uploaded schedule' if len(body.get('files',[]))==11 else 'Uploaded inputs')
    if route == '/api/generate':return workspace.generate(id)
    if route == '/api/compare':return workspace.compare(body.get('base_id',''),body.get('candidate_id',''))
    if route == '/api/rollback':return workspace.rollback(id,body.get('version'))
    if route == '/api/review':return workspace.record_review(id,body.get('version'),body.get('reviewer'),body.get('decision'),body.get('note'),body.get('request_id'))
    seconds=body.get('seconds',30)
    if type(seconds) not in (int,float) or not 1 <= seconds <= 60:raise RunError('Use a solver search limit of 1..60 seconds.')
    if route == '/api/optimise':return workspace.optimise(id,body.get('scenario'),seconds=seconds,workers=1)
    if route == '/api/alternative':
        run=workspace.assert_snapshot(id,body.get('version'))
        conflict=next((c for c in run['view']['planning']['conflicts'] if c['id']==body.get('conflict_id')),None)
        if not conflict or not conflict['actionable']:raise RunError('Choose an implemented actionable conflict.')
        workspace.export(id)
        return workspace.optimise(id,run['view']['scenario'],seconds=seconds,workers=1,alternative_for=conflict)
    if route == '/api/replan':return workspace.replan(id,body.get('version'),body.get('proposal'),seconds=seconds,workers=1)
    raise RunError('Unknown operation.')


def child_job(root, job_id):
    folder=Path(root)/'jobs'/job_id
    request=json.loads((folder/'request.json').read_text(encoding='utf-8'))
    workspace=DurableWorkspace(Path(root)/'sessions'/request['session'])
    try:
        result=dispatch(workspace,request['route'],request['body'])
        atomic_json(folder/'candidate.json',workspace.checkpoint(job_id))
        atomic_json(folder/'response.json',{'ok':True,'result':result})
    except (ValueError,TypeError,KeyError) as exc:
        atomic_json(folder/'response.json',{'ok':False,'error':str(exc),'details':getattr(exc,'details',None)})
    except Exception:
        atomic_json(folder/'response.json',{'ok':False,'error':'Operation failed; no new run was committed. Original runs remain available.'})


class Store:
    def __init__(self, root, *, deadline=120, max_sessions=32, max_bytes=512*1024*1024, start_worker=True):
        self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True)
        for name in ('sessions','jobs'):(self.root/name).mkdir(exist_ok=True)
        self.owner=(self.root/'owner.lock').open('a+b')
        try:
            if os.name=='nt':
                import msvcrt
                self.owner.seek(0);self.owner.write(b'1');self.owner.flush();self.owner.seek(0)
                msvcrt.locking(self.owner.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.owner.close();raise RuntimeError('Only one hosted server may own this data directory.')
        self.deadline=deadline;self.max_sessions=max_sessions;self.max_bytes=max_bytes
        self.lock=threading.RLock();self.stop=threading.Event();self.process=None
        self.db=self.root/'jobs.sqlite'
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, session TEXT, request_id TEXT, digest TEXT, state TEXT, created REAL, error TEXT, UNIQUE(session,request_id))')
            pending=db.execute("SELECT id,session FROM jobs WHERE state IN ('queued','running','cancelling')").fetchall()
            for job,sid in pending:
                state=self.root/'sessions'/sid/'state.json'
                committed=state.exists() and json.loads(state.read_text(encoding='utf-8')).get('last_job_id')==job
                db.execute('UPDATE jobs SET state=?,error=? WHERE id=?',('done' if committed else 'interrupted',None if committed else 'Server restarted before commit; resubmit explicitly.',job))
        self.thread=threading.Thread(target=self.worker,daemon=True)
        if start_worker:self.thread.start()

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.db,timeout=10)
        try:
            with db:yield db
        finally:db.close()

    def close(self):
        self.stop.set()
        if self.thread.is_alive():self.thread.join(timeout=5)
        self.owner.close()

    def expire(self):
        with self.connect() as db:
            active={r[0] for r in db.execute("SELECT session FROM jobs WHERE state IN ('queued','running','cancelling')")}
            for folder in (self.root/'sessions').iterdir():
                if not folder.is_dir() or not ID.fullmatch(folder.name) or folder.name in active:continue
                info=folder/'session.json'
                if info.exists() and time.time()-json.loads(info.read_text())['created'] > 86400:
                    for (job,) in db.execute('SELECT id FROM jobs WHERE session=?',(folder.name,)).fetchall():
                        path=self.root/'jobs'/job
                        if ID.fullmatch(job) and path.is_dir():remove_owned_directory(path,self.root/'jobs')
                    db.execute('DELETE FROM jobs WHERE session=?',(folder.name,))
                    remove_owned_directory(folder,self.root/'sessions')

    def session(self, candidate=None):
        with self.lock:
            self.expire()
            if candidate and ID.fullmatch(candidate) and (self.root/'sessions'/candidate/'session.json').exists():return candidate
            if len(list((self.root/'sessions').iterdir())) >= self.max_sessions:raise RunError('Demo session capacity reached. Sessions expire after 24 hours.')
            sid=uuid.uuid4().hex;folder=self.root/'sessions'/sid;folder.mkdir()
            atomic_json(folder/'session.json',{'created':time.time()})
            return sid

    def submit(self, sid, request_id, route, body):
        if not isinstance(request_id,str) or not re.fullmatch(r'[a-zA-Z0-9-]{1,64}',request_id):raise RunError('A request identifier is required.')
        digest=hashlib.sha256(json.dumps([route,body],sort_keys=True).encode()).hexdigest()
        with self.lock,self.connect() as db:
            old=db.execute('SELECT id,digest FROM jobs WHERE session=? AND request_id=?',(sid,request_id)).fetchone()
            if old:
                if old[1]!=digest:raise RunError('Request identifier reused with different contents.')
                return old[0]
            if db.execute("SELECT count(*) FROM jobs WHERE session=? AND state IN ('queued','running','cancelling')",(sid,)).fetchone()[0]:raise RunError('This session already has a pending job. Wait or cancel it first.')
            if db.execute("SELECT count(*) FROM jobs WHERE state IN ('queued','running','cancelling')").fetchone()[0]>=8:raise RunError('Demo queue is full; retry later.')
            if db.execute('SELECT count(*) FROM jobs WHERE session=?',(sid,)).fetchone()[0]>=100:raise RunError('This session reached its 100-job limit.')
            size=sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file())
            if size+MAX_REQUEST > self.max_bytes:raise RunError('Demo storage quota reached; export existing work and contact the host.')
            job=uuid.uuid4().hex;folder=self.root/'jobs'/job;folder.mkdir()
            atomic_json(folder/'request.json',{'session':sid,'route':route,'body':body})
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',(job,sid,request_id,digest,'queued',time.time(),None))
            return job

    def job(self, sid, job):
        with self.connect() as db:row=db.execute('SELECT state,error FROM jobs WHERE id=? AND session=?',(job,sid)).fetchone()
        if not row:raise RunError('Job not found in this session.')
        result={'job_id':job,'state':row[0],'error':row[1]}
        response=self.root/'jobs'/job/'response.json'
        if row[0]=='done':result.update(json.loads(response.read_text(encoding='utf-8')))
        elif row[0]=='failed' and response.exists():result['details']=json.loads(response.read_text(encoding='utf-8')).get('details')
        return result

    def active(self, sid):
        with self.connect() as db:row=db.execute("SELECT id FROM jobs WHERE session=? AND state IN ('queued','running','cancelling') ORDER BY created DESC LIMIT 1",(sid,)).fetchone()
        return self.job(sid,row[0]) if row else None

    def cancel(self, sid, job):
        with self.lock,self.connect() as db:
            state=self.job(sid,job)['state']
            if state in ('queued','running'):db.execute('UPDATE jobs SET state=? WHERE id=?',('cancelled' if state=='queued' else 'cancelling',job))
        return self.job(sid,job)

    def worker(self):
        while not self.stop.wait(.1):
            with self.lock,self.connect() as db:
                row=db.execute("SELECT id,session FROM jobs WHERE state='queued' ORDER BY created LIMIT 1").fetchone()
                if not row:continue
                job,sid=row;db.execute("UPDATE jobs SET state='running' WHERE id=?",(job,))
            folder=self.root/'jobs'/job;start=time.monotonic();reason=None
            # Windows venv launchers spawn a second process: invoke the base interpreter
            # with this environment's trusted site-packages to keep cancellation exact.
            executable=getattr(sys,'_base_executable',sys.executable) if os.name=='nt' else sys.executable
            bootstrap=f"import sys;sys.path.insert(0,{sysconfig.get_paths()['purelib']!r});from ps1.hosted import child_job;child_job({str(self.root)!r},{job!r})"
            try:
                self.process=subprocess.Popen([executable,'-c',bootstrap],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                while self.process.poll() is None:
                    if self.stop.wait(.1):reason='interrupted'
                    elif self.job(sid,job)['state']=='cancelling':reason='cancelled'
                    elif time.monotonic()-start>self.deadline:reason='timed_out'
                    if reason:
                        self.process.kill();self.process.wait();break
                response_path=folder/'response.json'
                response=json.loads(response_path.read_text(encoding='utf-8')) if response_path.exists() else {'ok':False,'error':'Worker stopped without a result; parent retained.'}
                with self.lock,self.connect() as db:
                    if not reason and self.job(sid,job)['state']=='cancelling':reason='cancelled'
                    if not reason and sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file())>self.max_bytes:
                        reason='storage_limit'
                    if not reason and response.get('ok'):
                        atomic_json(self.root/'sessions'/sid/'state.json',json.loads((folder/'candidate.json').read_text(encoding='utf-8')))
                    state=reason or ('done' if response.get('ok') else 'failed')
                    message=(f'Job {reason}; no new decisions committed. Original runs remain available.' if reason else response.get('error'))
                    db.execute('UPDATE jobs SET state=?,error=? WHERE id=?',(state,message,job))
            except Exception:
                with self.connect() as db:db.execute("UPDATE jobs SET state='failed',error='Worker failure; original runs retained.' WHERE id=?",(job,))
            finally:
                self.process=None
                # Only checkpointed runs are visible. Reclaim an interrupted child's
                # unpublished folders and large request/candidate copies.
                with self.lock:
                    session_root=self.root/'sessions'/sid
                    checkpoint=session_root/'state.json'
                    known=json.loads(checkpoint.read_text(encoding='utf-8'))['views'] if checkpoint.exists() else {}
                    for path in session_root.iterdir():
                        if path.is_dir() and ID.fullmatch(path.name) and path.name not in known:
                            remove_owned_directory(path,session_root)
                    for name in ('request.json','candidate.json','candidate.pending'):
                        (folder/name).unlink(missing_ok=True)


class Application:
    def __init__(self, store, origin, password=None, local=False):
        parsed=urlsplit(origin)
        if parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password or not parsed.netloc:raise ValueError('Origin must be scheme and host only.')
        if not local and (parsed.scheme!='https' or not password):raise ValueError('Hosted mode requires HTTPS origin and a nonempty demo password.')
        if local and (parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost')):raise ValueError('Local mode requires a loopback HTTP origin.')
        self.store=store;self.origin=origin;self.host=parsed.netloc;self.password=password;self.local=local
        key=store.root/'csrf.key'
        if not key.exists():key.write_bytes(secrets.token_bytes(32))
        self.secret=key.read_bytes()

    def token(self,sid):return hmac.new(self.secret,sid.encode(),hashlib.sha256).hexdigest()

    def __call__(self, env, start_response):
        headers=[('Cache-Control','no-store'),('X-Content-Type-Options','nosniff'),('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"),('Referrer-Policy','no-referrer')]
        def send(status,data,kind='application/json; charset=utf-8'):
            raw=data if isinstance(data,bytes) else json.dumps(data).encode()
            start_response(status,headers+[('Content-Type',kind),('Content-Length',str(len(raw)))])
            return [raw]
        try:
            path=env.get('PATH_INFO','/');method=env.get('REQUEST_METHOD','GET')
            if path=='/api/health' and method=='GET':return send('200 OK',{'status':'ready','scope':'hosted_step10'})
            if env.get('HTTP_HOST')!=self.host:return send('403 Forbidden',{'error':'Unexpected host.'})
            if self.password:
                try:provided=base64.b64decode(env.get('HTTP_AUTHORIZATION','').removeprefix('Basic '),validate=True).decode().split(':',1)[1]
                except Exception:provided=''
                if not hmac.compare_digest(provided.encode(),self.password.encode()):
                    headers.append(('WWW-Authenticate','Basic realm="Tracklight judging demo"'))
                    return send('401 Unauthorized',{'error':'Demo access required.'})
            cookie=SimpleCookie();cookie.load(env.get('HTTP_COOKIE',''))
            candidate=cookie['tracklight_session'].value if 'tracklight_session' in cookie else None
            if method=='GET' and path=='/':
                sid=self.store.session(candidate)
                headers.append(('Set-Cookie',f'tracklight_session={sid}; Path=/; HttpOnly; SameSite=Lax; Max-Age=86400'+('' if self.local else '; Secure')))
                raw=(WEB/'index.html').read_bytes().replace(b'__SESSION_TOKEN__',self.token(sid).encode())
                raw=raw.replace(b'LOCAL PROTOTYPE',b'JUDGING DEMO').replace(b'Local session',b'Isolated session').replace(b'All runs are kept separately for this local session.',b'Isolated storage expires 24 hours after session creation. Export your work.')
                return send('200 OK',raw,'text/html; charset=utf-8')
            if not candidate or not ID.fullmatch(candidate) or not (self.store.root/'sessions'/candidate/'session.json').exists():return send('403 Forbidden',{'error':'Open the app to establish a session.'})
            sid=candidate
            if time.time()-json.loads((self.store.root/'sessions'/sid/'session.json').read_text())['created']>86400:return send('403 Forbidden',{'error':'Session expired. Reload the app to begin another session.'})
            if method=='GET':
                if path in ('/app.js','/style.css'):return send('200 OK',(WEB/path[1:]).read_bytes(),'text/javascript' if path.endswith('.js') else 'text/css')
                if path=='/api/jobs/current':return send('200 OK',self.store.active(sid))
                if path.startswith('/api/jobs/'):return send('200 OK',self.store.job(sid,path.rsplit('/',1)[1]))
                if path.startswith('/api/export/'):
                    raw,_=DurableWorkspace(self.store.root/'sessions'/sid).export(path.rsplit('/',1)[1])
                    headers.append(('Content-Disposition','attachment; filename="tracklight-review.zip"'))
                    return send('200 OK',raw,'application/zip')
            if method!='POST':return send('404 Not Found',{'error':'Not found.'})
            if env.get('HTTP_ORIGIN') not in (None,self.origin) or not hmac.compare_digest(env.get('HTTP_X_PS1_TOKEN',''),self.token(sid)):return send('403 Forbidden',{'error':'Reload the app before submitting.'})
            length=int(env.get('CONTENT_LENGTH','0'))
            if not 0<length<=MAX_REQUEST or env.get('CONTENT_TYPE','').split(';')[0]!='application/json':return send('413 Payload Too Large',{'error':'Use a JSON body of at most 9 MiB.'})
            body=json.loads(env['wsgi.input'].read(length))
            if not isinstance(body,dict):raise RunError('Expected a JSON object.')
            if path=='/api/jobs/cancel':return send('200 OK',self.store.cancel(sid,body.get('job_id','')))
            if path in MUTATIONS:
                job=self.store.submit(sid,env.get('HTTP_X_REQUEST_ID'),path,body)
                return send('202 Accepted',{'job_id':job,'state':'queued'})
            if path in ('/api/runs','/api/run','/api/compare','/api/rollback'):
                return send('200 OK',dispatch(DurableWorkspace(self.store.root/'sessions'/sid),path,body))
            return send('404 Not Found',{'error':'Not found.'})
        except (ValueError,TypeError,KeyError) as exc:return send('400 Bad Request',{'error':str(exc),'details':getattr(exc,'details',None)})
        except Exception:return send('500 Internal Server Error',{'error':'Operation failed; existing runs remain preserved.'})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local',action='store_true')
    parser.add_argument('--port',type=int,default=int(os.environ.get('PORT','8080')))
    parser.add_argument('--data-dir',type=Path,default=Path(os.environ.get('TRACKLIGHT_DATA_DIR','.tracklight')))
    args=parser.parse_args()
    origin=f'http://127.0.0.1:{args.port}' if args.local else os.environ.get('TRACKLIGHT_ORIGIN','')
    store=Store(args.data_dir)
    try:
        app=Application(store,origin,os.environ.get('TRACKLIGHT_DEMO_PASSWORD'),local=args.local)
        from waitress import serve
        print(f'Tracklight ready: {origin}',flush=True)
        serve(app,host='127.0.0.1' if args.local else '0.0.0.0',port=args.port,threads=4,
              max_request_body_size=MAX_REQUEST,channel_timeout=30,connection_limit=64,expose_tracebacks=False)
    finally:store.close()


if __name__=='__main__':main()
