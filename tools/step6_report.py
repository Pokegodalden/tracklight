"""Optimise A/B/C from eight CSVs and publish checked, separate review outputs."""
import argparse
import json
from pathlib import Path
import sys
import zipfile
import io

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ps1.workspace import Workspace, BASE, INPUT_SCHEMAS, OUTPUT_SCHEMAS


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,default=BASE/'01_data')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'outputs/step6/runs')
    parser.add_argument('--seconds',type=float,default=30)
    parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--seed',type=int,default=0)
    parser.add_argument('--scenario',choices=('A','B','C','all'),default='all')
    args=parser.parse_args()
    out=args.output_dir.resolve()
    if any(out==p or out.is_relative_to(p) for p in (ROOT/'data',ROOT/'specs',args.inputs.resolve())):
        parser.error('Output must be outside inputs, source data and specifications.')
    # Refuse mixing outcomes from different attempts or leaving stale CSVs behind.
    if out.exists() and any(out.iterdir()):
        parser.error('Use an empty or new output directory for each experiment.')
    out.mkdir(parents=True,exist_ok=True)
    workspace=Workspace()
    summary={}
    try:
        inputs=workspace.create({n:(args.inputs/n).read_bytes() for n in INPUT_SCHEMAS},'A','Eight-file instance')
        for scenario in ('A','B','C') if args.scenario=='all' else (args.scenario,):
            view=workspace.optimise(inputs['id'],scenario,args.seconds,args.workers,args.seed)
            destination=out/scenario
            destination.mkdir()
            meta=view['optimisation']
            (destination/'optimisation.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
            (destination/'input-provenance.json').write_text(json.dumps({'input_data_sha256':view['input_identity'],'rule_profile':view['rule_profile']},indent=2)+'\n',encoding='utf-8')
            if view['tables'] is not None:
                raw,manifest=workspace.export(view['id'])
                (destination/'review-pack.zip').write_bytes(raw)
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    for n in (*OUTPUT_SCHEMAS,'validation.json','manifest.json'):
                        (destination/n).write_bytes(archive.read(n))
            summary[scenario]={k:meta.get(k) for k in ('status','solver_status','objective_tenths','best_bound_tenths','relative_gap','model_optimality_proven','elapsed_seconds','settings')}
            summary[scenario].update(input_data_sha256=view['input_identity'],all_work_complete=bool(view['validation'] and view['validation']['report']['metrics']['all_work_complete']),submission_ready=False)
            (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({scenario:summary[scenario]},indent=2),flush=True)
    finally:
        workspace.close()
    return 0 if all(v['all_work_complete'] for v in summary.values()) else 2


if __name__=='__main__':
    sys.exit(main())
