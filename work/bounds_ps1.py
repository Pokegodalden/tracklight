import contextlib,io,json,math,datetime as dt,collections
with contextlib.redirect_stdout(io.StringIO()):
    import audit_ps1 as d
out=[]
for a in d.A:
    p=d.projects[a['contract_number']]; start=(dt.date.fromisoformat(a['planned_start_date'])-d.base).days//7+1
    due=(dt.date.fromisoformat(p['planned_completion_date'])-d.base).days//7+1
    units=int(a['total_accesses']);nudge={1:.3,2:.2,3:0}[int(a['activity_priority'])];weight={1:100,2:10,3:1}[int(p['contract_priority'])]*(1+nudge)
    lbA=units;lbB=math.ceil(units/1.5);lbC=max(math.ceil(units/1.5),units-1)
    delayA=max(0,(d.base+dt.timedelta(days=7*(start+lbA-1)-1)-dt.date.fromisoformat(p['planned_completion_date'])).days)
    delayC=max(0,(d.base+dt.timedelta(days=7*(start+lbC-1)-1)-dt.date.fromisoformat(p['planned_completion_date'])).days)
    available=max(0,due-start+1);minECLO=max(0,2*(units-available))
    choices=[]
    for e in range(3):
        n=max(e,math.ceil(units-.5*e))
        delay=max(0,(d.base+dt.timedelta(days=7*(start+n-1)-1)-dt.date.fromisoformat(p['planned_completion_date'])).days)
        choices.append(dict(eclo=e,weeks=n,delay_days=delay,total_cost=round(delay*weight+5*e,6)))
    if delayA or delayC or minECLO:out.append(dict(activity=a['activity_id'],contract=a['contract_number'],units=units,start_week=start,due_week=due,available_weeks=available,A_earliest_finish=start+lbA-1,A_min_delay=delayA,A_delay_cost=delayA*weight,C_earliest_finish=start+lbC-1,C_min_delay=delayC,C_delay_cost=delayC*weight,C_cost_choices=choices,B_min_eclo=minECLO,B_individually_possible=minECLO<=available))
result=dict(assumptions=['at most one access per activity per week','Sunday completion dates','relax all resource, protection, predecessor and group constraints','C allows at most two ECLO accesses per activity','activity-level weighted-delay interpretation','ECLO penalty counted per activity access'],activities=out,A_delay_lower_bound=sum(r['A_delay_cost'] for r in out),C_delay_lower_bound=sum(r['C_delay_cost'] for r in out),C_delay_plus_eclo_lower_bound=sum(min(c['total_cost'] for c in r['C_cost_choices']) for r in out),B_min_eclo=sum(r['B_min_eclo'] for r in out),B_eclo_cost_lower_bound=5*sum(r['B_min_eclo'] for r in out))
(d.OUT/'bounds_ps1.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
