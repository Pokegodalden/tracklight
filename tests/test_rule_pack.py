"""Check that unsupported claims and specification drift are detected."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import rule_pack


class RulePackTests(unittest.TestCase):
    def setUp(self):
        self.rules, self.examples, self.profile = deepcopy(rule_pack.load_pack())

    def issues(self):
        return rule_pack.check_pack(self.rules, self.examples, self.profile)[0]

    def test_pack_and_selected_evidence_agree(self):
        self.assertEqual(self.issues(), [])
        self.assertTrue(all(rule_pack.check_selected_evidence(self.examples).values()))

    def test_profile_cannot_claim_unknown_checks_pass(self):
        self.profile["claim_policy"]["unverified_check_is_pass"] = True
        self.assertIn("Unknown checks must not pass", self.issues())

    def test_deferred_rule_cannot_silently_become_enforced(self):
        rule = next(r for r in self.rules["rules"] if r["id"] == "R12")
        rule["enforcement_mode"] = "enforce"
        self.profile["rules"]["R12"]["mode"] = "enforce"
        self.assertIn("Deferred rules cannot silently pass", self.issues())

    def test_official_result_cannot_be_invented(self):
        self.examples["cases"][0]["official_result"] = "PASS"
        self.assertIn("E01: fabricated official result", self.issues())

    def test_changed_source_evidence_is_detected(self):
        case = next(c for c in self.examples["cases"] if c["id"] == "E07")
        case["evidence"][0]["row"]["co_share_group"] = "changed"
        self.assertIn("E07: evidence row differs from frozen source", self.issues())

    def test_broken_rule_example_link_is_detected(self):
        self.rules["rules"][0]["examples"].append("E999")
        self.assertIn("R01: broken example link E999", self.issues())

    def test_wrong_spec_fingerprint_is_detected(self):
        self.profile["rules_sha256"] = "0" * 64
        self.assertIn("Rules digest mismatch", self.issues())

    def test_wrong_sample_score_is_detected(self):
        case = next(c for c in self.examples["cases"] if c["id"] == "E22")
        case["expected_by_interpretation"]["candidate_activity_weighted_score"] = "28"
        self.assertFalse(rule_pack.check_selected_evidence(self.examples)["E22_distinct_delay_totals"])

    def test_only_predecessor_question_is_resolved(self):
        self.assertEqual([q['id'] for q in self.rules['questions'] if q['response']], ['Q06'])
        self.assertEqual(self.profile['rules']['R18']['status'], 'documented')
        self.assertEqual(self.profile['unconfigured_rules'], ['R12','R15','R17'])
        self.assertFalse(self.profile['officially_confirmed'])

    def test_published_evidence_cannot_be_substituted(self):
        self.profile['source_updates'][0]['sha256'] = '0'*64
        self.assertIn('Source update fingerprint mismatch', self.issues())

    def test_unrelated_question_cannot_claim_published_resolution(self):
        self.rules['questions'][0]['response'] = 'Resolved'
        self.assertIn('Q01: unanswered draft must not invent a reply', self.issues())


if __name__ == "__main__":
    unittest.main()
