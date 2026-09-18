"""Integrity tests use disposable copies; the frozen source is never edited."""
import importlib.util
import argparse
import contextlib
import io
import json
import shutil
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("baseline", ROOT / "tools/baseline.py")
baseline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(baseline)
SNAPSHOT = ROOT / "data/baselines/ps1-0dfd901f97bf579f"


class BaselineIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.copy = Path(self.temp.name) / "relocated"
        shutil.copytree(SNAPSHOT, self.copy)

    def test_relocated_pristine_snapshot_verifies(self):
        self.assertTrue(baseline.verify_snapshot(self.copy)["passed"])

    def test_same_length_byte_change_is_detected(self):
        target = self.copy / "PS1/01_data/01_LINES.csv"
        data = target.read_bytes()
        self.assertIn(b"ALP", data)
        target.write_bytes(data.replace(b"ALP", b"XYZ", 1))
        result = baseline.verify_snapshot(self.copy)
        self.assertFalse(result["passed"])
        self.assertTrue(any("fingerprint mismatch" in issue for issue in result["issues"]))

    def test_missing_file_is_detected(self):
        (self.copy / "PS1/02_references/network_diagram.svg").unlink()
        result = baseline.verify_snapshot(self.copy)
        self.assertFalse(result["passed"])
        self.assertTrue(any("Missing file" in issue for issue in result["issues"]))

    def test_unlisted_file_is_detected(self):
        (self.copy / "extra.txt").write_text("Unexpected", encoding="utf-8")
        self.assertFalse(baseline.verify_snapshot(self.copy)["passed"])

    def test_manifest_fingerprint_change_is_detected(self):
        path = self.copy / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["pack_sha256"] = "0" * 64
        path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assertFalse(baseline.verify_snapshot(self.copy)["passed"])

    def edit_manifest(self, mutate):
        path = self.copy / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        mutate(manifest)
        path.write_text(json.dumps(manifest), encoding="utf-8")

    def test_unsupported_manifest_version_fails(self):
        self.edit_manifest(lambda m: m.update(manifest_version=999))
        self.assertFalse(baseline.verify_snapshot(self.copy)["passed"])

    def test_non_object_manifest_returns_a_failure_report(self):
        (self.copy / "manifest.json").write_text("[]", encoding="utf-8")
        self.assertFalse(baseline.verify_snapshot(self.copy)["passed"])

    def test_changed_role_cannot_redefine_eight_input_identity(self):
        def mutate(manifest):
            manifest["files"][0]["role"] = "reference"
            manifest["input_data_sha256"] = baseline.identity(
                [e for e in manifest["files"] if e["role"] == "input"])
        self.edit_manifest(mutate)
        self.assertFalse(baseline.verify_snapshot(self.copy)["passed"])

    def test_missing_manifest_returns_a_failure_report(self):
        (self.copy / "manifest.json").unlink()
        self.assertFalse(baseline.verify_snapshot(self.copy)["passed"])

    def test_invalid_utf8_file_returns_a_failure_report(self):
        (self.copy / "PS1/01_data/01_LINES.csv").write_bytes(b"\xff")
        self.assertFalse(baseline.verify_snapshot(self.copy)["passed"])

    def freeze_args(self):
        return argparse.Namespace(source_root=self.copy / "PS1",
                                  root_readme=self.copy / "README.md",
                                  destination=Path(self.temp.name) / "frozen")

    def test_extra_reference_does_not_change_eight_input_identity(self):
        (self.copy / "PS1/01_data/notes.txt").write_text("New note", encoding="utf-8")
        args = self.freeze_args()
        with contextlib.redirect_stdout(io.StringIO()):
            baseline.freeze(args)
        created = next(args.destination.glob("ps1-*/manifest.json"))
        original = json.loads((SNAPSHOT / "manifest.json").read_text(encoding="utf-8"))
        updated = json.loads(created.read_text(encoding="utf-8"))
        self.assertEqual(original["input_data_sha256"], updated["input_data_sha256"])
        self.assertNotEqual(original["pack_sha256"], updated["pack_sha256"])
        self.assertIsNone(updated["baseline"]["horizon"]["dated_operational_access_calendar_supplied"])

    def test_interrupted_copy_does_not_publish_partial_snapshot(self):
        args = self.freeze_args()
        original_write = Path.write_bytes
        calls = 0

        def fail_second_write(path, data):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("Simulated interrupted write")
            return original_write(path, data)

        with patch.object(Path, "write_bytes", fail_second_write):
            with self.assertRaises(OSError):
                baseline.freeze(args)
        self.assertEqual(list(args.destination.iterdir()), [])

    def test_unclosed_csv_quote_is_rejected(self):
        with self.assertRaises(baseline.csv.Error):
            baseline.csv_records(b'name\n"unfinished')

    def test_freeze_preserves_bytes_and_rerun_preserves_manifest(self):
        args = self.freeze_args()
        with contextlib.redirect_stdout(io.StringIO()):
            baseline.freeze(args)
        target = next(args.destination.glob("ps1-*"))
        before = (target / "manifest.json").read_bytes()
        for name in baseline.EXPECTED_PATHS:
            self.assertEqual((target / name).read_bytes(), (self.copy / name).read_bytes())
        with contextlib.redirect_stdout(io.StringIO()):
            baseline.freeze(args)
        self.assertEqual(before, (target / "manifest.json").read_bytes())
        self.assertTrue(baseline.verify_snapshot(target)["passed"])

    def test_changed_input_creates_new_identity(self):
        target = self.copy / "PS1/01_data/01_LINES.csv"
        target.write_bytes(target.read_bytes().replace(b"ALP", b"XYZ", 1))
        args = self.freeze_args()
        with contextlib.redirect_stdout(io.StringIO()):
            baseline.freeze(args)
        updated = json.loads(next(args.destination.glob("ps1-*/manifest.json")).read_text(encoding="utf-8"))
        original = json.loads((SNAPSHOT / "manifest.json").read_text(encoding="utf-8"))
        self.assertNotEqual(original["pack_sha256"], updated["pack_sha256"])
        self.assertNotEqual(original["input_data_sha256"], updated["input_data_sha256"])

    def test_changed_source_before_publication_is_rejected(self):
        args = self.freeze_args()
        inventory = baseline.source_inventory
        calls = 0

        def change_before_final_check(source, readme):
            nonlocal calls
            calls += 1
            if calls == 2:
                readme.write_bytes(readme.read_bytes() + b"\nchanged")
            return inventory(source, readme)

        with patch.object(baseline, "source_inventory", change_before_final_check):
            with self.assertRaisesRegex(ValueError, "Source changed"):
                baseline.freeze(args)
        self.assertEqual(list(args.destination.iterdir()), [])

    def test_destination_inside_source_is_rejected(self):
        args = self.freeze_args()
        args.destination = args.source_root / "frozen"
        with self.assertRaisesRegex(ValueError, "must not contain"):
            baseline.freeze(args)
        self.assertFalse(args.destination.exists())

    def test_malformed_json_cli_is_nonzero_without_traceback(self):
        (self.copy / "manifest.json").write_text("{", encoding="utf-8")
        result = subprocess.run([sys.executable, str(ROOT / "tools/baseline.py"),
                                 "verify", str(self.copy)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)["passed"])
        self.assertEqual(result.stderr, "")

    def test_path_traversal_in_manifest_is_rejected(self):
        self.edit_manifest(lambda m: m["files"][0].update(path="../outside.csv"))
        self.assertFalse(baseline.verify_snapshot(self.copy)["passed"])


if __name__ == "__main__":
    unittest.main()
