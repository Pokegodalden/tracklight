"""Reproduce the two Step 5 review packs and their measured evidence."""
from collections import Counter
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ps1.workspace import Workspace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'outputs/step5')
    output = parser.parse_args().output_dir.resolve()
    if any(output == p or output.is_relative_to(p) for p in (ROOT / 'data', ROOT / 'specs')):
        parser.error('Report output must be outside source data and rule specifications.')
    output.mkdir(parents=True, exist_ok=True)
    workspace = Workspace()
    evidence = {'created_utc': datetime.now(timezone.utc).isoformat(), 'runs': {}}
    try:
        for name in ('sample', 'baseline'):
            start = perf_counter()
            if name == 'sample':
                view = workspace.sample()
                sample_id = view['id']
            else:
                view = workspace.generate(sample_id)
            build_seconds = perf_counter()-start
            blob, manifest = workspace.export(view['id'])
            (output / f'{name}-review.zip').write_bytes(blob)
            r = view['validation']['report']
            evidence['runs'][name] = {
                'input_data_sha256': view['input_identity'],
                'import_generate_validate_seconds': round(build_seconds, 4),
                'status': r['status'], 'metrics': r['metrics'],
                'activities': len(view['model']['activities']),
                'accesses': len(view['tables']['SCHEDULE_ACCESS.csv']),
                'occupancy_rows': len(view['tables']['SCHEDULE_OCCUPANCY.csv']),
                'completed_contract_rows': len(view['tables']['RESULTS.csv']),
                'violation_codes': dict(Counter(f['code'] for f in r['findings'] if f['severity']=='violation')),
                'night_diagnostic_status': r['physical_night_diagnostic']['status'],
                'conditional_conflict_weeks': [w['week'] for w in r['physical_night_diagnostic']['weeks'] if w['conflicts']],
                'construction': view['construction'], 'export_manifest': manifest,
            }
        (output / 'evidence.json').write_text(json.dumps(evidence, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({k: {x:v[x] for x in ('status','activities','accesses','violation_codes','import_generate_validate_seconds')}
                          for k,v in evidence['runs'].items()}, indent=2))
    finally:
        workspace.close()


if __name__ == '__main__':
    main()
