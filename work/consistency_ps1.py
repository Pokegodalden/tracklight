import contextlib, io, collections, json
with contextlib.redirect_stdout(io.StringIO()):
    import audit_ps1 as d
edges=collections.defaultdict(list)
for (loc,w,g),aa in d.groups.items():
    for a in aa[1:]:
        edges[w].append((aa[0],a,loc,g))
conflicts=[]; night_conflicts=[]
for week,ee in edges.items():
    nodes={a for e in ee for a in e[:2]};parent={a:a for a in nodes}
    def find(a):
        while parent[a]!=a:
            parent[a]=parent[parent[a]];a=parent[a]
        return a
    for a,b,loc,g in ee:parent[find(a)]=find(b)
    comp_loc=collections.defaultdict(list);comp_contract=collections.defaultdict(list)
    for o in d.O:
        a=o['activity_id']
        if int(o['week'])==week and a in nodes:comp_loc[find(a),o['location_id']].append((a,o['co_share_group']))
    for (component,loc),pairs in comp_loc.items():
        if len({g for a,g in pairs})>1:conflicts.append(dict(week=week,location=loc,assignments=pairs,connecting_edges=[e for e in ee if find(e[0])==component]))
    for x in d.X:
        a=x['activity_id']
        if int(x['week'])==week and a in nodes:comp_contract[find(a),d.acts[a]['contract_number'],d.acts[a]['activity_type']].append((a,x['access_night']))
    for key,pairs in comp_contract.items():
        if len({n for a,n in pairs})>1:night_conflicts.append(dict(week=week,contract=key[1],assignments=pairs))
result=dict(scope='Conditional diagnostic: assume one activity access occurs on one physical night across its whole span; shared groups imply same night; different groups at same location imply different nights.',location_conflicts=conflicts,contract_night_conflicts=night_conflicts)
(d.OUT/'consistency_ps1.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(dict(location_conflict_count=len(conflicts),contract_night_conflict_count=len(night_conflicts),location_examples=conflicts[:3],night_examples=night_conflicts[:5]),indent=2))
