#!/usr/bin/env python3
"""Verträge der atomaren Governance-Templates und ihrer kanonischen Registry (Issue #52)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE_ROOT = ROOT / "bundle" / "agent-governance"
TEMPLATES_ROOT = GOVERNANCE_ROOT / "templates"
VALIDATOR = ROOT / "tests" / "support" / "catalog_validator.py"

TEMPLATE_FIELDS = {"path", "category", "format"}
CATEGORIES = {
    "git",
    "delivery",
    "review",
    "context",
    "communication",
    "external_effects",
}
TEMPLATE_DIRS = {
    "git",
    "delivery",
    "review",
    "context",
    "communication",
    "external-effects",
}
EXPECTED_TEMPLATES = {
    "git_commit": ("git/commit.md", "git"),
    "git_branch": ("git/branch.md", "git"),
    "delivery_push_pr_checkpoint": ("delivery/push-pr-checkpoint.md", "delivery"),
    "delivery_pull_request": ("delivery/pull-request.md", "delivery"),
    "delivery_release_checkpoint": ("delivery/release-checkpoint.md", "delivery"),
    "review_finding": ("review/finding.md", "review"),
    "context_handoff": ("context/handoff.md", "context"),
    "communication_status": ("communication/status.md", "communication"),
    "communication_tool_error_blocker": ("communication/tool-error-blocker.md", "communication"),
    "communication_completion": ("communication/completion.md", "communication"),
    "external_effects_approval_checkpoint": ("external-effects/approval-checkpoint.md", "external_effects"),
}
CONTRACT_SECTIONS = (
    "## Verantwortung",
    "## Pflichtfelder",
    "## Nicht verantwortlich",
    "## Form",
)


def load_validator(case: unittest.TestCase):
    case.assertTrue(VALIDATOR.is_file(), "catalog_validator.py fehlt")
    spec = importlib.util.spec_from_file_location("catalog_validator", VALIDATOR)
    case.assertIsNotNone(spec)
    case.assertIsNotNone(spec.loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_registry() -> dict:
    with (TEMPLATES_ROOT / "manifest.toml").open("rb") as handle:
        return tomllib.load(handle)


class TemplateRegistryContract(unittest.TestCase):
    def test_registry_is_closed_and_exactly_once(self):
        registry = load_registry()
        self.assertEqual(set(registry), {"schema_version", "templates"})
        self.assertEqual(registry["schema_version"], 1)
        templates = registry["templates"]
        self.assertEqual(set(templates), set(EXPECTED_TEMPLATES))
        for template_id, (path, category) in EXPECTED_TEMPLATES.items():
            entry = templates[template_id]
            self.assertEqual(set(entry), TEMPLATE_FIELDS, template_id)
            self.assertEqual(entry["path"], path, template_id)
            self.assertEqual(entry["category"], category, template_id)
            self.assertEqual(entry["format"], "markdown", template_id)

    def test_every_registered_template_file_exists(self):
        registry = load_registry()
        for entry in registry["templates"].values():
            path = TEMPLATES_ROOT / entry["path"]
            self.assertTrue(path.is_file(), entry["path"])
            self.assertFalse(path.is_symlink(), entry["path"])

    def test_stable_ids_are_independent_of_paths(self):
        registry = load_registry()
        for template_id in registry["templates"]:
            self.assertRegex(template_id, r"^[a-z][a-z0-9_]*$")
            self.assertNotIn("/", template_id)

    def test_no_empty_template_placeholders(self):
        for path in sorted((TEMPLATES_ROOT).rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("<>", text, path)
            self.assertNotIn("< >", text, path)

    def test_each_template_documents_contract_sections(self):
        registry = load_registry()
        for template_id, entry in registry["templates"].items():
            text = (TEMPLATES_ROOT / entry["path"]).read_text(encoding="utf-8")
            for section in CONTRACT_SECTIONS:
                self.assertIn(section, text, f"{template_id}: {section}")

    def test_templates_have_no_executable_or_secret_content(self):
        for path in sorted((TEMPLATES_ROOT).rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("-----BEGIN", text, path)
            self.assertNotIn("```sh", text, path)
            self.assertNotIn("```bash", text, path)

    def test_migrated_templates_preserve_existing_forms(self):
        commit = (TEMPLATES_ROOT / "git" / "commit.md").read_text(encoding="utf-8")
        self.assertIn("<type>(<scope>): <imperative summary>", commit)
        branch = (TEMPLATES_ROOT / "git" / "branch.md").read_text(encoding="utf-8")
        self.assertIn("<type>/<scope>/<short-topic>", branch)
        finding = (TEMPLATES_ROOT / "review" / "finding.md").read_text(encoding="utf-8")
        for classification in ("blocking-valid", "nonblocking-valid", "invalid", "not-applicable"):
            self.assertIn(classification, finding)
        self.assertIn("Re-Review:", finding)

    def test_no_duplicate_semantic_template(self):
        registry = load_registry()
        paths = [entry["path"] for entry in registry["templates"].values()]
        self.assertEqual(len(paths), len(set(paths)))
        ids = list(registry["templates"])
        self.assertEqual(len(ids), len(set(ids)))

    def test_finding_template_is_generic_not_role_split(self):
        files = [p.name for p in (TEMPLATES_ROOT / "review").glob("*.md")]
        self.assertEqual(files, ["finding.md"])

    def test_index_module_points_to_registry_and_categories(self):
        index = (GOVERNANCE_ROOT / "modules" / "templates.md").read_text(encoding="utf-8")
        self.assertIn("templates/manifest.toml", index)
        for category in CATEGORIES:
            self.assertIn(category, index)

    def test_index_module_lists_exactly_the_registry_templates(self):
        import re
        index = (GOVERNANCE_ROOT / "modules" / "templates.md").read_text(encoding="utf-8")
        registry = load_registry()
        links = re.findall(r"\[`([a-z][a-z0-9_]*)`\]\(\.\./templates/([^)]+)\)", index)
        self.assertEqual(len(links), len(EXPECTED_TEMPLATES))
        for template_id, rel in links:
            self.assertIn(template_id, registry["templates"], template_id)
            self.assertEqual(registry["templates"][template_id]["path"], rel, template_id)


class GapAnalysisContract(unittest.TestCase):
    def test_release_checkpoint_has_full_contract(self):
        text = (TEMPLATES_ROOT / "delivery" / "release-checkpoint.md").read_text(encoding="utf-8")
        for field in (
            "Release target:",
            "Exact Head:",
            "Version:",
            "Tag:",
            "Tag identity/signature:",
            "Required CI:",
            "Package artifact identity:",
            "Publish result:",
            "Registry read-back:",
            "Release object/read-back:",
            "Open findings:",
            "Authorized next action:",
        ):
            self.assertIn(field, text)
        for non_responsibility in ("Version berechnen", "Tag erzeugen", "veröffentlichen", "freigeben"):
            self.assertIn(non_responsibility, text)

    def test_external_effect_approval_has_full_contract(self):
        text = (TEMPLATES_ROOT / "external-effects" / "approval-checkpoint.md").read_text(encoding="utf-8")
        for field in (
            "Requested effect:",
            "Target:",
            "Expected mutation:",
            "Authority/source of approval:",
            "Authorized scope:",
            "Explicit exclusions:",
            "Precondition evidence:",
            "Rollback/recovery relevance:",
            "Read-back requirement:",
        ):
            self.assertIn(field, text)
        for non_responsibility in ("Autorisierung erzeugen", "Berechtigung prüfen", "ausführen"):
            self.assertIn(non_responsibility, text)

    def test_resume_decision_no_generic_resume_template(self):
        self.assertFalse((TEMPLATES_ROOT / "context" / "resume.md").exists())
        resume = (GOVERNANCE_ROOT / "modules" / "resume.md").read_text(encoding="utf-8")
        self.assertIn("## Resume-Checkpoint", resume)
        handoff = (TEMPLATES_ROOT / "context" / "handoff.md").read_text(encoding="utf-8")
        for resume_only in ("TOON-Projektion", "Binding-Fingerprints", "Dirty state"):
            self.assertNotIn(resume_only, handoff)

    def test_no_future_or_placeholder_template_domains(self):
        actual_dirs = {
            p.name
            for p in (TEMPLATES_ROOT).iterdir()
            if p.is_dir()
        }
        self.assertEqual(actual_dirs, TEMPLATE_DIRS)


class TemplateRegistryFailures(unittest.TestCase):
    def setUp(self):
        self.validator = load_validator(self)
        self.temporary = tempfile.TemporaryDirectory(prefix="governance-template-contract-")
        self.root = Path(self.temporary.name) / "agent-governance"
        shutil.copytree(GOVERNANCE_ROOT, self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def load(self):
        return self.validator.load_catalog_contract(self.root)

    def replace_registry(self, old: str, new: str) -> None:
        path = self.root / "templates" / "manifest.toml"
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text, f"Fixture-Marker fehlt: {old}")
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def test_unknown_registry_field_fails_closed(self):
        self.replace_registry('format = "markdown"', 'format = "markdown"\nunexpected = true')
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "unbekannte Felder"):
            self.load()

    def test_duplicate_template_path_fails_closed(self):
        self.replace_registry(
            'path = "git/branch.md"',
            'path = "git/commit.md"',
        )
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "doppelte Pfade"):
            self.load()

    def test_missing_template_file_fails_closed(self):
        (self.root / "templates" / "git" / "commit.md").unlink()
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "reguläre"):
            self.load()

    def test_unknown_category_fails_closed(self):
        self.replace_registry('category = "git"', 'category = "future"')
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "unbekannt"):
            self.load()

    def test_unsupported_format_fails_closed(self):
        self.replace_registry('format = "markdown"', 'format = "yaml"')
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "ungültig"):
            self.load()

    def test_root_escape_fails_closed(self):
        outside = self.root.parent / "outside.md"
        outside.write_text("outside\n", encoding="utf-8")
        self.replace_registry('path = "git/commit.md"', 'path = "../outside.md"')
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "Traversal"):
            self.load()

    def test_absolute_path_fails_closed(self):
        self.replace_registry('path = "git/commit.md"', f'path = "{self.root / "outside.md"}"')
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "ungültig"):
            self.load()

    def test_template_symlink_escape_fails_closed(self):
        target = self.root.parent / "commit-target.md"
        shutil.copy2(self.root / "templates" / "git" / "commit.md", target)
        source = self.root / "templates" / "git" / "commit.md"
        source.unlink()
        source.symlink_to(target)
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "Symlink"):
            self.load()

    def test_registered_directory_instead_of_file_fails_closed(self):
        path = self.root / "templates" / "git" / "commit.md"
        path.unlink()
        path.mkdir()
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "reguläre"):
            self.load()

    def test_unregistered_template_file_fails_closed(self):
        (self.root / "templates" / "git" / "orphan.md").write_text("# orphan\n", encoding="utf-8")
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "nicht registrierte"):
            self.load()

    def test_noncanonical_templates_path_fails_closed(self):
        manifest_path = self.root / "manifest.toml"
        text = manifest_path.read_text(encoding="utf-8")
        self.assertIn('templates = "templates/manifest.toml"', text)
        manifest_path.write_text(
            text.replace(
                'templates = "templates/manifest.toml"',
                'templates = "alternate/manifest.toml"',
                1,
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "kanonische"):
            self.load()

    def test_fresh_consumer_resolves_all_registered_templates(self):
        contract = self.load()
        self.assertTrue(contract.template_paths)
        for path in contract.template_paths:
            self.assertTrue(path.is_file(), path)
            self.assertFalse(path.is_symlink(), path)


if __name__ == "__main__":
    unittest.main()
