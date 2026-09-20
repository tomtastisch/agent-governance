#!/usr/bin/env python3
"""Mechanische Verträge für den zustandsgebundenen Resume Fast-Path (Issue #50)."""

from __future__ import annotations

from pathlib import Path
import unittest

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.11 ist Repositoryvertrag
    tomllib = None


ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE_ROOT = ROOT / "bundle" / "agent-governance"
MANIFEST = GOVERNANCE_ROOT / "manifest.toml"
TRIGGERS = GOVERNANCE_ROOT / "catalogs" / "triggers.toml"
RESUME = GOVERNANCE_ROOT / "modules" / "resume.md"
TEMPLATES = GOVERNANCE_ROOT / "modules" / "templates.md"

RESUME_TRIGGER = "resume_continuation"
RESUME_RULE_COUNT = 15

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
        self.assertRegex(
            self.text,
            r"(?is)`INCOMPLETE`.+niemals.+`PASS`",
        )

    def test_chat_is_transport_not_authority(self):
        self.assertIn("Chat context is transport, not authority", self.text)
        self.assertRegex(self.text, r"(?is)vorherige Chat.+keine.+Source of Truth")

    def test_toon_is_derived_projection_not_second_ssot(self):
        self.assertIn("Token-Oriented Object Notation", self.text)
        self.assertRegex(
            self.text,
            r"(?is)TOON.+keine zweite State-, Checkpoint- oder Evidence-Source of Truth",
        )
        self.assertRegex(self.text, r"(?is)manipulierte.+beschädigte.+veraltete.+fail-closed")
        self.assertRegex(self.text, r"(?is)keine neue Dependency")

    def test_duplicate_execution_is_fail_closed(self):
        self.assertRegex(
            self.text,
            r"(?is)externe.+nicht idempotente.+fail-closed",
        )

    def test_dirty_worktree_identity_is_bound(self):
        self.assertRegex(
            self.text,
            r"(?is)`HEAD`.+kein hinreichender Gleichheitsnachweis",
        )
        for term in ("staged", "unstaged", "untracked"):
            self.assertIn(term, self.text)

    def test_no_second_resume_authority_or_hash_primitive(self):
        self.assertRegex(
            self.text,
            r"(?is)einzelner globaler Hash.+unzureichend",
        )
        self.assertRegex(
            self.text,
            r"(?is)Git-Objektidentitäten.+nicht durch parallele\s+Hashlogik",
        )

    def test_operational_subsystems_are_explicitly_out_of_scope(self):
        for phrase in (
            "keine neue Datenbank",
            "keinen permanenten Daemon",
            "keinen Netzwerkdienst",
            "keine neue Credential-Infrastruktur",
        ):
            self.assertIn(phrase, self.text)


class ResumeTemplateContract(unittest.TestCase):
    def setUp(self):
        self.text = TEMPLATES.read_text(encoding="utf-8")

    def test_resume_checkpoint_is_a_strict_template(self):
        strict = self.text.split("## Strikte Vorlagen", 1)[1].split(
            "## Strukturierte Verträge", 1
        )[0]
        self.assertIn("### Resume-Checkpoint", strict)

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
