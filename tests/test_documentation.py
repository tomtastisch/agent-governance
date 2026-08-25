#!/usr/bin/env python3
"""Mitarbeiterfluss, Boundary-Dokument und aktuelle Releasemetadaten."""

from __future__ import annotations

from pathlib import Path
import json
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
CLI_REFERENCE_PATH = ROOT / "docs" / "installer-cli-reference.md"
HARNESS_RECIPES_PATH = ROOT / "docs" / "harness-recipes.md"
PACKAGE = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
PACKAGE_LOCK = json.loads((ROOT / "package-lock.json").read_text(encoding="utf-8"))


class ReadmeEntryContract(unittest.TestCase):
    """Catches a return from the concise entry layer to duplicated reference content."""

    REPOSITORY = "tomtastisch/agent-governance"
    RAW_MAIN = "https://raw.githubusercontent.com/tomtastisch/agent-governance/main"
    BLOB_MAIN = "https://github.com/tomtastisch/agent-governance/blob/main"

    def test_hero_orders_icon_title_pitch_and_exact_badge_classes(self):
        """Catches a missing pitch or badges taking the pitch position in the entry hero."""
        hero = README.split("\n## ", 1)[0]
        blocks = hero.strip().split("\n\n")
        self.assertEqual(len(blocks), 4)
        icon, title, pitch, badges = blocks
        self.assertIn("assets/branding/agent-governance-icon.png", icon)
        self.assertEqual(title, "# Agent Governance")
        self.assertRegex(pitch, r"^[A-ZÄÖÜ][^\n]{20,159}\.$")
        self.assertEqual(len(re.findall(r"[.!?](?:\s|$)", pitch)), 1)
        self.assertFalse(pitch.startswith("[!"))
        self.assertEqual(badges.count("[!["), 3)
        for badge_class in ("![npm]", "![CI]", "![License: Apache-2.0]"):
            self.assertEqual(badges.count(badge_class), 1)

    def test_readme_has_exactly_the_six_entry_sections(self):
        """Catches README growing into a second CLI, architecture, or security reference."""
        self.assertEqual(
            re.findall(r"(?m)^## .+$", README),
            [
                "## Was ist Agent Governance?",
                "## Warum Agent Governance?",
                "## Schnellstart",
                "## Wie funktioniert es?",
                "## Dokumentation",
                "## Support und Lizenz",
            ],
        )

    def test_badges_follow_package_and_ci_metadata(self):
        """Catches stale badges that no longer identify the published package, CI, or license."""
        ci_workflow = ROOT / ".github" / "workflows" / "ci.yml"
        self.assertTrue(ci_workflow.is_file())
        package_name = PACKAGE["name"]
        license_name = PACKAGE["license"]
        expected_badges = (
            f"https://img.shields.io/npm/v/{package_name}?style=flat-square",
            f"https://github.com/{self.REPOSITORY}/actions/workflows/{ci_workflow.name}/badge.svg?branch=main",
            f"License-{license_name.replace('-', '--')}",
        )
        for badge in expected_badges:
            with self.subTest(badge=badge):
                self.assertIn(badge, README)

    def test_quickstart_uses_stable_latest_for_plan_install_and_verify(self):
        """Catches a prerelease command or a quickstart that omits the explicit path contract."""
        section = README.split("## Schnellstart", 1)[1].split("\n## ", 1)[0]
        for command in ("plan", "install", "verify"):
            with self.subTest(command=command):
                self.assertIn(
                    f"npx @tomtastisch/agent-governance@latest {command}", section
                )
        for option in (
            "--scope global",
            "--installation-root",
            "--target-root",
            "--entry-file",
            "--non-interactive",
        ):
            self.assertIn(option, section)
        self.assertNotIn("@next", section)
        self.assertNotIn("--harness", section)

    def test_readme_navigates_to_current_reference_owners_on_main(self):
        """Catches relative or historical links instead of durable current-reference navigation."""
        paths = (
            "docs/installer-cli-reference.md",
            "docs/harness-recipes.md",
            "docs/installer-architecture.md",
            "docs/installer-threat-model.md",
            "docs/installer-json-schemas.md",
            "CHANGELOG.md",
            "bundle/GOVERNANCE.md",
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).is_file())
                self.assertIn(f"{self.BLOB_MAIN}/{path}", README)

    def test_assets_have_semantic_paths_and_a_single_readme_overview(self):
        """Catches duplicate, stale, or wrongly assigned visual documentation assets."""
        icon = "assets/branding/agent-governance-icon.png"
        overview = "assets/diagrams/governance-overview.png"
        architecture = "assets/diagrams/governance-architecture.png"
        for path in (icon, overview, architecture):
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).is_file())
        self.assertFalse((ROOT / "docs" / "images").exists())
        self.assertIn(f"{self.RAW_MAIN}/{icon}", README)
        self.assertEqual(README.count(f"{self.RAW_MAIN}/{overview}"), 1)
        architecture_doc = (ROOT / "docs" / "installer-architecture.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(f"../{architecture}", architecture_doc)
        for stale in (
            "docs/images/",
            "Governance-ujjm885-44_44.png",
            "Governance-dsfs652-20_44.png",
            "82b014a1-7278-4be4-a665-37dae365c850.png",
        ):
            self.assertNotIn(stale, "\n".join((README, architecture_doc)))

    def test_overview_graphic_belongs_to_how_it_works(self):
        """Catches the sole overview drifting into the problem or benefit narrative."""
        overview = f"{self.RAW_MAIN}/assets/diagrams/governance-overview.png"
        how = README.split("## Wie funktioniert es?", 1)[1].split("\n## ", 1)[0]
        self.assertEqual(how.count(overview), 1)

    def test_why_section_has_three_to_five_compact_benefits(self):
        """Catches a prose-only why section that does not expose the approved benefits."""
        why = README.split("## Warum Agent Governance?", 1)[1].split("\n## ", 1)[0]
        benefits = re.findall(r"(?m)^- \S.+$", why)
        self.assertGreaterEqual(len(benefits), 3)
        self.assertLessEqual(len(benefits), 5)

    def test_readme_drops_retired_entry_points_and_keeps_support(self):
        """Catches retired RC guidance or the accidental loss of the intended support destination."""
        for stale in ("@next", "Release Candidate", "RC", "INSTALL.md"):
            self.assertNotIn(stale, README)
        self.assertIn("https://buymeacoffee.com/tomtastisch", README)
        self.assertIn(PACKAGE["license"], README)


class CurrentDocumentationBoundaryContract(unittest.TestCase):
    def test_harness_recipes_are_source_linked_and_runtime_neutral(self):
        recipes = HARNESS_RECIPES_PATH.read_text(encoding="utf-8")
        for term in (
            "$HOME/.codex", "$HOME/.claude", "$HOME/.config/opencode",
            "$HOME/.openclaw/workspace", "AGENTS.md", "CLAUDE.md",
            "developers.openai.com/codex/guides/agents-md",
            "code.claude.com/docs/en/memory",
            "opencode.ai/v2/docs/instructions",
            "docs.openclaw.ai/agent-workspace",
        ):
            self.assertIn(term, recipes)
        self.assertIn(
            "https://github.com/tomtastisch/agent-governance/blob/main/docs/harness-recipes.md",
            README,
        )

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
        self.assertIn(
            "https://github.com/tomtastisch/agent-governance/blob/main/docs/installer-threat-model.md",
            README,
        )
        self.assertIn("reale Capability-Probe", threat)
        self.assertIn("verifizierter unveränderlicher Recoveryzustand erhalten", threat)
        for absolute_claim in ("race-free", "TOCTOU-proof", "tamper-proof", "atomic against all concurrent writers"):
            self.assertNotIn(absolute_claim, "\n".join((README, threat, architecture)).lower())

    def test_catchable_and_uncatchable_interruption_boundaries_are_explicit(self):
        architecture = (ROOT / "docs" / "installer-architecture.md").read_text(encoding="utf-8")
        for term in (
            "SIGINT",
            "SIGTERM",
            "PREPARED",
            "SIGKILL",
            "Stromausfall",
        ):
            self.assertIn(term, architecture)
        self.assertNotIn("registriert keine Signalhandler", architecture)
        cli_reference = CLI_REFERENCE_PATH.read_text(encoding="utf-8")
        for code in ("`130`", "`143`"):
            self.assertIn(code, cli_reference)


class InstallerCliReferenceContract(unittest.TestCase):
    def test_reference_is_linked_complete_and_non_normative(self):
        self.assertTrue(CLI_REFERENCE_PATH.is_file())
        reference = CLI_REFERENCE_PATH.read_text(encoding="utf-8")
        self.assertIn("docs/installer-cli-reference.md", README)
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
        """Catches a prerelease or current-version literal in the durable CLI contract."""
        reference = CLI_REFERENCE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("@next", reference)
        self.assertIn("@tomtastisch/agent-governance@latest", reference)

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
        """Catches loss of durable managed-block and retained-recovery semantics after migration."""
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
    def test_documentation_release_metadata_is_version_derived(self):
        self.assertEqual(PACKAGE["version"], VERSION)
        self.assertEqual(PACKAGE_LOCK["version"], VERSION)
        self.assertEqual(PACKAGE_LOCK["packages"][""]["version"], VERSION)
        self.assertIn("## Support und Lizenz", README)
        self.assertIn("https://buymeacoffee.com/tomtastisch", README)
        self.assertIn(PACKAGE["license"], README)
        current = CHANGELOG.split(f"## [{VERSION}]", 1)[1].split("\n## [", 1)[0]
        for term in (
            "kompakte README",
            "Dokumentationsarchitektur",
            "Harness Recipes",
            "semantische Assets",
            "INSTALL.md",
            "Package-, Test- und Linkbereinigung",
        ):
            self.assertIn(term, current)
        self.assertIn("**Breaking changes:** none", current)
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
