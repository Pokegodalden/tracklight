"""Durability and transport boundaries tested with real isolated worker processes."""
import base64
from io import BytesIO
import json
from pathlib import Path
import tempfile
import time
import unittest
import uuid

from ps1.hosted import Store,Application,DurableWorkspace,atomic_json
from test_planner import tiny_inputs
from test_planner import plan_files
from ps1.workspace import Workspace


class HostedTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=Store(Path(self.temp.name));self.addCleanup(self.store.close)
        self.app=Application(self.store,'http://127.0.0.1:8780',local=True)
        self.status,self.headers,_=self.call('/')
        self.cookie=dict(self.headers)['Set-Cookie'].split(';')[0]
        self.sid=self.cookie.split('=')[1]

    def call(self,path,body=None,cookie='',token=None,**extra):
        data=json.dumps(body or {}).encode()
        env={'REQUEST_METHOD':'GET' if body is None else 'POST','PATH_INFO':path,'HTTP_HOST':'127.0.0.1:8780',
             'HTTP_COOKIE':cookie,'CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(data)),
             'wsgi.input':BytesIO(data),'HTTP_X_REQUEST_ID':uuid.uuid4().hex}
        if token:env['HTTP_X_PS1_TOKEN']=token
        env.update(extra);captured=[]
        raw=b''.join(self.app(env,lambda status,headers:captured.extend([status,headers])))
        return captured[0],captured[1],raw

    def post(self,route,body,**kwargs):
        status,_,raw=self.call(route,body,self.cookie,self.app.token(self.sid),**kwargs)
        return status,json.loads(raw)

    def wait(self,job):
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            result=self.store.job(self.sid,job)
            if result['state'] not in ('queued','running','cancelling'):return result
            time.sleep(.05)
        self.fail('Worker did not finish within test deadline.')

    def imported(self):
        files=[{'name':n,'data':base64.b64encode(raw).decode()} for n,raw in tiny_inputs().items()]
        status,job=self.post('/api/import',{'files':files,'scenario':'A'})
        self.assertEqual(status,'202 Accepted')
        result=self.wait(job['job_id']);self.assertEqual(result['state'],'done',result)
        return result['result']

    def test_isolation_csrf_host_and_private_cookie(self):
        self.assertIn('HttpOnly',dict(self.headers)['Set-Cookie'])
        self.assertEqual(self.call('/api/runs',{},self.cookie)[0],'403 Forbidden')
        self.assertEqual(self.post('/api/runs',{},HTTP_ORIGIN='https://wrong.example')[0],'403 Forbidden')
        self.assertEqual(self.call('/',HTTP_HOST='wrong.example')[0],'403 Forbidden')
        first=self.imported();sid=self.store.session()
        self.assertNotIn(first['id'],DurableWorkspace(self.store.root/'sessions'/sid).runs)
        status,_,_=self.call('/api/run',{'id':first['id']},'tracklight_session='+sid,self.app.token(sid))
        self.assertEqual(status,'400 Bad Request')

    def test_real_import_solve_export_and_restart_recovery(self):
        parent=self.imported()
        _,job=self.post('/api/optimise',{'id':parent['id'],'scenario':'A','seconds':2})
        child=self.wait(job['job_id'])['result']
        self.assertTrue(child['planning']['summary']['checked_model_plan'])
        self.assertEqual(child['optimisation']['settings']['workers'],1)
        status,_,raw=self.call('/api/export/'+child['id'],cookie=self.cookie)
        self.assertEqual(status,'200 OK');self.assertTrue(raw.startswith(b'PK'))
        self.store.close()
        # The first store is closed before reopening its exclusive data directory.
        self.store=Store(Path(self.temp.name));self.addCleanup(self.store.close)
        self.app=Application(self.store,'http://127.0.0.1:8780',local=True)
        status,view=self.post('/api/run',{'id':child['id']})
        self.assertEqual(status,'200 OK');self.assertEqual(view['schedule_snapshot'],child['schedule_snapshot'])

    def test_idempotency_and_cancel_without_committing(self):
        self.store.stop.set();self.store.thread.join()
        id='same-request';body={'scenario':'A'}
        _,first=self.post('/api/sample',body,HTTP_X_REQUEST_ID=id)
        _,again=self.post('/api/sample',body,HTTP_X_REQUEST_ID=id)
        self.assertEqual(first['job_id'],again['job_id'])
        self.assertEqual(self.post('/api/sample',{'scenario':'B'},HTTP_X_REQUEST_ID=id)[0],'400 Bad Request')
        self.assertEqual(self.post('/api/sample',{})[0],'400 Bad Request')
        _,cancelled=self.post('/api/jobs/cancel',{'job_id':first['job_id']})
        self.assertEqual(cancelled['state'],'cancelled')
        self.assertEqual(DurableWorkspace(self.store.root/'sessions'/self.sid).summaries(),[])

    def test_timeout_kills_worker_and_preserves_original(self):
        parent=self.imported();self.store.deadline=.00001
        _,job=self.post('/api/optimise',{'id':parent['id'],'scenario':'A','seconds':60})
        result=self.wait(job['job_id']);self.assertEqual(result['state'],'timed_out')
        workspace=DurableWorkspace(self.store.root/'sessions'/self.sid)
        self.assertEqual([r['id'] for r in workspace.summaries()],[parent['id']])

    def test_interrupted_jobs_and_expiry_are_explicit(self):
        self.store.stop.set();self.store.thread.join()
        _,job=self.post('/api/sample',{})
        self.store.close();self.store=Store(Path(self.temp.name),start_worker=False);self.addCleanup(self.store.close)
        self.assertEqual(self.store.job(self.sid,job['job_id'])['state'],'interrupted')
        atomic_json(self.store.root/'sessions'/self.sid/'session.json',{'created':time.time()-90000})
        replacement=self.store.session(self.sid)
        self.assertNotEqual(replacement,self.sid)
        self.assertFalse((self.store.root/'sessions'/self.sid).exists())

    def test_public_mode_requires_https_and_demo_access(self):
        with self.assertRaises(ValueError):Application(self.store,'http://example.com','test')
        with self.assertRaises(ValueError):Application(self.store,'https://example.com')
        self.app=Application(self.store,'https://example.com','test-only-password')
        self.assertEqual(self.call('/',HTTP_HOST='example.com')[0],'401 Unauthorized')
        status,headers,_=self.call('/',HTTP_HOST='example.com',HTTP_AUTHORIZATION='Basic '+base64.b64encode(b'demo:test-only-password').decode())
        self.assertEqual(status,'200 OK');self.assertIn('Secure',dict(headers)['Set-Cookie'])
        with self.assertRaises(RuntimeError):Store(Path(self.temp.name))

    def test_cross_scenario_incumbent_is_checked_under_target_policy(self):
        with_workspace=Workspace()
        try:
            inputs=with_workspace.create(tiny_inputs(),'A','Inputs')
            parent=with_workspace.create(plan_files(with_workspace,inputs,second_week=True),'A','Late A')
            c=with_workspace.optimise(parent['id'],'C',seconds=1e-9,workers=1)
            self.assertTrue(c['planning']['summary']['checked_model_plan'])
            self.assertEqual(c['optimisation']['selected_from'],'incumbent')
            self.assertTrue(all(row['scenario']=='C' for row in c['tables']['RESULTS.csv']))
            b=with_workspace.optimise(parent['id'],'B',seconds=1e-9,workers=1)
            self.assertIsNone(b['tables'])
            self.assertTrue(all(row['scenario']=='A' for row in parent['tables']['RESULTS.csv']))
        finally:with_workspace.close()


if __name__=='__main__':unittest.main()
