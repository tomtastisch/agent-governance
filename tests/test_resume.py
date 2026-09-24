#!/usr/bin/env python3
"""Mechanische Verträge für den zustandsgebundenen Resume Fast-Path (Issue #50)."""

from __future__ import annotations

from pathlib import Path
import re
import unittest

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.11 ist Repositoryvertrag
    tomllib = None


ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE_ROOT = ROOT / "bundle" / "agent-governance"
MANIFEST = GOVERNANCE_ROOT / "manifest.toml"
TRIGGERS = GOVERNANCE_ROOT / "ssot" / "routing" / "triggers.toml"
RESUME = GOVERNANCE_ROOT / "modules" / "resume.md"

RESUME_TRIGGER = "resume_continuation"
RESUME_RULE_COUNT = 21

# Pflichtbegriffe: der normative Resume-Vertrag muss diese Semantik ausdrücken.
REQUIRED_TERMS = (
    "resume_continuation",
    "Resume statt Reconstruct",
    "Revalidate only what may have changed",
    "Reuse only what is still provably bound",
    "Chat context is transport, not authority",
    "REUSE",
    "RERUN",
    "INVALIDATE",
    "INCOMPLETE",
    "Duplicate",
    "Dirty",
    "Fingerprint",
    "Fresh-Chat",
    "Progressive",
    "Token-Oriented Object Notation",
    "TOON",
    "fail-closed",
    "work_resumed",
    "keine zweite",
    "keine neue Datenbank",
    "keinen permanenten Daemon",
    "keinen Netzwerkdienst",
    "keine neue Credential-Infrastruktur",
    "keine provider- oder modellspezifische Limitlogik",
    "atomaren Aktion",
    # Delivery-Boundary-Reuse (#93)
    "State transition != evidence invalidation",
    "Evidence-Key",
    "git push",
    "Pull Request",
    "Remote-Readback",
    "Remote-Branch-Head",
    "PR-Head",
    "GitHub CI",
    "Required Checks",
    "Branch Protection",
    "Base-unabhängige Evidence",
    "Base-/Diff-gebundene Evidence",
    "keine zweite Evidence-Registry",
    "keine zweite Resume-Engine",
    "keine zweite Checkpoint-Authority",
    "keine zweite PR-Contract-Authority",
    "keine harte Abhängigkeit",
)

# Provider-/modellspezifische Namen dürfen im neutralen Vertrag nicht auftauchen.
FORBIDDEN_PROVIDER_TERMS = ("openai", "anthropic", "gemini")


def load_manifest() -> dict:
    if tomllib is None:
        raise unittest.SkipTest("tomllib erfordert Python 3.11+")
    with MANIFEST.open("rb") as handle:
        return tomllib.load(handle)


def load_triggers() -> dict:
    if tomllib is None:
        raise unittest.SkipTest("tomllib erfordert Python 3.11+")
    with TRIGGERS.open("rb") as handle:
        return tomllib.load(handle)


def read_resume() -> str:
    if not RESUME.is_file():
        raise AssertionError("normatives Resume-Modul fehlt: modules/resume.md")
    return RESUME.read_text(encoding="utf-8")


def rule_section(text: str, number: int) -> str:
    pattern = rf"### RES-{number:03d}\b.*?(?=\n### RES-\d{{3}}\b|\n## )"
    match = re.search(pattern, text, re.DOTALL)
    if match is None:
        raise AssertionError(f"Abschnitt RES-{number:03d} fehlt")
    return match.group(0)


class ResumeManifestContract(unittest.TestCase):
    def setUp(self):
        self.manifest = load_manifest()
        self.triggers = load_triggers()

    def test_resume_continuation_trigger_is_declared(self):
        self.assertIn(RESUME_TRIGGER, self.triggers["triggers"])
        entry = self.triggers["triggers"][RESUME_TRIGGER]
        self.assertEqual(set(entry), {"label", "description"})
        self.assertRegex(
            entry["description"],
            r"(?is)ohne fachlichen Work-Item-Statuswechsel",
        )

    def test_resume_module_is_wired_exactly_once(self):
        modules = self.manifest["modules"]
        self.assertIn("resume", modules)
        entry = modules["resume"]
        self.assertEqual(entry["path"], "modules/resume.md")
        self.assertEqual(entry["triggers"], [RESUME_TRIGGER])
        self.assertEqual(
            sum(
                RESUME_TRIGGER in item["triggers"] for item in modules.values()
            ),
            1,
            "resume_continuation darf keine zweite Resume-Engine verdrahten",
        )

    def test_resume_module_dependencies_cover_referenced_rules(self):
        deps = set(self.manifest["modules"]["resume"]["dependencies"])
        self.assertLessEqual(deps, set(self.manifest["modules"]))
        self.assertLessEqual(
            {"evidence", "delivery", "security", "invariants", "context"}, deps
        )

    def test_resume_is_not_a_work_item_lifecycle_trigger(self):
        for trigger in ("work_resumed", "work_item_resume"):
            self.assertNotIn(trigger, self.triggers["triggers"])


class ResumeModuleContract(unittest.TestCase):
    def setUp(self):
        self.text = read_resume()

    def test_all_resume_rules_are_present(self):
        for number in range(1, RESUME_RULE_COUNT + 1):
            self.assertIn(f"### RES-{number:03d}", self.text, f"RES-{number:03d} fehlt")

    def test_required_semantics_are_present(self):
        normalized = " ".join(self.text.split())
        for term in REQUIRED_TERMS:
            with self.subTest(term=term):
                self.assertIn(" ".join(term.split()), normalized)

    def test_contract_is_provider_and_model_neutral(self):
        lowered = self.text.lower()
        for term in FORBIDDEN_PROVIDER_TERMS:
            self.assertNotIn(term, lowered)

    def test_evidence_binding_matrix_is_deterministic(self):
        for outcome in ("REUSE", "RERUN", "INVALIDATE", "INCOMPLETE"):
            self.assertIn(f"`{outcome}`", self.text)

    def test_incomplete_is_never_pass(self):
        section = rule_section(self.text, 8)
        self.assertIn("`INCOMPLETE`", section)
        self.assertIn("niemals", section)
        self.assertIn("`PASS`", section)

    def test_chat_is_transport_not_authority(self):
        self.assertIn("Chat context is transport, not authority", self.text)
        section = " ".join(rule_section(self.text, 5).split())
        self.assertIn("vorherige Chat", section)
        self.assertIn("keine erforderliche Source of Truth", section)

    def test_toon_is_derived_projection_not_second_ssot(self):
        self.assertIn("Token-Oriented Object Notation", self.text)
        section = " ".join(rule_section(self.text, 13).split())
        self.assertIn("keine zweite State-, Checkpoint- oder Evidence-Source of Truth", section)
        self.assertIn("fail-closed", section)
        self.assertIn("eine eigene allgemeine TOON-Implementierung wird nicht gebaut", section)

    def test_duplicate_execution_is_fail_closed(self):
        section = rule_section(self.text, 10)
        self.assertIn("nicht idempotente", section)
        self.assertIn("fail-closed", section)

    def test_dirty_worktree_identity_is_bound(self):
        section = rule_section(self.text, 11)
        self.assertIn("kein hinreichender Gleichheitsnachweis", section)
        for term in ("staged", "unstaged", "untracked"):
            self.assertIn(term, section)

    def test_no_second_resume_authority_or_hash_primitive(self):
        section = rule_section(self.text, 3)
        self.assertIn("einzelner globaler Hash", section)
        self.assertIn("unzureichend", section)
        self.assertIn("nicht durch parallele", section)
        self.assertIn("Hashlogik", section)

    def test_operational_subsystems_are_explicitly_out_of_scope(self):
        for phrase in (
            "keine neue Datenbank",
            "keinen permanenten Daemon",
            "keinen Netzwerkdienst",
            "keine neue Credential-Infrastruktur",
        ):
            self.assertIn(phrase, self.text)

    def test_delivery_transition_does_not_invalidate_evidence(self):
        section = rule_section(self.text, 16)
        self.assertIn("State transition != evidence invalidation", " ".join(section.split()))
        self.assertIn("git push", section)
        self.assertIn("Pull Request", section)

    def test_evidence_key_binds_config_environment_and_base_diff(self):
        section = " ".join(rule_section(self.text, 17).split())
        for term in (
            "Evidence-Key",
            "content identity",
            "check identity",
            "configuration",
            "environment",
            "scope",
            "freshness",
            "base/diff",
        ):
            with self.subTest(term=term):
                self.assertIn(term, section)

    def test_remote_readback_is_required_before_reuse(self):
        section = rule_section(self.text, 18)
        for term in ("Remote-Branch-Head", "PR-Head", "fail-closed"):
            with self.subTest(term=term):
                self.assertIn(term, section)

    def test_identical_vs_independent_checks(self):
        section = " ".join(rule_section(self.text, 19).split())
        for term in ("identische", "unabhängige", "GitHub CI", "eigenständige Evidence"):
            with self.subTest(term=term):
                self.assertIn(term, section)

    def test_base_diff_bound_evidence_is_selectively_invalidated(self):
        section = " ".join(rule_section(self.text, 20).split())
        for term in ("Base-unabhängige", "Base-/Diff-gebundene", "keine pauschale Invalidierung"):
            with self.subTest(term=term):
                self.assertIn(term, section)

    def test_remote_gates_are_not_weakened(self):
        section = rule_section(self.text, 21)
        for term in ("Required Checks", "Branch Protection", "Security", "Approval", "Signing"):
            with self.subTest(term=term):
                self.assertIn(term, section)

    def test_no_second_delivery_or_checkpoint_authority(self):
        normalized = " ".join(self.text.split())
        for term in (
            "keine zweite Evidence-Registry",
            "keine zweite Resume-Engine",
            "keine zweite Checkpoint-Authority",
            "keine zweite PR-Contract-Authority",
            "keine harte Abhängigkeit",
        ):
            with self.subTest(term=term):
                self.assertIn(term, normalized)


class ResumeTemplateContract(unittest.TestCase):
    def setUp(self):
        self.text = RESUME.read_text(encoding="utf-8")

    def test_resume_checkpoint_is_a_strict_template(self):
        self.assertIn("## Resume-Checkpoint", self.text)

    def test_resume_checkpoint_binds_identity_and_evidence(self):
        for field in (
            "Auftrag:",
            "Scope:",
            "Task-Identität:",
            "Scope-Identität:",
            "Repository/Worktree/Branch:",
            "Exact state:",
            "Dirty state:",
            "Abgeschlossene Evidence:",
            "Unvollständige Evidence:",
            "Nächste atomare Aktion:",
            "TOON-Projektion:",
        ):
            with self.subTest(field=field):
                self.assertIn(field, self.text)


if __name__ == "__main__":
    unittest.main()
