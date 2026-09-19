"""Isolated prototype runs and byte-preserving review exports."""
import base64
import csv
from copy import deepcopy
from datetime import datetime, timezone
import io
import json
import shutil
import re
from pathlib import Path
import tempfile
import uuid
import zipfile

from .baseline_scheduler import construct
from .importer import import_directory, sha
from .schema import SCHEMAS as INPUT_SCHEMAS
from .validator import SCHEMAS as OUTPUT_SCHEMAS, read_schedules, validate_schedule
from . import planner

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/baselines/ps1-0dfd901f97bf579f/PS1"
MAX_FILE_BYTES = 512 * 1024
MAX_TOTAL_BYTES = 6 * 1024 * 1024
LIMITS = {"activities": 250, "bookable_locations": 500, "horizon_weeks": 104, "access_rows": 1500, "occupancy_rows": 20000}


class RunError(ValueError):
    def __init__(self, message, details=None):
        super().__init__(message)
        self.details = details


def decode_upload(files):
    if not isinstance(files, list) or len(files) not in (8, 11):
        raise RunError("Select all eight inputs, optionally with all three schedule files.")
    decoded = {}
    allowed = set(INPUT_SCHEMAS) | set(OUTPUT_SCHEMAS)
    for item in files:
        if not isinstance(item, dict) or item.get("name") not in allowed or item["name"] in decoded:
            raise RunError("Unexpected or duplicate filename. Use the eight named PS1 inputs and three documented schedule filenames.")
        try:
            raw = base64.b64decode(item["data"], validate=True)
        except (ValueError, TypeError, KeyError) as exc:
            raise RunError("A file could not be decoded.") from exc
        if len(raw) > MAX_FILE_BYTES:
            raise RunError("Each file must be at most 512 KiB for this local prototype.")
        decoded[item["name"]] = raw
    if set(decoded) not in (set(INPUT_SCHEMAS), allowed) or sum(map(len, decoded.values())) > MAX_TOTAL_BYTES:
        raise RunError("The file set is incomplete or exceeds the 6 MiB prototype limit.")
    return decoded


def csv_bytes(name, rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(OUTPUT_SCHEMAS[name]), extrasaction="ignore", lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def source_fingerprints():
    paths = sorted(Path(__file__).parent.glob('*.py'))
    result = {p.name: sha(p.read_bytes()) for p in paths}
    result.update({f'web/{p.name}': sha(p.read_bytes()) for p in sorted((ROOT / 'web').iterdir()) if p.is_file()})
    return result


class Workspace:
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ps1-web-")
        self.root = Path(self.temp.name).resolve()
        self.runs = {}
        self.sources = source_fingerprints()

    def check_sources(self):
        if source_fingerprints() != self.sources:
            raise RunError('Application source changed during this session. Restart the server and re-import before scheduling or exporting.')

    def summaries(self):
        return [{k: run['view'][k] for k in ('id', 'label', 'scenario')} for run in self.runs.values()]

    def close(self):
        self.temp.cleanup()

    def sample(self):
        files = {n: (BASE / "01_data" / n).read_bytes() for n in INPUT_SCHEMAS}
        files.update({n: (BASE / "03_submission_sample" / n).read_bytes() for n in OUTPUT_SCHEMAS})
        return self.create(files, "A", "Supplied sample")

    def create(self, files, scenario, label, construction=None, parent_id=None, optimisation=None, alternative_for=None, planning_context=None, replanning=None):
        self.check_sources()
        if scenario not in ("A", "B", "C"):
            raise RunError("Choose scenario A, B or C.")
        if len(self.runs) >= 16:
            raise RunError("This local session holds 16 runs. Export your work, then restart to begin another session.")
        id = uuid.uuid4().hex
        folder = self.root / id
        try:
            return self._create(files, scenario, label, construction, parent_id, id, folder, optimisation, alternative_for, planning_context, replanning)
        except Exception:
            # Only remove the generated child directory owned by this workspace.
            if folder.resolve().parent == self.root and folder.exists():
                shutil.rmtree(folder)
            raise

    def _create(self, files, scenario, label, construction, parent_id, id, folder, optimisation, alternative_for, planning_context, replanning):
        inputs, schedule = folder / "inputs", folder / "schedule"
        inputs.mkdir(parents=True)
        schedule.mkdir()
        for name, raw in files.items():
            if name not in INPUT_SCHEMAS and name not in OUTPUT_SCHEMAS:
                raise RunError("Unexpected input filename.")
            if len(raw) > MAX_FILE_BYTES:
                raise RunError("A file exceeds the local size limit.")
            ((inputs if name in INPUT_SCHEMAS else schedule) / name).write_bytes(raw)
        # Row limits before graph work; these are prototype limits, not organiser requirements.
        for name in INPUT_SCHEMAS:
            path = inputs / name
            if path.exists():
                try:
                    count = sum(1 for _ in csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig")), strict=True))-1
                    if count > 2000:
                        raise RunError("An input table exceeds the local 2,000-row limit.")
                except (UnicodeError, csv.Error):
                    pass  # The source-aware importer produces the actual format error.
        imported = import_directory(inputs)
        if not imported["report"]["input_valid"]:
            raise RunError("Input checks failed. No new run was loaded.", imported["report"])
        model = imported['model']
        if planning_context:
            from .replan import supply_overrides
            supply_overrides(model, planning_context['weekly_supply'])
            model['weekly_supply_overrides'] = deepcopy(planning_context['weekly_supply'])
        counts = imported["report"]["counts"]
        if counts["activities"] > LIMITS["activities"] or counts["bookable_locations"] > LIMITS["bookable_locations"] or model["calendar"]["weeks"] > LIMITS["horizon_weeks"]:
            raise RunError("This prototype supports up to 250 activities, 500 locations and 104 weeks.")
        has_schedule = all(n in files for n in OUTPUT_SCHEMAS)
        if any(n in files for n in OUTPUT_SCHEMAS) and not has_schedule:
            raise RunError("Provide all three schedule CSVs together.")
        tables, validation = None, None
        if has_schedule:
            tables, _, issues = read_schedules(schedule)
            if issues:
                raise RunError("Schedule CSV format checks failed. No new run was loaded.", {"issues": issues})
            if len(tables["SCHEDULE_ACCESS.csv"]) > LIMITS["access_rows"] or len(tables["SCHEDULE_OCCUPANCY.csv"]) > LIMITS["occupancy_rows"]:
                raise RunError("The schedule exceeds the local row limits: 1,500 accesses or 20,000 occupancy rows.")
            validation = validate_schedule(inputs, schedule, scenario, search_budget=5000, weekly_supply=(planning_context or {}).get('weekly_supply'))
        view = {"id": id, "label": label, "scenario": scenario, "parent_id": parent_id,
                "input_report": imported["report"], "input_identity": imported["provenance"]["input_data_sha256"],
                "rule_profile": {k: imported["provenance"][k] for k in ("profile_id", "profile_sha256", "source_updates")},
                "source_sha256": dict(self.sources),
                "model": model, "tables": tables, "validation": validation, "construction": construction, "optimisation": optimisation,
                "planning_context": deepcopy(planning_context), "replanning": deepcopy(replanning),
                "export_kind": "REVIEW_PACK_ONLY", "submission_ready": False}
        if optimisation is not None and tables is not None:
            from .optimizer import window_check
            report = validation['report']
            if (report['metrics'] is None or not report['metrics']['all_work_complete']
                    or any(f['severity'] in ('error', 'violation') for f in report['findings'])
                    or report['physical_night_diagnostic']['status'] != 'ASSIGNED_FOR_MODELLED_RELATIONS'
                    or report['metrics']['score_tenths'] != optimisation['objective_tenths']
                    or (scenario == 'C' and not window_check(model, tables)['passed'])):
                raise RunError('Exported solver decisions failed independent validation. The parent run is preserved.')
        view['schedule_snapshot'] = planner.snapshot(view, files)
        view['planning'] = {'version': planner.VERSION, 'summary': planner.summary(view),
                            'conflicts': planner.conflicts(view), 'activities': planner.activity_contexts(view)}
        view['planner_review'] = {'snapshot_version': view['schedule_snapshot']['version'],
                                  'scope': planner.SCOPE, 'identity_assurance': 'Self-entered reviewer name; no authentication or signature.',
                                  'current_decision': None, 'records': []}
        view['alternative'] = None
        if alternative_for is not None:
            comparison = planner.compare(self.get(parent_id)['view'], view) if tables is not None else None
            view['alternative'] = {'target': deepcopy(alternative_for), 'base_run_id': parent_id,
                                   'status': 'CHECKED_MODEL_ALTERNATIVE' if comparison and comparison['after']['checked_model_plan'] else 'NO_CHECKED_ALTERNATIVE',
                                   'strategy': 'Whole-plan optimisation under unchanged inputs and scenario; changed allocations are not minimised.',
                                   'comparison': comparison, 'scope': planner.SCOPE}
        if replanning is not None and tables is not None:
            from .replan import audit, comparison
            base = self.get(parent_id)['view']
            check = audit(base, view, planning_context)
            if not check['passed']:
                raise RunError('Replanned CSVs failed independent lock validation.', check)
            view['replanning']['lock_audit'] = check
            view['replanning']['comparison'] = comparison(base, view, replanning)
        self.check_sources()
        self.runs[id] = {"view": view, "files": dict(files), "folder": folder}
        return view

    def get(self, id):
        if id not in self.runs:
            raise RunError("Run not found in this session. Reload the sample or import your files.")
        return self.runs[id]

    def generate(self, id):
        self.check_sources()
        parent = self.get(id)
        if parent['view'].get('planning_context'):
            raise RunError('Use controlled replanning to preserve completed work, locks and supply changes.')
        generated = construct(parent["view"]["model"])
        files = {n: parent["files"][n] for n in INPUT_SCHEMAS}
        files.update({n: csv_bytes(n, rows) for n, rows in generated["tables"].items()})
        return self.create(files, "A", "Scenario A baseline", generated["construction"], id)

    def optimise(self, id, scenario, seconds=30, workers=4, seed=0, alternative_for=None):
        self.check_sources()
        from .optimizer import optimise
        parent = self.get(id)
        if len(self.runs) >= 16:
            raise RunError('Export your work and restart: the 16-run session limit has been reached.')
        view = parent['view']
        if view.get('planning_context'):
            raise RunError('Use controlled replanning to preserve completed work, locks and supply changes.')
        incumbent = deepcopy(view['tables'])
        if incumbent is not None and view['scenario'] != scenario:
            for row in incumbent['RESULTS.csv']:
                row['scenario'] = scenario
        # The optimiser independently checks this retagged candidate against the
        # target policy; e.g. an A plan can seed C but may violate B's hard dates.
        candidate = optimise(view['model'], scenario, seconds=seconds, workers=workers, seed=seed,
                             incumbent=incumbent)
        files = {n:parent['files'][n] for n in INPUT_SCHEMAS}
        if candidate['tables'] is not None:
            files.update({n:csv_bytes(n,rows) for n,rows in candidate['tables'].items()})
        label = ('Checked alternative' if alternative_for else 'Optimised draft') if candidate['tables'] is not None else 'Solver outcome'
        return self.create(files, scenario, label, parent_id=id, optimisation=candidate['optimisation'], alternative_for=alternative_for)

    def assert_snapshot(self, id, version):
        self.check_sources()
        run = self.get(id)
        current = planner.snapshot(run['view'], run['files'])
        if current != run['view']['schedule_snapshot'] or version != current['version']:
            raise RunError('The schedule version differs from the one displayed. Reload the run before continuing.')
        return run

    def compare(self, base_id, candidate_id):
        self.check_sources()
        views = [self.get(id)['view'] for id in (base_id, candidate_id)]
        for view in views:
            self.assert_snapshot(view['id'], view['schedule_snapshot']['version'])
        if views[1].get('replanning') and views[1]['parent_id'] == views[0]['id']:
            from .replan import comparison
            return comparison(*views, views[1]['replanning'])
        if views[0].get('replanning') and views[0]['parent_id'] == views[1]['id']:
            from .replan import comparison
            return comparison(views[1], views[0], views[0]['replanning'])
        return planner.compare(*views)

    def alternative(self, id, version, conflict_id, seconds=30):
        run = self.assert_snapshot(id, version)
        conflict = next((c for c in run['view']['planning']['conflicts'] if c['id'] == conflict_id), None)
        if not conflict or not conflict['actionable']:
            raise RunError('Select an implemented conflict. Unresolved rules require clarification, not a claimed repair.')
        # Recheck the exact parent bytes before using its displayed conflict context.
        self.export(id)
        return self.optimise(id, run['view']['scenario'], seconds=seconds, alternative_for=conflict)

    def replan(self, id, version, proposal, seconds=30, workers=4, seed=0):
        from .replan import prepare, VERSION
        from .optimizer import optimise
        parent = self.assert_snapshot(id, version)
        if len(self.runs) >= 16:
            raise RunError('Export your work and restart: the 16-run session limit has been reached.')
        self.export(id)
        base = parent['view']
        files, context = prepare(base, {n:parent['files'][n] for n in INPUT_SCHEMAS}, proposal)
        with tempfile.TemporaryDirectory(prefix='ps1-disruption-') as temporary:
            path = Path(temporary)
            for name, raw in files.items():
                (path/name).write_bytes(raw)
            imported = import_directory(path)
            if not imported['report']['input_valid']:
                raise RunError('Revised inputs failed validation. Original preserved.', imported['report'])
            model = imported['model']
            if len(model['activities']) > LIMITS['activities']:
                raise RunError('Revised instance exceeds the local activity limit.')
            model['weekly_supply_overrides'] = context['weekly_supply']
            candidate = optimise(model, base['scenario'], seconds=seconds, workers=workers, seed=seed,
                                 incumbent=base['tables'], replanning={'parent':base, 'context':context})
            diagnostic = None
            if candidate['optimisation']['status'] == 'INFEASIBLE_MODEL' and context['locked_activity_ids']:
                relaxed = dict(context, locked_activity_ids=[])
                trial = optimise(model, base['scenario'], seconds=min(5, seconds), workers=workers, seed=seed,
                                 replanning={'parent':base, 'context':relaxed})
                diagnostic = {'kind':'counterfactual_only', 'released_for_diagnosis':context['locked_activity_ids'],
                    'completed_work_still_frozen':True, 'search_limit_seconds':min(5, seconds),
                    'status':trial['optimisation']['status'], 'solution_without_explicit_locks':trial['tables'] is not None,
                    'explanation':('A checked model solution exists with explicit locks released, while completed work stays frozen. Reconsider these locks collectively; no minimal conflict set is claimed.' if trial['tables'] is not None else
                                   'Releasing explicit locks did not establish a solution. Inspect workload, completed work, deadlines and supply; this does not identify a minimal conflict.'),
                    'locks_removed_from_actual_plan':False}
        record = {'version':VERSION, 'parent_run_id':id, 'parent_snapshot':base['schedule_snapshot'],
                  'proposal':deepcopy(proposal), 'context':context, 'lock_diagnostic':diagnostic,
                  'status':'CHECKED_REVISION' if candidate['tables'] is not None else 'NO_CHECKED_REVISION',
                  'comparison':None, 'scope':planner.SCOPE,
                  'rollback_note':'Return to the preserved parent; its old requirements still apply. Rollback does not resolve the disruption.'}
        if candidate['tables'] is not None:
            files.update({n:csv_bytes(n,rows) for n,rows in candidate['tables'].items()})
        return self.create(files, base['scenario'], 'Replanned draft' if candidate['tables'] is not None else 'Replanning outcome',
                           parent_id=id, optimisation=candidate['optimisation'], planning_context=context, replanning=record)

    def rollback(self, id, version):
        run = self.assert_snapshot(id, version)['view']
        if not run.get('replanning'):
            raise RunError('Only a disruption version has a replanning parent to return to.')
        parent = self.assert_snapshot(run['parent_id'], run['replanning']['parent_snapshot']['version'])
        self.export(parent['view']['id'])
        return parent['view']

    def record_review(self, id, version, reviewer, decision, note, request_id):
        run = self.assert_snapshot(id, version)
        view = run['view']
        if view['tables'] is None:
            raise RunError('There is no schedule version to review.')
        if not isinstance(reviewer, str) or not 1 <= len(reviewer.strip()) <= 80:
            raise RunError('Enter a reviewer name of 1..80 characters.')
        if not isinstance(note, str) or not 1 <= len(note.strip()) <= 2000:
            raise RunError('Enter a review note of 1..2,000 characters.')
        if decision not in ('comment', 'needs_changes', 'recommend_for_planning', 'rejected'):
            raise RunError('Choose a documented planning-review decision.')
        if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9-]{1,64}', request_id):
            raise RunError('A review request identifier is required.')
        payload = {'reviewer': reviewer.strip(), 'decision': decision, 'note': note.strip(), 'request_id': request_id}
        review = view['planner_review']
        old = next((r for r in review['records'] if r['request_id'] == request_id), None)
        if old:
            if any(old[k] != value for k, value in payload.items()):
                raise RunError('This request identifier was already used for a different review.')
            return view
        if len(review['records']) >= 100:
            raise RunError('This local run supports at most 100 review records. Export the review history.')
        if decision == 'recommend_for_planning' and not planner.summary(view)['checked_model_plan']:
            raise RunError('A planning recommendation requires complete work, no implemented violations and a checked night assignment. Record changes needed or a comment instead.')
        self.export(id)
        event = {**payload, 'id': uuid.uuid4().hex, 'run_id': id,
                 'snapshot_version': version, 'recorded_at': datetime.now(timezone.utc).isoformat(),
                 'operational_authorisation': False}
        updated = deepcopy(review)
        updated['records'].append(event)
        if decision != 'comment':
            updated['current_decision'] = decision
        target = run['folder'] / 'planner-review.json'
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(updated, indent=2), encoding='utf-8')
        temporary.replace(target)
        view['planner_review'] = updated
        return view

    def export(self, id):
        self.check_sources()
        run = self.get(id)
        view = run["view"]
        if view["tables"] is None:
            raise RunError("There is no schedule to export. Import a schedule, generate a baseline or optimise a scenario first.")
        # Re-import the exact output bytes through the public checker before packaging.
        with tempfile.TemporaryDirectory(prefix="ps1-roundtrip-") as temporary:
            path = Path(temporary)
            for n in OUTPUT_SCHEMAS:
                (path / n).write_bytes(run["files"][n])
            repeated = validate_schedule(run["folder"] / "inputs", path, view["scenario"], search_budget=5000, weekly_supply=(view.get("planning_context") or {}).get("weekly_supply"))
            if repeated['provenance']['input']['input_data_sha256'] != view['input_identity']:
                raise RunError('Input identity changed since this run was loaded. Export stopped; re-import the run.')
            if repeated["report"] != view["validation"]["report"]:
                raise RunError("Round-trip validation differs from the displayed result. Export stopped.")
            for key in ("profile_id", "profile_sha256", "source_updates"):
                if repeated["provenance"]["input"][key] != view["rule_profile"][key]:
                    raise RunError("Rule evidence changed since this run was loaded. Export stopped; re-import the run.")
        self.check_sources()
        if view['source_sha256'] != self.sources:
            raise RunError('Source provenance differs from the saved session. Export stopped.')
        self.assert_snapshot(id, view['schedule_snapshot']['version'])
        if view.get('replanning'):
            from .replan import audit
            check = audit(self.get(view['parent_id'])['view'], view, view['planning_context'])
            if not check['passed']:
                raise RunError('Lock audit failed at export.', check)
        review_bytes = json.dumps(view['planner_review'], indent=2).encode()
        alternative_bytes = json.dumps(view['alternative'], indent=2).encode()
        manifest = {"run_id": id, "label": view["label"], "scenario": view["scenario"],
                    "input_data_sha256": view["input_identity"], "submission_ready": False,
                    "rule_profile": view["rule_profile"],
                    "optimiser_version": view['optimisation']['version'] if view['optimisation'] else None,
                    "purpose": "Review or partial-draft export; not official acceptance or operational authority.",
                    "round_trip_report_equal": True, "bytes_preserved": True,
                    "schedule_sha256": {n: sha(run["files"][n]) for n in OUTPUT_SCHEMAS},
                    "source_sha256": dict(view['source_sha256'])}
        manifest.update(schedule_snapshot=view['schedule_snapshot'], planner_review_sha256=sha(review_bytes),
                        alternative_sha256=sha(alternative_bytes))
        context_bytes = json.dumps(view.get('planning_context'), indent=2).encode()
        replan_bytes = json.dumps(view.get('replanning'), indent=2).encode()
        manifest.update(planning_context_sha256=sha(context_bytes), replanning_sha256=sha(replan_bytes))
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for n in OUTPUT_SCHEMAS:
                archive.writestr(n, run["files"][n])
            for name, payload in (("manifest.json", manifest), ("validation.json", repeated), ("construction.json", view["construction"]), ('optimisation.json',view['optimisation'])):
                archive.writestr(name, json.dumps(payload, indent=2))
            archive.writestr('planner-review.json', review_bytes)
            archive.writestr('alternative.json', alternative_bytes)
            archive.writestr('planning-context.json', context_bytes)
            archive.writestr('replanning.json', replan_bytes)
            if view.get('replanning'):
                for n in INPUT_SCHEMAS:
                    archive.writestr('inputs/'+n, run['files'][n])
                parent = self.get(view['parent_id'])
                for n,raw in parent['files'].items():
                    archive.writestr('parent/'+n, raw)
                archive.writestr('parent/planning-context.json', json.dumps(parent['view'].get('planning_context'), indent=2))
            archive.writestr("README.txt", "PS1 REVIEW PACK\nFor Step 8 revisions, inputs/ contains changed inputs and planning-context.json defines explicit weekly supply overrides. Revalidate with --planning-context planning-context.json; the three schedule CSVs alone do not encode the disruption. replanning.json and parent/ retain before/after evidence.\nNot an officially validated submission.\nProtection remains unverified. Incomplete contracts have no fabricated completion rows.\nSee validation.json for completeness and construction.json for generated-run decisions and unfinished work.\nplanner-review.json contains comments and decisions for the exact schedule version in manifest.json. Reviewer names are self-entered, not authenticated signatures.\nalternative.json contains the selected conflict and checked comparison when this run was generated as an alternative.\nNo planner decision grants operational track-entry authority.\n")
        return buffer.getvalue(), manifest
