"""Strict eight-CSV importer with source-aware errors and reproducible JSON output.

Usage: python -m ps1.importer INPUT_DIRECTORY --output IMPORT_RESULT.json
No schedules are created or validated here. No third-party dependencies.
"""
import argparse
from collections import defaultdict, deque
import csv
from datetime import date, timedelta
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile

from .network import build_network, working_span
from .schema import ACCESS_TYPES, BOUNDS, KEYS, NATURES, SCHEMAS

ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = ROOT / "specs/ps1/v0.2.0"
IMPORT_VERSION = "ps1-import-0.2.0"
PROFILE_SHA256 = "a4f79f7e20bc4e6dbc6c07de64e1a090d443b00a5ddf81b6c04a926f143eda8e"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fingerprint(files):
    # Same logical names and identity algorithm as the Step 1 baseline utility.
    return sha("".join(f"PS1/01_data/{name}\t{files[name]['sha256']}\n"
                       for name in sorted(files)).encode("utf-8"))


def parse_value(raw, kind):
    if kind == "optional_id" and raw == "":
        return None
    if not raw or raw != raw.strip() or any(ord(c) < 32 for c in raw):
        raise ValueError("Provide a nonblank value without surrounding whitespace or control characters.")
    if kind in ("id", "optional_id"):
        if any(c.isspace() for c in raw):
            raise ValueError("Identifiers cannot contain whitespace.")
        return raw
    if kind in ("nonnegative", "positive", "flag", "priority"):
        if not re.fullmatch(r"0|[1-9][0-9]*", raw):
            raise ValueError("Use a base-10 integer without signs, decimals or leading zeroes.")
        value = int(raw)
        if kind == "positive" and value == 0:
            raise ValueError("Value must be greater than zero.")
        if kind == "flag" and value not in (0, 1):
            raise ValueError("Flag must be 0 or 1.")
        if kind == "priority" and value not in (1, 2, 3):
            raise ValueError("Priority must be 1, 2 or 3.")
        return value
    if kind == "date":
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", raw):
            raise ValueError("Use an ISO calendar date YYYY-MM-DD.")
        return date.fromisoformat(raw).isoformat()
    if kind == "workload":
        if not re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", raw):
            raise ValueError("Workload must be a positive ordinary decimal, without exponent notation.")
        whole, _, fraction = raw.partition(".")
        if fraction.rstrip("0") not in ("", "5") or (int(whole) == 0 and not fraction.rstrip("0")):
            raise ValueError("This profile supports positive workload in exact half-unit increments only.")
        return raw
    return raw


class Importer:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.reset()

    def reset(self):
        # Allocate fresh containers: previously returned results must not change
        # when the same importer reads a later revision of the input directory.
        self.issues = []
        self.files = {}
        self.tables = {}
        self.index = {}
        self.profile = None
        self.profile_hash = None

    def issue(self, code, row, field, message, severity="error", value=None):
        source = row.get("source", {}) if row else {}
        self.issues.append({"severity": severity, "code": code, "file": source.get("file"),
                            "line": source.get("line"), "field": field, "value": value,
                            "message": message})

    @property
    def failed(self):
        return any(i["severity"] == "error" for i in self.issues)

    def load_profile(self):
        try:
            raw = (PROFILE_DIR / "profile.json").read_bytes()
            if sha(raw) != PROFILE_SHA256:
                raise ValueError("The released v0.2.0 profile changed; review and version the importer before adoption.")
            profile = json.loads(raw)
            if profile["profile_id"] != "ps1-provisional-0.2.0":
                raise ValueError("Unsupported rule profile ID.")
            for filename, key in (("rules.json", "rules_sha256"), ("examples.json", "examples_sha256")):
                if sha((PROFILE_DIR / filename).read_bytes()) != profile[key]:
                    raise ValueError(f"Profile fingerprint mismatch for {filename}.")
            for update in profile["source_updates"]:
                if sha((ROOT / update["file"]).read_bytes()) != update["sha256"]:
                    raise ValueError("Published README evidence fingerprint mismatch.")
            # This importer is an implementation of these exact Step 2 policies.
            # Refuse changed relevant semantics rather than silently ignoring them.
            required = {
                "R01": {"unit_scale": 2},
                "R04": {"sec_span": "inclusive_tunnels_and_incident_platforms", "unsupported_path": "input_error"},
                "R14": {"capacity": "separate_by_line_bound_location"},
                "R18": {"relation": "successor_first_week > predecessor_last_week", "cross_contract_links": True,
                        "finish_basis": "last_scheduled_access_week", "same_week_allowed": False},
                "R19": {"week_days": 7, "release_rounding": "floor_plus_one"},
                "R20": {"repeat_within_horizon": True, "missing_location": "input_error"},
                "R21": {"min_week": 1, "max_week": "horizon_weeks", "extend": False},
            }
            for rule_id, fields in required.items():
                if any(profile["rules"][rule_id]["policy"][key] != value for key, value in fields.items()):
                    raise ValueError(f"Unsupported importer policy change: {rule_id}.")
            if (profile["unconfigured_rules"] != ["R12", "R15", "R17"]
                    or profile["claim_policy"]["unverified_check_is_pass"] is not False):
                raise ValueError("Protection/readiness policy has changed; review implementation first.")
            self.profile, self.profile_hash = profile, sha(raw)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.issue("rule_profile", None, None, f"Cannot load the reviewed rule profile: {exc}")

    def read_inputs(self):
        try:
            if not self.directory.is_dir():
                self.issue("input_directory", None, None, "Select a directory containing the eight PS1 input CSVs.")
                return
            extras = sorted(p.name for p in self.directory.iterdir() if p.is_file() and p.name not in SCHEMAS)
        except OSError as exc:
            self.issue("input_directory", None, None, f"Cannot inspect the input directory: {exc}")
            return
        for extra in extras:
            self.issue("extra_file", {"source": {"file": extra}}, None,
                       "Additional file is not part of the eight-file input contract and is not consumed.", "warning")
        for name, schema in SCHEMAS.items():
            source = {"file": name, "line": 1}
            path = self.directory / name
            rows = []
            self.tables[name] = rows
            try:
                raw = path.read_bytes()
                self.files[name] = {"sha256": sha(raw), "size_bytes": len(raw)}
                reader = csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
                header = next(reader, [])
                if len(set(header)) != len(header) or set(header) != set(schema):
                    self.issue("csv_header", {"source": source}, None,
                               f"Expected each column once; missing={sorted(set(schema)-set(header))}, extra={sorted(set(header)-set(schema))}.")
                    continue
                seen = {}
                while True:
                    line = reader.line_num + 1
                    source = {"file": name, "line": line}
                    values = next(reader, None)
                    if values is None:
                        break
                    if len(values) != len(header):
                        self.issue("csv_width", {"source": source}, None,
                                   f"Expected {len(header)} cells; found {len(values)}. Blank rows are not silently skipped.")
                        continue
                    row = {"source": source}
                    for column, value in zip(header, values):
                        try:
                            row[column] = parse_value(value, schema[column])
                        except ValueError as exc:
                            self.issue("invalid_value", row, column, str(exc), value=value)
                    if len(row) != len(schema) + 1:
                        continue
                    key = tuple(row[k] for k in KEYS[name])
                    if key in seen:
                        self.issue("duplicate_key", row, ",".join(KEYS[name]),
                                   f"Duplicate key {key}; first occurrence is at line {seen[key]}.")
                    seen.setdefault(key, line)
                    rows.append(row)
                if not rows:
                    self.issue("empty_table", {"source": {"file": name, "line": 1}}, None, "Required table has no usable records.")
            except (OSError, UnicodeError, csv.Error) as exc:
                self.issue("read_input", {"source": source}, None, f"Cannot read valid UTF-8 CSV: {exc}")

    def references(self):
        lines = {r["line_code"]: r for r in self.tables["01_LINES.csv"]}
        stations = {(r["line_code"], r["station_id"]): r for r in self.tables["02_STATIONS.csv"]}
        sectors = {r["sector_id"]: r for r in self.tables["03_SECTORS.csv"]}
        locations = {r["location_id"]: r for r in self.tables["04_LOCATION_SUPPLY.csv"]}
        projects = {(r["contract_number"], r["activity_type"]): r for r in self.tables["07_PROJECT_DETAILS.csv"]}
        activities = {r["activity_id"]: r for r in self.tables["08_ACTIVITY_DETAILS.csv"]}
        buffers = {r["nature_of_works"]: r for r in self.tables["05_BUFFER_LOCATION.csv"]}
        params = {r["key"]: r for r in self.tables["06_PARAMETERS.csv"]}
        self.index = dict(lines=lines, stations=stations, sectors=sectors, locations=locations,
                          projects=projects, activities=activities, buffers=buffers, params=params)
        for table in ("02_STATIONS.csv", "03_SECTORS.csv", "04_LOCATION_SUPPLY.csv"):
            for row in self.tables[table]:
                if row["line_code"] not in lines:
                    self.issue("unknown_line", row, "line_code", "Reference a line listed in 01_LINES.csv.")
        for rows in (stations.values(), sectors.values()):
            seen = {}
            for row in rows:
                key = row["line_code"], row["seq"]
                if key in seen:
                    self.issue("duplicate_sequence", row, "seq", f"Duplicate order value on this line; first at line {seen[key]}.")
                seen.setdefault(key, row["source"]["line"])
        for row in sectors.values():
            for field in ("from_station_id", "to_station_id"):
                if (row["line_code"], row[field]) not in stations:
                    self.issue("unknown_station", row, field, "Sector endpoint must reference a station on the same line.")
            if row["from_station_id"] == row["to_station_id"]:
                self.issue("self_loop", row, "to_station_id", "A tunnel must connect two distinct stations.")
            if row["is_shared"]:
                self.issue("unsupported_shared_track", row, "is_shared", "Shared capacity is not configured by R14; review before importing is_shared=1.")
            expected = f"SEC:{row['line_code']}:{row['from_station_id']}_{row['to_station_id']}"
            if row["sector_id"] != expected:
                self.issue("sector_identity", row, "sector_id", f"Expected structured sector ID {expected}.")
        # Construct identities from referenced rows, not by splitting station IDs on '_'.
        expected_locations = {}

        def add_location(id, identity, row):
            if id in expected_locations and expected_locations[id] != identity:
                self.issue("location_identity_collision", row, "line_code,station_id,sector_id",
                           f"Generated ID {id} represents two different locations: {expected_locations[id]} and {identity}. Use unambiguous identifiers; capacity cannot be merged.")
            else:
                expected_locations[id] = identity

        for sector in sectors.values():
            for bound in BOUNDS:
                add_location(f"{sector['sector_id']}:{bound}",
                             ("tunnel sector", sector["line_code"], bound, "sector_id", sector["sector_id"]), sector)
        for line, station in stations:
            for bound in BOUNDS:
                add_location(f"PLAT:{line}:{station}:{bound}",
                             ("platform sector", line, bound, "station_id", station), stations[(line, station)])
        for id, row in locations.items():
            if id not in expected_locations:
                self.issue("unknown_location", row, "location_id", "Location does not match a supplied sector or station, line and EB/WB bound.")
                continue
            kind, line, bound, entity, entity_id = expected_locations[id]
            for field, value in (("location_kind", kind), ("line_code", line), ("bound", bound)):
                if row[field] != value:
                    self.issue("location_metadata", row, field, f"Location ID requires {field}={value}.")
            row[entity] = entity_id
        for id in sorted(expected_locations.keys()-locations.keys()):
            self.issue("missing_supply", {"source": {"file": "04_LOCATION_SUPPLY.csv"}}, "location_id",
                       f"Missing required location {id}; add an explicit capacity, including zero where appropriate.")
        if set(buffers) != set(NATURES):
            self.issue("buffer_categories", None, "nature_of_works", f"Expected exactly these nature categories: {NATURES}.")
        for nature, row in buffers.items():
            if row["opposite_bound_required"] != int(nature == "Live"):
                self.issue("mirror_flag", row, "opposite_bound_required", "The current profile requires opposite-bound effects for Live only.")
            if nature == "Non-live (Others)" and row["up_to_buffer_sectors"] != 0:
                self.issue("buffer_policy", row, "up_to_buffer_sectors", "Non-live (Others) has no buffer under this profile.")
        if set(params) != {"horizon_start", "horizon_weeks"}:
            self.issue("parameter_keys", None, "key", "Expected exactly horizon_start and horizon_weeks; unknown parameters need review.")
        for key, kind in (("horizon_start", "date"), ("horizon_weeks", "positive")):
            if key in params:
                try:
                    params[key]["value"] = parse_value(params[key]["value"], kind)
                except ValueError as exc:
                    self.issue("parameter_value", params[key], "value", str(exc))
        # Contract-wide dates/priority must not depend on arbitrary first-row selection.
        contracts = {}
        for row in projects.values():
            if row["nature_of_activity"] not in buffers:
                self.issue("unknown_nature", row, "nature_of_activity", "Reference a nature_of_works row in the buffer table.")
            if row["access_type"] not in ACCESS_TYPES:
                self.issue("access_category", row, "access_type", f"Expected one of {ACCESS_TYPES}.")
            previous = contracts.setdefault(row["contract_number"], row)
            for field in ("contract_award_date", "contract_completion_date", "planned_completion_date", "contract_priority"):
                if row[field] != previous[field]:
                    self.issue("ambiguous_contract", row, field, "Contract-level dates and priority must agree across activity types; clarify conflicting rows.")
            for field in ("contract_completion_date", "planned_completion_date"):
                if row[field] < row["contract_award_date"]:
                    self.issue("date_order", row, field, "Completion cannot precede the contract award date.")
            if row["planned_completion_date"] > row["contract_completion_date"]:
                self.issue("target_after_contract", row, "planned_completion_date", "Planned target is later than the contractual deadline; both dates are preserved.", "warning")
            if not row["number_of_workfronts"] or not row["number_of_maximum_access_per_week"]:
                self.issue("zero_allocation", row, "number_of_workfronts,number_of_maximum_access_per_week", "Zero resources are preserved and may prevent scheduling; no replacement capacity is invented.", "warning")
        for row in activities.values():
            if (row["contract_number"], row["activity_type"]) not in projects:
                self.issue("unknown_project_type", row, "contract_number,activity_type", "Activity must reference an exact contract/type pair in 07_PROJECT_DETAILS.csv.")
            for field in ("start_location_id", "end_location_id"):
                if row[field] not in locations:
                    self.issue("unknown_endpoint", row, field, "Endpoint must reference a location in 04_LOCATION_SUPPLY.csv.")
            predecessor = row["predecessor_activity_id"]
            if predecessor is not None and predecessor not in activities:
                self.issue("unknown_predecessor", row, "predecessor_activity_id", "Reference one existing activity ID, or leave blank; lists are unsupported.")
        # An interchange flag describes a station membership, not shared capacity.
        membership = defaultdict(list)
        for row in stations.values():
            membership[row["station_id"]].append(row)
        for rows in membership.values():
            expected = int(len(rows) > 1)
            for row in rows:
                if row["is_interchange"] != expected:
                    self.issue("interchange_membership", row, "is_interchange", "Flag must agree with station membership across the supplied lines; external lines are unsupported.")

    def dependencies(self):
        activities = self.index["activities"]
        children, degree, edges = defaultdict(list), {}, []
        for id, activity in activities.items():
            pred = activity["predecessor_activity_id"]
            degree[id] = int(pred is not None)
            if pred:
                children[pred].append(id)
                edges.append({"predecessor": pred, "successor": id, "source": activity["source"]})
        queue, order = deque(sorted(id for id, n in degree.items() if n == 0)), []
        while queue:
            id = queue.popleft()
            order.append(id)
            for child in sorted(children[id]):
                degree[child] -= 1
                if degree[child] == 0:
                    queue.append(child)
        if len(order) != len(activities):
            blocked = {id for id, n in degree.items() if n}
            trail, positions = [], {}
            current = min(blocked)
            while current not in positions:
                positions[current] = len(trail)
                trail.append(current)
                current = activities[current]["predecessor_activity_id"]
            cycle = trail[positions[current]:] + [current]
            self.issue("dependency_cycle", activities[current], "predecessor_activity_id",
                       "Dependency cycle (following predecessor links): " + " -> ".join(cycle))
        return {"edges": edges, "topological_order": order, "scheduling_relation": "R18: successor_first_week > predecessor_last_week",
                "rule_status": self.profile["rules"]["R18"]["status"], "readme_rule": "2.4 rule 3",
                "cross_contract_links_allowed": True}

    def normalize(self, network, dependencies):
        idx = self.index
        start = date.fromisoformat(idx["params"]["horizon_start"]["value"])
        weeks = idx["params"]["horizon_weeks"]["value"]
        try:
            end = start + timedelta(days=7*weeks-1)
        except (OverflowError, ValueError):
            self.issue("horizon_range", idx["params"]["horizon_weeks"], "value", "Horizon exceeds the supported ISO date range.")
            return None
        activities = []
        for row in idx["activities"].values():
            project = idx["projects"][(row["contract_number"], row["activity_type"])]
            buffer = idx["buffers"][project["nature_of_activity"]]
            raw_week = (date.fromisoformat(row["planned_start_date"])-start).days//7+1
            record = dict(row)
            record.update(project_key=[row["contract_number"], row["activity_type"]],
                          project_source=project["source"], access_type=project["access_type"],
                          nature_of_works=project["nature_of_activity"],
                          workload_units_scaled=scaled_workload(row["total_accesses"]),
                          planned_start_week=raw_week, earliest_in_horizon_week=max(1, raw_week))
            if raw_week > weeks:
                self.issue("release_after_horizon", row, "planned_start_date", "No in-horizon week meets this release date; preserve the activity for scheduling diagnostics.", "warning")
            if row["planned_start_date"] < project["contract_award_date"]:
                self.issue("release_before_award", row, "planned_start_date", "Planned release precedes award; dates are preserved for review.", "warning")
            try:
                span = working_span(row, network, idx["locations"], idx["sectors"])
                record["working_span"] = {"rule_id": "R04", "status": "PROVISIONAL", "location_ids": span}
                # No scheduled group/week exists yet. These are demand locations only.
                record["supply_demand"] = {"location_ids": span.copy(), "unit": "distinct_group_per_location_week",
                                           "consumption": None, "status": "NOT_SCHEDULED"}
            except ValueError as exc:
                self.issue("unsupported_span", row, "start_location_id,end_location_id", str(exc))
            record["protection"] = {
                "status": "UNVERIFIED", "location_ids": None, "affected_line_codes": None,
                "buffer_sectors_each_side": buffer["up_to_buffer_sectors"],
                "opposite_bound_required": bool(buffer["opposite_bound_required"]),
                "buffer_source": buffer["source"], "unconfigured_rules": ["R12", "R15", "R17"],
            }
            activities.append(record)
        return {"lines": list(idx["lines"].values()), "stations": list(idx["stations"].values()),
                "sectors": list(idx["sectors"].values()), "locations": list(idx["locations"].values()),
                "buffer_classes": list(idx["buffers"].values()), "parameters": list(idx["params"].values()),
                "project_types": list(idx["projects"].values()), "activities": activities,
                "calendar": {"start": start.isoformat(), "weeks": weeks, "inclusive_end": end.isoformat(),
                             "days_per_week": 7, "rule_id": "R19", "dated_access_calendar": None},
                "workload_unit_scale": 2, "supply_policy": {"rule_id": "R20", "repeat_within_horizon": True},
                "dependencies": dependencies}

    def run(self):
        self.reset()
        self.load_profile()
        self.read_inputs()
        model, network = None, None
        if not self.failed:
            self.references()
        if not self.failed:
            idx = self.index
            dependencies = self.dependencies()
            network = build_network(idx["lines"], list(idx["stations"].values()),
                                    list(idx["sectors"].values()), list(idx["locations"].values()), self.issue)
            if not self.failed:
                model = self.normalize(network, dependencies)
        counts = None
        if not self.failed:
            counts = {"lines": len(model["lines"]), "station_line_memberships": len(model["stations"]),
                      "distinct_stations": len({s["station_id"] for s in model["stations"]}),
                      "sectors": len(model["sectors"]), "bookable_locations": len(model["locations"]),
                      "contracts": len({p["contract_number"] for p in model["project_types"]}),
                      "project_type_rows": len(model["project_types"]), "activities": len(model["activities"]),
                      "workload_units_scaled": sum(a["workload_units_scaled"] for a in model["activities"]),
                      "dependency_edges": len(model["dependencies"]["edges"]),
                      "network_incidence_links": len(network["incidence_links"])}
        identity = fingerprint(self.files) if set(self.files) == set(SCHEMAS) else None
        implementation = {p.name: sha(p.read_bytes()) for p in sorted(Path(__file__).parent.glob("*.py"))}
        return {"schema_version": IMPORT_VERSION,
                "report": {"status": "FAILED" if self.failed else "IMPORTED_WITH_UNVERIFIED_RULES",
                           "input_valid": not self.failed, "schedule_feasibility": "NOT_EVALUATED",
                           "protection_validation": "UNVERIFIED", "official_validation": "NOT_RUN",
                           "counts": counts, "issues": self.issues,
                           "unconfigured_rules": ["R12", "R15", "R17"]},
                "provenance": {"input_directory": str(self.directory), "input_data_sha256": identity,
                               "files": self.files, "profile_id": self.profile["profile_id"] if self.profile else None,
                               "profile_sha256": self.profile_hash,
                               "source_updates": self.profile["source_updates"] if self.profile else [],
                               "profile_source_input_sha256": self.profile["input_data_sha256"] if self.profile else None,
                               "matches_profile_source_input": identity == self.profile["input_data_sha256"] if self.profile and identity else False,
                               "implementation_sha256": implementation},
                "model": None if self.failed else model, "network": None if self.failed else network}


def import_directory(directory):
    return Importer(directory).run()


def scaled_workload(value):
    """Exact integer arithmetic, independent of decimal context precision."""
    whole, _, fraction = value.partition(".")
    return int(whole)*2 + int(bool(fraction.rstrip("0")))


def write_result(result, output, input_directory):
    """One atomic bundle avoids stale successful models beside failed reports."""
    output = Path(output).resolve()
    protected = (Path(input_directory).resolve(), ROOT / "data/baselines", ROOT / "specs")
    if any(output == folder or output.is_relative_to(folder) for folder in protected):
        raise ValueError("Output must be outside input, baseline and rule-specification directories.")
    if output.suffix.lower() != ".json":
        raise ValueError("Choose a .json output file.")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=output.parent,
                                         prefix=".import-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(result, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        os.replace(temporary, output)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_directory", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = import_directory(args.input_directory)
        if args.output:
            write_result(result, args.output, args.input_directory)
        print(json.dumps(result["report"], indent=2))
        return 0 if result["report"]["input_valid"] else 1
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "FAILED", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
