"""Independent schedule accounting under the pinned provisional PS1 profile.

python -m ps1.validator INPUT_DIRECTORY SCHEDULE_DIRECTORY --scenario A --output report.json
Always imports the eight inputs afresh. Never trusts submitted occupancy or RESULTS
as the source of workload, expected working locations or completion dates.
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, timedelta
import io
import json
from pathlib import Path
import sys

from .importer import import_directory, parse_value, sha, write_result
from .night_diagnostic import diagnose, validate_options

VERSION = "ps1-validation-0.3.0"
# Delay weighting and the non-delay score rates, named once so that presentation
# code can cite them instead of copying the literals.
CONTRACT_PRIORITY_WEIGHT = {1: 100, 2: 10, 3: 1}
ACTIVITY_PRIORITY_WEIGHT = {1: 13, 2: 12, 3: 10}
EXCESS_SLOT_TENTHS = 70
ECLO_ACCESS_TENTHS = 50
SCHEMAS = {
    "SCHEDULE_ACCESS.csv": {"activity_id": "id", "access_seq": "positive", "week": "positive", "eclo": "flag", "access_night": "positive"},
    "SCHEDULE_OCCUPANCY.csv": {"activity_id": "id", "week": "positive", "location_id": "id", "co_share_group": "text"},
    "RESULTS.csv": {"scenario": "id", "contract_number": "id", "simulated_completion_date": "date", "overrun_days": "nonnegative"},
}
RULES = ("R01", "R02", "R03", "R04", "R05", "R06", "R07", "R08", "R09", "R10", "R12", "R13", "R15", "R16", "R17", "R18", "R19", "R21", "R22", "R23", "R24", "R25", "R26", "R27", "R28", "R30", "R31", "R32", "R33")


def finding(rule, code, message, activities=(), location=None, week=None, observed=None, expected=None, source=None, severity="violation"):
    return {"rule_id": rule, "code": code, "severity": severity, "activities": sorted(activities),
            "location_id": location, "week": week, "observed": observed, "expected": expected,
            "source": source, "message": message}


def read_schedules(directory):
    directory = Path(directory)
    tables, hashes, issues = {}, {}, []
    for name, schema in SCHEMAS.items():
        rows, source = [], {"file": name, "line": 1}
        tables[name] = rows
        try:
            raw = (directory / name).read_bytes()
            hashes[name] = sha(raw)
            reader = csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
            header = next(reader, [])
            if len(header) != len(set(header)) or set(header) != set(schema):
                issues.append(finding("R33", "csv_header", "Require each documented column exactly once.", observed=header, expected=list(schema), source=source))
                continue
            while True:
                source = {"file": name, "line": reader.line_num+1}
                values = next(reader, None)
                if values is None:
                    break
                if len(values) != len(header):
                    issues.append(finding("R33", "csv_width", "Row width differs from header.", observed=len(values), expected=len(header), source=source))
                    continue
                row = {"source": source}
                for column, value in zip(header, values):
                    try:
                        row[column] = parse_value(value, schema[column])
                    except ValueError as exc:
                        issues.append(finding("R33", "csv_value", f"{column}: {exc}", observed=value, source=source))
                if len(row) == len(schema)+1:
                    rows.append(row)
        except (OSError, UnicodeError, csv.Error) as exc:
            issues.append(finding("R33", "schedule_read", str(exc), source=source))
    return tables, hashes, issues


def reconstruct_span(activity, model):
    """Independent of the imported cached working_span and submitted occupancy."""
    locations = {l["location_id"]: l for l in model["locations"]}
    sectors = {s["sector_id"]: s for s in model["sectors"]}
    start, end = (locations[activity[k]] for k in ("start_location_id", "end_location_id"))
    line, bound = start["line_code"], start["bound"]
    following = {s["from_station_id"]: s for s in sectors.values() if s["line_code"] == line}
    current, seen, result = sectors[start["sector_id"]], set(), set()
    while current["sector_id"] not in seen:
        seen.add(current["sector_id"])
        result.add(current["sector_id"] + ":" + bound)
        result.update(f"PLAT:{line}:{station}:{bound}" for station in (current["from_station_id"], current["to_station_id"]))
        if current["sector_id"] == end["sector_id"]:
            return result
        current = following[current["to_station_id"]]
    raise ValueError("Imported topology does not provide the expected working span.")


def decimal_tenths(value):
    return f"{value//10}.{value%10}"


def check_schedule(model, tables, scenario, night_limit=7, search_budget=50000):
    """Internal API: model from successful current import, typed parsed rows only."""
    validate_options(night_limit, search_budget)
    if scenario not in ("A", "B", "C"):
        raise ValueError("Choose scenario A, B or C explicitly.")
    checks = {rule: "NOT_EVALUATED" for rule in RULES}
    issues = []

    def emit(rule, code, message, **kwargs):
        issues.append(finding(rule, code, message, **kwargs))

    def finish(metrics=None, diagnostic=None):
        for f in issues:
            if f["severity"] == "error":
                checks[f["rule_id"]] = "ERROR"
            elif f["severity"] == "violation":
                checks[f["rule_id"]] = "FAIL"
            elif checks[f["rule_id"]] != "FAIL":
                checks[f["rule_id"]] = "UNVERIFIED"
        violated = any(f["severity"] == "violation" for f in issues)
        internal_error = any(f["severity"] == "error" for f in issues)
        return {"status": "VALIDATION_ERROR" if internal_error else "INVALID_UNDER_PROFILE" if violated else "UNVERIFIED",
                "full_feasibility_established": False, "official_validation": "NOT_RUN",
                "rule_checks": checks, "findings": issues, "metrics": metrics,
                "physical_night_diagnostic": diagnostic or {"status": "NOT_EVALUATED", "reason": "Required schedule structure or occupancy is invalid."}}

    accesses, occupancy, results = (tables[n] for n in SCHEMAS)
    acts = {a["activity_id"]: a for a in model["activities"]}
    projects = {(p["contract_number"], p["activity_type"]): p for p in model["project_types"]}
    contracts = {p["contract_number"]: p for p in model["project_types"]}
    locations = {l["location_id"]: l for l in model["locations"]}
    horizon = model["calendar"]["weeks"]
    start = date.fromisoformat(model["calendar"]["start"])
    aw, seq = {}, set()
    for r in accesses:
        a, w = r["activity_id"], r["week"]
        if a not in acts:
            emit("R33", "unknown_activity", "Access references an unknown activity.", activities=[a], source=r.get("source"))
        if (a, w) in aw:
            emit("R03", "duplicate_activity_week", "At most one access per activity/week.", activities=[a], week=w, source=r.get("source"))
        if (a, r["access_seq"]) in seq:
            emit("R33", "duplicate_access_sequence", "Access sequence must identify one access within its activity.", activities=[a], observed=r["access_seq"], source=r.get("source"))
        if not 1 <= w <= horizon:
            emit("R21", "outside_horizon", "Access is outside the supplied horizon.", activities=[a], week=w, expected=[1, horizon])
        aw[(a, w)] = r
        seq.add((a, r["access_seq"]))
    if issues:
        return finish()
    for rule in ("R03", "R21", "R33"):
        checks[rule] = "PASS_UNDER_PROFILE"

    by_activity, local, allocations = defaultdict(list), defaultdict(list), defaultdict(set)
    for r in accesses:
        a = acts[r["activity_id"]]
        p = projects[tuple(a["project_key"])]
        key = (*a["project_key"], r["week"])
        by_activity[a["activity_id"]].append(r)
        local[(*key, r["access_night"])].append(a["activity_id"])
        allocations[key].add(r["access_night"])
        release = (date.fromisoformat(a["planned_start_date"])-start).days//7+1
        if r["week"] < release:
            emit("R02", "before_release", "Activity is placed before its planned-start week.", activities=[a["activity_id"]], week=r["week"], expected=f">= {release}")
        if r["access_night"] > p["number_of_maximum_access_per_week"]:
            emit("R07", "allocation_index", "Contract/type local night index exceeds its supplied allocation.", activities=[a["activity_id"]], week=r["week"], observed=r["access_night"], expected=p["number_of_maximum_access_per_week"])
        if scenario == "A" and r["eclo"]:
            emit("R22", "eclo_forbidden", "Scenario A forbids ECLO.", activities=[a["activity_id"]], week=r["week"])
    for (contract, kind, week, index), jobs in local.items():
        cap = projects[(contract, kind)]["number_of_workfronts"]
        if len(jobs) > cap:
            emit("R08", "workfront_limit", f"Contract {contract}/{kind} local index {index} exceeds its workfront limit.", activities=jobs, week=week, observed=len(jobs), expected=cap)
    for (contract, kind, week), indices in allocations.items():
        cap = projects[(contract, kind)]["number_of_maximum_access_per_week"]
        if len(indices) > cap:
            emit("R07", "allocation_count", f"Contract {contract}/{kind} uses too many distinct local indices.", week=week, observed=len(indices), expected=cap)

    completion, workload = {}, []
    for id, activity in acts.items():
        rows = by_activity[id]
        yield_scaled = sum(3 if r["eclo"] else 2 for r in rows)
        required = activity["workload_units_scaled"]
        full = yield_scaled >= required
        if not full:
            emit("R01", "incomplete_workload", "Activity workload is incomplete; missing activities are never treated as complete.", activities=[id], observed=yield_scaled, expected=required)
        completion[id] = (start + timedelta(days=max(r["week"] for r in rows)*7-1)).isoformat() if full else None
        workload.append({"activity_id": id, "required_scaled": required, "delivered_scaled": yield_scaled, "complete": full, "completion_date": completion[id]})
    for a in acts.values():
        pred = a["predecessor_activity_id"]
        if pred and by_activity[a["activity_id"]]:
            if completion[pred] is None:
                emit("R18", "predecessor_incomplete", "A scheduled successor has an incomplete predecessor.", activities=[pred, a["activity_id"]])
            elif min(r["week"] for r in by_activity[a["activity_id"]]) <= max(r["week"] for r in by_activity[pred]):
                emit("R18", "predecessor_order", "README section 2.4 rule 3 requires the successor to start strictly after the predecessor's last scheduled week, including across contracts.", activities=[pred, a["activity_id"]])

    # Expected coverage is driven only by input topology and access placements.
    spans = {id: reconstruct_span(a, model) for id, a in acts.items()}
    expected_occ = {(a, w, l) for a, w in aw for l in spans[a]}
    actual_occ, groups, by_location = set(), defaultdict(list), defaultdict(set)
    occ_error = False
    for r in occupancy:
        a, w, l = r["activity_id"], r["week"], r["location_id"]
        key = a, w, l
        if key in actual_occ:
            emit("R30", "duplicate_occupancy", "Duplicate activity/week/location row.", activities=[a], location=l, week=w, source=r.get("source"))
            occ_error = True
        actual_occ.add(key)
        if key not in expected_occ:
            emit("R30", "unexpected_occupancy", "Row is outside the reconstructed working span or has no matching access.", activities=[a], location=l, week=w, source=r.get("source"))
            occ_error = True
        groups[(l, w, r["co_share_group"])].append(a)
        by_location[(l, w)].add(r["co_share_group"])
    for a, w, l in sorted(expected_occ-actual_occ):
        emit("R30", "missing_occupancy", "Required working location is missing; it cannot hide a capacity or sharing conflict.", activities=[a], location=l, week=w)
        occ_error = True
    excess, capacity_rows = None, None
    if not occ_error:
        excess, capacity_rows = 0, []
        for (l, w, group), jobs in groups.items():
            types = Counter(acts[a]["access_type"] for a in jobs)
            legal = ((types["PM"] == 1 and len(jobs) == 1) or
                     (types["PM"] == 0 and types["PC"] <= 1 and len(jobs) <= 4))
            if not legal:
                emit("R05", "illegal_sharing", f"Group {group} violates PM/PC/C composition limits.", activities=jobs, location=l, week=w, observed=dict(types), expected="PM alone; 1 PC + 0..3 C; 1..4 C")
            flags = {aw[(a, w)]["eclo"] for a in jobs}
            if len(flags) > 1:
                emit("R27", "mixed_eclo_group", "Provisional R27 requires equal ECLO flags within a local group.", activities=jobs, location=l, week=w, observed=sorted(flags))
        for (l, w), labels in sorted(by_location.items()):
            supply = next((r["capacity"] for r in model.get("weekly_supply_overrides", []) if r["location_id"] == l and r["week"] == w), locations[l]["supply_capacity"])
            extra = max(0, len(labels)-supply)
            excess += extra
            capacity_rows.append({"location_id": l, "week": w, "groups": len(labels), "supply": supply, "excess": extra})
            if scenario != "B" and extra > (0 if scenario == "A" else 1):
                affected = {a for label in labels for a in groups[(l, w, label)]}
                emit("R22" if scenario == "A" else "R24", "capacity_limit", "Distinct local groups exceed the scenario allowance.", activities=affected, location=l, week=w, observed=len(labels), expected=supply+(scenario == "C"), source=locations[l].get("source"))
        for rule in ("R04", "R05", "R06", "R09", "R27", "R30"):
            checks[rule] = "PASS_UNDER_PROFILE"
    else:
        for rule in ("R04", "R05", "R06", "R09", "R27"):
            checks[rule] = "NOT_EVALUATED"

    line_weeks, live_eclo = defaultdict(set), []
    if scenario == "C":
        for r in accesses:
            if r["eclo"]:
                a = acts[r["activity_id"]]
                own_line = locations[a["start_location_id"]]["line_code"]
                line_weeks[own_line].add(r["week"])
                if a["nature_of_works"] == "Live":
                    live_eclo.append(a["activity_id"])
        for line, weeks in sorted(line_weeks.items()):
            if max(weeks)-min(weeks) > 1:
                emit("R25", "eclo_window", f"ECLO on working line {line} does not fit two adjacent weeks.", observed=sorted(weeks), expected="max(week)-min(week) <= 1")
        if live_eclo:
            emit("R25", "eclo_affected_lines_unknown", "Working-line windows checked; complete Live affected-line windows depend on unresolved R15.", activities=set(live_eclo), severity="unverified")
        checks["R25"] = "PASS_UNDER_PROFILE"
        emit("R32", "scenario_c_input_unconfirmed", "No organiser confirmation of the Scenario C input manifest is available.", severity="unverified")
    else:
        checks["R25"] = checks["R32"] = "NOT_APPLICABLE"

    result_map = {}
    for r in results:
        c = r["contract_number"]
        if c in result_map or c not in contracts or r["scenario"] != scenario:
            emit("R33", "result_identity", "RESULTS must contain exactly one row per known contract for the requested scenario.", observed={k: r[k] for k in ("contract_number", "scenario")}, expected=scenario, source=r.get("source"))
        result_map[c] = r
    for c in sorted(contracts.keys()-result_map.keys()):
        emit("R31", "missing_result", f"RESULTS omits contract {c}.")
    contract_details, activity_days, weighted_tenths, contract_days, contract_weighted = [], 0, 0, 0, 0
    all_complete = all(v is not None for v in completion.values())
    weights, multiplier = CONTRACT_PRIORITY_WEIGHT, ACTIVITY_PRIORITY_WEIGHT
    for id, a in acts.items():
        p = projects[tuple(a["project_key"])]
        if completion[id] is not None:
            late = max(0, (date.fromisoformat(completion[id])-date.fromisoformat(p["planned_completion_date"])).days)
            activity_days += late
            weighted_tenths += late*weights[p["contract_priority"]]*multiplier[a["activity_priority"]]
    for c, project in contracts.items():
        jobs = [id for id, a in acts.items() if a["contract_number"] == c]
        done = bool(jobs) and all(completion[a] is not None for a in jobs)
        finish_date = max(completion[a] for a in jobs) if done else None
        late = max(0, (date.fromisoformat(finish_date)-date.fromisoformat(project["planned_completion_date"])).days) if done else None
        contract_details.append({"contract_number": c, "completion_date": finish_date, "overrun_days": late})
        if not done:
            emit("R31", "contract_completion_unavailable", f"Contract {c} has no complete activity-based finish date; its submitted date cannot establish completion.", severity="unverified")
            all_complete = False
            continue
        contract_days += late
        contract_weighted += late*weights[project["contract_priority"]]
        if c in result_map and (result_map[c]["simulated_completion_date"] != finish_date or result_map[c]["overrun_days"] != late):
            emit("R31", "result_mismatch", f"Contract {c} RESULTS differs from independently recomputed completion.", observed={k: result_map[c][k] for k in ("simulated_completion_date", "overrun_days")}, expected={"simulated_completion_date": finish_date, "overrun_days": late}, source=result_map[c].get("source"))
        if scenario == "B" and late:
            emit("R23", "planned_date", f"Scenario B contract {c} misses its planned completion date.", activities=jobs, observed=late, expected=0)

    for rule in ("R01", "R02", "R07", "R08", "R18", "R19", "R26", "R28", "R31"):
        checks[rule] = "PASS_UNDER_PROFILE"
    if not all_complete:
        checks["R19"] = checks["R28"] = "NOT_EVALUATED"
    if excess is None:
        checks["R28"] = "NOT_EVALUATED"
    for rule, applicable in (("R22", "A"), ("R23", "B"), ("R24", "C")):
        checks[rule] = ("NOT_APPLICABLE" if scenario != applicable else
                        "NOT_EVALUATED" if (scenario != "B" and occ_error) or not all_complete else "PASS_UNDER_PROFILE")
    for rule in ("R12", "R13", "R15", "R16", "R17"):
        emit(rule, "protection_unverified", "Complete protection validation is unavailable: buffer geometry, mirror extent, interchange propagation or temporal/exemption semantics are unresolved.", severity="unverified")
    eclo = sum(r["eclo"] for r in accesses)
    total = None
    if all_complete and excess is not None:
        total = (weighted_tenths if scenario != "B" else 0) + (EXCESS_SLOT_TENTHS*excess+ECLO_ACCESS_TENTHS*eclo if scenario != "A" else 0)
    metrics = {"scope": "Provisional arithmetic, not a feasibility or official-score verdict.",
               "workload_unit_scale": 2, "workload": workload, "contracts": contract_details,
               "all_work_complete": all_complete, "activity_delay_days": activity_days if all_complete else None,
               "contract_delay_days": contract_days if all_complete else None,
               "contract_weighted_delay": contract_weighted if all_complete else None,
               "activity_weighted_delay_tenths": weighted_tenths if all_complete else None,
               "excess_location_week_units": excess, "eclo_activity_accesses": eclo,
               "score_tenths": total, "score_decimal": decimal_tenths(total) if total is not None else None,
               "score_eligible": False, "capacity": capacity_rows,
               "eclo_working_line_weeks": {line: sorted(weeks) for line, weeks in sorted(line_weeks.items())}}
    # Diagnostic uses reconstructed spans, not a mutable cached importer field.
    diagnostic_model = dict(model, activities=[dict(a, working_span={"location_ids": sorted(spans[a["activity_id"]])}) for a in model["activities"]])
    diagnostic = diagnose(diagnostic_model, accesses, occupancy, night_limit, search_budget) if not occ_error else None
    if diagnostic is not None:
        scheduled = {r["activity_id"] for r in accesses}
        diagnostic["coverage"] = {"scope": "Submitted accesses only; no missing work is assigned.",
                                  "required_activities": len(acts), "scheduled_activities": len(scheduled),
                                  "unscheduled_activity_ids": sorted(acts.keys()-scheduled),
                                  "incomplete_activity_ids": sorted(w["activity_id"] for w in workload if not w["complete"]),
                                  "all_work_complete": all_complete}
        checks["R10"] = {"NO_ACCESSES": "NOT_APPLICABLE", "ASSIGNED_FOR_MODELLED_RELATIONS": "CONDITIONAL_ASSIGNMENT",
                         "INCONSISTENT_UNDER_ASSUMPTIONS": "CONDITIONAL_CONFLICT", "UNKNOWN_SEARCH_LIMIT": "UNKNOWN_SEARCH_LIMIT",
                         "INTERNAL_ERROR": "ERROR"}[diagnostic["status"]]
        if diagnostic["status"] == "INTERNAL_ERROR":
            emit("R10", "diagnostic_internal_error", "The computed night assignment failed independent runtime checks; no assignment is published. This is a checker error, not proof of schedule infeasibility.", severity="error")
    return finish(metrics, diagnostic)


def validate_schedule(input_directory, schedule_directory, scenario, night_limit=7, search_budget=50000, weekly_supply=None):
    validate_options(night_limit, search_budget)
    if scenario not in ("A", "B", "C"):
        raise ValueError("Choose scenario A, B or C explicitly.")
    imported = import_directory(input_directory)
    if weekly_supply:
        from .replan import supply_overrides
        if not imported['report']['input_valid']:
            raise ValueError('Cannot apply planning supply to invalid inputs.')
        supply_overrides(imported['model'], weekly_supply)
        imported['model']['weekly_supply_overrides'] = weekly_supply
    tables, hashes, parse_issues = read_schedules(schedule_directory)
    input_findings = []
    for issue in imported["report"]["issues"]:
        item = finding(None, "input_"+issue["code"], issue["message"], observed=issue["value"],
                       source={"file": issue["file"], "line": issue["line"]},
                       severity="violation" if issue["severity"] == "error" else "warning")
        item.update(stage="input", field=issue["field"])
        input_findings.append(item)
    if not imported["report"]["input_valid"] or parse_issues:
        report = {"status": "INVALID_INPUT_OR_SCHEDULE", "full_feasibility_established": False,
                  "official_validation": "NOT_RUN", "rule_checks": {r: "NOT_EVALUATED" for r in RULES},
                  "findings": parse_issues, "metrics": None,
                  "physical_night_diagnostic": {"status": "NOT_EVALUATED"}}
        if parse_issues:
            report["rule_checks"]["R33"] = "FAIL"
    else:
        report = check_schedule(imported["model"], tables, scenario, night_limit, search_budget)
    report["findings"].extend(input_findings)
    identity = sha("".join(f"{name}\t{digest}\n" for name, digest in sorted(hashes.items())).encode()) if set(hashes) == set(SCHEMAS) else None
    return {"version": VERSION, "scenario": scenario, "report": report,
            "input_report": imported["report"], "provenance": {"input": imported["provenance"],
            "schedule_directory": str(Path(schedule_directory).resolve()), "schedule_files_sha256": hashes,
            "schedule_sha256": identity, "weekly_supply_overrides": weekly_supply or [], "night_limit": night_limit, "search_budget_per_week": search_budget,
            "validator_source_sha256": {name: sha(Path(__file__).with_name(name).read_bytes()) for name in ("validator.py", "night_diagnostic.py")}}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_directory", type=Path)
    parser.add_argument("schedule_directory", type=Path)
    parser.add_argument("--scenario", required=True, choices=("A", "B", "C"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--night-limit", type=int, choices=range(1, 8), default=7)
    parser.add_argument("--search-budget", type=int, default=50000)
    parser.add_argument("--planning-context", type=Path, help="Explicit Step 8 planning-context.json for weekly supply overrides; not an organiser CSV.")
    args = parser.parse_args()
    try:
        if args.search_budget < 0:
            raise ValueError("Search budget must be nonnegative.")
        result = validate_schedule(args.input_directory, args.schedule_directory, args.scenario, args.night_limit, args.search_budget,
                                   json.loads(args.planning_context.read_text(encoding='utf-8'))['weekly_supply'] if args.planning_context else None)
        if args.output:
            if args.output.resolve().is_relative_to(args.schedule_directory.resolve()):
                raise ValueError("Output must be outside the schedule input directory.")
            write_result(result, args.output, args.input_directory)
        report = result["report"]
        print(json.dumps({"status": report["status"], "scenario": args.scenario,
                          "findings_by_severity": dict(Counter(f["severity"] for f in report["findings"])),
                          "score_decimal": report["metrics"]["score_decimal"] if report["metrics"] else None,
                          "physical_night_status": report["physical_night_diagnostic"]["status"]}, indent=2))
        return 1 if report["status"].startswith("INVALID") or report["status"] == "VALIDATION_ERROR" else 2
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "FAILED", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
