#!/usr/bin/env python3
"""Mitarbeiterfluss, Boundary-Dokument und aktuelle Releasemetadaten."""

from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
INSTALL = (ROOT / "INSTALL.md").read_text(encoding="utf-8")
CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


class EmployeeReadmeContract(unittest.TestCase):
    def test_readme_covers_complete_employee_flow(self):
        headings = (
            "## Was ist agent-governance?",
            "## Welches Problem löst es?",
            "## Architektur",
            "## Governance und Enforcement",
            "## Schnellstart",
            "## Installation und erster Start",
            "## Fresh, Current und Legacy",
            "## Nutzung",
            "## Routing und Rollen",
            "## Lokale persönliche Regeln",
            "## Module und Rollen erweitern",
            "## Microsoft-AGT-Integration",
            "## Verifikation und Tests",
            "## Versionierung",
            "## Security- und Betriebsgrenzen",
            "## Bekannte Einschränkungen",
        )
        for heading in headings:
            self.assertIn(heading, README)
        self.assertLessEqual(README.count("```mermaid"), 3)

    def test_quickstart_is_short_and_points_to_executable_contract(self):
        section = README.split("## Schnellstart", 1)[1].split("\n## ", 1)[0]
        for step in (
            "veröffentlichten",
            "Installation.bootstrap.prompt.md",
            "Harness",
            "Installationszustand",
            "Verifikationsstatus",
            "neue Agentensitzung",
        ):
            self.assertIn(step, section)
        self.assertLessEqual(len(re.findall(r"(?m)^\d+\. ", section)), 5)

    def test_microsoft_boundary_and_verified_support_are_precise(self):
        for term in (
            "v4.1.0",
            "0de71ca6c95cf8b9b975ac96f48eaa7826bbe258",
            "Public Preview",
            "Enforcement-Provider",
            "keine Governance-Quelle",
            "kein offizieller Codex-Adapter",
            "Codex CLI 0.147.0",
            "danger-full-access",
            "Standard-Seccomp",
        ):
            self.assertIn(term, README)
        self.assertNotRegex(README, r"(?i)Microsoft-(?:certified|approved)")
        self.assertNotRegex(README, r"(?i)Microsoft AGT (?:ist )?GA")

    def test_private_rules_and_runtime_evidence_boundary_are_explicit(self):
        for term in (
            "local_rules",
            "manifest.toml",
            "nicht committed",
            "keine Hashes",
            "codex exec",
            "codex debug prompt-input",
        ):
            self.assertIn(term, README)
        self.assertRegex(README, r"(?is)codex debug prompt-input.+nicht ausreichend")

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
        self.assertIn("Installation.bootstrap.prompt.md", INSTALL)
        self.assertIn("einzige ausführbare Installationsvertrag", INSTALL)
        self.assertNotRegex(INSTALL, r"(?m)^\d+\. ")
        self.assertIn("[`VERSION`](VERSION)", INSTALL)


class ReleaseMetadataContract(unittest.TestCase):
    def test_semver_breaking_tool_name_release_is_consistent(self):
        self.assertEqual(VERSION, "0.5.0")
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
        self.assertIn("## [0.5.0] — 2026-08-22", CHANGELOG)
        current = CHANGELOG.split(f"## [{VERSION}]", 1)[1].split("\n## [", 1)[0]
        for term in (
            "mcp__agent_governance__execute",
            "agent_governance__execute",
            "native MCP-Namensräume",
            "Kompatibilitätsalias",
            "**BREAKING:**",
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
