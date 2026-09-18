"""Isolated prototype runs and byte-preserving review exports."""
import base64
import csv
import io
import json
import shutil
from pathlib import Path
import tempfile
import uuid
import zipfile

from .baseline_scheduler import construct
from .importer import import_directory, sha
from .schema import SCHEMAS as INPUT_SCHEMAS
from .validator import SCHEMAS as OUTPUT_SCHEMAS, read_schedules, validate_schedule

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

    def create(self, files, scenario, label, construction=None, parent_id=None, optimisation=None):
        self.check_sources()
        if scenario not in ("A", "B", "C"):
            raise RunError("Choose scenario A, B or C.")
        if len(self.runs) >= 16:
            raise RunError("This local session holds 16 runs. Export your work, then restart to begin another session.")
        id = uuid.uuid4().hex
        folder = self.root / id
        try:
            return self._create(files, scenario, label, construction, parent_id, id, folder, optimisation)
        except Exception:
            # Only remove the generated child directory owned by this workspace.
            if folder.resolve().parent == self.root and folder.exists():
                shutil.rmtree(folder)
            raise

    def _create(self, files, scenario, label, construction, parent_id, id, folder, optimisation):
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
        model = imported["model"]
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
            validation = validate_schedule(inputs, schedule, scenario, search_budget=5000)
        view = {"id": id, "label": label, "scenario": scenario, "parent_id": parent_id,
                "input_report": imported["report"], "input_identity": imported["provenance"]["input_data_sha256"],
                "rule_profile": {k: imported["provenance"][k] for k in ("profile_id", "profile_sha256", "source_updates")},
                "source_sha256": dict(self.sources),
                "model": model, "tables": tables, "validation": validation, "construction": construction, "optimisation": optimisation,
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
        generated = construct(parent["view"]["model"])
        files = {n: parent["files"][n] for n in INPUT_SCHEMAS}
        files.update({n: csv_bytes(n, rows) for n, rows in generated["tables"].items()})
        return self.create(files, "A", "Scenario A baseline", generated["construction"], id)

    def optimise(self, id, scenario, seconds=30, workers=4, seed=0):
        self.check_sources()
        from .optimizer import optimise
        parent = self.get(id)
        if len(self.runs) >= 16:
            raise RunError('Export your work and restart: the 16-run session limit has been reached.')
        view = parent['view']
        candidate = optimise(view['model'], scenario, seconds=seconds, workers=workers, seed=seed,
                             incumbent=view['tables'] if view['scenario']==scenario else None)
        files = {n:parent['files'][n] for n in INPUT_SCHEMAS}
        if candidate['tables'] is not None:
            files.update({n:csv_bytes(n,rows) for n,rows in candidate['tables'].items()})
        return self.create(files, scenario, 'Optimised draft' if candidate['tables'] is not None else 'Solver outcome',
                             parent_id=id, optimisation=candidate['optimisation'])

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
            repeated = validate_schedule(run["folder"] / "inputs", path, view["scenario"], search_budget=5000)
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
        manifest = {"run_id": id, "label": view["label"], "scenario": view["scenario"],
                    "input_data_sha256": view["input_identity"], "submission_ready": False,
                    "rule_profile": view["rule_profile"],
                    "optimiser_version": view['optimisation']['version'] if view['optimisation'] else None,
                    "purpose": "Review or partial-draft export; not official acceptance or operational authority.",
                    "round_trip_report_equal": True, "bytes_preserved": True,
                    "schedule_sha256": {n: sha(run["files"][n]) for n in OUTPUT_SCHEMAS},
                    "source_sha256": dict(view['source_sha256'])}
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for n in OUTPUT_SCHEMAS:
                archive.writestr(n, run["files"][n])
            for name, payload in (("manifest.json", manifest), ("validation.json", repeated), ("construction.json", view["construction"]), ('optimisation.json',view['optimisation'])):
                archive.writestr(name, json.dumps(payload, indent=2))
            archive.writestr("README.txt", "PS1 REVIEW PACK\nNot an officially validated submission.\nProtection remains unverified. Incomplete contracts have no fabricated completion rows.\nSee validation.json for completeness and construction.json for generated-run decisions and unfinished work.\n")
        return buffer.getvalue(), manifest
