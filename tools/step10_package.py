"""Build nine candidate CSVs plus reproducible validation and demonstration evidence."""
import argparse
import csv
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import platform
import re
import sys
from time import perf_counter
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ps1.workspace import Workspace,BASE,INPUT_SCHEMAS,OUTPUT_SCHEMAS,source_fingerprints
from ps1 import planner
from ps1.validator import validate_schedule


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def hidden_style(files):
    """Synthetic renamed fixture, explicitly not an official hidden instance."""
    result={}
    for name,raw in files.items():
        text=raw.decode('utf-8-sig').replace('ALP','XALP').replace('BET','YBET')
        text=re.sub(r'\bA(\d{3})\b',r'JOB\1',text)
        text=re.sub(r'\bC(\d{3})\b',r'CTR\1',text)
        result[name]=text.encode()
    return result


def save(workspace,view,folder):
    folder.mkdir(parents=True)
    raw,manifest=workspace.export(view['id'])
    (folder/'review-pack.zip').write_bytes(raw)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for name in (*OUTPUT_SCHEMAS,'validation.json','manifest.json','optimisation.json','replanning.json','planning-context.json'):
            (folder/name).write_bytes(archive.read(name))
    inputs=folder/'inputs';inputs.mkdir()
    for name in INPUT_SCHEMAS:(inputs/name).write_bytes(workspace.get(view['id'])['files'][name])
    repeated=validate_schedule(inputs,folder,view['scenario'],search_budget=5000,weekly_supply=(view.get('planning_context') or {}).get('weekly_supply'))
    assert repeated['report']==view['validation']['report']
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'outputs/step10/release')
    parser.add_argument('--seconds',type=float,default=30)
    parser.add_argument('--workers',type=int,default=1)
    args=parser.parse_args();out=args.output_dir.resolve()
    if any(out==p or out.is_relative_to(p) for p in (ROOT/'data',ROOT/'specs',ROOT/'ps1',ROOT/'web',ROOT/'tests')):parser.error('Use an output directory outside source/inputs.')
    if out.exists() and any(out.iterdir()):parser.error('Use a new or empty output directory.')
    out.mkdir(parents=True,exist_ok=True)
    workspace=Workspace();timings={};summary={};completed=False
    try:
        files={n:(BASE/'01_data'/n).read_bytes() for n in INPUT_SCHEMAS}
        start=perf_counter();sample=workspace.sample();timings['sample_import_and_validation']=perf_counter()-start
        start=perf_counter();baseline=workspace.generate(sample['id']);timings['greedy_baseline_and_validation']=perf_counter()-start
        summary['greedy_baseline']=planner.summary(baseline)
        summary['supplied_sample']=planner.summary(sample)
        save(workspace,sample,out/'evidence/sample');save(workspace,baseline,out/'evidence/greedy-baseline')
        conflict=next(c for c in sample['planning']['conflicts'] if c['kind']=='night' and c['week']==23 and set(c['activities'])=={'A001','A011'})
        write(out/'evidence/selected-conflict.json',conflict)
        scenarios={}
        for scenario in ('A','B','C'):
            start=perf_counter()
            view=workspace.optimise((scenarios['A'] if scenario=='C' else sample)['id'],scenario,seconds=args.seconds,workers=args.workers,seed=0,alternative_for=conflict if scenario=='A' else None)
            timings['scenario_'+scenario]=perf_counter()-start
            write(out/f'evidence/{scenario}/solver-outcome.json',view['optimisation'])
            if view['tables'] is None:
                raise RuntimeError('No complete '+scenario+' candidate within the limit; no submission ZIP published.')
            assert view['planning']['summary']['checked_model_plan']
            scenarios[scenario]=view
            # Save evidence separately: answer folders contain exactly three CSVs.
            evidence=out/'evidence'/scenario
            raw,_=workspace.export(view['id']);(evidence/'review-pack.zip').write_bytes(raw)
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                for name in ('validation.json','manifest.json'):(evidence/name).write_bytes(archive.read(name))
                answer=out/'submission'/scenario;answer.mkdir(parents=True)
                for name in OUTPUT_SCHEMAS:
                    data=archive.read(name);(answer/name).write_bytes(data)
                    assert next(csv.reader(io.StringIO(data.decode())))==list(OUTPUT_SCHEMAS[name])
            check=validate_schedule(BASE/'01_data',answer,scenario,search_budget=5000)
            assert check['report']==view['validation']['report']
            summary[scenario]={**planner.summary(view),'solver':view['optimisation']['status'],'model_optimality_proven':view['optimisation']['model_optimality_proven'],
                               'lower_bound_tenths':view['optimisation']['best_bound_tenths'],'gap':view['optimisation']['relative_gap'],'snapshot':view['schedule_snapshot']}
            print(json.dumps({'scenario':scenario,'score':summary[scenario]['score'],'seconds':timings['scenario_'+scenario]}),flush=True)
        write(out/'evidence/sample-to-A-comparison.json',scenarios['A']['alternative']['comparison'])
        fixture=hidden_style(files);fixture_folder=out/'hidden-style-inputs';fixture_folder.mkdir()
        for n,raw in fixture.items():(fixture_folder/n).write_bytes(raw)
        start=perf_counter();hidden=workspace.create(fixture,'A','Synthetic renamed eight-file input')
        hidden=workspace.optimise(hidden['id'],'A',seconds=args.seconds,workers=args.workers,seed=0)
        timings['synthetic_hidden_style_import_solve_validate']=perf_counter()-start
        if not hidden['planning']['summary']['checked_model_plan']:raise RuntimeError('Synthetic hidden-style test did not produce a complete checked plan.')
        save(workspace,hidden,out/'evidence/hidden-style')
        summary['hidden_style']={**planner.summary(hidden),'fixture':'Renamed public benchmark; not an official hidden instance.'}
        parent=scenarios['A'];proposal={'completed_through_week':10,'locked_activity_ids':['A002'],'changes':[{'type':'workload','activity_id':'A001','additional_units':1}]}
        start=perf_counter();revised=workspace.replan(parent['id'],parent['schedule_snapshot']['version'],proposal,seconds=args.seconds,workers=args.workers,seed=0)
        timings['disruption_and_validation']=perf_counter()-start
        write(out/'evidence/disruption-outcome.json',{'replanning':revised['replanning'],'optimisation':revised['optimisation']})
        if revised['tables'] is None:raise RuntimeError('Disruption demo has no checked revision; report retained, release not marked complete.')
        save(workspace,revised,out/'evidence/disruption')
        assert workspace.rollback(revised['id'],revised['schedule_snapshot']['version'])['id']==parent['id']
        summary['disruption']={**planner.summary(revised),'lock_audit':revised['replanning']['lock_audit'],'changed_activity_count':revised['replanning']['comparison']['changed_activity_count'],'rollback_verified':True}
        inputs_dir=out/'inputs';inputs_dir.mkdir()
        for name,raw in files.items():(inputs_dir/name).write_bytes(raw)
        with zipfile.ZipFile(out/'tracklight-ABC-candidates.zip','w',zipfile.ZIP_DEFLATED) as z:
            for path in sorted((out/'submission').rglob('*.csv')):z.write(path,path.relative_to(out/'submission').as_posix())
        summary['baseline_comparison_note']='Identical input bytes and rule/source profile. Greedy baseline is incomplete: do not rank its score against complete plans. Supplied sample has conditional conflicts: comparison describes model repair, not an official validator improvement.'
        completed=True
    finally:
        packages={line.split('==')[0]:importlib.metadata.version(line.split('==')[0]) for line in (ROOT/'requirements.txt').read_text().splitlines() if '==' in line}
        packages['waitress']=importlib.metadata.version('waitress')
        write(out/'summary.json',summary)
        write(out/'manifest.json',{'local_package_complete':completed,'official_validation':'NOT_RUN','full_feasibility_established':False,
             'input_data_sha256':locals().get('sample',{}).get('input_identity'),'rule_profile':locals().get('sample',{}).get('rule_profile'),
             'source_sha256':source_fingerprints(),'python':sys.version,'platform':platform.platform(),'packages':packages,
             'settings':{'seconds':args.seconds,'workers':args.workers,'seed':0},'measured_wall_seconds':timings,
             'limitations':['Complete protection unresolved','No official validator available','C uses supplied inputs and conservative Live line-window policy','Synthetic upload is not an official hidden-instance test','Hosted quota and performance require selected-host verification'],
             'files_sha256':{p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file() and p!=out/'manifest.json'}})
        write(out/'summary.json',summary)
        workspace.close()
    return 0 if completed else 2


if __name__=='__main__':sys.exit(main())
