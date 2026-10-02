#!/usr/bin/env python3
"""Copilot-Integration-Test: Verifikation der GitHub Copilot App als Governance-Consumer."""

from __future__ import annotations

import re
from pathlib import Path
import unittest

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - yaml might not be installed
    yaml = None


ROOT = Path(__file__).resolve().parents[1]
GITHUB_AGENTS_DIR = ROOT / ".github" / "agents"
GITHUB_APP_YML = ROOT / ".github" / "github-app.yml"
CUSTOM_AGENT = GITHUB_AGENTS_DIR / "governance.agent.md"
GOVERNANCE_BOOTSTRAP = ROOT / "bundle" / "GOVERNANCE.md"
MANIFEST_TOML = ROOT / "bundle" / "agent-governance" / "manifest.toml"


class CopilotIntegrationContract(unittest.TestCase):
    """Testet die GitHub Copilot App Integration als Governance-Consumer."""

    def setUp(self):
        """Stelle sicher, dass wir im richtigen Repository arbeiten."""
        self.assertTrue(
            GOVERNANCE_BOOTSTRAP.is_file(),
            f"Kanonische Governance-Quelle fehlt: {GOVERNANCE_BOOTSTRAP}"
        )
        self.assertTrue(
            MANIFEST_TOML.is_file(),
            f"Manifest fehlt: {MANIFEST_TOML}"
        )

    def test_custom_agent_exists(self):
        """Testet, dass der Custom Agent existiert."""
        self.assertTrue(
            CUSTOM_AGENT.is_file(),
            f"Custom Agent fehlt: {CUSTOM_AGENT}"
        )

    def test_custom_agent_frontmatter(self):
        """Testet, dass der Custom Agent korrektes Frontmatter hat."""
        if not CUSTOM_AGENT.is_file():
            self.skipTest("Custom Agent existiert nicht")

        content = CUSTOM_AGENT.read_text(encoding="utf-8")
        
        # Prüfe, dass das File mit Frontmatter beginnt
        self.assertTrue(
            content.startswith("---\n"),
            "Custom Agent muss mit Frontmatter beginnen"
        )
        
        # Extrahiere Frontmatter
        frontmatter_end = content.find("\n---\n", 4)
        self.assertNotEqual(
            frontmatter_end, -1,
            "Frontmatter muss mit --- beendet werden"
        )
        
        frontmatter = content[4:frontmatter_end]
        
        # Prüfe erforderliche Felder
        self.assertIn("name: Governance", frontmatter)
        self.assertIn("target: github-copilot", frontmatter)
        self.assertIn("user-invocable: true", frontmatter)
        self.assertIn("disable-model-invocation: true", frontmatter)
        
        # Prüfe, dass es keine zusätzlichen unerwünschten Felder gibt, die Governance-Regeln enthalten könnten
        self.assertNotIn("tools:", frontmatter)
        self.assertNotIn("model:", frontmatter)

    def test_custom_agent_content(self):
        """Testet, dass der Custom Agent keine Governance-Regeln enthält."""
        if not CUSTOM_AGENT.is_file():
            self.skipTest("Custom Agent existiert nicht")

        content = CUSTOM_AGENT.read_text(encoding="utf-8")
        
        # Entferne Frontmatter für Inhaltprüfung
        frontmatter_end = content.find("\n---\n", 4)
        if frontmatter_end != -1:
            content = content[frontmatter_end + 5:]  # +5 to skip "\n---\n"
        
        # Prüfe, dass es klare Aussagen über seine Rolle als Bootstrap gibt
        self.assertIn(
            "Dieses Agent-Profil ist ausschließlich ein Harness-Adapter",
            content
        )
        self.assertIn(
            "enthält KEINE Governance-Regeln",
            content
        )
        self.assertIn(
            "bundle/GOVERNANCE.md",
            content
        )
        
        # Prüfe, dass es keine kopierten Governance-Regeln enthält
        # Suche nach typischen Governance-Regelmarkierungen
        self.assertNotRegex(
            content, r"GOV-\d{3}",
            "Custom Agent darf keine Governance-Regel-IDs enthalten"
        )
        self.assertNotRegex(
            content, r"DEL-\d{3}",
            "Custom Agent darf keine Delivery-Regel-IDs enthalten"
        )
        self.assertNotRegex(
            content, r"TOL-\d{3}",
            "Custom Agent darf keine Tool-Routing-Regel-IDs enthalten"
        )

    def test_github_app_yml_exists(self):
        """Testet, dass die github-app.yml existiert."""
        # Hinweis: Diese Datei ist optional gemäß den Anforderungen
        # Wir testen nur, falls sie existiert, dass sie gültig ist
        if not GITHUB_APP_YML.is_file():
            self.skipTest("github-app.yml existiert nicht (optional)")

    def test_github_app_yml_structure(self):
        """Testet, dass die github-app.yml strukturell gültig ist."""
        if not GITHUB_APP_YML.is_file():
            self.skipTest("github-app.yml existiert nicht")
        
        if yaml is None:
            self.skipTest("yaml Bibliothek nicht verfügbar für Testing")
            
        try:
            content = GITHUB_APP_YML.read_text(encoding="utf-8")
            data = yaml.safe_load(content)
            
            # Grundlegende Strukturprüfung
            self.assertIsInstance(data, dict)
            
            # Prüfe, dass es keine Governance-Regeln enthält
            yaml_str = yaml.dump(data, default_flow_style=False)
            self.assertNotRegex(
                yaml_str, r"GOV-\d{3}|DEL-\d{3}|TOL-\d{3}",
                "github-app.yml darf keine Governance-Regel-IDs enthalten"
            )
            
        except yaml.YAMLError as e:
            self.fail(f"github-app.yml ist kein gültiges YAML: {e}")

    def test_no_agents_md_in_root(self):
        """Testet, dass keine AGENTS.md im Repository-Root existiert."""
        agents_md_root = ROOT / "AGENTS.md"
        self.assertFalse(
            agents_md_root.is_file(),
            f"Keine AGENTS.md im Repository-Root erlaubt: {agents_md_root}"
        )
        
        # Auch keine templates/AGENTS.md
        agents_md_templates = ROOT / "templates" / "AGENTS.md"
        self.assertFalse(
            agents_md_templates.is_file(),
            f"Keine templates/AGENTS.md erlaubt: {agents_md_templates}"
        )

    def test_custom_agent_references_correct_bootstrap(self):
        """Testet, dass der Custom Agent auf den korrekten Bootstrap verweist."""
        if not CUSTOM_AGENT.is_file():
            self.skipTest("Custom Agent existiert nicht")

        content = CUSTOM_AGENT.read_text(encoding="utf-8")
        
        # Prüfe explizite Referenz auf GOVERNANCE.md
        self.assertIn(
            "bundle/GOVERNANCE.md",
            content,
            "Custom Agent muss auf bundle/GOVERNANCE.md verweisen"
        )
        
        # Prüfe, dass es keine anderen Bootstrap-Quellen erwähnt
        # (Dies wäre schwieriger zu testen präzise, aber wir können nach offensichtlichen Alternativen suchen)
        self.assertNotIn(
            "AGENTS.md",
            content,
            "Custom Agent darf auf AGENTS.md verweisen"
        )

    def test_manifest_exists(self):
        """Testet, dass das Manifest existiert (Voraussetzung für Lazy Loading)."""
        self.assertTrue(
            MANIFEST_TOML.is_file(),
            f"Manifest muss existieren für Lazy Loading: {MANIFEST_TOML}"
        )
        
        # Grundlegende TOML-Strukturprüfung
        try:
            import tomllib
            with MANIFEST_TOML.open("rb") as f:
                data = tomllib.load(f)
                self.assertIn("schema_version", data)
                self.assertIn("routing", data)
                self.assertIn("modules", data)
        except ImportError:
            # Falls tomllib nicht verfügbar, zumindest prüfen dass es nicht leer ist
            self.assertGreater(
                len(MANIFEST_TOML.read_text(encoding="utf-8")),
                100,
                "Manifest sollte nicht leer sein"
            )
        except Exception as e:
            self.fail(f"Manifest ist kein gültiges TOML: {e}")


if __name__ == "__main__":
    unittest.main()