#!/usr/bin/env python3
"""Copilot-QA-Binding: mechanische Referenz- und Delivery-Verträge."""

from __future__ import annotations

from pathlib import Path
import re
import unittest

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Projekt erfordert Python 3.11+
    tomllib = None


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "bundle"
GOVERNANCE_ROOT = BUNDLE / "agent-governance"
MANIFEST = GOVERNANCE_ROOT / "manifest.toml"
BINDING = ROOT / ".github" / "copilot-instructions.md"
DELIVERY = GOVERNANCE_ROOT / "modules" / "delivery.md"

RULE_DEF_RE = re.compile(r"(?m)^### ([A-Z][A-Z0-9-]*-\d{3}) — ")
RULE_TOKEN_RE = re.compile(r"\b[A-Z][A-Z0-9-]*-\d{3}\b")

EXPECTED_BINDING_PATHS = (
    "bundle/agent-governance/roles/quality-assurance.md",
    "bundle/agent-governance/modules/delivery.md",
    "bundle/agent-governance/modules/tool-routing.md",
)
EXPECTED_BINDING_RULE_IDS = ("DEL-002", "DEL-003", "DEL-007", "DEL-008", "DEL-009", "TOL-004")


def normative_files() -> list[Path]:
    return [
        BUNDLE / "GOVERNANCE.md",
        *sorted((GOVERNANCE_ROOT / "modules").glob("*.md")),
        *sorted((GOVERNANCE_ROOT / "roles").glob("*.md")),
    ]


def rule_definitions() -> dict[str, list[Path]]:
    definitions: dict[str, list[Path]] = {}
    for path in normative_files():
        for rule_id in RULE_DEF_RE.findall(path.read_text(encoding="utf-8")):
            definitions.setdefault(rule_id, []).append(path.resolve())
    return definitions


def binding_violations(text: str) -> list[str]:
    violations: list[str] = []
    if re.search(r"https?://", text):
        violations.append("HTTP(S)-URL")
    if re.search(r"(?:^|[\s`])(?:~/|/Users/|/home/|\$HOME/)", text):
        violations.append("Home-/Host-Pfad")
    for span in re.findall(r"`([^`]+)`", text):
        candidate = span.strip()
        if candidate.startswith("bundle/") and not (ROOT / candidate).is_file():
            violations.append(f"nicht auflösbarer Pfad: {candidate}")
    definitions = rule_definitions()
    for rule_id in sorted(set(RULE_TOKEN_RE.findall(text))):
        if len(definitions.get(rule_id, [])) != 1:
            violations.append(f"Rule-ID nicht eindeutig: {rule_id}")
    return violations


class BindingArtifactContract(unittest.TestCase):
    def setUp(self):
        self.text = BINDING.read_text(encoding="utf-8")

    def test_binding_file_exists(self):
        self.assertTrue(BINDING.is_file())

    def test_binding_is_non_normative_consumer_artifact(self):
        self.assertRegex(self.text, r"(?i)nicht normativ")
        self.assertRegex(self.text, r"(?i)Consumer")
        self.assertNotRegex(self.text, RULE_DEF_RE)

    def test_binding_references_canonical_paths(self):
        for path in EXPECTED_BINDING_PATHS:
            self.assertIn(path, self.text, path)

    def test_binding_rule_ids_exist_exactly_once(self):
        definitions = rule_definitions()
        for rule_id in EXPECTED_BINDING_RULE_IDS:
            self.assertIn(rule_id, self.text, rule_id)
            self.assertEqual(len(definitions.get(rule_id, [])), 1, rule_id)

    def test_binding_has_no_violations(self):
        self.assertEqual(binding_violations(self.text), [])

    def test_binding_is_small_and_copies_no_rule_set(self):
        self.assertLessEqual(self.text.count("\n") + 1, 80)
        source = "\n".join(
            (GOVERNANCE_ROOT / "roles" / "quality-assurance.md").read_text(encoding="utf-8"),
            (GOVERNANCE_ROOT / "modules" / "delivery.md").read_text(encoding="utf-8"),
        )
        source_paragraphs = {
            " ".join(p.split()) for p in re.split(r"\n\s*\n", source)
            if len(" ".join(p.split())) >= 80
        }
        for paragraph in re.split(r"\n\s*\n", self.text):
            normalized = " ".join(paragraph.split())
            self.assertNotIn(normalized, source_paragraphs, normalized[:80])

    def test_binding_reference_mutation_fails(self):
        bad = (
            "Referenz auf `bundle/agent-governance/roles/qualitaetssicherung.md` und DEL-999.\n"
            "Zusätzlich https://example.com/include."
        )
        violations = binding_violations(bad)
        self.assertIn(
            "nicht auflösbarer Pfad: bundle/agent-governance/roles/qualitaetssicherung.md",
            violations,
        )
        self.assertIn("Rule-ID nicht eindeutig: DEL-999", violations)
        self.assertIn("HTTP(S)-URL", violations)


class DeliveryContract(unittest.TestCase):
    def setUp(self):
        self.delivery = DELIVERY.read_text(encoding="utf-8")

    def test_del_008_requires_valid_binding(self):
        self.assertRegex(
            self.delivery,
            r"(?is)GitHub Copilot.+bevorzugte QA-Provider.+Exact-Head-SHA.+"
            r"`.github/copilot-instructions.md`.+auflösbaren",
        )

    def test_del_008_keeps_independent_fallback(self):
        self.assertIn("`no`", self.delivery)
        self.assertIn("`unknown`", self.delivery)
        self.assertRegex(self.delivery, r"frischer\s+unabhängiger read-only")

    def test_del_010_defines_opt_in_parallel_qa(self):
        self.assertRegex(self.delivery, r"(?m)^### DEL-010 — ")
        self.assertRegex(self.delivery, r"(?is)DEL-010")
        self.assertRegex(self.delivery, r"(?is)nicht standardmäßig")
        self.assertRegex(self.delivery, r"(?is)ausdrücklich")
        self.assertRegex(self.delivery, r"(?is)denselben Exact Head")

    def test_del_010_keeps_sec_additive(self):
        self.assertRegex(self.delivery, r"(?is)Parallel-QA ersetzt SEC nicht")
        self.assertRegex(self.delivery, r"(?is)SEC-Rolle.+zusätzlich erforderlich")


class ToolRoutingContract(unittest.TestCase):
    def test_github_cli_required_on_unchanged(self):
        if tomllib is None:
            self.skipTest("tomllib erfordert Python 3.11+")
        with (GOVERNANCE_ROOT / "catalogs" / "tools.toml").open("rb") as handle:
            tools = tomllib.load(handle)["tools"]
        self.assertEqual(tools["github_cli"]["required_on"], ["github_remote"])


if __name__ == "__main__":
    unittest.main()
