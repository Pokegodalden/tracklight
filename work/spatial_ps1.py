import contextlib, io
with contextlib.redirect_stdout(io.StringIO()):
    import audit_ps1 as d
import json, collections, itertools

def footprint(aid):
    line,bound,i,j=d.spanmeta[aid]
    nature=d.projects[d.acts[aid]['contract_number']]['nature_of_activity']
    b={'Live':2,'Non-live (Consist)':1,'Non-live (Others)':0}[nature]
    sectors=d.ordered[line][max(0,i-b):min(9,j+b+1)]
    bounds=['EB','WB'] if nature=='Live' else [bound]
    result=set()
    for bd in bounds:
        result|={r['sector_id']+':'+bd for r in sectors}
        result|={f'PLAT:{line}:{s}:{bd}' for r in sectors for s in [r['from_station_id'],r['to_station_id']]}
    if nature=='Live' and any('H01_H02' in x for x in d.spans[aid]):
        other='BET' if line=='ALP' else 'ALP'
        result|={f'{loc}:{bd}' for bd in bounds for loc in [f'SEC:{other}:H01_H02',f'PLAT:{other}:H01',f'PLAT:{other}:H02']}
    return result

fp={a:footprint(a) for a in d.acts}
byweek=collections.defaultdict(list)
for x in d.X:byweek[int(x['week'])].append(x['activity_id'])
og={(o['activity_id'],int(o['week']),o['location_id']):o['co_share_group'] for o in d.O}
pairs=[]; protected=[]
for week,aa in byweek.items():
    for a,b in itertools.combinations(aa,2):
        common=d.spans[a]&d.spans[b]
        shared=[loc for loc in common if og[a,week,loc]==og[b,week,loc]]
        touch=fp[a]&fp[b]
        closure=(fp[a]&d.spans[b])|(fp[b]&d.spans[a])
        if closure and not shared:pairs.append(dict(week=week,a=a,b=b,overlap=sorted(closure),same_line_bound=d.spanmeta[a][:2]==d.spanmeta[b][:2],span_overlap=sorted(common)))
        if touch and not shared:protected.append(dict(week=week,a=a,b=b,overlap=sorted(touch)))

live=[]
for aid in ['A074','A075']:
    week=int(d.aw[aid][0]['week'])
    live.append(dict(activity=aid,week=week,work=sorted(d.spans[aid]),inferred_protected=sorted(fp[aid]),other_activities=byweek[week],other_work_inside=[dict(activity=a,locations=sorted(d.spans[a]&fp[aid])) for a in byweek[week] if a!=aid and d.spans[a]&fp[aid]]))

g_mismatch=[]
for k,aa in d.groups.items():
    if len(aa)>1:
        nights={a:next(int(x['access_night']) for x in d.aw[a] if int(x['week'])==k[1]) for a in aa}
        if len(set(nights.values()))>1:g_mismatch.append(dict(location=k[0],week=k[1],group=k[2],local_indices=nights))
per_activity_vary=[dict(activity=a,week=w,groups=sorted({r['co_share_group'] for r in rows})) for (a,w),rows in d.ow.items() if len({r['co_share_group'] for r in rows})>1]
weekly_same_contract=[]
for k,aa in d.front.items():
    if len(aa)>1:weekly_same_contract.append(dict(contract=k[0],week=k[2],local_night=k[3],activities=sorted(aa)))

top=[]
for loc,cap in d.supply.items():
    uses=[len(d.locweek.get((loc,w),set())) for w in range(1,d.horizon+1)]
    rows=sum(1 for o in d.O if o['location_id']==loc)
    top.append(dict(location=loc,capacity=cap,groups=sum(uses),occupied_weeks=sum(v>0 for v in uses),saturated_weeks=sum(v==cap for v in uses),activity_rows=rows))
top.sort(key=lambda r:(r['saturated_weeks'],r['groups']),reverse=True)
result=dict(interpretation='Sensitivity check only: whole-week protection; one shared work location exempts pair; buffers expanded by adjacent sectors and endpoints; Live crossover only at H01-H02.',closure_pairs=pairs,protected_pairs=protected,live=live,co_shared_different_local_indices=g_mismatch,activity_week_with_location_specific_groups=per_activity_vary,same_contract_same_night=weekly_same_contract,hotspots=top)
(d.OUT/'spatial_ps1.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(dict(closure_pairs=len(pairs),protected_pairs=len(protected),examples=pairs[:8],protected_examples=protected[:5],live=live,local_index_mismatch_count=len(g_mismatch),local_index_examples=g_mismatch[:3],varying_group_count=len(per_activity_vary),varying_group_examples=per_activity_vary[:3],same_contract_examples=weekly_same_contract[:3],hotspots=top[:12]),indent=2))
