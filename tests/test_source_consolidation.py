#!/usr/bin/env python3
"""Regression contracts for the Cluster 3 governance-source consolidation."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import unittest

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - CI and this project require Python 3.11+
    tomllib = None


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "bundle"
BOOTSTRAP = BUNDLE / "GOVERNANCE.md"
MANIFEST = BUNDLE / "agent-governance" / "manifest.toml"
HISTORICAL_MARKER = "Historische Evidenz - nicht normativ"
CLUSTER4_MARKER = "Cluster-4-Bestand - keine Governance-Quelle"

LEGACY_PATHS = (
    "adapters",
    "core",
    "profile",
    "templates",
)

LEGACY_REFERENCES = (
    "adapters/",
    "core/core.md",
    "core/roles/",
    "core/branch-tags.toml",
    "profile/profile.example.md",
    "templates/AGENTS.md",
    "templates/CLAUDE.md",
    "templates/README.md",
    "templates/claude-agents/",
)

ACTIVE_REFERENCE_FILES = (
    ROOT / "README.md",
    ROOT / "INSTALL.md",
    ROOT / ".github" / "workflows" / "ci.yml",
    ROOT / "tools" / "tools.md",
)

RULE_DEFINITION_RE = re.compile(r"(?m)^### [A-Z][A-Z0-9-]*-\d{3} — ")
AUTHORITY_DECLARATION_RE = re.compile(
    r"(?i)(?:einzige\s+autoritative\s+quelle|prim(?:a|ä)re\s+governance|"
    r"master[- ](?:regel|governance)|kernregelwerk)"
)
STATIC_HOME_IMPORT_RE = re.compile(
    r"(?im)(?:@~[/\\]|(?:import|load|lade|lies)\b[^\n]*~[/\\])"
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def current_non_bundle_markdown() -> list[Path]:
    excluded_roots = {ROOT / "docs", ROOT / "tests", BUNDLE}
    result = []
    for path in ROOT.rglob("*.md"):
        if any(root == path or root in path.parents for root in excluded_roots):
            continue
        if path == ROOT / "CHANGELOG.md":
            continue
        result.append(path)
    return sorted(result)


class SingleBootstrapSource(unittest.TestCase):
    def test_canonical_bootstrap_exists(self):
        self.assertTrue(BOOTSTRAP.is_file())

    def test_no_harness_bootstrap_sources_exist(self):
        found = sorted(
            path.relative_to(ROOT).as_posix()
            for path in ROOT.rglob("*")
            if path.is_file() and path.name in {"AGENTS.md", "CLAUDE.md"}
            and ".git" not in path.parts
        )
        self.assertEqual(found, [])

    def test_legacy_source_trees_are_absent(self):
        found = [rel for rel in LEGACY_PATHS if (ROOT / rel).exists()]
        self.assertEqual(found, [])

    def test_no_other_current_markdown_claims_governance_authority(self):
        claimants = []
        for path in current_non_bundle_markdown():
            text = read(path)
            if AUTHORITY_DECLARATION_RE.search(text) and CLUSTER4_MARKER not in text:
                claimants.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(claimants, [])

    def test_project_contract_is_explicitly_not_a_governance_source(self):
        if tomllib is None:
            self.skipTest("tomllib requires Python 3.11+")
        with (ROOT / "project.toml").open("rb") as handle:
            project = tomllib.load(handle)["project"]
        self.assertIn("not a governance source", project["description"].lower())


class LegacyReferenceContract(unittest.TestCase):
    def test_no_current_entrypoint_references_removed_sources(self):
        dangling = []
        for path in ACTIVE_REFERENCE_FILES:
            text = read(path)
            for reference in LEGACY_REFERENCES:
                if reference in text:
                    dangling.append((path.relative_to(ROOT).as_posix(), reference))
        self.assertEqual(dangling, [])

    def test_no_current_source_contains_static_home_imports(self):
        offenders = []
        for path in current_non_bundle_markdown():
            if STATIC_HOME_IMPORT_RE.search(read(path)):
                offenders.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(offenders, [])

    def test_no_stable_rule_definitions_exist_outside_bundle(self):
        offenders = []
        for path in current_non_bundle_markdown():
            if RULE_DEFINITION_RE.search(read(path)):
                offenders.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(offenders, [])

    def test_current_governance_does_not_import_historical_documents(self):
        current = [BOOTSTRAP, *sorted((BUNDLE / "agent-governance").rglob("*.md"))]
        offenders = [
            path.relative_to(ROOT).as_posix()
            for path in current
            if "docs/" in read(path) or "../docs" in read(path)
        ]
        self.assertEqual(offenders, [])


class ReferenceGraphContract(unittest.TestCase):
    def test_manifest_does_not_point_back_to_bootstrap(self):
        if tomllib is None:
            self.skipTest("tomllib requires Python 3.11+")
        with MANIFEST.open("rb") as handle:
            data = tomllib.load(handle)
        self.assertNotIn("bootstrap", data)

    def test_module_dependency_graph_is_closed_and_acyclic(self):
        if tomllib is None:
            self.skipTest("tomllib requires Python 3.11+")
        with MANIFEST.open("rb") as handle:
            modules = tomllib.load(handle)["modules"]

        visiting: list[str] = []
        visited: set[str] = set()

        def visit(name: str) -> None:
            self.assertIn(name, modules, f"unknown module: {name}")
            self.assertNotIn(name, visiting, f"cycle: {' -> '.join([*visiting, name])}")
            if name in visited:
                return
            visiting.append(name)
            for dependency in modules[name]["dependencies"]:
                visit(dependency)
            visiting.pop()
            visited.add(name)

        for module in modules:
            visit(module)


class HistoricalEvidenceContract(unittest.TestCase):
    def test_every_historical_document_is_explicitly_non_normative(self):
        missing = []
        for path in sorted((ROOT / "docs").rglob("*.md")):
            if HISTORICAL_MARKER not in "\n".join(read(path).splitlines()[:10]):
                missing.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(missing, [])


class ReleaseMetadataContract(unittest.TestCase):
    def test_source_removal_is_declared_breaking(self):
        changelog = read(ROOT / "CHANGELOG.md")
        unreleased = changelog.split("## [Unreleased]", 1)[1].split("\n## [", 1)[0]
        self.assertIn("**Breaking changes:** present", unreleased)
        self.assertRegex(unreleased, r"(?m)^- \*\*BREAKING:\*\* .+")


class Cluster4BoundaryContract(unittest.TestCase):
    def test_operational_cluster4_surface_is_preserved(self):
        required = (
            "project.toml",
            "tools/tools.md",
            "tools/Brewfile",
            "tools/Brewfile.optional",
            "tests/check_links.py",
        )
        self.assertEqual([rel for rel in required if not (ROOT / rel).is_file()], [])

    def test_operational_project_contract_remains_fail_closed(self):
        if tomllib is None:
            self.skipTest("tomllib requires Python 3.11+")
        with (ROOT / "project.toml").open("rb") as handle:
            data = tomllib.load(handle)
        self.assertEqual(data["tooling"]["resolution"], "server")
        self.assertTrue(data["tooling"]["fail_closed"])
        self.assertFalse(data["tooling"]["allow_client_local_fallbacks"])
        self.assertFalse(data["tooling"]["allow_unregistered_providers"])


class PrivateProfileMigrationGuardContract(unittest.TestCase):
    @staticmethod
    def check_ignore(path: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "check-ignore", "--no-index", "-v", "--", path],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_private_profile_path_is_ignored_by_exact_repository_rule(self):
        result = self.check_ignore("profile/profile.md")

        self.assertEqual(result.returncode, 0, result.stderr)
        rule, ignored_path = result.stdout.rstrip("\n").split("\t", 1)
        source, _line, pattern = rule.rsplit(":", 2)
        self.assertEqual(source, ".gitignore")
        self.assertEqual(pattern, "profile/profile.md")
        self.assertEqual(ignored_path, "profile/profile.md")

    def test_legacy_profile_example_remains_absent_and_visible(self):
        result = self.check_ignore("profile/profile.example.md")

        self.assertFalse((ROOT / "profile" / "profile.example.md").exists())
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_installation_status_documents_cluster_boundaries_and_guard_lifetime(self):
        install = read(ROOT / "INSTALL.md")

        self.assertRegex(install, r"(?m)^- Cluster 4: .*Control-Plane.*Tool-Allowlist")
        self.assertRegex(install, r"(?m)^- Cluster 5: .*Installer")
        self.assertRegex(install, r"(?m)^- Cluster 6: .*Nutzerregelmigration")
        self.assertRegex(
            install,
            r"profile/profile\.md[^.]*bis[^.]*Cluster 6|"
            r"(?:bis|vor)[^.]*Cluster 6[^.]*profile/profile\.md",
        )


if __name__ == "__main__":
    unittest.main()
