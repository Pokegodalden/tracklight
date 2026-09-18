"""Independent small schedule cases and frozen sample reconciliation."""
from copy import deepcopy
from datetime import date, timedelta
from itertools import combinations, product
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ps1.importer import import_directory
from ps1.validator import check_schedule, validate_schedule
from ps1.night_diagnostic import color_graph

BASE = ROOT / "data/baselines/ps1-0dfd901f97bf579f/PS1"


class ValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_model = import_directory(BASE / "01_data")["model"]

    def fixture(self, n=1):
        model = deepcopy(self.base_model)
        original_activity, original_project = model["activities"][0], model["project_types"][0]
        model["activities"], model["project_types"] = [], []
        rows = {name: [] for name in ("SCHEDULE_ACCESS.csv", "SCHEDULE_OCCUPANCY.csv", "RESULTS.csv")}
        for loc in model["locations"]:
            loc["supply_capacity"] = 20
        for i in range(n):
            id, contract = f"job-{i}", f"contract-{i}"
            a = dict(original_activity, activity_id=id, contract_number=contract, project_key=[contract, "Construction"],
                     activity_type="Construction", nature_of_works="Non-live (Others)", access_type="C",
                     start_location_id="SEC:ALP:S01_S02:EB", end_location_id="SEC:ALP:S01_S02:EB",
                     planned_start_date="2027-01-04", predecessor_activity_id=None, workload_units_scaled=2, activity_priority=3)
            p = dict(original_project, contract_number=contract, activity_type="Construction", nature_of_activity="Non-live (Others)",
                     access_type="C", number_of_workfronts=1, number_of_maximum_access_per_week=3,
                     contract_priority=3, planned_completion_date="2027-01-10")
            model["activities"].append(a)
            model["project_types"].append(p)
            rows["SCHEDULE_ACCESS.csv"].append(dict(activity_id=id, access_seq=1, week=1, eclo=0, access_night=1))
            for location in ("PLAT:ALP:S01:EB", "SEC:ALP:S01_S02:EB", "PLAT:ALP:S02:EB"):
                rows["SCHEDULE_OCCUPANCY.csv"].append(dict(activity_id=id, week=1, location_id=location, co_share_group=f"group-{i}"))
            rows["RESULTS.csv"].append(dict(scenario="A", contract_number=contract, simulated_completion_date="2027-01-10", overrun_days=0))
        return model, rows

    def run_case(self, model, tables, scenario="A", **kwargs):
        for r in tables["RESULTS.csv"]:
            r["scenario"] = scenario
        return check_schedule(model, tables, scenario, **kwargs)

    def codes(self, result):
        return {f["code"] for f in result["findings"] if f["severity"] == "violation"}

    def move(self, rows, id, week):
        for name in ("SCHEDULE_ACCESS.csv", "SCHEDULE_OCCUPANCY.csv"):
            for r in rows[name]:
                if r["activity_id"] == id:
                    r["week"] = week
        for r in rows["RESULTS.csv"]:
            if r["contract_number"] == id.replace("job", "contract"):
                r["simulated_completion_date"] = (date(2027, 1, 4)+timedelta(days=7*week-1)).isoformat()
                r["overrun_days"] = (week-1)*7

    def test_clean_small_case_stays_unverified_not_feasible(self):
        result = self.run_case(*self.fixture())
        self.assertEqual(self.codes(result), set())
        self.assertEqual(result["status"], "UNVERIFIED")
        self.assertFalse(result["full_feasibility_established"])
        self.assertEqual(result["physical_night_diagnostic"]["status"], "ASSIGNED_FOR_MODELLED_RELATIONS")

    def test_sample_reconciles_and_reproduces_conditional_witnesses(self):
        result = validate_schedule(BASE / "01_data", BASE / "03_submission_sample", "A")["report"]
        self.assertEqual(self.codes(result), set())
        self.assertEqual(result["metrics"]["score_decimal"], "48.3")
        self.assertEqual(result["metrics"]["activity_delay_days"], 42)
        self.assertEqual(result["metrics"]["contract_delay_days"], 28)
        weeks = {w["week"]: w for w in result["physical_night_diagnostic"]["weeks"]}
        self.assertTrue(any(set(c["activities"]) == {"A001", "A011"} for c in weeks[23]["conflicts"]))
        self.assertTrue(any(c["kind"] == "simultaneous_workfront_excess" and c["contract"] == "C007" for c in weeks[25]["conflicts"]))

    def test_workload_and_missing_activity_cannot_disappear(self):
        model, rows = self.fixture()
        rows["SCHEDULE_ACCESS.csv"].clear()
        rows["SCHEDULE_OCCUPANCY.csv"].clear()
        r = self.run_case(model, rows)
        self.assertIn("incomplete_workload", self.codes(r))
        self.assertIsNone(r["metrics"]["score_decimal"])
        self.assertIsNone(r["metrics"]["contracts"][0]["completion_date"])

    def test_two_eclo_accesses_supply_three_work_units(self):
        model, rows = self.fixture()
        model["activities"][0]["workload_units_scaled"] = 6
        model["project_types"][0]["planned_completion_date"] = "2027-01-17"
        rows["SCHEDULE_ACCESS.csv"][0]["eclo"] = 1
        rows["SCHEDULE_ACCESS.csv"].append(dict(rows["SCHEDULE_ACCESS.csv"][0], week=2, access_seq=2))
        rows["SCHEDULE_OCCUPANCY.csv"].extend([dict(r, week=2) for r in rows["SCHEDULE_OCCUPANCY.csv"]])
        rows["RESULTS.csv"][0].update(simulated_completion_date="2027-01-17")
        r = self.run_case(model, rows, "B")
        self.assertEqual(self.codes(r), set())
        self.assertEqual(r["metrics"]["score_decimal"], "10.0")
        rows["SCHEDULE_ACCESS.csv"][1]["eclo"] = 0
        self.assertIn("incomplete_workload", self.codes(self.run_case(model, rows, "B")))

    def test_duplicate_week_sequence_and_outside_horizon(self):
        model, rows = self.fixture()
        rows["SCHEDULE_ACCESS.csv"].append(dict(rows["SCHEDULE_ACCESS.csv"][0]))
        r = self.run_case(model, rows)
        self.assertTrue({"duplicate_activity_week", "duplicate_access_sequence"} <= self.codes(r))
        self.assertIsNone(r["metrics"])
        rows["SCHEDULE_ACCESS.csv"].pop()
        rows["SCHEDULE_ACCESS.csv"][0]["week"] = 31
        self.assertIn("outside_horizon", self.codes(self.run_case(model, rows)))

    def test_release_and_contract_index(self):
        model, rows = self.fixture()
        model["activities"][0]["planned_start_date"] = "2027-01-13"
        rows["SCHEDULE_ACCESS.csv"][0]["access_night"] = 4
        self.assertTrue({"before_release", "allocation_index"} <= self.codes(self.run_case(model, rows)))

    def test_omitted_duplicate_extra_occupancy_cannot_hide_conflicts(self):
        for change, code in ((lambda r: r.pop(), "missing_occupancy"),
                             (lambda r: r.append(dict(r[0])), "duplicate_occupancy"),
                             (lambda r: r.append(dict(r[0], location_id="UNKNOWN")), "unexpected_occupancy")):
            with self.subTest(code=code):
                model, rows = self.fixture()
                change(rows["SCHEDULE_OCCUPANCY.csv"])
                result = self.run_case(model, rows)
                self.assertIn(code, self.codes(result))
                self.assertIsNone(result["metrics"]["excess_location_week_units"])
                self.assertEqual(result["physical_night_diagnostic"]["status"], "NOT_EVALUATED")

    def test_cached_work_span_is_not_trusted(self):
        model, rows = self.fixture()
        model["activities"][0]["working_span"] = {"location_ids": ["FAKE"]}
        self.assertEqual(self.codes(self.run_case(model, rows)), set())

    def test_sharing_compositions_and_mixed_eclo(self):
        for types, legal in ((["PM"], True), (["PM", "C"], False), (["PC", "PC"], False),
                             (["PC", "C", "C", "C"], True), (["C"]*5, False)):
            with self.subTest(types=types):
                model, rows = self.fixture(len(types))
                for a, kind in zip(model["activities"], types):
                    a["access_type"] = kind
                for r in rows["SCHEDULE_OCCUPANCY.csv"]:
                    r["co_share_group"] = "shared"
                self.assertEqual("illegal_sharing" not in self.codes(self.run_case(model, rows)), legal)
        model, rows = self.fixture(2)
        for r in rows["SCHEDULE_OCCUPANCY.csv"]:
            r["co_share_group"] = "shared"
        rows["SCHEDULE_ACCESS.csv"][0]["eclo"] = 1
        self.assertIn("mixed_eclo_group", self.codes(self.run_case(model, rows, "B")))

    def test_scenario_capacity_excess_and_penalty_units(self):
        model, rows = self.fixture(3)
        for loc in model["locations"]:
            loc["supply_capacity"] = 1
        self.assertIn("capacity_limit", self.codes(self.run_case(model, rows, "A")))
        self.assertIn("capacity_limit", self.codes(self.run_case(model, rows, "C")))
        b = self.run_case(model, rows, "B")
        self.assertEqual(self.codes(b), set())
        self.assertEqual(b["metrics"]["excess_location_week_units"], 6)
        self.assertEqual(b["metrics"]["score_decimal"], "42.0")
        model, rows = self.fixture(2)
        for loc in model["locations"]:
            loc["supply_capacity"] = 1
        c = self.run_case(model, rows, "C")
        self.assertNotIn("capacity_limit", self.codes(c))
        self.assertEqual(c["metrics"]["score_decimal"], "21.0")

    def test_scenario_a_forbids_eclo_and_b_forbids_lateness(self):
        model, rows = self.fixture()
        rows["SCHEDULE_ACCESS.csv"][0]["eclo"] = 1
        self.assertIn("eclo_forbidden", self.codes(self.run_case(model, rows)))
        self.move(rows, "job-0", 2)
        self.assertIn("planned_date", self.codes(self.run_case(model, rows, "B")))

    def test_predecessor_requires_complete_earlier_week(self):
        model, rows = self.fixture(2)
        model["activities"][1]["predecessor_activity_id"] = "job-0"
        self.assertIn("predecessor_order", self.codes(self.run_case(model, rows)))
        self.move(rows, "job-1", 2)
        self.assertNotIn("predecessor_order", self.codes(self.run_case(model, rows)))
        model["activities"][0]["workload_units_scaled"] = 4
        self.assertIn("predecessor_incomplete", self.codes(self.run_case(model, rows)))

    def test_predecessor_uses_last_scheduled_access_not_first_full_yield(self):
        model, rows = self.fixture(2)
        self.assertNotEqual(model['activities'][0]['contract_number'], model['activities'][1]['contract_number'])
        model['activities'][1]['predecessor_activity_id'] = 'job-0'
        self.move(rows, 'job-1', 2)
        # P already has its full workload in week 1, but retains an extra access in week 3.
        rows['SCHEDULE_ACCESS.csv'].append(dict(activity_id='job-0', access_seq=2, week=3, eclo=0, access_night=1))
        rows['SCHEDULE_OCCUPANCY.csv'].extend(dict(r, week=3) for r in list(rows['SCHEDULE_OCCUPANCY.csv']) if r['activity_id']=='job-0')
        self.assertIn('predecessor_order', self.codes(self.run_case(model, rows)))
        self.move(rows, 'job-1', 3)
        self.assertIn('predecessor_order', self.codes(self.run_case(model, rows)))
        self.move(rows, 'job-1', 4)
        self.assertNotIn('predecessor_order', self.codes(self.run_case(model, rows)))

    def test_results_are_recomputed_and_scenario_is_explicit(self):
        model, rows = self.fixture()
        rows["RESULTS.csv"][0]["overrun_days"] = 10
        self.assertIn("result_mismatch", self.codes(self.run_case(model, rows)))
        rows["RESULTS.csv"].clear()
        self.assertIn("missing_result", self.codes(self.run_case(model, rows)))
        model, rows = self.fixture()
        self.assertIn("result_identity", self.codes(check_schedule(model, rows, "B")))

    def test_c_window_separate_lines_and_unresolved_live_propagation(self):
        model, rows = self.fixture(2)
        for r in rows["SCHEDULE_ACCESS.csv"]:
            r["eclo"] = 1
        self.move(rows, "job-0", 10)
        self.move(rows, "job-1", 11)
        self.assertNotIn("eclo_window", self.codes(self.run_case(model, rows, "C")))
        self.move(rows, "job-1", 12)
        self.assertIn("eclo_window", self.codes(self.run_case(model, rows, "C")))
        a = model["activities"][1]
        a.update(start_location_id="SEC:BET:S11_S12:EB", end_location_id="SEC:BET:S11_S12:EB")
        for r in rows["SCHEDULE_OCCUPANCY.csv"]:
            if r["activity_id"] == "job-1":
                r["location_id"] = r["location_id"].replace("ALP", "BET").replace("S01", "S11").replace("S02", "S12")
        self.assertNotIn("eclo_window", self.codes(self.run_case(model, rows, "C")))
        a["nature_of_works"] = "Live"
        report = self.run_case(model, rows, "C")
        self.assertEqual(report["rule_checks"]["R25"], "UNVERIFIED")
        self.assertEqual(report["rule_checks"]["R32"], "UNVERIFIED")

    def test_renaming_local_groups_preserves_accounting(self):
        model, rows = self.fixture(2)
        before = self.run_case(model, rows)
        for r in rows["SCHEDULE_OCCUPANCY.csv"]:
            r["co_share_group"] = r["location_id"] + "/" + r["co_share_group"]
        after = self.run_case(model, rows)
        self.assertEqual(before["metrics"], after["metrics"])
        self.assertEqual(before["physical_night_diagnostic"]["status"], after["physical_night_diagnostic"]["status"])

    def test_combined_c_score_is_exact_and_ineligible_for_official_claims(self):
        model, rows = self.fixture()
        model["activities"][0]["activity_priority"] = 1
        for loc in model["locations"]:
            loc["supply_capacity"] = 0
        rows["SCHEDULE_ACCESS.csv"][0]["eclo"] = 1
        self.move(rows, "job-0", 2)
        result = self.run_case(model, rows, "C")
        self.assertEqual(self.codes(result), set())
        # 7 days * 1 * 1.3 + 3 location-week excess units * 7 + 1 ECLO * 5.
        self.assertEqual(result["metrics"]["score_tenths"], 351)
        self.assertEqual(result["metrics"]["score_decimal"], "35.1")
        self.assertFalse(result["metrics"]["score_eligible"])

    def test_local_and_physical_workfront_checks_are_separate(self):
        model, rows = self.fixture(2)
        model["activities"][1].update(contract_number="contract-0", project_key=["contract-0", "Construction"])
        model["project_types"].pop()
        rows["RESULTS.csv"].pop()
        same_index = self.run_case(model, rows)
        self.assertIn("workfront_limit", self.codes(same_index))
        rows["SCHEDULE_ACCESS.csv"][1]["access_night"] = 2
        for r in rows["SCHEDULE_OCCUPANCY.csv"]:
            r["co_share_group"] = "shared"
        different_indices = self.run_case(model, rows)
        self.assertEqual(self.codes(different_indices), set())
        conflicts = different_indices["physical_night_diagnostic"]["weeks"][0]["conflicts"]
        self.assertTrue(any(c["kind"] == "simultaneous_workfront_excess" for c in conflicts))

    def test_known_live_mirror_core_forces_different_abstract_nights(self):
        model, rows = self.fixture(2)
        model["activities"][0]["nature_of_works"] = "Live"
        a = model["activities"][1]
        a.update(start_location_id="SEC:ALP:S01_S02:WB", end_location_id="SEC:ALP:S01_S02:WB")
        for r in rows["SCHEDULE_OCCUPANCY.csv"]:
            if r["activity_id"] == "job-1":
                r["location_id"] = r["location_id"].replace(":EB", ":WB")
        diag = self.run_case(model, rows)["physical_night_diagnostic"]
        week = diag["weeks"][0]
        self.assertEqual(week["known_live_mirror_relations"], 3)
        self.assertNotEqual(week["assignment"]["job-0"], week["assignment"]["job-1"])
        self.assertFalse(diag["physical_feasibility_established"])

    def test_malformed_csv_and_cli_unverified_exit_code(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "schedule"
            shutil.copytree(BASE / "03_submission_sample", folder)
            process = subprocess.run([sys.executable, "-m", "ps1.validator", str(BASE / "01_data"), str(folder), "--scenario", "A"], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(process.returncode, 2)
            (folder / "SCHEDULE_ACCESS.csv").write_text("wrong,header\n", encoding="utf-8")
            report = validate_schedule(BASE / "01_data", folder, "A")["report"]
            self.assertEqual(report["status"], "INVALID_INPUT_OR_SCHEDULE")
            self.assertIsNone(report["metrics"])

    def test_input_failure_is_visible_in_primary_findings(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "inputs"
            shutil.copytree(BASE / "01_data", folder)
            (folder / "01_LINES.csv").unlink()
            result = validate_schedule(folder, BASE / "03_submission_sample", "A")["report"]
            self.assertTrue(result["findings"])
            self.assertTrue(any(f.get("stage") == "input" and f["source"]["file"] == "01_LINES.csv" for f in result["findings"]))

    def test_invalid_diagnostic_options_rejected_even_when_inputs_are_bad(self):
        with tempfile.TemporaryDirectory() as directory:
            for settings in ({"night_limit": 0}, {"night_limit": True}, {"search_budget": -1}):
                with self.subTest(settings=settings), self.assertRaises(ValueError):
                    validate_schedule(directory, BASE / "03_submission_sample", "A", **settings)

    def test_empty_accesses_do_not_claim_nights_were_assigned(self):
        model, rows = self.fixture()
        rows["SCHEDULE_ACCESS.csv"].clear()
        rows["SCHEDULE_OCCUPANCY.csv"].clear()
        result = self.run_case(model, rows)
        self.assertEqual(result["physical_night_diagnostic"]["status"], "NO_ACCESSES")

    def test_partial_diagnostic_discloses_unscheduled_work(self):
        model, rows = self.fixture(2)
        rows["SCHEDULE_ACCESS.csv"] = rows["SCHEDULE_ACCESS.csv"][:1]
        rows["SCHEDULE_OCCUPANCY.csv"] = rows["SCHEDULE_OCCUPANCY.csv"][:3]
        result = self.run_case(model, rows)
        coverage = result["physical_night_diagnostic"]["coverage"]
        self.assertEqual(coverage["required_activities"], 2)
        self.assertEqual(coverage["scheduled_activities"], 1)
        self.assertFalse(coverage["all_work_complete"])

    def test_night_assignment_range_is_verified(self):
        model, rows = self.fixture()
        for assignment in ({"job-0": 0}, {"job-0": 8}, {"job-0": True}, {}, None, {"job-0": 1, "extra": 1}):
            with self.subTest(assignment=assignment), patch("ps1.night_diagnostic.color_graph", return_value=("ASSIGNED", assignment, 0)):
                result = self.run_case(model, rows)
            self.assertEqual(result["status"], "VALIDATION_ERROR")
            diagnostic = result["physical_night_diagnostic"]
            self.assertEqual(diagnostic["status"], "INTERNAL_ERROR")
            self.assertIsNone(diagnostic["weeks"][0]["assignment"])

    def test_assignment_verification_survives_python_optimisation(self):
        code = """
import sys
sys.path.insert(0, 'tests')
from test_validator import ValidatorTests
from unittest.mock import patch
ValidatorTests.setUpClass()
case = ValidatorTests()
model, rows = case.fixture(2)
with patch('ps1.night_diagnostic.color_graph', return_value=('ASSIGNED', {'job-0': 1, 'job-1': 1}, 0)):
    result = case.run_case(model, rows)
print(result['status'])
"""
        result = subprocess.run([sys.executable, "-O", "-c", code], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "VALIDATION_ERROR")

    def test_night_limit_failure_contains_replayable_constraints(self):
        result = self.run_case(*self.fixture(8))
        week = result["physical_night_diagnostic"]["weeks"][0]
        self.assertEqual(week["status"], "INCONSISTENT_UNDER_ASSUMPTIONS")
        witness = next(c for c in week["conflicts"] if c["kind"] == "night_limit_exceeded")
        self.assertEqual(witness["night_limit"], 7)
        self.assertEqual(len(witness["components"]), 8)
        self.assertEqual(len(witness["separation_edges"]), 28)

    def test_capacity_findings_identify_affected_activities(self):
        model, rows = self.fixture(2)
        for loc in model["locations"]:
            loc["supply_capacity"] = 1
        result = self.run_case(model, rows)
        problems = [f for f in result["findings"] if f["code"] == "capacity_limit"]
        self.assertTrue(problems)
        self.assertTrue(all(f["activities"] == ["job-0", "job-1"] for f in problems))


class NightColoringTests(unittest.TestCase):
    def test_seven_night_bound_and_search_limit_are_distinct(self):
        graph = {str(i): {str(j) for j in range(8) if i != j} for i in range(8)}
        self.assertEqual(color_graph(graph, 7, 50000)[0], "INCONSISTENT_UNDER_ASSUMPTIONS")
        self.assertEqual(color_graph(graph, 7, 0)[0], "UNKNOWN_SEARCH_LIMIT")

    def test_two_color_results_match_exhaustive_oracle_on_all_four_node_graphs(self):
        edges = list(combinations(range(4), 2))
        for mask in range(1 << len(edges)):
            selected = [edge for i, edge in enumerate(edges) if mask & (1 << i)]
            graph = {i: set() for i in range(4)}
            for a, b in selected:
                graph[a].add(b)
                graph[b].add(a)
            possible = any(all(colors[a] != colors[b] for a, b in selected) for colors in product(range(2), repeat=4))
            status, assignment, _ = color_graph(graph, 2, 1000)
            self.assertEqual(status == "ASSIGNED", possible, selected)
            if assignment:
                self.assertTrue(all(assignment[a] != assignment[b] for a, b in selected))


if __name__ == "__main__":
    unittest.main()
