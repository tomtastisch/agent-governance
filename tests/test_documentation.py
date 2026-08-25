#!/usr/bin/env python3
"""Mitarbeiterfluss, Boundary-Dokument und aktuelle Releasemetadaten."""

from __future__ import annotations

from pathlib import Path
import json
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
INSTALL = (ROOT / "INSTALL.md").read_text(encoding="utf-8")
CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
CLI_REFERENCE_PATH = ROOT / "docs" / "installer-cli-reference.md"
HARNESS_RECIPES_PATH = ROOT / "docs" / "harness-recipes.md"
PACKAGE = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))


class EmployeeReadmeContract(unittest.TestCase):
    def test_readme_covers_complete_employee_flow(self):
        headings = (
            "## Was ist agent-governance?",
            "## Welches Problem löst es?",
            "## Architektur",
            "## Schnellstart",
            "## CLI- und Managed-Block-Vertrag",
            "## Transaktion, Update und Recovery",
            "## Lokale persönliche Regeln",
            "## Dokumentierte Harnessrezepte",
            "## Capability- und Kompatibilitätsstatus",
            "## Migration von v0.5.0",
            "## Releaseprozess",
            "## Verifikation und Tests",
            "## Security- und Betriebsgrenzen",
            "## Bekannte Einschränkungen",
        )
        for heading in headings:
            self.assertIn(heading, README)
        self.assertLessEqual(README.count("```mermaid"), 3)

    def test_quickstart_is_short_and_uses_the_explicit_path_contract(self):
        section = README.split("## Schnellstart", 1)[1].split("\n## ", 1)[0]
        for step in (
            "@tomtastisch/agent-governance",
            "--scope global",
            "--installation-root",
            "--target-root",
            "--entry-file",
            "--non-interactive",
        ):
            self.assertIn(step, section)
        self.assertNotIn("--harness", section)

    def test_adapterless_boundary_and_verified_support_are_precise(self):
        for term in (
            "GLOBAL_EXPLICIT_PATH_MANAGED_BLOCK",
            "keine Harnesserkennung",
            "keine Harnessadapter",
            "keine Runtime-Abhängigkeiten",
            "HARNESS_E2E_VERIFIED",
            "Fresh Session",
        ):
            self.assertIn(term, README)
        self.assertNotIn("PreToolUse-Bridge", README)
        self.assertNotIn("eigene Bridge", README)

    def test_private_rules_and_runtime_evidence_boundary_are_explicit(self):
        for term in (
            "local_rules",
            "manifest.toml",
            "nicht committed",
            "keine Hashes",
            "--local-rules",
            "explizite",
        ):
            self.assertIn(term, README)

    def test_governance_diagrams_are_local_non_normative_explanations(self):
        image_names = (
            "Governance-ujjm885-44_44.png",
            "Governance-dsfs652-20_44.png",
        )
        for name in image_names:
            with self.subTest(name=name):
                self.assertTrue((ROOT / "docs" / "images" / name).is_file())
                self.assertIn(f"docs/images/{name}", README)
        self.assertRegex(README, r"(?is)nicht normative.+Erklärung")
        self.assertIn("<details>", README)
        self.assertIn("Technischen Governance-Ablauf als Grafik anzeigen", README)

    def test_readme_names_current_catalog_paths_without_duplication(self):
        for path in (
            "catalogs/triggers.toml",
            "catalogs/policy-tags.toml",
            "catalogs/scopes.toml",
            "catalogs/tools.toml",
            "modules/tool-routing.md",
        ):
            self.assertIn(path, README)
        self.assertRegex(README, r"(?is)manifest\.toml.+Root-Index")
        self.assertRegex(README, r"(?is)schematisch.+nicht normativ")


class InstallBoundaryContract(unittest.TestCase):
    def test_install_is_boundary_not_second_executable_guide(self):
        self.assertIn("Boundary- und Verantwortungsdokument", INSTALL)
        self.assertIn("öffentliche CLI", INSTALL)
        self.assertIn("GLOBAL_EXPLICIT_PATH_MANAGED_BLOCK", INSTALL)
        self.assertNotRegex(INSTALL, r"(?m)^\d+\. ")
        self.assertIn("[`VERSION`](VERSION)", INSTALL)

    def test_harness_recipes_are_source_linked_and_runtime_neutral(self):
        for term in (
            "$HOME/.codex", "$HOME/.claude", "$HOME/.config/opencode",
            "$HOME/.openclaw/workspace", "AGENTS.md", "CLAUDE.md",
            "developers.openai.com/codex/guides/agents-md",
            "code.claude.com/docs/en/memory",
            "opencode.ai/v2/docs/instructions",
            "docs.openclaw.ai/concepts/agent-workspace",
        ):
            self.assertIn(term, README)
        self.assertRegex(README, r"(?is)Rezepte.+Dokumentation.+nicht.+Runtime")

    def test_threat_model_schema_and_adapter_decision_are_durable(self):
        threat = (ROOT / "docs" / "installer-threat-model.md").read_text(encoding="utf-8")
        schemas = (ROOT / "docs" / "installer-json-schemas.md").read_text(encoding="utf-8")
        audit = (ROOT / "docs" / "adapter-audit.md").read_text(encoding="utf-8")
        for term in ("Trust Boundaries", "Symlink", "TOCTOU", "Receipt", "Residual"):
            self.assertIn(term, threat)
        for term in ("schemaVersion", "OUTDATED", "DOWNGRADE_BLOCKED", "Feldsemantik"):
            self.assertIn(term, schemas)
        for term in ("NO_GO", "rulesync", "uri-templates", "keine Runtime-Abhängigkeit"):
            self.assertIn(term, audit)

    def test_installer_security_contract_has_one_narrow_atomicity_boundary(self):
        threat = (ROOT / "docs" / "installer-threat-model.md").read_text(encoding="utf-8")
        architecture = (ROOT / "docs" / "installer-architecture.md").read_text(encoding="utf-8")
        for term in (
            "## In Scope",
            "## Out of Atomic Guarantee",
            "Same-UID-Final-Component-Co-Writer",
            "kein atomarer Inode-CAS-Vertrag",
            "kein privilegierter Broker",
            "RENAME_NOREPLACE",
            "RENAME_EXCL",
        ):
            self.assertIn(term, threat)
        self.assertIn("docs/installer-threat-model.md", README)
        self.assertIn("Same-UID-Final-Component-Co-Writer", README)
        self.assertIn("Same-UID-Final-Component-Co-Writer", INSTALL)
        self.assertIn("reale Capability-Probe", threat)
        self.assertIn("verifizierter unveränderlicher Recoveryzustand erhalten", threat)
        self.assertIn("Directory-Handles", README)
        for absolute_claim in ("race-free", "TOCTOU-proof", "tamper-proof", "atomic against all concurrent writers"):
            self.assertNotIn(absolute_claim, "\n".join((README, INSTALL, threat, architecture)).lower())

    def test_catchable_and_uncatchable_interruption_boundaries_are_explicit(self):
        for term in (
            "SIGINT",
            "SIGTERM",
            "PREPARED",
            "130",
            "143",
            "SIGKILL",
            "Stromausfall",
        ):
            self.assertIn(term, README)
        self.assertNotIn("registriert keine Signalhandler", README)


class InstallerCliReferenceContract(unittest.TestCase):
    def test_reference_is_linked_complete_and_non_normative(self):
        self.assertTrue(CLI_REFERENCE_PATH.is_file())
        reference = CLI_REFERENCE_PATH.read_text(encoding="utf-8")
        self.assertIn("docs/installer-cli-reference.md", README)
        self.assertIn("docs/installer-cli-reference.md", INSTALL)
        self.assertRegex(reference, r"(?i)nicht normative.+CLI-Bedienreferenz")
        for command in (
            "inspect", "plan", "install", "verify",
            "status", "update", "uninstall", "rollback",
        ):
            self.assertRegex(reference, rf"(?m)^### `?{command}`?$")
        for option in (
            "--scope global", "--installation-root", "--target-root",
            "--entry-file", "--local-rules", "--dry-run", "--json",
            "--non-interactive",
        ):
            self.assertIn(f"`{option}`", reference)
        self.assertNotIn("--harness", reference)
        self.assertRegex(reference, r"(?i)kein cwd-Fallback")
        self.assertRegex(reference, r"(?i)kein implizites (?:Default-)?Ziel")

    def test_reference_is_the_only_packaged_docs_file(self):
        self.assertIn("docs/installer-cli-reference.md", PACKAGE["files"])
        packaged_docs = [entry for entry in PACKAGE["files"] if entry.startswith("docs/")]
        self.assertEqual(packaged_docs, ["docs/installer-cli-reference.md"])

    def test_current_cli_examples_do_not_retain_the_next_channel(self):
        """Catches the retired prerelease channel being presented as the current CLI contract."""
        reference = CLI_REFERENCE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("@next", reference)
        self.assertIn("@tomtastisch/agent-governance@1.0.1", reference)

    def test_cli_reference_owns_exit_behavior(self):
        """Catches exit behavior being split across lifecycle or schema references."""
        reference = CLI_REFERENCE_PATH.read_text(encoding="utf-8")
        self.assertIn("## Exitverhalten", reference)
        for code in ("`0`", "`2`", "`4`", "`5`", "`6`", "`130`", "`143`"):
            self.assertIn(code, reference)


class HarnessRecipeReferenceContract(unittest.TestCase):
    def test_harness_recipes_keep_each_verified_harness_contract_source_backed(self):
        """Catches a return to undocumented README-owned harness paths."""
        self.assertTrue(HARNESS_RECIPES_PATH.is_file())
        recipes = HARNESS_RECIPES_PATH.read_text(encoding="utf-8")
        contracts = {
            "Codex": (
                "${CODEX_HOME:-$HOME/.codex}/AGENTS.md",
                "https://developers.openai.com/codex/guides/agents-md",
            ),
            "Claude Code": (
                "$HOME/.claude/CLAUDE.md",
                "https://code.claude.com/docs/en/memory",
            ),
            "OpenCode V2": (
                "$XDG_CONFIG_HOME/opencode/AGENTS.md",
                "https://opencode.ai/v2/docs/instructions",
            ),
            "OpenClaw": (
                "AGENTS.md",
                "https://docs.openclaw.ai/agent-workspace",
            ),
        }
        for heading, (target, source_url) in contracts.items():
            with self.subTest(heading=heading):
                section = re.search(
                    rf"(?ms)^## {re.escape(heading)}$\n(.*?)(?=^## |\Z)", recipes
                )
                self.assertIsNotNone(section)
                self.assertIn(target, section.group(0))
                self.assertIn(source_url, section.group(0))

    def test_harness_recipes_use_latest_without_patch_pins(self):
        """Catches examples that turn the living recipes into stale patch instructions."""
        recipes = HARNESS_RECIPES_PATH.read_text(encoding="utf-8")
        self.assertIn("@tomtastisch/agent-governance@latest", recipes)
        self.assertNotRegex(recipes, r"@tomtastisch/agent-governance@\d+\.\d+\.\d+")


class InstallerArchitectureReferenceContract(unittest.TestCase):
    def test_architecture_retains_the_managed_block_recovery_contract(self):
        """Catches loss of durable managed-block and retained-recovery semantics before INSTALL removal."""
        architecture = (ROOT / "docs" / "installer-architecture.md").read_text(encoding="utf-8")
        for term in (
            "<!-- BEGIN AGENT_GOVERNANCE_MANAGED_V1 -->",
            "<!-- END AGENT_GOVERNANCE_MANAGED_V1 -->",
            "Außenbytes",
            "LF-/CRLF-Zeilenenden",
            "doppelte, unvollständige, fremde oder manipulierte Marker scheitern fail-closed",
            "entry.bin",
        ):
            self.assertIn(term, architecture)
        self.assertRegex(
            architecture,
            r"weder von Uninstall noch durch spätere Transaktionen implizit\s+gelöscht",
        )

    def test_architecture_links_to_schema_owner_instead_of_enumerating_json_or_exits(self):
        """Catches a second JSON or exit-code contract in the lifecycle reference."""
        architecture = (ROOT / "docs" / "installer-architecture.md").read_text(encoding="utf-8")
        self.assertIn("[JSON-Schemas](installer-json-schemas.md)", architecture)
        self.assertNotIn("JSON-Schema 1 nennt", architecture)
        self.assertNotIn("Exitcodes sind", architecture)


class ReleaseMetadataContract(unittest.TestCase):
    def test_installer_release_candidate_is_consistent(self):
        self.assertEqual(VERSION, "1.0.0")
        badge_line = README.splitlines()[2]
        self.assertIn(
            "[![Version](https://img.shields.io/github/v/release/"
            "tomtastisch/agent-governance?sort=semver&display_name=tag&style=flat-square&"
            "label=version&color=2ea44f)](VERSION)",
            badge_line,
        )
        self.assertNotIn(VERSION, badge_line)
        self.assertIn(
            "[![Changelog](https://img.shields.io/badge/changelog-view-1f6feb?"
            "style=flat-square)](CHANGELOG.md)",
            badge_line,
        )
        self.assertIn("\n## Support\n", README)
        self.assertIn(
            "[![Buy Me a Coffee](https://img.buymeacoffee.com/button-api/?"
            "text=Buy%20me%20a%20coffee&emoji=&slug=tomtastisch&button_colour=FFDD00&"
            "font_colour=000000&font_family=Cookie&outline_colour=000000&"
            "coffee_colour=ffffff)](https://buymeacoffee.com/tomtastisch)",
            README,
        )
        self.assertIn("## [1.0.0-rc.1] — 2026-08-24", CHANGELOG)
        current = CHANGELOG.split(f"## [{VERSION}]", 1)[1].split("\n## [", 1)[0]
        for term in (
            "transaktionalem Explicit-Path-Installer",
            "adapterlosem",
            "Rollback",
            "keine Harnessadapter",
            "macOS-Testfixtures",
        ):
            self.assertIn(term, current)
        self.assertIn("**Breaking changes:** present", current)
        recovery_patch = CHANGELOG.split("## [0.4.1]", 1)[1].split("\n## [", 1)[0]
        self.assertIn("**Breaking changes:** none", recovery_patch)
        historical = CHANGELOG.split("## [0.4.0]", 1)[1].split("\n## [", 1)[0]
        for term in (
            "Manifest-Schema 2",
            "catalogs/triggers.toml",
            "catalogs/policy-tags.toml",
            "catalogs/scopes.toml",
            "catalogs/tools.toml",
            "**BREAKING:**",
        ):
            self.assertIn(term, historical)
        self.assertIn("**Breaking changes:** present", historical)

    def test_published_032_recovery_metadata_remains_historical(self):
        self.assertIn("## [0.3.2] — 2026-08-15", CHANGELOG)
        section = CHANGELOG.split("## [0.3.2]", 1)[1].split("\n## [", 1)[0]
        for term in (
            "Allowed-Signers",
            "fingerprint",
            "Release-Verifikation",
            "v0.3.1",
            "ohne GitHub Release",
        ):
            self.assertIn(term, section)
        self.assertIn("**Breaking changes:** none", section)


if __name__ == "__main__":
    unittest.main()
