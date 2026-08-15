#!/usr/bin/env python3
"""Mitarbeiterfluss, Boundary-Dokument und Releasemetadaten für 0.3.0."""

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


class InstallBoundaryContract(unittest.TestCase):
    def test_install_is_boundary_not_second_executable_guide(self):
        self.assertIn("Boundary- und Verantwortungsdokument", INSTALL)
        self.assertIn("Installation.bootstrap.prompt.md", INSTALL)
        self.assertIn("einzige ausführbare Installationsvertrag", INSTALL)
        self.assertNotRegex(INSTALL, r"(?m)^\d+\. ")
        self.assertIn("[`VERSION`](VERSION)", INSTALL)


class ReleaseMetadataContract(unittest.TestCase):
    def test_semver_minor_release_is_consistent(self):
        self.assertEqual(VERSION, "0.3.0")
        self.assertIn("**Version:** [`0.3.0`](VERSION)", README)
        self.assertIn("## [0.3.0] — 2026-08-12", CHANGELOG)
        section = CHANGELOG.split("## [0.3.0]", 1)[1].split("\n## [", 1)[0]
        for term in (
            "Installation.bootstrap.prompt.md",
            "Fresh",
            "Current",
            "Legacy",
            "Microsoft Agent Governance Toolkit",
            "v4.1.0",
            "Enforcement",
            "local_rules",
        ):
            self.assertIn(term, section)
        self.assertIn("**Breaking changes:** none", section)


if __name__ == "__main__":
    unittest.main()
