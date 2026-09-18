"""Real input, topology and failure-boundary tests on disposable copies."""
import csv
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
from ps1.importer import PROFILE_DIR, Importer, import_directory, parse_value, scaled_workload, write_result

BASELINE = ROOT / "data/baselines/ps1-0dfd901f97bf579f"
INPUTS = BASELINE / "PS1/01_data"


class ImporterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "inputs"
        shutil.copytree(INPUTS, self.directory)

    def edit(self, name, change):
        path = self.directory / name
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            header, rows = reader.fieldnames, list(reader)
        change(rows)
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=header)
            writer.writeheader()
            writer.writerows(rows)

    def invalid(self, code):
        result = import_directory(self.directory)
        self.assertFalse(result["report"]["input_valid"], result["report"])
        self.assertIsNone(result["model"])
        self.assertIsNone(result["network"])
        self.assertIn(code, {i["code"] for i in result["report"]["issues"]})
        return result

    def test_baseline_counts_identity_and_unknown_protection(self):
        result = import_directory(self.directory)
        self.assertTrue(result["report"]["input_valid"])
        self.assertEqual(result["report"]["counts"], dict(lines=2, station_line_memberships=20,
            distinct_stations=18, sectors=18, bookable_locations=76, contracts=14,
            project_type_rows=14, activities=54, workload_units_scaled=384,
            dependency_edges=6, network_incidence_links=72))
        self.assertEqual(result["provenance"]["input_data_sha256"],
                         "2c66b645033c6949c8262e974333663abef18ade8a7f151e0210d290f0baf64e")
        for activity in result["model"]["activities"]:
            self.assertIsNone(activity["protection"]["location_ids"])
            self.assertEqual(activity["protection"]["status"], "UNVERIFIED")
            self.assertIsNone(activity["supply_demand"]["consumption"])

    def test_all_sample_occupancy_spans_reconcile(self):
        result = import_directory(self.directory)
        expected = {a["activity_id"]: set(a["working_span"]["location_ids"]) for a in result["model"]["activities"]}
        observed = {}
        with (BASELINE / "PS1/03_submission_sample/SCHEDULE_OCCUPANCY.csv").open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                observed.setdefault((row["activity_id"], row["week"]), []).append(row["location_id"])
        self.assertEqual(len(observed), 192)
        self.assertEqual(sum(map(len, observed.values())), 928)
        for (activity, week), locations in observed.items():
            self.assertEqual(set(locations), expected[activity], (activity, week))
            self.assertEqual(len(locations), len(set(locations)))

    def test_interchange_and_bound_capacity_stay_separate(self):
        result = import_directory(self.directory)
        nodes = {n["location_id"]: n for n in result["network"]["nodes"]}
        ids = [f"PLAT:{line}:H01:{bound}" for line in ("ALP", "BET") for bound in ("EB", "WB")]
        self.assertEqual(len({nodes[id]["capacity_resource_id"] for id in ids}), 4)
        self.assertEqual(result["network"]["cross_line_travel_edges"], [])
        for link in result["network"]["incidence_links"]:
            tunnel, platform = nodes[link["tunnel_location_id"]], nodes[link["platform_location_id"]]
            self.assertEqual((tunnel["line_code"], tunnel["bound"]), (platform["line_code"], platform["bound"]))

    def test_duplicate_key_reports_source_line(self):
        self.edit("08_ACTIVITY_DETAILS.csv", lambda rows: rows.append(dict(rows[0])))
        result = self.invalid("duplicate_key")
        issue = next(i for i in result["report"]["issues"] if i["code"] == "duplicate_key")
        self.assertEqual((issue["file"], issue["line"]), ("08_ACTIVITY_DETAILS.csv", 56))

    def test_unknown_project_type_and_predecessor(self):
        self.edit("08_ACTIVITY_DETAILS.csv", lambda rows: rows[0].update(activity_type="Unknown", predecessor_activity_id="Missing"))
        result = self.invalid("unknown_project_type")
        self.assertIn("unknown_predecessor", {i["code"] for i in result["report"]["issues"]})

    def test_cycle_has_a_concrete_witness(self):
        self.edit("08_ACTIVITY_DETAILS.csv", lambda rows: (rows[0].update(predecessor_activity_id=rows[1]["activity_id"]), rows[1].update(predecessor_activity_id=rows[0]["activity_id"])))
        result = self.invalid("dependency_cycle")
        issue = next(i for i in result["report"]["issues"] if i["code"] == "dependency_cycle")
        self.assertIn("A001 -> A002 -> A001", issue["message"])

    def test_published_rule_accepts_cross_contract_predecessor(self):
        def link(rows):
            predecessor = rows[0]
            successor = next(r for r in rows if r['contract_number'] != predecessor['contract_number'] and not r['predecessor_activity_id'])
            successor['predecessor_activity_id'] = predecessor['activity_id']
            self.expected_edge = (predecessor['activity_id'], successor['activity_id'])
        self.edit('08_ACTIVITY_DETAILS.csv', link)
        result = import_directory(self.directory)
        self.assertTrue(result['report']['input_valid'], result['report'])
        dependencies = result['model']['dependencies']
        self.assertIn(self.expected_edge, [(e['predecessor'], e['successor']) for e in dependencies['edges']])
        self.assertEqual(dependencies['rule_status'], 'documented')
        self.assertEqual(result['provenance']['profile_id'], 'ps1-provisional-0.2.0')
        self.assertEqual(result['provenance']['source_updates'][0]['commit'], '966c976005db2e3e40a691cff268fdb8f396a5df')

    def test_self_dependency_is_a_cycle(self):
        self.edit("08_ACTIVITY_DETAILS.csv", lambda rows: rows[0].update(predecessor_activity_id=rows[0]["activity_id"]))
        self.invalid("dependency_cycle")

    def test_zero_supply_is_preserved_missing_supply_fails(self):
        self.edit("04_LOCATION_SUPPLY.csv", lambda rows: rows[0].update(supply_capacity="0"))
        result = import_directory(self.directory)
        self.assertTrue(result["report"]["input_valid"])
        self.assertEqual(result["model"]["locations"][0]["supply_capacity"], 0)
        self.edit("04_LOCATION_SUPPLY.csv", lambda rows: rows.pop(0))
        self.invalid("missing_supply")

    def test_numeric_date_category_and_whitespace_errors(self):
        for column, value in (("total_accesses", "NaN"), ("total_accesses", "0.25"),
                              ("total_accesses", "-2"), ("activity_priority", "4"),
                              ("planned_start_date", "2027-02-30"), ("activity_id", " A001")):
            with self.subTest(column=column, value=value):
                shutil.copy2(INPUTS / "08_ACTIVITY_DETAILS.csv", self.directory)
                self.edit("08_ACTIVITY_DETAILS.csv", lambda rows: rows[0].update({column: value}))
                self.invalid("invalid_value")

    def test_workload_uses_exact_half_units_without_rounding(self):
        self.edit("08_ACTIVITY_DETAILS.csv", lambda rows: rows[0].update(total_accesses="2.50"))
        result = import_directory(self.directory)
        self.assertEqual(result["model"]["activities"][0]["workload_units_scaled"], 5)
        number = "123456789012345678901234567890.5"
        self.assertEqual(scaled_workload(parse_value(number, "workload")), 246913578024691357802469135781)

    def test_malformed_encoding_header_and_width(self):
        path = self.directory / "01_LINES.csv"
        for content in (b"\xff", b"line_code,line_code\nALP,Alpha\n", b"line_code,line_name\nALP,Alpha,extra\n", b'line_code,line_name\nALP,"unclosed'):
            with self.subTest(content=content):
                path.write_bytes(content)
                result = import_directory(self.directory)
                self.assertFalse(result["report"]["input_valid"])
                self.assertIsNone(result["model"])

    def test_empty_and_missing_file_fail(self):
        path = self.directory / "01_LINES.csv"
        path.write_text("line_code,line_name\n", encoding="utf-8")
        self.invalid("empty_table")
        path.unlink()
        self.invalid("read_input")

    def test_gapped_shuffled_sector_sequence_does_not_create_links(self):
        before = import_directory(self.directory)
        def change(rows):
            for i, row in enumerate(rows):
                row["seq"] = str(1000-i*7)
            rows.reverse()
        self.edit("03_SECTORS.csv", change)
        after = import_directory(self.directory)
        self.assertTrue(after["report"]["input_valid"], after["report"])
        self.assertEqual(before["network"]["line_sector_order"], after["network"]["line_sector_order"])
        self.assertEqual([a["working_span"] for a in before["model"]["activities"]], [a["working_span"] for a in after["model"]["activities"]])

    def test_cross_line_platform_and_reversed_spans_fail_explicitly(self):
        for updates in ({"end_location_id": "SEC:ALP:S01_S02:EB"},
                        {"end_location_id": "SEC:BET:S16_S17:WB"},
                        {"start_location_id": "PLAT:BET:S15:EB"},
                        {"start_location_id": "SEC:BET:S16_S17:EB", "end_location_id": "SEC:BET:S15_S16:EB"}):
            with self.subTest(updates=updates):
                shutil.copy2(INPUTS / "08_ACTIVITY_DETAILS.csv", self.directory)
                self.edit("08_ACTIVITY_DETAILS.csv", lambda rows: rows[0].update(updates))
                self.invalid("unsupported_span")

    def test_disconnect_is_not_bridged_by_sequence(self):
        removed = "SEC:ALP:S03_S04"
        self.edit("03_SECTORS.csv", lambda rows: rows.__setitem__(slice(None), [r for r in rows if r["sector_id"] != removed]))
        self.edit("04_LOCATION_SUPPLY.csv", lambda rows: rows.__setitem__(slice(None), [r for r in rows if not r["location_id"].startswith(removed+":")]))
        self.edit("08_ACTIVITY_DETAILS.csv", lambda rows: [r.update({k: "SEC:ALP:S01_S02:"+r[k].rsplit(":", 1)[1] for k in ("start_location_id", "end_location_id") if r[k].startswith(removed+":")}) for r in rows])
        self.invalid("unsupported_topology")

    def test_shared_capacity_and_wrong_bound_metadata_rejected(self):
        self.edit("03_SECTORS.csv", lambda rows: rows[0].update(is_shared="1"))
        self.edit("04_LOCATION_SUPPLY.csv", lambda rows: rows[0].update(bound="WB"))
        result = self.invalid("unsupported_shared_track")
        self.assertIn("location_metadata", {i["code"] for i in result["report"]["issues"]})

    def test_dates_outside_horizon_are_preserved_as_warnings(self):
        self.edit("08_ACTIVITY_DETAILS.csv", lambda rows: (rows[0].update(planned_start_date="2028-01-01"), rows[1].update(planned_start_date="2027-01-01")))
        result = import_directory(self.directory)
        self.assertTrue(result["report"]["input_valid"])
        self.assertIn("release_after_horizon", {i["code"] for i in result["report"]["issues"]})
        self.assertEqual(result["model"]["activities"][1]["planned_start_week"], 0)
        self.assertEqual(result["model"]["activities"][1]["earliest_in_horizon_week"], 1)

    def test_midweek_release_and_horizon_end(self):
        self.edit("08_ACTIVITY_DETAILS.csv", lambda rows: rows[0].update(planned_start_date="2027-01-13"))
        result = import_directory(self.directory)
        self.assertEqual(result["model"]["activities"][0]["planned_start_week"], 2)
        self.assertEqual(result["model"]["calendar"]["inclusive_end"], "2027-08-01")

    def test_unknown_and_overflowing_horizon_fail(self):
        self.edit("06_PARAMETERS.csv", lambda rows: rows[1].update(value="10000000000000000"))
        self.invalid("horizon_range")

    def test_new_identifiers_counts_and_project_type_pairs(self):
        for path in self.directory.glob("*.csv"):
            path.write_bytes(path.read_bytes().replace(b"ALP", b"RIVER").replace(b"BET", b"FOREST").replace(b"A001", b"Job-901").replace(b"C001", b"Contract-X"))
        self.edit("07_PROJECT_DETAILS.csv", lambda rows: rows.append(dict(rows[0], activity_type="Inspection")))
        self.edit("08_ACTIVITY_DETAILS.csv", lambda rows: rows.append(dict(rows[0], activity_id="New-Job", activity_type="Inspection")))
        result = import_directory(self.directory)
        self.assertTrue(result["report"]["input_valid"], result["report"])
        self.assertEqual(result["report"]["counts"]["activities"], 55)
        self.assertEqual(result["report"]["counts"]["project_type_rows"], 15)
        self.assertFalse(result["provenance"]["matches_profile_source_input"])

    def test_conflicting_contract_dates_fail(self):
        self.edit("07_PROJECT_DETAILS.csv", lambda rows: rows.append(dict(rows[0], activity_type="Inspection", planned_completion_date="2027-06-20")))
        self.invalid("ambiguous_contract")

    def test_branch_is_rejected_instead_of_choosing_a_route(self):
        self.edit("03_SECTORS.csv", lambda rows: rows.append(dict(rows[0],
            sector_id="SEC:ALP:S02_S04", from_station_id="S02", to_station_id="S04", seq="999")))
        self.edit("04_LOCATION_SUPPLY.csv", lambda rows: rows.extend([
            dict(rows[0], location_id="SEC:ALP:S02_S04:EB"),
            dict(rows[0], location_id="SEC:ALP:S02_S04:WB", bound="WB")]))
        self.invalid("unsupported_branch")

    def test_smaller_one_line_instance_and_reordered_headers(self):
        self.edit("01_LINES.csv", lambda rows: rows.__setitem__(slice(None), rows[:1]))
        self.edit("02_STATIONS.csv", lambda rows: rows.__setitem__(slice(None), rows[:2]))
        self.edit("03_SECTORS.csv", lambda rows: rows.__setitem__(slice(None), rows[:1]))
        allowed = {f"{id}:{bound}" for id in ("SEC:ALP:S01_S02", "PLAT:ALP:S01", "PLAT:ALP:S02") for bound in ("EB", "WB")}
        self.edit("04_LOCATION_SUPPLY.csv", lambda rows: rows.__setitem__(slice(None), [r for r in rows if r["location_id"] in allowed]))
        self.edit("07_PROJECT_DETAILS.csv", lambda rows: rows.__setitem__(slice(None), rows[:1]))
        self.edit("08_ACTIVITY_DETAILS.csv", lambda rows: rows.__setitem__(slice(None), [dict(rows[0],
            start_location_id="SEC:ALP:S01_S02:EB", end_location_id="SEC:ALP:S01_S02:EB")]))
        (self.directory / "01_LINES.csv").write_text("line_name,line_code\nLine Alpha,ALP\n", encoding="utf-8")
        result = import_directory(self.directory)
        self.assertTrue(result["report"]["input_valid"], result["report"])
        self.assertEqual(result["report"]["counts"]["lines"], 1)
        self.assertEqual(result["report"]["counts"]["bookable_locations"], 6)
        self.assertEqual(result["report"]["counts"]["activities"], 1)

    def test_changed_profile_is_rejected_before_modelling(self):
        profile_copy = Path(self.temp.name) / "profile"
        shutil.copytree(PROFILE_DIR, profile_copy)
        path = profile_copy / "profile.json"
        content = json.loads(path.read_text(encoding="utf-8"))
        content["rules"]["R18"]["policy"]["relation"] = "ignore_predecessors"
        path.write_text(json.dumps(content), encoding="utf-8")
        with patch("ps1.importer.PROFILE_DIR", profile_copy):
            self.invalid("rule_profile")

    def test_atomic_bundle_replaces_old_model_after_failed_import(self):
        output = Path(self.temp.name) / "result.json"
        write_result(import_directory(self.directory), output, self.directory)
        self.edit("08_ACTIVITY_DETAILS.csv", lambda rows: rows[0].update(predecessor_activity_id="Missing"))
        failed = import_directory(self.directory)
        write_result(failed, output, self.directory)
        self.assertIsNone(json.loads(output.read_text(encoding="utf-8"))["model"])
        self.assertEqual(list(output.parent.glob(".import-*.tmp")), [])
        with self.assertRaises(ValueError):
            write_result(failed, self.directory / "result.json", self.directory)

    def test_cli_bad_input_returns_nonzero_and_actionable_report(self):
        self.edit("08_ACTIVITY_DETAILS.csv", lambda rows: rows[0].update(activity_priority="9"))
        run = subprocess.run([sys.executable, "-m", "ps1.importer", str(self.directory)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(run.returncode, 1)
        self.assertNotIn("Traceback", run.stderr)
        report = json.loads(run.stdout)
        self.assertEqual(report["issues"][0]["field"], "activity_priority")

    def test_reused_importer_does_not_retain_missing_file_or_change_prior_result(self):
        importer = Importer(self.directory)
        first = importer.run()
        (self.directory / "01_LINES.csv").unlink()
        second = importer.run()
        self.assertIsNone(second["provenance"]["input_data_sha256"])
        self.assertNotIn("01_LINES.csv", second["provenance"]["files"])
        self.assertEqual(first["report"]["issues"], [])
        shutil.copy2(INPUTS / "01_LINES.csv", self.directory)
        third = importer.run()
        self.assertTrue(third["report"]["input_valid"])

    def test_csv_parser_error_points_to_bad_record_start(self):
        (self.directory / "01_LINES.csv").write_text('line_code,line_name\nALP,Alpha\nBET,"unclosed\n', encoding="utf-8")
        result = self.invalid("read_input")
        issue = next(i for i in result["report"]["issues"] if i["code"] == "read_input")
        self.assertEqual(issue["line"], 3)

    def test_third_duplicate_still_points_to_first_occurrence(self):
        self.edit("08_ACTIVITY_DETAILS.csv", lambda rows: rows.extend([dict(rows[0]), dict(rows[0])]))
        result = self.invalid("duplicate_key")
        issues = [i for i in result["report"]["issues"] if i["code"] == "duplicate_key"]
        self.assertEqual(len(issues), 2)
        self.assertTrue(all("first occurrence is at line 2." in i["message"] for i in issues))

    def test_directory_permission_failure_returns_structured_result(self):
        with patch.object(Path, "iterdir", side_effect=PermissionError("test permission failure")):
            self.invalid("input_directory")

    def test_generated_location_collision_cannot_merge_two_lines(self):
        # These two different station memberships both spell PLAT:L:X:A:EB.
        lines = [{"line_code": "L", "line_name": "One"}, {"line_code": "L:X", "line_name": "Two"}]
        stations, sectors, supply = [], [], {}
        for line, start, end in (("L", "X:A", "B"), ("L:X", "A", "C")):
            sector = f"SEC:{line}:{start}_{end}"
            for seq, station in enumerate((start, end), 1):
                stations.append(dict(station_id=station, line_code=line, seq=str(seq), is_interchange="0"))
            sectors.append(dict(sector_id=sector, line_code=line, from_station_id=start,
                                to_station_id=end, seq="1", is_shared="0"))
            for bound in ("EB", "WB"):
                for id, kind in ((f"{sector}:{bound}", "tunnel sector"),
                                 (f"PLAT:{line}:{start}:{bound}", "platform sector"),
                                 (f"PLAT:{line}:{end}:{bound}", "platform sector")):
                    supply[id] = dict(location_id=id, location_kind=kind, line_code=line,
                                      bound=bound, supply_capacity="4")
        for name, records in (("01_LINES.csv", lines), ("02_STATIONS.csv", stations),
                              ("03_SECTORS.csv", sectors), ("04_LOCATION_SUPPLY.csv", list(supply.values()))):
            self.edit(name, lambda rows, records=records: rows.__setitem__(slice(None), records))
        self.edit("08_ACTIVITY_DETAILS.csv", lambda rows: [r.update(start_location_id="SEC:L:X:A_B:EB",
                       end_location_id="SEC:L:X:A_B:EB") for r in rows])
        self.invalid("location_identity_collision")

    def test_failed_publication_preserves_previous_bundle_and_cleans_temporary(self):
        output = Path(self.temp.name) / "result.json"
        result = import_directory(self.directory)
        write_result(result, output, self.directory)
        original = output.read_bytes()
        with patch("ps1.importer.os.replace", side_effect=PermissionError("test locked output")):
            with self.assertRaises(PermissionError):
                write_result({"report": {"status": "FAILED"}, "model": None}, output, self.directory)
        self.assertEqual(output.read_bytes(), original)
        self.assertEqual(list(output.parent.glob(".import-*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
