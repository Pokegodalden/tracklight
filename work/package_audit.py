import json, hashlib, datetime as dt, csv
from pathlib import Path
ROOT=Path(r'C:\Users\pokeg\Downloads\PS1');WORK=Path(__file__).parent;OUT=WORK.parent/'outputs'
audit=json.loads((WORK/'audit_ps1.json').read_text())
spatial=json.loads((WORK/'spatial_ps1.json').read_text())
consistency=json.loads((WORK/'consistency_ps1.json').read_text())
bounds=json.loads((WORK/'bounds_ps1.json').read_text())
manifest=[]
for p in sorted(ROOT.rglob('*')):
    if p.is_file():manifest.append(dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
for row in audit['inventory']:
    match=next(m for m in manifest if Path(m['path']).name==row['file'])
    assert row['sha256']==match['sha256'],f'Source changed: {row["file"]}'
assert len(audit['checks'])==27 and all(c['status']=='PASS' for c in audit['checks'])
assert audit['counts']['required_access_units']==192==audit['counts']['access_rows']
assert abs(audit['scores']['activity_weighted_delay']-48.3)<1e-8
assert len(consistency['location_conflicts'])==49
assert len(consistency['contract_night_conflicts'])==3
assert abs(bounds['C_delay_plus_eclo_lower_bound']-25.2)<1e-8
with (ROOT/'01_data'/'02_STATIONS.csv').open(newline='') as f:stations=list(csv.DictReader(f))
with (ROOT/'01_data'/'03_SECTORS.csv').open(newline='') as f:sectors=list(csv.DictReader(f))
expected=set()
for line in ['ALP','BET']:
    ss=sorted([s for s in stations if s['line_code']==line],key=lambda s:int(s['seq']))
    ee=sorted([e for e in sectors if e['line_code']==line],key=lambda e:int(e['seq']))
    assert [(e['from_station_id'],e['to_station_id']) for e in ee]==list(zip([s['station_id'] for s in ss[:-1]],[s['station_id'] for s in ss[1:]]))
    expected|={f'PLAT:{line}:{s["station_id"]}:{b}' for s in ss for b in ['EB','WB']}
    expected|={e['sector_id']+':'+b for e in ee for b in ['EB','WB']}
with (ROOT/'01_data'/'04_LOCATION_SUPPLY.csv').open(newline='') as f:supply=list(csv.DictReader(f))
assert {s['location_id'] for s in supply}==expected
evidence=dict(audit_date='2026-09-17',official_validator_run=False,source_csv_hashes_unchanged=True,source_manifest=manifest,accounting_audit=audit,conditional_physical_night_diagnostic=consistency,non_authoritative_protection_sensitivity=spatial,relaxed_lower_bounds=bounds,topology_extra_checks=dict(consecutive_sectors_match_station_order=True,all_76_expected_locations_present=True),method_limits=['No executable official validator supplied or run','No proof of sample physical-night feasibility','No optimality or solver runtime claim','B/C not solved','Protection sensitivity and physical-night contradictions depend on stated assumptions'])
(OUT/'PS1_audit_evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
print(json.dumps(dict(packaged_files=[p.name for p in OUT.glob('PS1_*')],manifest_files=len(manifest),source_csv_hashes_unchanged=True,topology_checks='passed',direct_check_categories=26,conditional_predecessor_check_categories=1,evidence_bytes=(OUT/'PS1_audit_evidence.json').stat().st_size),indent=2))
