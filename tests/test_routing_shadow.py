"""Fail-closed Shadow-Vergleichsvertrag für #94: Semantic-Change-Bindung und Baseline-Git-Bindung."""

import subprocess
import unittest

from tests.support.routing_shadow import (
    ShadowBaselineError,
    unexplained_semantic_changes,
    verify_baseline_git_binding,
)
from tests.support.routing_measurement import measure_route
from tests.test_routing_performance import BASELINE, BUNDLE, loaded_rules, semantic_text


class ShadowSemanticChangeContract(unittest.TestCase):
    def test_documented_change_matching_expected_contract_is_not_unexplained(self):
        expected = BASELINE["expected_changes"]
        current = {rule: expected[rule] for rule in expected}
        changed = sorted(expected)
        self.assertEqual(
            unexplained_semantic_changes(changed, current, expected), []
        )

    def test_further_weakening_of_a_security_rule_is_flagged(self):
        expected = BASELINE["expected_changes"]
        weakened = expected["GOV-006"].replace(
            "Security-Vorklassifikation", "Optionale Prüfung"
        )
        self.assertNotEqual(weakened, expected["GOV-006"])
        self.assertEqual(
            unexplained_semantic_changes(["GOV-006"], {"GOV-006": weakened}, expected),
            ["GOV-006"],
        )

    def test_further_weakening_of_provider_boundary_is_flagged(self):
        expected = BASELINE["expected_changes"]
        weakened = expected["TOL-004"].replace(
            "neu geroutet", "ohne Sicherheitsprüfung übersprungen"
        )
        self.assertNotEqual(weakened, expected["TOL-004"])
        self.assertEqual(
            unexplained_semantic_changes(["TOL-004"], {"TOL-004": weakened}, expected),
            ["TOL-004"],
        )

    def test_rule_change_without_expected_contract_is_flagged(self):
        expected = BASELINE["expected_changes"]
        changed_text = "### DEL-001 — Relevante Tests\n\nGeschwächt ohne Vertrag."
        self.assertEqual(
            unexplained_semantic_changes(["DEL-001"], {"DEL-001": changed_text}, expected),
            ["DEL-001"],
        )

    def test_expected_changes_contract_matches_current_bundle(self):
        route = measure_route(
            BUNDLE, ["external_effect", "security_sensitive_change", "tool_selection"], 1
        )
        current = loaded_rules(BUNDLE, route)
        for rule, expected in BASELINE["expected_changes"].items():
            with self.subTest(rule=rule):
                self.assertEqual(semantic_text(current[rule]), semantic_text(expected))


class ShadowBaselineBindingContract(unittest.TestCase):
    def test_recorded_baseline_head_is_a_real_ancestor(self):
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        verify_baseline_git_binding(BASELINE["head"], head)

    def test_invalid_commit_sha_fails_closed(self):
        with self.assertRaises(ShadowBaselineError):
            verify_baseline_git_binding("0" * 40, "HEAD")

    def test_non_ancestor_sha_fails_closed(self):
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        parent = subprocess.check_output(["git", "rev-parse", "HEAD^"], text=True).strip()
        with self.assertRaises(ShadowBaselineError):
            verify_baseline_git_binding(head, parent)


if __name__ == "__main__":
    unittest.main()
