#!/usr/bin/env python3
"""Regression contracts for the Cluster 3 governance-source consolidation."""

from __future__ import annotations

import ast
from pathlib import Path, PurePath
import re
import shutil
import subprocess
import tarfile
import tempfile
import unittest

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - CI and this project require Python 3.11+
    tomllib = None


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "bundle"
BOOTSTRAP = BUNDLE / "GOVERNANCE.md"
MANIFEST = BUNDLE / "agent-governance" / "manifest.toml"
VENDORED_UPSTREAM = (
    ROOT / "integrations" / "microsoft-agent-governance-toolkit" / "upstream"
)
VENDORED_UPSTREAM_ARCHIVE = VENDORED_UPSTREAM / "agent-governance-toolkit-v4.1.0.tar.gz"
HISTORICAL_MARKER = "Historische Evidenz - nicht normativ"

REMOVED_LEGACY_SOURCE_TREES = (
    "adapters",
    "core",
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
    ROOT / "docs" / "installer-cli-reference.md",
    ROOT / "docs" / "harness-recipes.md",
    ROOT / "docs" / "installer-architecture.md",
    ROOT / "docs" / "installer-threat-model.md",
    ROOT / "docs" / "installer-json-schemas.md",
    ROOT / ".github" / "workflows" / "ci.yml",
)

CURRENT_REFERENCE_FILES = (
    ROOT / "docs" / "installer-cli-reference.md",
    ROOT / "docs" / "harness-recipes.md",
    ROOT / "docs" / "installer-architecture.md",
    ROOT / "docs" / "installer-threat-model.md",
    ROOT / "docs" / "installer-json-schemas.md",
)

HISTORICAL_EVIDENCE_FILES = (
    ROOT / "docs" / "adapter-audit.md",
    ROOT / "docs" / "audits" / "2026-07-30-source-migration.md",
    ROOT / "docs" / "decisions" / "0001-branch-tags-statt-agenten-praefix.md",
    ROOT / "docs" / "decisions" / "0002-vorgang-sub-pr-in-haupt-pr-branch.md",
    ROOT / "docs" / "decisions" / "0003-canonical-governance-bundle.md",
    ROOT / "docs" / "dependency-evidence.md",
    ROOT / "docs" / "superpowers" / "plans" / "2026-08-12-generic-bootstrap-enforcement.md",
    ROOT / "docs" / "superpowers" / "plans" / "2026-08-17-typed-routing-catalogs.md",
    ROOT / "docs" / "superpowers" / "plans" / "2026-08-19-copilot-qa-binding.md",
    ROOT / "docs" / "superpowers" / "plans" / "2026-08-24-global-explicit-path-installer.md",
    ROOT / "docs" / "superpowers" / "plans" / "2026-08-24-installer-security-contract-boundary.md",
    ROOT / "docs" / "superpowers" / "plans" / "2026-08-25-issue-39-documentation-architecture.md",
    ROOT / "docs" / "superpowers" / "specs" / "2026-08-12-generic-bootstrap-enforcement-design.md",
    ROOT / "docs" / "superpowers" / "specs" / "2026-08-19-copilot-qa-binding-design.md",
    ROOT / "docs" / "superpowers" / "specs" / "2026-08-24-global-explicit-path-installer-design.md",
    ROOT / "docs" / "superpowers" / "specs" / "2026-08-25-issue-39-documentation-architecture-design.md",
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
    excluded_roots = {ROOT / "docs", ROOT / "tests", BUNDLE, VENDORED_UPSTREAM}
    result = []
    for path in ROOT.rglob("*.md"):
        if any(root == path or root in path.parents for root in excluded_roots):
            continue
        if path == ROOT / "CHANGELOG.md":
            continue
        result.append(path)
    return sorted(result)


LITERAL_ALLOWED_HISTORICAL_RECORDS = (
    "docs/superpowers/specs/2026-08-25-issue-39-documentation-architecture-design.md",
    "docs/superpowers/plans/2026-08-25-issue-39-documentation-architecture.md",
)
LITERAL_PRODUCTION_PATHS = (
    "README.md",
    "docs/installer-cli-reference.md",
    "docs/harness-recipes.md",
    "docs/installer-architecture.md",
    "docs/installer-threat-model.md",
    "docs/installer-json-schemas.md",
    "tools",
    ".github/workflows",
)
LITERAL_CONTRACT_TESTS = (
    "tests/test_documentation.py",
    "tests/test_installer_distribution.py",
    "tests/test_source_consolidation.py",
    "tests/test_release_check.py",
    "tests/test_ci_workflow.py",
)
LITERAL_SCANNED_SUFFIXES = {".md", ".py", ".mjs", ".ts", ".sh", ".yml", ".yaml", ".json"}


def fixture_line_numbers(path: Path) -> set[int]:
    """Allows only the test_npm_publish_* scenario bodies as current-version fixture data."""
    if path.name != "test_ci_workflow.py":
        return set()
    tree = ast.parse(read(path), filename=str(path))
    return {
        line
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_npm_publish_")
        for line in range(node.lineno, node.end_lineno + 1)
    }


def current_version_literal_violations(root: Path, version: str) -> list[str]:
    """Finds current-version literals outside named historical records and scenario fixtures."""
    candidates: list[Path] = []
    for relative in LITERAL_PRODUCTION_PATHS:
        path = root / relative
        candidates.extend(path.rglob("*") if path.is_dir() else (path,))
    candidates.extend(root / relative for relative in LITERAL_CONTRACT_TESTS)
    violations = []
    for path in sorted(set(candidates)):
        if not path.is_file() or path.suffix not in LITERAL_SCANNED_SUFFIXES:
            continue
        allowed_lines = fixture_line_numbers(path)
        for number, line in enumerate(read(path).splitlines(), start=1):
            if version in line and number not in allowed_lines:
                violations.append(f"{path.relative_to(root).as_posix()}:{number}")
    return violations


class SingleBootstrapSource(unittest.TestCase):
    def test_canonical_bootstrap_exists(self):
        self.assertTrue(BOOTSTRAP.is_file())

    def test_no_harness_bootstrap_sources_exist(self):
        found = sorted(
            path.relative_to(ROOT).as_posix()
            for path in ROOT.rglob("*")
            if path.is_file() and path.name in {"AGENTS.md", "CLAUDE.md"}
            and ".git" not in path.parts
            and VENDORED_UPSTREAM not in path.parents
        )
        self.assertEqual(found, [])

    def test_instruction_named_dependency_files_are_confined_to_untrusted_snapshot(self):
        self.assertTrue(VENDORED_UPSTREAM_ARCHIVE.is_file())
        with tarfile.open(VENDORED_UPSTREAM_ARCHIVE, "r:gz") as archive:
            vendored = sorted(
                member.name
                for member in archive.getmembers()
                if member.isfile()
                and PurePath(member.name).name in {"AGENTS.md", "CLAUDE.md"}
            )
        self.assertTrue(vendored)
        integration_readme = read(VENDORED_UPSTREAM.parent / "README.md")
        self.assertIn("untrusted data", integration_readme)
        self.assertNotIn("integrations/", read(MANIFEST))

    def test_removed_legacy_source_trees_are_absent(self):
        found = [
            rel for rel in REMOVED_LEGACY_SOURCE_TREES if (ROOT / rel).exists()
        ]
        self.assertEqual(found, [])

    def test_no_other_current_markdown_claims_governance_authority(self):
        claimants = []
        for path in current_non_bundle_markdown():
            text = read(path)
            if AUTHORITY_DECLARATION_RE.search(text):
                claimants.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(claimants, [])

    def test_competing_operational_project_contract_is_absent(self):
        self.assertFalse((ROOT / "project.toml").exists())

    def test_bootstrap_describes_bundle_state_without_installation_context(self):
        self.assertNotRegex(read(BOOTSTRAP), r"(?i)\binstall\w*")

    def test_readme_links_the_normative_governance_owner(self):
        readme = read(ROOT / "README.md")
        self.assertIn(
            "https://github.com/tomtastisch/agent-governance/blob/main/bundle/GOVERNANCE.md",
            readme,
        )


class LegacyReferenceContract(unittest.TestCase):
    def test_no_current_entrypoint_references_removed_sources(self):
        dangling = []
        for path in ACTIVE_REFERENCE_FILES:
            if not path.is_file():
                continue
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
    def test_current_references_are_not_mislabeled_as_historical_evidence(self):
        """Catches current installer references being classified as historical snapshots."""
        missing = [
            path.relative_to(ROOT).as_posix()
            for path in CURRENT_REFERENCE_FILES
            if not path.is_file()
        ]
        self.assertEqual(missing, [])
        mislabeled = [
            path.relative_to(ROOT).as_posix()
            for path in CURRENT_REFERENCE_FILES
            if HISTORICAL_MARKER in "\n".join(read(path).splitlines()[:10])
        ]
        self.assertEqual(mislabeled, [])

    def test_historical_evidence_inventory_keeps_its_non_normative_marker(self):
        """Catches genuine historical evidence being reclassified as a current reference."""
        missing = [
            path.relative_to(ROOT).as_posix()
            for path in HISTORICAL_EVIDENCE_FILES
            if not path.is_file()
        ]
        self.assertEqual(missing, [])
        unmarked = [
            path.relative_to(ROOT).as_posix()
            for path in HISTORICAL_EVIDENCE_FILES
            if HISTORICAL_MARKER not in "\n".join(read(path).splitlines()[:10])
        ]
        self.assertEqual(unmarked, [])

class ReleaseMetadataContract(unittest.TestCase):
    def test_current_version_declares_documentation_release(self):
        changelog = read(ROOT / "CHANGELOG.md")
        version = read(ROOT / "VERSION").strip()
        current = changelog.split(f"## [{version}]", 1)[1].split("\n## [", 1)[0]
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
        recovery_patch = changelog.split("## [0.4.1]", 1)[1].split("\n## [", 1)[0]
        self.assertIn("**Breaking changes:** none", recovery_patch)
        historical = changelog.split("## [0.4.0]", 1)[1].split("\n## [", 1)[0]
        self.assertIn("**Breaking changes:** present", historical)
        self.assertIn("**BREAKING:**", historical)
        for catalog in ("triggers", "policy-tags", "scopes", "tools"):
            self.assertIn(f"catalogs/{catalog}.toml", historical)

    def test_current_version_literal_is_limited_to_derived_or_historical_records(self):
        """Catches a current-version literal in a named current surface, not whole source trees."""
        current_version = read(ROOT / "VERSION").strip()
        self.assertEqual(current_version_literal_violations(ROOT, current_version), [])
        for relative in LITERAL_ALLOWED_HISTORICAL_RECORDS:
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_literal_drift_catches_productive_extensions_and_nonfixture_test_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            version = "7.8.9"
            for suffix in (".mjs", ".ts", ".sh"):
                path = root / "tools" / f"productive{suffix}"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"const version = '{version}';\n", encoding="utf-8")
            test_path = root / "tests" / "test_ci_workflow.py"
            test_path.parent.mkdir(parents=True, exist_ok=True)
            test_path.write_text(f"value = '{version}'\n", encoding="utf-8")
            distribution_test = root / "tests" / "test_installer_distribution.py"
            distribution_test.write_text(f"value = '{version}'\n", encoding="utf-8")

            violations = current_version_literal_violations(root, version)

        self.assertEqual(
            violations,
            [
                "tests/test_ci_workflow.py:1",
                "tests/test_installer_distribution.py:1",
                "tools/productive.mjs:1",
                "tools/productive.sh:1",
                "tools/productive.ts:1",
            ],
        )

    def test_unreleased_is_reset_after_version_classification(self):
        changelog = read(ROOT / "CHANGELOG.md")
        unreleased = changelog.split("## [Unreleased]", 1)[1].split("\n## [", 1)[0]
        self.assertIn("**Breaking changes:** none", unreleased)
        self.assertNotIn("**BREAKING:**", unreleased)

    def test_published_recovery_patch_remains_unchanged(self):
        changelog = read(ROOT / "CHANGELOG.md")
        published = changelog.split("## [0.3.2]", 1)[1].split("\n## [", 1)[0]
        self.assertIn("**Breaking changes:** none", published)
        self.assertNotIn("**BREAKING:**", published)
        for recovery_term in ("Allowed-Signers", "fingerprint", "Signatur", "v0.3.1"):
            self.assertIn(recovery_term, published)


class PrivateProfileMigrationGuardContract(unittest.TestCase):
    @staticmethod
    def check_ignore(path: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory(prefix="agent-governance-ignore-") as directory:
            repository = Path(directory)
            shutil.copy2(ROOT / ".gitignore", repository / ".gitignore")
            subprocess.run(
                ["git", "-c", "init.defaultBranch=master", "init", "--quiet"],
                cwd=repository,
                check=True,
                capture_output=True,
                text=True,
            )
            return subprocess.run(
                ["git", "check-ignore", "--no-index", "-v", "--", path],
                cwd=repository,
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

    def test_current_documentation_rejects_future_operational_clusters(self):
        changelog = read(ROOT / "CHANGELOG.md")
        unreleased = changelog.split("## [Unreleased]", 1)[1].split("\n## [", 1)[0]
        numbered_cluster = re.compile(r"(?i)Cluster\s+\d+")
        future_operation = re.compile(
            r"(?im)^(?=[^\n]*(?:Installer|Migration))"
            r"(?=[^\n]*(?:künftig\w*|später\w*|ausstehend\w*|vorgesehen))[^\n]+$"
        )
        current_documents = {
            "README.md": read(ROOT / "README.md"),
            "CHANGELOG.md [Unreleased]": unreleased,
        }
        for name, text in current_documents.items():
            self.assertNotRegex(text, numbered_cluster, name)
            self.assertNotRegex(text, future_operation, name)
        self.assertRegex("Cluster 7 Installer", numbered_cluster)
        self.assertRegex("Ein Installer ist künftig vorgesehen", future_operation)


if __name__ == "__main__":
    unittest.main()
