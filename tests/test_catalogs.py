#!/usr/bin/env python3
"""Geschlossene Schema-, Pfad- und Referenzverträge der Governance-Kataloge."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE_ROOT = ROOT / "bundle" / "agent-governance"
VALIDATOR = ROOT / "tests" / "support" / "catalog_validator.py"
EXPECTED_CATALOG_PATHS = {
    "triggers": "catalogs/triggers.toml",
    "policy_tags": "catalogs/policy-tags.toml",
    "scopes": "catalogs/scopes.toml",
    "tools": "catalogs/tools.toml",
}
EXPECTED_TOOLS = {
    "local_git_cli",
    "repository_checks",
    "github",
    "github_cli",
    "github_connector",
    "authoritative_documentation",
    "superpowers",
    "independent_review_provider",
    "security_diff_scan",
    "microsoft_apm",
    "linear",
    "supabase",
    "supermetrics",
    "data_analytics",
    "canonical_memory_verifier",
}
TOOL_FIELDS = {
    "name",
    "purpose",
    "required_on",
    "useful_on",
    "policy_tags",
    "scopes",
    "evidence",
    "fallback",
    "constraints",
}


def load_validator(case: unittest.TestCase):
    case.assertTrue(VALIDATOR.is_file(), "catalog_validator.py fehlt")
    spec = importlib.util.spec_from_file_location("catalog_validator", VALIDATOR)
    case.assertIsNotNone(spec)
    case.assertIsNotNone(spec.loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CatalogContract(unittest.TestCase):
    def setUp(self):
        self.validator = load_validator(self)
        self.contract = self.validator.load_catalog_contract(GOVERNANCE_ROOT)

    def test_manifest_schema_two_references_exact_catalogs(self):
        self.assertEqual(self.contract.manifest["schema_version"], 2)
        self.assertEqual(self.contract.manifest["catalogs"], EXPECTED_CATALOG_PATHS)
        self.assertEqual(
            set(self.contract.manifest),
            {"schema_version", "local_rules", "catalogs", "routing", "modules", "roles"},
        )
        self.assertEqual(
            self.contract.manifest["routing"],
            {"unknown": "block", "ambiguous": "block"},
        )
        self.assertNotIn("known_triggers", self.contract.manifest["routing"])

    def test_catalogs_have_closed_top_level_and_entry_fields(self):
        self.assertEqual(set(self.contract.catalogs["triggers"]), {"schema_version", "triggers"})
        self.assertEqual(
            set(self.contract.catalogs["policy_tags"]), {"schema_version", "policy_tags"}
        )
        self.assertEqual(set(self.contract.catalogs["scopes"]), {"schema_version", "scopes"})
        self.assertEqual(set(self.contract.catalogs["tools"]), {"schema_version", "tools"})
        for catalog_name in ("triggers", "policy_tags", "scopes"):
            for item_id, item in self.contract.catalogs[catalog_name][catalog_name].items():
                self.assertEqual(set(item), {"label", "description"}, item_id)
        for tool_id, tool in self.contract.tools.items():
            self.assertEqual(set(tool), TOOL_FIELDS, tool_id)

    def test_every_module_role_and_tool_reference_is_closed(self):
        for group_name in ("modules", "roles"):
            for item_id, item in self.contract.manifest[group_name].items():
                self.assertLessEqual(set(item["triggers"]), self.contract.triggers, item_id)
        for tool_id, tool in self.contract.tools.items():
            self.assertLessEqual(set(tool["required_on"]), self.contract.triggers, tool_id)
            self.assertLessEqual(set(tool["useful_on"]), self.contract.triggers, tool_id)
            self.assertLessEqual(set(tool["policy_tags"]), self.contract.policy_tags, tool_id)
            self.assertLessEqual(set(tool["scopes"]), self.contract.scopes, tool_id)

    def test_every_required_tool_trigger_routes_through_tool_routing_semantics(self):
        required_triggers = {
            trigger
            for tool in self.contract.tools.values()
            for trigger in tool["required_on"]
        }
        self.assertEqual(
            set(self.contract.manifest["modules"]["tool_routing"]["triggers"]),
            {"tool_selection", *required_triggers},
        )

    def test_catalog_contains_all_migrated_and_required_tools(self):
        self.assertEqual(set(self.contract.tools), EXPECTED_TOOLS)
        for required in (
            "linear",
            "supabase",
            "superpowers",
            "supermetrics",
            "github",
            "data_analytics",
            "canonical_memory_verifier",
            "microsoft_apm",
        ):
            self.assertIn(required, self.contract.tools)

    def test_policy_tags_are_only_effect_classes_and_scopes_are_only_resources(self):
        self.assertEqual(self.contract.policy_tags, frozenset({"read", "write"}))
        self.assertEqual(
            self.contract.scopes,
            frozenset({
                "repository",
                "github",
                "documentation",
                "work_tracking",
                "database",
                "authentication",
                "storage",
                "realtime",
                "edge_functions",
                "marketing_data",
                "structured_data",
                "analytics_artifacts",
                "canonical_memory",
                "agent_packages",
            }),
        )
        policy_text = (
            GOVERNANCE_ROOT / EXPECTED_CATALOG_PATHS["policy_tags"]
        ).read_text(encoding="utf-8")
        scope_text = (GOVERNANCE_ROOT / EXPECTED_CATALOG_PATHS["scopes"]).read_text(
            encoding="utf-8"
        )
        self.assertRegex(policy_text, r"(?is)erzeugt niemals selbst eine Autorisierung")
        self.assertRegex(scope_text, r"(?is)beschreibt.+Ressourcenklasse.+keine Autorisierung")

    def test_specialized_tool_boundaries_are_explicit(self):
        apm = self.contract.tools["microsoft_apm"]
        for term in ("Microsoft APM", "Agent Package Manager", "github.com/microsoft/apm"):
            self.assertIn(term, apm["purpose"] + apm["constraints"])
        self.assertIn("apm.yml", apm["evidence"])
        self.assertIn("apm.lock.yaml", apm["evidence"])
        self.assertRegex(apm["constraints"], r"(?is)keine automatische Installation.+Aktualisierung")

        memory = self.contract.tools["canonical_memory_verifier"]
        self.assertRegex(
            memory["constraints"],
            r"(?is)explizit.+ausgewählte.+keine allgemeine\s+Memory-Suche",
        )

        supermetrics = self.contract.tools["supermetrics"]
        self.assertRegex(supermetrics["constraints"], r"(?is)kein Ersatz für Data Analytics")

        supabase = self.contract.tools["supabase"]
        supabase_text = " ".join(str(value) for value in supabase.values())
        for term in (
            "PostgreSQL",
            "Schema",
            "Migration",
            "RLS",
            "Auth",
            "Storage",
            "Realtime",
            "Edge Functions",
            "Backenddiagnostik",
        ):
            self.assertIn(term, supabase_text)

    def test_github_profiles_distinguish_remote_local_cli_and_connector(self):
        self.assertIn("github", self.contract.tools)
        self.assertIn("github_cli", self.contract.tools)
        self.assertIn("github_connector", self.contract.tools)
        self.assertIn("local_git_cli", self.contract.tools)
        self.assertRegex(
            self.contract.tools["local_git_cli"]["constraints"],
            r"(?is)keinen Remotezustand",
        )

    def test_repository_checks_classify_expected_artifact_writes(self):
        self.assertEqual(
            self.contract.tools["repository_checks"]["policy_tags"],
            ["read", "write"],
        )
        self.assertRegex(
            self.contract.tools["repository_checks"]["constraints"],
            r"(?is)write.+keine Autorisierung",
        )

    def test_github_connector_preserves_conditional_required_path(self):
        connector_trigger = "github_connector_required"
        connector = self.contract.tools["github_connector"]
        self.assertIn(connector_trigger, self.contract.triggers)
        self.assertEqual(connector["required_on"], [connector_trigger])
        self.assertIn(
            connector_trigger,
            self.contract.manifest["modules"]["tool_routing"]["triggers"],
        )
        trigger_description = self.contract.catalogs["triggers"]["triggers"][
            connector_trigger
        ]["description"]
        self.assertRegex(
            trigger_description,
            r"(?is)ausdrücklich.+Connector.+primäre.+Evidenz.+nicht.+auflösbar",
        )

    def test_microsoft_apm_preserves_required_provenance_and_drift_paths(self):
        required = {
            "agent_dependencies",
            "agent_package_provenance",
            "dependency_drift",
        }
        apm = self.contract.tools["microsoft_apm"]
        self.assertEqual(set(apm["required_on"]), required)
        self.assertEqual(apm["useful_on"], [])
        self.assertLessEqual(
            {"agent_package_provenance", "dependency_drift"},
            set(self.contract.manifest["modules"]["tool_routing"]["triggers"]),
        )
        self.assertRegex(
            apm["constraints"],
            r"(?is)fehlt.+deklarierter APM-Zustand.+Abwesenheit.+ohne Dateien anzulegen",
        )

    def test_tool_catalog_has_no_installation_or_availability_state(self):
        text = (GOVERNANCE_ROOT / EXPECTED_CATALOG_PATHS["tools"]).read_text(
            encoding="utf-8"
        )
        self.assertNotRegex(
            text,
            r"(?im)^\s*(?:installed|available|connected|authenticated|version_on_host|"
            r"workspace|login)\s*=",
        )
        for forbidden_field in ("required_when", "useful_when", "conditions", "situations", "events"):
            self.assertNotRegex(text, rf"(?m)^\s*{forbidden_field}\s*=")


class CatalogMutationCase(unittest.TestCase):
    def setUp(self):
        self.validator = load_validator(self)
        self.temporary = tempfile.TemporaryDirectory(prefix="governance-catalog-contract-")
        self.root = Path(self.temporary.name) / "agent-governance"
        shutil.copytree(GOVERNANCE_ROOT, self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def load(self):
        return self.validator.load_catalog_contract(self.root)

    def replace(self, relative: str, old: str, new: str) -> None:
        path = self.root / relative
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text, f"Fixture-Marker fehlt: {relative}: {old}")
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def append_tool(
        self,
        tool_id: str = "validation_probe",
        *,
        required_on: str = '["analysis"]',
        useful_on: str = "[]",
        policy_tags: str = '["read"]',
        scopes: str = '["repository"]',
        include_constraints: bool = True,
        extra: str = "",
    ) -> None:
        constraints = 'constraints = "Probe constraints."\n' if include_constraints else ""
        payload = f'''\n[tools."{tool_id}"]
name = "Validation Probe"
purpose = "Probe purpose."
required_on = {required_on}
useful_on = {useful_on}
policy_tags = {policy_tags}
scopes = {scopes}
evidence = "Probe evidence."
fallback = "Probe fallback."
{constraints}{extra}'''
        path = self.root / "catalogs" / "tools.toml"
        path.write_text(path.read_text(encoding="utf-8") + payload, encoding="utf-8")


class CatalogReferenceFailures(CatalogMutationCase):
    def test_unknown_module_trigger_fails_closed(self):
        self.replace(
            "manifest.toml",
            'triggers = ["external_effect", "security_sensitive_change"]',
            'triggers = ["unknown_module_trigger", "security_sensitive_change"]',
        )
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "unbekannten Trigger"):
            self.load()

    def test_unknown_role_trigger_fails_closed(self):
        self.replace(
            "manifest.toml",
            'triggers = ["role_architecture"]',
            'triggers = ["unknown_role_trigger"]',
        )
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "unbekannten Trigger"):
            self.load()

    def test_unknown_required_on_fails_closed(self):
        self.append_tool(required_on='["unknown_required_trigger"]')
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "unbekannten Trigger"):
            self.load()

    def test_unknown_useful_on_fails_closed(self):
        self.append_tool(useful_on='["unknown_useful_trigger"]')
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "unbekannten Trigger"):
            self.load()

    def test_required_on_without_tool_routing_module_fails_closed(self):
        self.append_tool(required_on='["analysis"]')
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "Tool-Routing"):
            self.load()

    def test_unknown_policy_tag_fails_closed(self):
        self.append_tool(policy_tags='["execute"]')
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "unbekannten Policy-Tag"):
            self.load()

    def test_unknown_scope_fails_closed(self):
        self.append_tool(scopes='["production"]')
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "unbekannten Scope"):
            self.load()

    def test_unknown_module_dependency_fails_closed(self):
        self.replace(
            "manifest.toml",
            'dependencies = []\n\n[modules.enforcement]',
            'dependencies = ["missing_module"]\n\n[modules.enforcement]',
        )
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "unbekannte Module"):
            self.load()

    def test_unknown_role_module_fails_closed(self):
        self.replace(
            "manifest.toml",
            'modules = ["evidence", "architecture", "invariants", "delivery"]',
            'modules = ["evidence", "architecture", "missing_module", "delivery"]',
        )
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "unbekannte Module"):
            self.load()

    def test_module_dependency_cycle_fails_closed(self):
        self.replace(
            "manifest.toml",
            'dependencies = []\n\n[modules.enforcement]',
            'dependencies = ["enforcement"]\n\n[modules.enforcement]',
        )
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "zyklisch"):
            self.load()


class CatalogSchemaFailures(CatalogMutationCase):
    def test_unknown_tool_field_fails_closed(self):
        self.append_tool(extra="unexpected = true\n")
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "unbekannte Felder"):
            self.load()

    def test_unknown_vocabulary_field_fails_closed(self):
        for relative in (
            "catalogs/triggers.toml",
            "catalogs/policy-tags.toml",
            "catalogs/scopes.toml",
        ):
            with self.subTest(relative=relative):
                path = self.root / relative
                original = path.read_text(encoding="utf-8")
                path.write_text(original + "unexpected = true\n", encoding="utf-8")
                with self.assertRaisesRegex(self.validator.CatalogValidationError, "unbekannte Felder"):
                    self.load()
                path.write_text(original, encoding="utf-8")

    def test_unknown_catalog_top_level_field_fails_closed(self):
        path = self.root / "catalogs" / "triggers.toml"
        path.write_text("unexpected = true\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "Top-Level"):
            self.load()

    def test_missing_mandatory_field_fails_closed(self):
        self.append_tool(include_constraints=False)
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "fehlende Felder"):
            self.load()

    def test_wrong_type_fails_closed(self):
        self.append_tool(required_on='"analysis"')
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "Liste"):
            self.load()

    def test_invalid_id_fails_closed(self):
        self.append_tool(tool_id="Invalid-ID")
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "ungültige ID"):
            self.load()

    def test_unknown_module_field_fails_closed(self):
        self.replace(
            "manifest.toml",
            'dependencies = []\n\n[modules.enforcement]',
            'dependencies = []\nunexpected = true\n\n[modules.enforcement]',
        )
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "unbekannte Felder"):
            self.load()

    def test_unknown_role_field_fails_closed(self):
        self.replace(
            "manifest.toml",
            'modules = ["evidence", "architecture", "invariants", "delivery"]',
            'modules = ["evidence", "architecture", "invariants", "delivery"]\n'
            'unexpected = true',
        )
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "unbekannte Felder"):
            self.load()

    def test_missing_module_field_fails_closed(self):
        self.replace("manifest.toml", 'path = "modules/invariants.md"\n', "")
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "fehlende Felder"):
            self.load()

    def test_wrong_module_field_type_fails_closed(self):
        self.replace(
            "manifest.toml",
            'dependencies = []\n\n[modules.enforcement]',
            'dependencies = "none"\n\n[modules.enforcement]',
        )
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "Liste"):
            self.load()

    def test_invalid_module_id_fails_closed(self):
        self.replace("manifest.toml", "[modules.invariants]", '[modules."Invalid-ID"]')
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "ungültige ID"):
            self.load()


class CatalogPathFailures(CatalogMutationCase):
    def test_absolute_local_rules_path_fails_closed(self):
        self.replace(
            "manifest.toml",
            'local_rules = "local/user-rules.md"',
            'local_rules = "/tmp/user-rules.md"',
        )
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "local_rules"):
            self.load()

    def test_local_rules_path_traversal_fails_closed(self):
        self.replace(
            "manifest.toml",
            'local_rules = "local/user-rules.md"',
            'local_rules = "../user-rules.md"',
        )
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "Traversal"):
            self.load()

    def test_local_rules_backslash_path_fails_closed(self):
        self.replace(
            "manifest.toml",
            'local_rules = "local/user-rules.md"',
            'local_rules = "local\\\\user-rules.md"',
        )
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "local_rules"):
            self.load()

    def test_unexpected_local_rules_symlink_fails_closed(self):
        outside = self.root.parent / "outside-rules.md"
        outside.write_text("outside\n", encoding="utf-8")
        local_rules = self.root / "local" / "user-rules.md"
        local_rules.symlink_to(outside)
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "Symlink"):
            self.load()

    def test_missing_catalog_fails_closed(self):
        (self.root / "catalogs" / "tools.toml").unlink()
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "reguläre"):
            self.load()

    def test_catalog_path_traversal_fails_closed(self):
        self.replace(
            "manifest.toml",
            'tools = "catalogs/tools.toml"',
            'tools = "catalogs/../catalogs/tools.toml"',
        )
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "Traversal"):
            self.load()

    def test_catalog_root_escape_fails_closed(self):
        outside = self.root.parent / "outside.toml"
        shutil.copy2(self.root / "catalogs" / "tools.toml", outside)
        self.replace(
            "manifest.toml",
            'tools = "catalogs/tools.toml"',
            'tools = "../outside.toml"',
        )
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "Traversal"):
            self.load()

    def test_absolute_external_catalog_fails_closed(self):
        outside = self.root.parent / "outside.toml"
        shutil.copy2(self.root / "catalogs" / "tools.toml", outside)
        self.replace(
            "manifest.toml",
            'tools = "catalogs/tools.toml"',
            f'tools = "{outside}"',
        )
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "Katalogpfad"):
            self.load()

    def test_unexpected_catalog_symlink_fails_closed(self):
        target = self.root.parent / "tools-target.toml"
        source = self.root / "catalogs" / "tools.toml"
        shutil.copy2(source, target)
        source.unlink()
        source.symlink_to(target)
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "Symlink"):
            self.load()

    def test_absolute_unselected_module_path_fails_closed(self):
        outside = self.root.parent / "outside.md"
        outside.write_text("outside\n", encoding="utf-8")
        self.replace(
            "manifest.toml",
            'path = "modules/context.md"',
            f'path = "{outside}"',
        )
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "Modulpfad"):
            self.load()

    def test_unselected_module_path_traversal_fails_closed(self):
        outside = self.root.parent / "outside.md"
        outside.write_text("outside\n", encoding="utf-8")
        self.replace(
            "manifest.toml",
            'path = "modules/context.md"',
            'path = "../outside.md"',
        )
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "Traversal"):
            self.load()

    def test_unexpected_unselected_module_symlink_fails_closed(self):
        outside = self.root.parent / "outside.md"
        outside.write_text("outside\n", encoding="utf-8")
        module = self.root / "modules" / "context.md"
        module.unlink()
        module.symlink_to(outside)
        with self.assertRaisesRegex(self.validator.CatalogValidationError, "Symlink"):
            self.load()


if __name__ == "__main__":
    unittest.main()
