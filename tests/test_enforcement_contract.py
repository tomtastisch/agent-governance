#!/usr/bin/env python3
"""Mechanische Verträge für die providerneutrale Enforcement-Grenze."""

from __future__ import annotations

from pathlib import Path
import unittest

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.11 ist Repositoryvertrag
    tomllib = None


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "bundle" / "agent-governance" / "manifest.toml"
ENFORCEMENT = ROOT / "bundle" / "agent-governance" / "modules" / "enforcement.md"


def load_manifest() -> dict:
    if tomllib is None:
        raise unittest.SkipTest("tomllib erfordert Python 3.11+")
    with MANIFEST.open("rb") as handle:
        return tomllib.load(handle)


def read_contract() -> str:
    if not ENFORCEMENT.is_file():
        raise AssertionError("normativer Enforcement-Vertrag fehlt")
    return ENFORCEMENT.read_text(encoding="utf-8")


class EnforcementManifestContract(unittest.TestCase):
    def setUp(self):
        self.manifest = load_manifest()

    def test_manifest_routes_exactly_one_enforcement_module(self):
        modules = self.manifest["modules"]
        self.assertIn("enforcement", modules)
        entry = modules["enforcement"]
        self.assertEqual(entry["path"], "modules/enforcement.md")
        self.assertEqual(entry["triggers"], ["external_effect"])
        self.assertEqual(entry["dependencies"], ["invariants"])
        self.assertEqual(
            sum(item["path"] == "modules/enforcement.md" for item in modules.values()),
            1,
        )

    def test_external_effect_closure_loads_invariants_before_enforcement(self):
        modules = self.manifest["modules"]
        self.assertIn("enforcement", modules)
        self.assertEqual(modules["enforcement"]["dependencies"], ["invariants"])
        self.assertIn("external_effect", modules["invariants"]["triggers"])


class GenericEnforcementContract(unittest.TestCase):
    def test_contract_defines_minimal_action_envelope(self):
        text = read_contract()
        for field in (
            "action_id",
            "action",
            "resource",
            "effect",
            "semantic_authorization",
            "approval_context",
            "risk_context",
            "evidence_id",
        ):
            self.assertIn(f"`{field}`", text)

    def test_contract_defines_closed_normalized_decisions(self):
        text = read_contract()
        for decision in ("allow", "deny", "require_approval", "error", "unknown"):
            self.assertIn(f"`{decision}`", text)
        self.assertRegex(text, r"(?m)^### ENF-002 — Geschlossene Providerentscheidung$")

    def test_provider_can_only_restrict_governance(self):
        text = read_contract()
        self.assertRegex(
            text,
            r"(?is)Governance.+`deny`.+Provider.+`allow`.+niemals",
        )
        self.assertRegex(text, r"(?is)Provider.+darf.+nur.+einschränken.+niemals.+erweitern")

    def test_non_allow_paths_are_fail_closed(self):
        text = read_contract()
        required_rules = {
            "deny": r"(?is)Provider.+`deny`.+blockiert",
            "approval": r"(?is)`require_approval`.+keine Approval.+erfunden.+sonst.+blockiert",
            "error": r"(?is)`error`.+`unknown`.+verpflichtend.+fail-closed",
            "allow": r"(?is)ausschließlich.+`allow`.+fortsetzen",
        }
        for name, pattern in required_rules.items():
            with self.subTest(name=name):
                self.assertRegex(text, pattern)

    def test_contract_is_provider_neutral(self):
        text = read_contract()
        self.assertNotRegex(text, r"(?i)Microsoft|\bAGT\b|Cedar|MCP Gateway")

    def test_contract_has_no_runtime_or_control_plane_scope(self):
        text = read_contract()
        for forbidden in ("Fleet Management", "Control Plane", "Background Updater"):
            self.assertNotIn(forbidden, text)
        self.assertRegex(text, r"(?is)Verfügbarkeit.+niemals.+Berechtigung")


if __name__ == "__main__":
    unittest.main()
