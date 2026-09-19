"""Reproduce conflict -> checked alternative -> comparison -> versioned review export."""
import argparse
import io
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ps1.workspace import Workspace, INPUT_SCHEMAS, OUTPUT_SCHEMAS
from ps1.importer import sha


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')


def save(workspace, view, folder):
    folder.mkdir()
    raw, manifest = workspace.export(view['id'])
    (folder/'review-pack.zip').write_bytes(raw)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for name in (*OUTPUT_SCHEMAS, 'manifest.json', 'validation.json', 'optimisation.json', 'planner-review.json', 'alternative.json'):
            (folder/name).write_bytes(archive.read(name))
        assert sha(archive.read('planner-review.json')) == manifest['planner_review_sha256']
        assert sha(archive.read('alternative.json')) == manifest['alternative_sha256']
        assert all(sha(archive.read(n)) == manifest['schedule_sha256'][n] for n in OUTPUT_SCHEMAS)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'outputs/step7/demo')
    parser.add_argument('--seconds', type=float, default=30)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if any(out == p or out.is_relative_to(p) for p in (ROOT/'data', ROOT/'specs', ROOT/'ps1', ROOT/'web', ROOT/'tests')):
        parser.error('Use an output directory outside source and frozen inputs.')
    if out.exists() and any(out.iterdir()):
        parser.error('Use a new or empty output directory for each experiment.')
    out.mkdir(parents=True, exist_ok=True)
    w = Workspace()
    try:
        sample = w.sample()
        target = next(c for c in sample['planning']['conflicts'] if c['kind'] == 'night' and c['week'] == 23 and set(c['activities']) == {'A001', 'A011'})
        w.record_review(sample['id'], sample['schedule_snapshot']['version'], 'Demonstration reviewer', 'needs_changes',
                        'Automated demonstration: Week 23 requires A001 and A011 to be both together and apart. Request a checked replacement.', 'demo-base')
        base_files = dict(w.get(sample['id'])['files'])
        candidate = w.alternative(sample['id'], sample['schedule_snapshot']['version'], target['id'], seconds=args.seconds)
        assert w.get(sample['id'])['files'] == base_files
        write_json(out/'solver-outcome.json', candidate['optimisation'])
        if candidate['tables'] is None:
            write_json(out/'summary.json', {'status':'NO_CHECKED_ALTERNATIVE', 'solver_status':candidate['optimisation']['status'], 'parent_preserved':True})
            return 2
        comparison = candidate['alternative']['comparison']
        assert comparison['after']['checked_model_plan']
        w.record_review(candidate['id'], candidate['schedule_snapshot']['version'], 'Demonstration reviewer', 'recommend_for_planning',
                        'Automated demonstration only: implemented checks pass. Review changed allocations and obtain unresolved protection evidence before any operational decision.', 'demo-candidate')
        save(w, sample, out/'sample')
        save(w, candidate, out/'alternative-a')
        write_json(out/'comparison-a.json', comparison)
        # Import the existing reviewed B CSVs; check them again with current code.
        files = {n: base_files[n] for n in INPUT_SCHEMAS}
        files.update({n: (ROOT/'outputs/step6/reviewed-runs/B'/n).read_bytes() for n in OUTPUT_SCHEMAS})
        policy_b = w.create(files, 'B', 'Previously reviewed B CSVs, rechecked')
        cross_scenario = w.compare(candidate['id'], policy_b['id'])
        assert not cross_scenario['scores_comparable'] and cross_scenario['deltas']['score'] is None
        save(w, policy_b, out/'policy-b')
        write_json(out/'comparison-ab.json', cross_scenario)
        summary = {'target':target, 'base':comparison['before'], 'alternative':comparison['after'],
                   'deltas':comparison['deltas'], 'changed_activities':comparison['changed_activity_count'],
                   'base_version':sample['schedule_snapshot']['version'], 'candidate_version':candidate['schedule_snapshot']['version'],
                   'parent_preserved':True, 'same_inputs_rules_and_code':True, 'review_export_hashes_verified':True,
                   'cross_scenario_score_ranking_disabled':True, 'source_sha256':candidate['source_sha256'],
                   'reviewer_identity':'Demonstration only; not a real planner sign-off.', 'official_validation':'NOT_RUN',
                   'full_feasibility_established':False}
        write_json(out/'summary.json', summary)
        print(json.dumps({k:summary[k] for k in ('base','alternative','deltas','changed_activities','parent_preserved')}, indent=2))
    finally:
        w.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
