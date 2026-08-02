#!/usr/bin/env python3
"""Operational Cluster 4 preservation checks.

These checks deliberately do not define governance. They preserve the existing project/tool
surface while Cluster 3 removes legacy normative sources. Functional Cluster 4 changes remain
out of scope.
"""

from __future__ import annotations

from pathlib import Path
import re
import unittest

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - CI and this project require Python 3.11+
    tomllib = None


ROOT = Path(__file__).resolve().parents[1]
TOOLS = (ROOT / "tools" / "tools.md").read_text(encoding="utf-8")
BREW = (ROOT / "tools" / "Brewfile").read_text(encoding="utf-8")
BREW_OPT = (ROOT / "tools" / "Brewfile.optional").read_text(encoding="utf-8")


def section(text: str, heading: str) -> str:
    match = re.search(r"(?m)^" + re.escape(heading) + r"\s*$", text)
    if not match:
        return ""
    start = match.end()
    following = re.search(r"(?m)^##\s", text[start:])
    return text[start:start + following.start()] if following else text[start:]


class OperationalCluster4Contract(unittest.TestCase):
    def test_project_contract_retains_operational_sections(self):
        if tomllib is None:
            self.skipTest("tomllib requires Python 3.11+")
        with (ROOT / "project.toml").open("rb") as handle:
            data = tomllib.load(handle)
        self.assertEqual(
            set(data), {"schema_version", "project", "tooling", "activities", "roles", "session"}
        )
        self.assertTrue(data["tooling"]["fail_closed"])
        self.assertFalse(data["tooling"]["allow_client_local_fallbacks"])
        self.assertFalse(data["tooling"]["allow_unregistered_providers"])

    def test_brewfiles_remain_documented_and_separate(self):
        cli = section(TOOLS, "## CLI-Grundwerkzeuge")
        self.assertTrue(cli)
        required_line = next((line for line in cli.splitlines() if "erforderlich" in line), "")
        optional_line = next(
            (line for line in cli.splitlines() if "Optional empfohlen" in line), ""
        )
        required_documented = set(re.findall(r"`([^`]+)`", required_line))
        optional_documented = set(re.findall(r"`([^`]+)`", optional_line))
        required_packages = set(re.findall(r'brew\s+"([^"]+)"', BREW))
        optional_packages = set(re.findall(r'brew\s+"([^"]+)"', BREW_OPT))
        self.assertTrue(required_packages)
        self.assertFalse(required_packages & optional_packages)
        self.assertEqual(required_packages - required_documented, set())
        self.assertEqual(optional_packages - optional_documented, set())

    def test_every_tool_entry_retains_classification_and_install_block(self):
        blocks = re.split(r"(?m)^### ", TOOLS)[1:]
        self.assertTrue(blocks)
        for block in blocks:
            title = block.splitlines()[0].strip()
            self.assertRegex(
                block,
                r"(Standard-Setup|Optional empfohlen)",
                f"tool '{title}' lacks its retained classification",
            )
            self.assertIn("```", block, f"tool '{title}' lacks its retained install block")

    def test_catalog_links_are_well_formed(self):
        for url in re.findall(r"https?://\S+", TOOLS):
            url = url.rstrip(">).,")
            self.assertRegex(url, r"^https?://[^\s]+\.[^\s]+$", f"invalid URL: {url}")

    def test_legacy_tool_manifest_remains_absent(self):
        self.assertFalse((ROOT / "tools" / "tools.toml").exists())


if __name__ == "__main__":
    unittest.main()
