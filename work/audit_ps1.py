import csv, json, hashlib, re, html, collections, datetime as dt
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(r'C:\Users\pokeg\Downloads\PS1')
OUT=Path(__file__).parent
def read(name, folder='01_data'):
    path=ROOT/folder/name
    with path.open(encoding='utf-8-sig',newline='') as f:
        rd=csv.DictReader(f); rows=list(rd); fields=rd.fieldnames
    return fields,rows
data={}
inventory=[]
for folder in ['01_data','03_submission_sample']:
    for p in sorted((ROOT/folder).glob('*.csv')):
        fields,rows=read(p.name,folder)
        data[p.stem]=rows
        inventory.append(dict(file=p.name,rows=len(rows),columns=fields,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
L=data['01_LINES']; S=data['02_STATIONS']; E=data['03_SECTORS']; U=data['04_LOCATION_SUPPLY']; B=data['05_BUFFER_LOCATION']; P=data['07_PROJECT_DETAILS']; A=data['08_ACTIVITY_DETAILS']; X=data['SCHEDULE_ACCESS']; O=data['SCHEDULE_OCCUPANCY']; R=data['RESULTS']
param={r['key']:r['value'] for r in data['06_PARAMETERS']}
base=dt.date.fromisoformat(param['horizon_start']); horizon=int(param['horizon_weeks'])
projects={r['contract_number']:r for r in P}; acts={r['activity_id']:r for r in A}; supply={r['location_id']:int(r['supply_capacity']) for r in U}
checks=[]
def check(name, errors, scope='direct'):
    checks.append(dict(name=name,scope=scope,status='PASS' if not errors else 'FAIL',count=len(errors),evidence=errors))
def duplicates(rows,keys):
    counts=collections.Counter(tuple(r[k] for k in keys) for r in rows)
    return [dict(key=k,count=v) for k,v in counts.items() if v>1]
for rows,keys,name in [(L,['line_code'],'line keys'),(S,['line_code','station_id'],'station composite keys'),(E,['sector_id'],'sector keys'),(U,['location_id'],'supply keys'),(P,['contract_number','activity_type'],'project keys'),(A,['activity_id'],'activity keys'),(X,['activity_id','access_seq'],'access sequence keys'),(X,['activity_id','week'],'one access per activity week'),(O,['activity_id','week','location_id'],'occupancy keys'),(R,['scenario','contract_number'],'result keys')]: check(name,duplicates(rows,keys))
check('blank or malformed CSV cells',[dict(file=name,row=i+2,field=k) for name,rows in data.items() for i,r in enumerate(rows) for k,v in r.items() if k is None or v is None or (v=='' and k!='predecessor_activity_id')])
lineids={r['line_code'] for r in L}; stationkeys={(r['line_code'],r['station_id']) for r in S}
check('input foreign keys',[r for r in A if r['contract_number'] not in projects or r['start_location_id'] not in supply or r['end_location_id'] not in supply or (r['predecessor_activity_id'] and r['predecessor_activity_id'] not in acts)]+[r for r in S if r['line_code'] not in lineids]+[r for r in E if (r['line_code'],r['from_station_id']) not in stationkeys or (r['line_code'],r['to_station_id']) not in stationkeys])
check('sample foreign keys',[r for r in X if r['activity_id'] not in acts]+[r for r in O if r['activity_id'] not in acts or r['location_id'] not in supply]+[r for r in R if r['contract_number'] not in projects])
check('activity and project type match',[r for r in A if r['activity_type']!=projects[r['contract_number']]['activity_type']])
ordered={line:sorted([r for r in E if r['line_code']==line],key=lambda r:int(r['seq'])) for line in lineids}
spans={}; spanmeta={}
for a in A:
    start,end=a['start_location_id'],a['end_location_id']; _,line,_,bound=start.split(':')
    seq=ordered[line]; ids=[r['sector_id'] for r in seq]
    i,j=sorted((ids.index(start.rsplit(':',1)[0]),ids.index(end.rsplit(':',1)[0])))
    path=seq[i:j+1]
    locs={r['sector_id']+':'+bound for r in path}
    locs|={f'PLAT:{line}:{station}:{bound}' for r in path for station in [r['from_station_id'],r['to_station_id']]}
    spans[a['activity_id']]=locs; spanmeta[a['activity_id']]=(line,bound,i,j)
aw=collections.defaultdict(list); ow=collections.defaultdict(list)
for r in X: aw[r['activity_id']].append(r)
for r in O: ow[r['activity_id'],int(r['week'])].append(r)
ledger=[]; release_errors=[]; seq_errors=[]; domain_errors=[]
for a in A:
    aid=a['activity_id']; rows=aw[aid]; weeks=sorted(int(r['week']) for r in rows)
    done=sum(1+0.5*int(r['eclo']) for r in rows)
    release=(dt.date.fromisoformat(a['planned_start_date'])-base).days//7+1
    ledger.append(dict(activity=aid,contract=a['contract_number'],required=int(a['total_accesses']),delivered=done,weeks=weeks,release_week=release,span_locations=len(spans[aid])))
    release_errors += [dict(activity=aid,week=w,release=release) for w in weeks if w<release]
    if sorted(int(r['access_seq']) for r in rows)!=list(range(1,len(rows)+1)): seq_errors.append(aid)
    for r in rows:
        if int(r['week']) not in range(1,horizon+1) or r['eclo'] not in ['0','1'] or not 1<=int(r['access_night'])<=int(projects[a['contract_number']]['number_of_maximum_access_per_week']):domain_errors.append(r)
check('complete exact workload',[r for r in ledger if r['delivered']!=r['required']])
check('planned release week',release_errors);check('sequential access_seq',seq_errors);check('access field domains and horizon',domain_errors)
check('scenario A ECLO forbidden',[r for r in X if r['eclo']!='0'])
spanerrors=[]
for r in X:
    key=r['activity_id'],int(r['week']);actual={o['location_id'] for o in ow[key]};expected=spans[key[0]]
    if expected!=actual: spanerrors.append(dict(activity=key[0],week=key[1],missing=sorted(expected-actual),extra=sorted(actual-expected)))
check('work-span occupancy expansion',spanerrors)
accesskeys={(r['activity_id'],int(r['week'])) for r in X}
check('occupancy has access row',[dict(activity=k[0],week=k[1]) for k in ow if k not in accesskeys])
contractweek=collections.defaultdict(set);front=collections.defaultdict(set)
for r in X:
    a=acts[r['activity_id']]; c=a['contract_number'];typ=a['activity_type'];w=int(r['week']);n=int(r['access_night'])
    contractweek[c,typ,w].add(n);front[c,typ,w,n].add(a['activity_id'])
check('weekly distinct access-night cap',[dict(contract=k[0],type=k[1],week=k[2],nights=sorted(v)) for k,v in contractweek.items() if len(v)>int(projects[k[0]]['number_of_maximum_access_per_week'])])
check('workfront cap',[dict(contract=k[0],type=k[1],week=k[2],night=k[3],activities=sorted(v)) for k,v in front.items() if len(v)>int(projects[k[0]]['number_of_workfronts'])])
groups=collections.defaultdict(list);locweek=collections.defaultdict(set)
for r in O:
    k=r['location_id'],int(r['week']),r['co_share_group'];groups[k].append(r['activity_id']);locweek[k[:2]].add(k[2])
mixerr=[];mixcount=collections.Counter();shared=[]
for k,v in groups.items():
    types=collections.Counter(projects[acts[a]['contract_number']]['access_type'] for a in v)
    ok=(len(v)==1 and types['PM']==1) or (types['PM']==0 and types['PC']<=1 and types['C']<=3 if types['PC'] else types['PM']==0 and types['C']<=4)
    if not ok:mixerr.append(dict(location=k[0],week=k[1],group=k[2],activities=v,types=dict(types)))
    mixcount['+'.join(sorted(types.elements()))]+=1
    if len(v)>1:shared.append(dict(location=k[0],week=k[1],group=k[2],activities=v))
check('legal group mix',mixerr)
capacity=[dict(location=k[0],week=k[1],groups=len(v),capacity=supply[k[0]]) for k,v in locweek.items() if len(v)>supply[k[0]]]
check('nominal location-week capacity',capacity)
deps=[]
for a in A:
    pred=a['predecessor_activity_id']
    if pred:deps.append(dict(predecessor=pred,successor=a['activity_id'],predecessor_last=max(int(r['week']) for r in aw[pred]),successor_first=min(int(r['week']) for r in aw[a['activity_id']])))
check('strict next-week predecessor interpretation',[r for r in deps if r['successor_first']<=r['predecessor_last']],scope='inferred, not confirmed validator rule')
res=[];reserr=[];late=[]
for p in P:
    c=p['contract_number']; rows=[r for r in X if acts[r['activity_id']]['contract_number']==c]
    last=max(int(r['week']) for r in rows);completion=base+dt.timedelta(days=7*last-1)
    deadline=dt.date.fromisoformat(p['planned_completion_date']);over=max(0,(completion-deadline).days)
    actual=next(r for r in R if r['contract_number']==c)
    rec=dict(contract=c,last_week=last,completion=str(completion),planned=str(deadline),overrun=over,priority=int(p['contract_priority']))
    res.append(rec)
    if actual['simulated_completion_date']!=str(completion) or int(actual['overrun_days'])!=over:reserr.append(dict(calculated=rec,provided=actual))
for a in A:
    c=a['contract_number'];p=projects[c];last=max(int(r['week']) for r in aw[a['activity_id']]);completion=base+dt.timedelta(days=7*last-1);days=max(0,(completion-dt.date.fromisoformat(p['planned_completion_date'])).days)
    if days:late.append(dict(activity=a['activity_id'],contract=c,days=days,activity_priority=int(a['activity_priority']),contract_priority=int(p['contract_priority']),weighted=days*{1:100,2:10,3:1}[int(p['contract_priority'])]*(1+{1:.3,2:.2,3:0}[int(a['activity_priority'])])))
check('RESULTS recomputed with Sunday week end',reserr)
texts=[]
for cell in ET.parse(ROOT/'02_references'/'PS1.drawio').iter('mxCell'):
    val=cell.get('value','')
    if val:
        text=html.unescape(re.sub('<[^>]+>',' ',val));text=re.sub(r'\s+',' ',text).strip()
        if text:texts.append(dict(id=cell.get('id'),text=text))
(OUT/'drawio_text.json').write_text(json.dumps(texts,indent=2,ensure_ascii=False),encoding='utf-8')
summary=dict(inventory=inventory,parameters=param,counts=dict(lines=len(L),station_memberships=len(S),physical_station_ids=len({r['station_id'] for r in S}),sectors=len(E),locations=len(U),contracts=len(P),activities=len(A),required_access_units=sum(int(r['total_accesses']) for r in A),access_rows=len(X),occupancy_rows=len(O),location_week_groups=len(groups),co_shared_groups=len(shared),occupied_location_weeks=len(locweek)),distributions=dict(nature=collections.Counter(projects[a['contract_number']]['nature_of_activity'] for a in A),access_type=collections.Counter(projects[a['contract_number']]['access_type'] for a in A),supply=collections.Counter(r['supply_capacity'] for r in U),mixes=mixcount),checks=checks,workload_ledger=ledger,dependencies=deps,results=res,late_activities=late,scores=dict(contract_overrun_days=sum(r['overrun'] for r in res),activity_overrun_days=sum(r['days'] for r in late),activity_weighted_delay=sum(r['weighted'] for r in late)),shared_groups=shared,span_locations={k:sorted(v) for k,v in spans.items()})
(OUT/'audit_ps1.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps({k:summary[k] for k in ['parameters','counts','distributions','dependencies','results','late_activities','scores']},indent=2))
print(json.dumps([dict(name=c['name'],status=c['status'],count=c['count'],evidence=c['evidence'][:4]) for c in checks],indent=2))
print('DRAWIO DISTINCT TEXT:',json.dumps(sorted({x['text'] for x in texts}),ensure_ascii=False))
