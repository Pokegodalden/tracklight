"""Check specification consistency and render Step 2 documents; not a solver.

Examples are isolated rule specifications, not runnable official submissions.
"""
import argparse
from collections import Counter
import csv
from datetime import date, timedelta
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import sys

from baseline import verify_snapshot

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "specs/ps1/v0.2.0"
SNAPSHOT = ROOT / "data/baselines/ps1-0dfd901f97bf579f"
REPORTS = ROOT / "outputs/readme-update-966c976"
UPDATE_COMMIT = "966c976005db2e3e40a691cff268fdb8f396a5df"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_pack(directory=PACK):
    return tuple(json.loads((directory / name).read_text(encoding="utf-8"))
                 for name in ("rules.json", "examples.json", "profile.json"))


def read_rows(file):
    with (SNAPSHOT / file).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return {reader.line_num: row for row in reader}


def check_pack(register, examples, profile, directory=PACK):
    issues = []
    def require(condition, message):
        if not condition:
            issues.append(message)

    require(verify_snapshot(SNAPSHOT)["passed"], "Frozen baseline failed verification")
    manifest = json.loads((SNAPSHOT / "manifest.json").read_text(encoding="utf-8"))
    inventory = {entry["path"] for entry in manifest["files"]}
    for name, obj in (("rules", register), ("examples", examples), ("profile", profile)):
        for key in ("snapshot_id", "pack_sha256", "input_data_sha256"):
            require(obj[key] == manifest[key], f"{name}: incorrect baseline {key}")
        require(obj["version"] == profile["version"] and obj["version"] in ("0.1.0", "0.2.0"), f"{name}: unexpected version")
    updated = profile["version"] == "0.2.0"
    extra_sources = {}
    for update in profile.get("source_updates", []):
        expected = f"data/source_updates/{UPDATE_COMMIT}/PS1_README.md"
        require(update["file"] == expected and update["commit"] == UPDATE_COMMIT, "Unexpected source update")
        if update["file"] == expected:
            path = ROOT / update["file"]
            require(path.exists() and digest(path) == update["sha256"], "Source update fingerprint mismatch")
            extra_sources[update["file"]] = path
    require(not updated or len(extra_sources) == 1, "Updated profile needs published README evidence")
    for obj in (register, examples):
        require(obj.get("source_updates", []) == profile.get("source_updates", []), "Source update metadata drift")
    require(profile["rules_sha256"] == digest(directory / "rules.json"), "Rules digest mismatch")
    require(profile["examples_sha256"] == digest(directory / "examples.json"), "Examples digest mismatch")
    rules = {r["id"]: r for r in register["rules"]}
    cases = {c["id"]: c for c in examples["cases"]}
    questions = {q["id"]: q for q in register["questions"]}
    require(len(rules) == len(register["rules"]), "Duplicate rule IDs")
    require(len(cases) == len(examples["cases"]), "Duplicate case IDs")
    require(len(questions) == len(register["questions"]), "Duplicate question IDs")
    require(set(profile["rules"]) == set(rules), "Profile rule coverage mismatch")
    evidence_count = 0
    for id, rule in rules.items():
        require(rule["status"] in register["status_definitions"], f"{id}: unknown status")
        require(bool(rule["decision"] and rule["selected_policy"] and rule["enforcement_location"]), f"{id}: missing interpretation/policy/enforcement")
        require(bool(rule["sources"]), f"{id}: missing sources")
        if updated and id == "R18":
            require(rule["status"] == "documented" and rule["official_rule_version"] == UPDATE_COMMIT
                    and rule["organiser_question"] is None and bool(rule["organiser_response"]), "R18: missing published precedence confirmation")
        else:
            require(rule["organiser_response"] is None and rule["official_rule_version"] is None,
                    f"{id}: must not invent organiser confirmation")
        question = rule["organiser_question"]
        require(question is None or question in questions, f"{id}: unknown question")
        if rule["status"] != "documented":
            require(question in questions, f"{id}: assumption lacks organiser question")
        require(profile["rules"].get(id) == {"status": rule["status"], "mode": rule["enforcement_mode"], "policy": rule["selected_policy"]}, f"{id}: profile drift")
        require(bool(rule["examples"]), f"{id}: no example")
        for example in rule["examples"]:
            require(example in cases and id in cases[example]["rule_ids"], f"{id}: broken example link {example}")
        for ref in rule["sources"]:
            require(ref["file"] in inventory or ref["file"] in extra_sources, f"{id}: source outside frozen inventory")
            if ref["file"] in inventory or ref["file"] in extra_sources:
                path = extra_sources.get(ref["file"], SNAPSHOT / ref["file"])
                lines = path.read_text(encoding="utf-8-sig").splitlines()
                require(0 < ref["line"] <= len(lines) and ref["anchor"] in lines[ref["line"]-1], f"{id}: source anchor/line mismatch")
    for id, case in cases.items():
        require(case["official_result"] is None, f"{id}: fabricated official result")
        require(bool(case["given"] and case["expected_by_interpretation"] and case["expectation_basis"]), f"{id}: incomplete example")
        for rule_id in case["rule_ids"]:
            require(rule_id in rules and id in rules[rule_id]["examples"], f"{id}: broken rule link {rule_id}")
        require(case["question"] is None or case["question"] in questions, f"{id}: unknown question")
        for record in case["evidence"]:
            evidence_count += 1
            require(record["file"] in inventory, f"{id}: evidence outside frozen inventory")
            if record["file"] in inventory:
                require(read_rows(record["file"]).get(record["line"]) == record["row"], f"{id}: evidence row differs from frozen source")
    for id, question in questions.items():
        if updated and id == "Q06":
            require(question["sent"] is False and bool(question["response"])
                    and question.get("official_rule_version") == UPDATE_COMMIT
                    and question.get("status") == "resolved_by_published_readme", "Q06: missing published resolution")
        else:
            require(question["sent"] is False and question["response"] is None, f"{id}: unanswered draft must not invent a reply")
        require(all(case in cases for case in question["examples"]), f"{id}: unknown example")
    deferred = sorted(r["id"] for r in rules.values() if r["status"] == "deferred")
    require(sorted(profile["unconfigured_rules"]) == deferred, "Unconfigured rule list mismatch")
    require(all(rules[id]["enforcement_mode"] == "unverified" for id in deferred), "Deferred rules cannot silently pass")
    require(profile["officially_confirmed"] is False, "Profile cannot claim official confirmation")
    require(profile["claim_policy"]["unverified_check_is_pass"] is False, "Unknown checks must not pass")
    for flag in ("complete_protection_validation", "official_score_equivalence", "physical_dispatch"):
        require(profile["readiness"][flag] is False, f"Readiness claim not supported: {flag}")
    return issues, evidence_count


def check_selected_evidence(examples):
    """Recompute cited observations and hand arithmetic, not all rule outcomes."""
    cases = {c["id"]: c for c in examples["cases"]}
    checks = {}
    by_place = {}
    for record in cases["E07"]["evidence"]:
        row = record["row"]
        by_place.setdefault(row["location_id"], {})[row["activity_id"]] = row["co_share_group"]
    checks["E07_equality_contradiction"] = (by_place["PLAT:BET:S15:EB"]["A001"] != by_place["PLAT:BET:S15:EB"]["A011"] and by_place["PLAT:BET:S16:EB"]["A001"] == by_place["PLAT:BET:S16:EB"]["A011"])
    activity_rows = {row["activity_id"]: row for row in read_rows("PS1/01_data/08_ACTIVITY_DETAILS.csv").values()}
    checks["E07_identical_work_spans"] = all(activity_rows["A001"][key] == activity_rows["A011"][key] for key in ("start_location_id", "end_location_id"))
    evidence8 = cases["E08"]["evidence"]
    local8 = [r["row"] for r in evidence8 if r["file"].endswith("SCHEDULE_ACCESS.csv")]
    group8 = [r["row"] for r in evidence8 if r["file"].endswith("SCHEDULE_OCCUPANCY.csv")]
    p8 = [r["row"] for r in evidence8 if r["file"].endswith("07_PROJECT_DETAILS.csv")][0]
    checks["E08_workfront_contradiction"] = (len(local8) == 2 and {r["access_night"] for r in local8} == {"1", "3"} and len(group8) == 2 and {r["co_share_group"] for r in group8} == {"b4"} and p8["number_of_workfronts"] == "1" and all(activity_rows[r["activity_id"]]["contract_number"] == "C007" for r in local8) and len({activity_rows[r["activity_id"]]["activity_type"] for r in local8}) == 1)
    start = date(2027, 1, 4)
    e15 = cases["E15"]["expected_by_interpretation"]
    checks["E15_week_boundaries"] = all(e15[key] == (start + timedelta(days=week*7-1)).isoformat() for key, week in (("week_1_end", 1), ("week_30_end", 30)))
    e21 = cases["E21"]["expected_by_interpretation"]
    delay = Decimal(7)*Decimal("1.3") + Decimal(14)
    checks["E21_candidate_score_arithmetic"] = (Decimal(e21["selected_activity_weighted_delay"]) == delay and Decimal(e21["selected_C_score"]) == delay+2*7+3*5 and Decimal(e21["alternative_C_score"]) == 14+2*7+3*5)
    last_weeks = {}
    for row in read_rows("PS1/03_submission_sample/SCHEDULE_ACCESS.csv").values():
        last_weeks[row["activity_id"]] = max(last_weeks.get(row["activity_id"], 0), int(row["week"]))
    projects = {row["contract_number"]: row for row in read_rows("PS1/01_data/07_PROJECT_DETAILS.csv").values()}
    late_records, finishes = [], {}
    for activity_id, week in sorted(last_weeks.items()):
        activity = activity_rows[activity_id]
        contract = activity["contract_number"]
        completion = start + timedelta(days=week*7-1)
        finishes[contract] = max(finishes.get(contract, start), completion)
        days = max(0, (completion-date.fromisoformat(projects[contract]["planned_completion_date"])).days)
        if days:
            weight = {"1": Decimal(100), "2": Decimal(10), "3": Decimal(1)}[projects[contract]["contract_priority"]]
            multiplier = {"1": Decimal("1.3"), "2": Decimal("1.2"), "3": Decimal(1)}[activity["activity_priority"]]
            late_records.append(dict(activity_id=activity_id, contract=contract, late_days=days, weighted=str(days*weight*multiplier)))
    e22 = cases["E22"]
    checks["E22_late_activity_records"] = late_records == e22["given"]["late_activities"]
    sample_results = list(read_rows("PS1/03_submission_sample/RESULTS.csv").values())
    checks["E22_all_contract_completion_dates"] = all(row["simulated_completion_date"] == finishes[row["contract_number"]].isoformat() and int(row["overrun_days"]) == max(0, (finishes[row["contract_number"]]-date.fromisoformat(projects[row["contract_number"]]["planned_completion_date"])).days) for row in sample_results)
    checks["E22_distinct_delay_totals"] = (sum(int(r["overrun_days"]) for r in sample_results) == e22["expected_by_interpretation"]["contract_days_from_RESULTS"] == 28 and sum(r["late_days"] for r in late_records) == e22["expected_by_interpretation"]["activity_days"] == 42 and sum(Decimal(r["weighted"]) for r in late_records) == Decimal(e22["expected_by_interpretation"]["candidate_activity_weighted_score"]) == Decimal("48.3"))
    expected24 = {"PLAT:ALP:H01:EB", "PLAT:ALP:H02:EB", "SEC:ALP:H01_H02:EB"}
    checks["E24_working_rows_only"] = len(cases["E24"]["evidence"]) == 3 and {r["row"]["location_id"] for r in cases["E24"]["evidence"]} == expected24
    return checks


def format_value(value):
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def source_link(ref):
    path = ROOT / ref["file"] if ref["file"].startswith("data/source_updates/") else SNAPSHOT / ref["file"]
    target = Path(os.path.relpath(path, REPORTS)).as_posix()
    return f"[{ref['file']} — {ref.get('section', 'record')}, line {ref['line']}]({target})"


def render(register, examples, profile):
    preamble = (f"Version {profile['version']}; baseline `{profile['snapshot_id']}`. "
                "Published README commit `966c976` resolves predecessor semantics. No direct organiser reply or official tool result is available.\n\n")
    rule_text = "# PS1 rule register\n\n" + preamble
    rule_text += "This is a specification, not implemented scheduling validation.\n\n"
    for name, meaning in register["status_definitions"].items():
        rule_text += f"- **{name}:** {meaning}\n"
    rule_text += "\nDeferred rules have an explicit UNVERIFIED handling policy; they are not resolved operational rules.\n"
    for rule in register["rules"]:
        rule_text += f"\n## {rule['id']} — {rule['title']}\n\nStatus: **{rule['status']}**. Planned enforcement: {rule['enforcement_location']}.\n\n{rule['decision']}\n\n"
        rule_text += "Sources: " + "; ".join(source_link(s) for s in rule["sources"]) + ".\n\n"
        rule_text += "Examples: " + ", ".join(f"[{e}](examples.md#{e.lower()})" for e in rule["examples"]) + ". "
        rule_text += f"Organiser question: {rule['organiser_question'] or 'None currently required'}. Published confirmation/version: {rule['official_rule_version'] or 'none'}.\n"
    example_text = "# PS1 small rule examples\n\n" + preamble
    example_text += "These are isolated specifications with stipulated context, not complete eight-CSV submissions. PASS/FAIL applies only to the named rule/interpretation. None is an official validator verdict. Synthetic names such as a, b and L are placeholders, not missing baseline records.\n\nOnly the cited sample rows and selected arithmetic/logic observations are recomputed by the Step 2 checker. The remaining outcomes are authored expectations for later checker/solver tests.\n"
    for case in examples["cases"]:
        example_text += f"\n<a id=\"{case['id'].lower()}\"></a>\n\n## {case['id']} — {case['title']}\n\nRules: {', '.join(case['rule_ids'])}. Basis: {case['expectation_basis']}.\n\nGiven:\n\n"
        example_text += "\n".join(f"- {key}: {format_value(value)}" for key, value in case["given"].items()) + "\n\nExpected under each interpretation:\n\n"
        example_text += "\n".join(f"- **{key}:** {format_value(value)}" for key, value in case["expected_by_interpretation"].items()) + "\n"
        if case["evidence"]:
            example_text += "\nExact source records:\n\n"
            for ref in case["evidence"]:
                example_text += f"- {source_link(ref)}: `{json.dumps(ref['row'], ensure_ascii=False)}`\n"
        example_text += f"\nOrganiser question: {case['question'] or 'None currently required'}. Official result: unknown.\n"
    question_text = "# PS1 organiser clarification draft\n\n" + preamble
    question_text += "Prepared for review; not sent. Q06 is resolved by the published README update; the other 11 questions remain open. P0 means resolve before freezing solver/protection/scoring behaviour; P1 means resolve before claiming full coverage of the affected feature. Both remain important.\n\nPlease answer open questions with concrete expected outcomes or location lists and identify the validator/brief version. The examples are in the accompanying example pack.\n"
    for q in register["questions"]:
        resolution = f"{q['response']} Source: {q.get('resolved_by', '')}" if q["response"] else "pending"
        question_text += f"\n## {q['id']} ({q['priority']})\n\n{q['question']}\n\n{q['requested_response']}\n\nExamples: " + ", ".join(f"[{e}](examples.md#{e.lower()})" for e in q["examples"]) + f".\n\nResponse / organiser version: {resolution}.\n"
    return {"rule_register.md": rule_text, "examples.md": example_text, "organiser_questions.md": question_text}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render", action="store_true", help="Refresh derived Markdown views after checking the specification")
    args = parser.parse_args()
    try:
        register, examples, profile = load_pack()
        issues, records = check_pack(register, examples, profile)
        arithmetic = check_selected_evidence(examples)
        issues += [name for name, passed in arithmetic.items() if not passed]
        documents = render(register, examples, profile)
        if args.render and not issues:
            REPORTS.mkdir(parents=True, exist_ok=True)
            for name, content in documents.items():
                (REPORTS / name).write_text(content, encoding="utf-8")
        for name, content in documents.items():
            if not (REPORTS / name).exists() or (REPORTS / name).read_text(encoding="utf-8") != content:
                issues.append(f"Missing or stale derived document: {name}")
        result = {"scope": "Specification consistency, source evidence and selected arithmetic only; not official feasibility",
                  "version": profile["version"], "passed": not issues, "rule_count": len(register["rules"]),
                  "rule_status_counts": dict(Counter(r["status"] for r in register["rules"])),
                  "example_count": len(examples["cases"]), "question_count": len(register["questions"]),
                  "exact_source_records_checked": records, "selected_checks": arithmetic,
                  "spec_sha256": {name: digest(PACK / name) for name in ("rules.json", "examples.json", "profile.json")},
                  "issues": issues}
        REPORTS.mkdir(parents=True, exist_ok=True)
        (REPORTS / "verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
        return 0 if result["passed"] else 1
    except (OSError, ValueError, KeyError, TypeError, csv.Error) as error:
        print(json.dumps({"passed": False, "error": str(error)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
