"""Reproduce a frozen-history, locked-allocation workload disruption and recovery."""
import argparse
import io
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ps1.workspace import Workspace, BASE, INPUT_SCHEMAS, OUTPUT_SCHEMAS
from ps1.importer import sha
from ps1.validator import validate_schedule


def write(path, value):
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'outputs/step8/demo')
    parser.add_argument('--seconds',type=float,default=30)
    args=parser.parse_args(); out=args.output_dir.resolve()
    if any(out == p or out.is_relative_to(p) for p in (ROOT/'data',ROOT/'specs',ROOT/'ps1',ROOT/'web',ROOT/'tests')):
        parser.error('Use an output directory outside source and frozen inputs.')
    if out.exists() and any(out.iterdir()):parser.error('Use a new or empty output directory.')
    out.mkdir(parents=True,exist_ok=True)
    w=Workspace()
    try:
        files={n:(BASE/'01_data'/n).read_bytes() for n in INPUT_SCHEMAS}
        files.update({n:(ROOT/'outputs/step7/review-demo/alternative-a'/n).read_bytes() for n in OUTPUT_SCHEMAS})
        parent=w.create(files,'A','Step 7 checked A schedule, revalidated')
        before=dict(w.get(parent['id'])['files'])
        proposal={'completed_through_week':10,'locked_activity_ids':['A002'],
                  'changes':[{'type':'workload','activity_id':'A001','additional_units':1}]}
        write(out/'proposal.json',proposal)
        child=w.replan(parent['id'],parent['schedule_snapshot']['version'],proposal,seconds=args.seconds,workers=4,seed=0)
        write(out/'solver-outcome.json',child['optimisation'])
        write(out/'replanning.json',child['replanning'])
        assert before == w.get(parent['id'])['files']
        if child['tables'] is None:
            write(out/'summary.json',{'status':'NO_CHECKED_REVISION','solver_status':child['optimisation']['status'],'parent_preserved':True})
            return 2
        for name,view in [('parent',parent),('revised',child)]:
            folder=out/name;folder.mkdir()
            raw,manifest=w.export(view['id'])
            (folder/'review-pack.zip').write_bytes(raw)
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                for member in (*OUTPUT_SCHEMAS,'manifest.json','validation.json','planning-context.json','replanning.json'):
                    (folder/member).write_bytes(z.read(member))
                assert sha(z.read('planning-context.json')) == manifest['planning_context_sha256']
                assert sha(z.read('replanning.json')) == manifest['replanning_sha256']
            run=w.get(view['id'])
            inputs=folder/'inputs';inputs.mkdir()
            for n in INPUT_SCHEMAS:(inputs/n).write_bytes(run['files'][n])
            repeated=validate_schedule(inputs,folder,'A',search_budget=5000,weekly_supply=(view.get('planning_context') or {}).get('weekly_supply'))
            assert repeated['report'] == view['validation']['report']
        restored=w.rollback(child['id'],child['schedule_snapshot']['version'])
        assert restored == parent and child['id'] in w.runs
        comparison=child['replanning']['comparison'];write(out/'comparison.json',comparison)
        summary={'status':'CHECKED_REVISION','before':comparison['before'],'after':comparison['after'],
                 'changed_activities':comparison['changed_activity_count'],'proposal':proposal,
                 'lock_audit':child['replanning']['lock_audit'],'parent_preserved':True,'rollback_verified':True,
                 'independent_export_reports_equal':True,'export_context_hashes_verified':True,
                 'model_optimality_proven':child['optimisation']['model_optimality_proven'],
                 'churn_optimality_proven':child['optimisation']['churn_optimality_proven'],
                 'solver_seconds':child['optimisation']['solver_seconds'],'elapsed_seconds':child['optimisation']['elapsed_seconds'],
                 'source_sha256':child['source_sha256'],'full_feasibility_established':False,'official_validation':'NOT_RUN'}
        write(out/'summary.json',summary)
        print(json.dumps({k:summary[k] for k in ('status','changed_activities','lock_audit','model_optimality_proven','churn_optimality_proven','elapsed_seconds')},indent=2))
    finally:w.close()
    return 0


if __name__=='__main__':sys.exit(main())
