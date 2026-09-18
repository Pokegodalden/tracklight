"""Freeze and verify PS1 source bytes. Uses only the Python standard library.

This is an evidence utility, not the scheduling importer or official validator.
"""

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath


INPUT_NAMES = (
    "01_LINES.csv", "02_STATIONS.csv", "03_SECTORS.csv",
    "04_LOCATION_SUPPLY.csv", "05_BUFFER_LOCATION.csv", "06_PARAMETERS.csv",
    "07_PROJECT_DETAILS.csv", "08_ACTIVITY_DETAILS.csv",
)
INPUT_PATHS = frozenset(f"PS1/01_data/{name}" for name in INPUT_NAMES)
IDENTITY_METHOD = "SHA-256 of UTF-8 sorted path<TAB>file_sha256<LF> records"
EXPECTED_PATHS = (
    "README.md", "PS1/PS1_README.md",
    *(f"PS1/01_data/{name}" for name in INPUT_NAMES),
    "PS1/02_references/PS1.drawio", "PS1/02_references/network_diagram.svg",
    *(f"PS1/03_submission_sample/{name}.csv" for name in
      ("RESULTS", "SCHEDULE_ACCESS", "SCHEDULE_OCCUPANCY")),
)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def identity(entries):
    # Portable identity: paths and exact bytes, independent of date/source machine.
    canonical = "".join(f"{e['path']}\t{e['sha256']}\n"
                        for e in sorted(entries, key=lambda item: item["path"]))
    return sha256(canonical.encode("utf-8"))


def csv_records(data):
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
    rows = list(reader)
    if (not reader.fieldnames or any(not name.strip() for name in reader.fieldnames)
            or len(set(reader.fieldnames)) != len(reader.fieldnames)):
        raise ValueError("Missing or duplicate CSV column names")
    if any(None in row or None in row.values() for row in rows):
        raise ValueError("CSV row width does not match header")
    return reader.fieldnames, rows


def baseline_summary(blobs):
    tables = {name: csv_records(blobs[f"PS1/01_data/{name}"])[1]
              for name in INPUT_NAMES}
    params = {row["key"]: row["value"] for row in tables["06_PARAMETERS.csv"]}
    start = date.fromisoformat(params["horizon_start"])
    weeks = int(params["horizon_weeks"])
    counts = {
        "lines": len(tables["01_LINES.csv"]),
        "station_line_memberships": len(tables["02_STATIONS.csv"]),
        "distinct_stations": len({r["station_id"] for r in tables["02_STATIONS.csv"]}),
        "sectors": len(tables["03_SECTORS.csv"]),
        "bookable_locations": len(tables["04_LOCATION_SUPPLY.csv"]),
        "contracts": len({r["contract_number"] for r in tables["07_PROJECT_DETAILS.csv"]}),
        "activities": len(tables["08_ACTIVITY_DETAILS.csv"]),
        "workload_standard_equivalent_units": str(sum(
            (Decimal(r["total_accesses"]) for r in tables["08_ACTIVITY_DETAILS.csv"]), Decimal(0))),
    }
    expected = dict(lines=2, station_line_memberships=20, distinct_stations=18,
                    sectors=18, bookable_locations=76, contracts=14, activities=54,
                    workload_standard_equivalent_units="192")
    samples = {name: csv_records(blobs[f"PS1/03_submission_sample/{name}.csv"])[1]
               for name in ("RESULTS", "SCHEDULE_ACCESS", "SCHEDULE_OCCUPANCY")}
    return {
        "observed": counts,
        "expected_from_workflow": expected,
        "counts_match_workflow": counts == expected,
        "line_codes": sorted({r["line_code"] for r in tables["01_LINES.csv"]}),
        "horizon": {
            "start": start.isoformat(), "weeks": weeks,
            "inclusive_end": (start + timedelta(weeks=weeks) - timedelta(days=1)).isoformat(),
            "end_derivation": "start + 7 * weeks - 1 days; not a completion-date rule",
            # Absence was reviewed for the original 15-file layout only.
            "dated_operational_access_calendar_supplied":
                False if set(blobs) == set(EXPECTED_PATHS) else None,
        },
        "sample_rows": {name: len(rows) for name, rows in samples.items()},
        "sample_scenarios": sorted({row["scenario"] for row in samples["RESULTS"]}),
        "scope": "Inventory, CSV structure and baseline counts only; no scheduling feasibility checks",
    }


def file_role(name):
    return ("input" if name in INPUT_PATHS else
            "sample_output" if name.startswith("PS1/03_submission_sample/") else
            "reference" if name.startswith("PS1/02_references/") else
            "brief" if name.endswith(".md") else "additional")


def safe_relative_path(name):
    if not isinstance(name, str) or not name or "\\" in name or ":" in name:
        return False
    path = PurePosixPath(name)
    return (not path.is_absolute() and ".." not in path.parts
            and path.as_posix() == name and name != "."
            and not any(ord(c) < 32 for c in name))


def source_inventory(source, readme):
    files = {}
    for path in source.rglob("*"):
        if path.is_symlink() or path.is_junction():
            raise ValueError(f"Linked source paths are not supported: {path}")
        if path.is_file():
            name = f"PS1/{path.relative_to(source).as_posix()}"
            if not safe_relative_path(name):
                raise ValueError(f"Unsupported source path: {name}")
            files[name] = path
    files["README.md"] = readme
    return files


def freeze(args):
    source = args.source_root.resolve()
    readme = args.root_readme.resolve()
    destination = args.destination.resolve()
    if destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError("Source and snapshot destination must not contain one another")
    source_files = source_inventory(source, readme)
    missing = set(EXPECTED_PATHS) - source_files.keys()
    if missing:
        raise ValueError(f"Missing expected source files: {sorted(missing)}")
    # Include additional files if a later pack supplies them; don't silently omit.
    blobs = {name: path.read_bytes() for name, path in source_files.items()}
    entries = []
    for name in sorted(blobs):
        role = file_role(name)
        entry = {"path": name, "role": role, "size_bytes": len(blobs[name]),
                 "sha256": sha256(blobs[name]), "source_path": str(source_files[name])}
        if name.endswith(".csv"):
            columns, rows = csv_records(blobs[name])
            entry.update(csv_columns=columns, csv_data_rows=len(rows))
        entries.append(entry)
    digest = identity(entries)
    manifest = {
        "manifest_version": 1,
        "snapshot_id": f"ps1-{digest[:16]}",
        "pack_sha256": digest,
        "input_data_sha256": identity([e for e in entries if e["path"] in INPUT_PATHS]),
        "identity_method": IDENTITY_METHOD,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "files": entries,
        "additional_paths": sorted(set(blobs) - set(EXPECTED_PATHS)),
        "baseline": baseline_summary(blobs),
    }
    target = destination / manifest["snapshot_id"]
    if target.exists():
        result = verify_snapshot(target)
        if not result["passed"]:
            raise ValueError("Existing snapshot failed verification; refusing to overwrite")
        existing = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
        if existing["pack_sha256"] != digest:
            raise ValueError("Snapshot name collision; full fingerprints differ")
        print(json.dumps({"status": "existing_verified", "snapshot": str(target)}, indent=2))
        return
    destination.mkdir(parents=True, exist_ok=True)
    # Publish only a verified complete directory. Cleanup is confined to the
    # unique temporary directory directly inside the resolved destination.
    with tempfile.TemporaryDirectory(dir=destination, prefix=".staging-") as temp:
        staging_parent = Path(temp).resolve()
        if staging_parent.parent != destination or target.parent != destination:
            raise ValueError("Snapshot staging paths escaped destination")
        staging = staging_parent / manifest["snapshot_id"]
        staging.mkdir()
        for name, data in blobs.items():
            output = staging / name
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(data)
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        result = verify_snapshot(staging)
        if not result["passed"]:
            raise ValueError(f"Snapshot verification failed: {result['issues']}")
        if source_inventory(source, readme).keys() != source_files.keys():
            raise ValueError("Source file inventory changed during freeze")
        for name, path in source_files.items():
            if path.read_bytes() != blobs[name]:
                raise ValueError(f"Source changed during freeze: {name}")
        staging.rename(target)
    print(json.dumps({"status": "created_verified", "snapshot": str(target),
                      "pack_sha256": digest, "baseline": manifest["baseline"]}, indent=2))


def validate_manifest(manifest):
    if not isinstance(manifest, dict):
        raise ValueError("Manifest must be a JSON object")
    if type(manifest.get("manifest_version")) is not int or manifest["manifest_version"] != 1:
        raise ValueError("Unsupported manifest version")
    if manifest.get("identity_method") != IDENTITY_METHOD:
        raise ValueError("Unsupported identity method")
    for key in ("pack_sha256", "input_data_sha256"):
        if not isinstance(manifest.get(key), str) or not re.fullmatch("[0-9a-f]{64}", manifest[key]):
            raise ValueError(f"Invalid {key}")
    if not isinstance(manifest.get("snapshot_id"), str):
        raise ValueError("Missing snapshot identifier")
    if not isinstance(manifest.get("baseline"), dict):
        raise ValueError("Missing baseline summary")
    if not isinstance(manifest.get("files"), list) or not manifest["files"]:
        raise ValueError("Manifest must list files")
    for entry in manifest["files"]:
        if not isinstance(entry, dict) or not safe_relative_path(entry.get("path")):
            raise ValueError("Invalid or unsafe manifest file path")
        name = entry["path"]
        if name == "manifest.json":
            raise ValueError("Manifest cannot inventory itself")
        if entry.get("role") != file_role(name):
            raise ValueError(f"Incorrect file role: {name}")
        if type(entry.get("size_bytes")) is not int or entry["size_bytes"] < 0:
            raise ValueError(f"Invalid byte size: {name}")
        if not isinstance(entry.get("sha256"), str) or not re.fullmatch("[0-9a-f]{64}", entry["sha256"]):
            raise ValueError(f"Invalid file fingerprint: {name}")
        if name.endswith(".csv"):
            if (not isinstance(entry.get("csv_columns"), list)
                    or not entry["csv_columns"]
                    or not all(isinstance(c, str) and c.strip() for c in entry["csv_columns"])
                    or type(entry.get("csv_data_rows")) is not int
                    or entry["csv_data_rows"] < 0):
                raise ValueError(f"Invalid CSV inventory: {name}")
    names = [entry["path"] for entry in manifest["files"]]
    if len(names) != len(set(name.casefold() for name in names)):
        raise ValueError("Duplicate or case-colliding manifest paths")
    if manifest.get("additional_paths") != sorted(set(names) - set(EXPECTED_PATHS)):
        raise ValueError("Additional-file inventory mismatch")


def _verify_snapshot(root):
    root = root.resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    validate_manifest(manifest)
    issues, blobs = [], {}
    entries = manifest["files"]
    names = [entry["path"] for entry in entries]
    if len(names) != len(set(names)):
        issues.append("Duplicate manifest paths")
    if not set(EXPECTED_PATHS).issubset(names):
        issues.append("Expected source files missing from manifest")
    if identity(entries) != manifest["pack_sha256"]:
        issues.append("Pack fingerprint mismatch")
    if manifest["snapshot_id"] != "ps1-" + manifest["pack_sha256"][:16]:
        issues.append("Snapshot identifier mismatch")
    if identity([e for e in entries if e["path"] in INPUT_PATHS]) != manifest["input_data_sha256"]:
        issues.append("Input-data fingerprint mismatch")
    for entry in entries:
        name = entry["path"]
        path = root / name
        if not path.resolve().is_relative_to(root):
            issues.append(f"Path outside snapshot: {name}")
            continue
        if not path.is_file():
            issues.append(f"Missing file: {name}")
            continue
        data = path.read_bytes()
        blobs[name] = data
        if len(data) != entry["size_bytes"] or sha256(data) != entry["sha256"]:
            issues.append(f"File fingerprint mismatch: {name}")
            continue
        if name.endswith(".csv"):
            columns, rows = csv_records(data)
            if columns != entry["csv_columns"] or len(rows) != entry["csv_data_rows"]:
                issues.append(f"CSV inventory mismatch: {name}")
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    unexpected = actual - set(names) - {"manifest.json"}
    if unexpected:
        issues.append(f"Unlisted snapshot files: {sorted(unexpected)}")
    if not issues and baseline_summary(blobs) != manifest["baseline"]:
        issues.append("Derived baseline summary mismatch")
    return {"snapshot_id": manifest["snapshot_id"], "passed": not issues,
            "files_checked": len(entries), "issues": issues}


def verify_snapshot(root):
    try:
        return _verify_snapshot(root)
    except (OSError, ValueError, KeyError, TypeError, csv.Error, InvalidOperation, OverflowError) as error:
        return {"snapshot_id": None, "passed": False, "files_checked": 0,
                "issues": [f"Unable to verify snapshot: {error}"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("freeze")
    create.add_argument("--source-root", type=Path, required=True)
    create.add_argument("--root-readme", type=Path, required=True)
    create.add_argument("--destination", type=Path, default=Path("data/baselines"))
    check = sub.add_parser("verify")
    check.add_argument("snapshot", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "freeze":
            freeze(args)
        else:
            result = verify_snapshot(args.snapshot)
            print(json.dumps(result, indent=2))
            return 0 if result["passed"] else 1
    except (OSError, ValueError, KeyError, TypeError, csv.Error, InvalidOperation, OverflowError) as error:
        print(json.dumps({"passed": False, "error": str(error)}, indent=2))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
