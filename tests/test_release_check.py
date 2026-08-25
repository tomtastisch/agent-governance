#!/usr/bin/env python3
"""Tests für tools/release_check.py — Tree-, Tag- und Release-Konsistenz.

Alle Tests verwenden synthetische Fixtures (tempfile.TemporaryDirectory) für reproduzierbare
Negativ-/Positivszenarien. Keine echten Tags oder GitHub-Releases werden erzeugt.

Abdeckung:
  Cluster A: Tag-Auflösung, Peel, Signaturprüfung, deterministische Tag-Wahl
  Cluster B: CHANGELOG-Abschnittsweise Validierung (kein Cross-Section-Leak)
  Cluster C: Release-Modus via injizierte gh-Ausgaben
  Cluster D: README-Dokumentlinks/VERSION fail-closed
"""

import base64
import inspect
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools.release_check as release_check  # noqa: E402

from tools.release_check import (  # noqa: E402
    CheckResult, GitRunner, GhRunner,
    check_tree, check_tag, check_release,
    _is_valid_semver, _split_changelog_sections, _parse_section,
    _semver_cmp, _resolve_target_commitish,
    REQUIRED_CATEGORIES,
)


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


_CHANGELOG_MIN = (
    "## [Unreleased]\n### Added\n- item\n### Changed\n- Keine.\n"
    "### Fixed\n- Keine.\n### Removed\n- Keine.\n\n**Breaking changes:** none\n\n"
    "## [0.1.0] — 2026-07-27\n### Added\n- item\n### Changed\n- Keine.\n"
    "### Fixed\n- Keine.\n### Removed\n- Keine.\n\n**Breaking changes:** none\n"
)

_CANONICAL_DOCUMENT_PATHS = (
    "docs/installer-cli-reference.md",
    "docs/harness-recipes.md",
    "docs/installer-architecture.md",
    "docs/installer-threat-model.md",
    "docs/installer-json-schemas.md",
    "CHANGELOG.md",
    "bundle/GOVERNANCE.md",
)
_BLOB_MAIN = "https://github.com/tomtastisch/agent-governance/blob/main"


def _canonical_readme(overrides=None, omitted=(), extra=(), raw_lines=()):
    overrides = overrides or {}
    lines = ["# Fixture", "", "## Dokumentation", ""]
    for path in _CANONICAL_DOCUMENT_PATHS:
        if path not in omitted:
            lines.append(f"- [{path}]({overrides.get(path, f'{_BLOB_MAIN}/{path}')})")
    lines.extend(f"- [extra]({url})" for url in extra)
    lines.extend(raw_lines)
    lines.extend(("", "## Support und Lizenz", "", "[Support](https://example.com/support)", ""))
    return "\n".join(lines)


def _write_documentation_tree(root, readme=None):
    _write(os.path.join(root, "README.md"), readme or _canonical_readme())
    version = "0.1.0"
    version_path = os.path.join(root, "VERSION")
    if os.path.exists(version_path):
        with open(version_path, encoding="utf-8") as handle:
            version = handle.read().strip()
    _write(os.path.join(root, "package.json"), json.dumps({"version": version}))
    _write(
        os.path.join(root, "package-lock.json"),
        json.dumps({"version": version, "packages": {"": {"version": version}}}),
    )
    for path in _CANONICAL_DOCUMENT_PATHS:
        if path != "CHANGELOG.md":
            _write(os.path.join(root, path), f"fixture for {path}\n")

_RELEASE_SIGNER_PRINCIPAL = "82227609+tomtastisch@users.noreply.github.com"
_RELEASE_SIGNER_KEY = (
    "AAAAC3NzaC1lZDI1NTE5AAAAIJJqgiZKUWTznfSu2g34z5dJoK0GLqv+fiIX/i6hzYCB"
)
_RELEASE_ALLOWED_SIGNER = (
    f'{_RELEASE_SIGNER_PRINCIPAL} namespaces="git" '
    f"ssh-ed25519 {_RELEASE_SIGNER_KEY}\n"
)


# ═══════════════════════════════════════════════════════════════════════
# Unit
# ═══════════════════════════════════════════════════════════════════════

class SemVerParsing(unittest.TestCase):
    def test_valid_versions(self):
        for v in ("0.0.0", "0.1.0", "1.0.0", "10.20.30", "0.1.0-alpha", "0.1.0-alpha.1",
                  "1.0.0+build.1", "1.0.0-alpha+001"):
            self.assertTrue(_is_valid_semver(v), f"'{v}' sollte gültig sein")

    def test_invalid_versions(self):
        for v in ("1", "1.0", "01.0.0", "1.0.0-", "v1.0.0", "abc", ""):
            self.assertFalse(_is_valid_semver(v), f"'{v}' sollte ungültig sein")


class SemVerCmp(unittest.TestCase):
    def test_ordering(self):
        self.assertGreater(_semver_cmp("1.0.0", "0.9.0"), 0)
        self.assertGreater(_semver_cmp("0.2.0", "0.1.0"), 0)
        self.assertEqual(_semver_cmp("0.1.0", "0.1.0"), 0)
        self.assertLess(_semver_cmp("0.1.0", "0.2.0"), 0)

    def test_prerelease_precedence(self):
        self.assertGreater(_semver_cmp("1.0.0-rc.2", "1.0.0-rc.1"), 0)
        self.assertGreater(_semver_cmp("1.0.0-rc.10", "1.0.0-rc.2"), 0)
        self.assertGreater(_semver_cmp("1.0.0", "1.0.0-rc.2"), 0)
        self.assertLess(_semver_cmp("1.0.0-rc.2", "1.0.0"), 0)
        self.assertLess(_semver_cmp("1.0.0-1", "1.0.0-alpha"), 0)
        self.assertLess(_semver_cmp("1.0.0-alpha", "1.0.0-alpha.1"), 0)
        self.assertEqual(_semver_cmp("1.0.0+build.1", "1.0.0+build.2"), 0)


# ═══════════════════════════════════════════════════════════════════════
# Cluster D: VERSION
# ═══════════════════════════════════════════════════════════════════════

class TreeVersionMissing(unittest.TestCase):
    def test_version_missing_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            r = check_tree(root=d)
            self.assertFalse(r.ok)
            self.assertTrue(any("VERSION fehlt" in e for e in r.errors))


class TreeVersionForm(unittest.TestCase):
    def test_empty_version_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "VERSION"), "\n")
            r = check_tree(root=d)
            self.assertFalse(r.ok)
            self.assertTrue(any("exakt" in e for e in r.errors))

    def test_multiline_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "VERSION"), "0.1.0\nextra text\n")
            r = check_tree(root=d)
            self.assertFalse(r.ok)
            self.assertTrue(any("exakt" in e for e in r.errors))

    def test_whitespace_blank_lines_and_crlf_are_errors(self):
        for raw in (" 0.1.0\n", "0.1.0 \n", "0.1.0\n\n", "0.1.0\r\n"):
            with self.subTest(raw=repr(raw)):
                with tempfile.TemporaryDirectory() as d:
                    _write(os.path.join(d, "VERSION"), raw)

                    r = check_tree(root=d)

                self.assertFalse(r.ok)
                self.assertTrue(any("exakt" in error or "gültiges SemVer" in error for error in r.errors), r.errors)

    def test_bad_semver_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "VERSION"), "not.a.version\n")
            r = check_tree(root=d)
            self.assertFalse(r.ok)
            self.assertTrue(any("exakt" in e for e in r.errors))

    def test_single_line_with_newline_is_ok(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "VERSION"), "0.1.0\n")
            _write(os.path.join(d, "CHANGELOG.md"), _CHANGELOG_MIN)
            _write_documentation_tree(d)
            r = check_tree(root=d)
            self.assertTrue(r.ok, f"Erwartet OK, Fehler: {r.errors}")


# ═══════════════════════════════════════════════════════════════════════
# Cluster D: Konkurrierende Quelle
# ═══════════════════════════════════════════════════════════════════════

class TreeCompetingSource(unittest.TestCase):
    def _write_minimum_tree(self, root):
        _write(os.path.join(root, "VERSION"), "0.1.0\n")
        _write(os.path.join(root, "CHANGELOG.md"), _CHANGELOG_MIN)
        _write_documentation_tree(root)

    def test_toml_version_is_competing(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "VERSION"), "0.1.0\n")
            _write(os.path.join(d, "config.toml"), 'version = "0.2.0"\n')
            r = check_tree(root=d)
            self.assertFalse(r.ok)
            self.assertTrue(any("konkurrierende version-Deklaration" in e for e in r.errors))

    def test_root_package_version_must_match_version_source(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_minimum_tree(d)
            _write(os.path.join(d, "package.json"), '{"version": "0.2.0"}')
            r = check_tree(root=d)
            self.assertFalse(r.ok)
            self.assertTrue(any("package.json" in e and "VERSION" in e for e in r.errors))

    def test_matching_root_package_version_is_derived_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_minimum_tree(d)
            _write(os.path.join(d, "package.json"), '{"version": "0.1.0"}')
            r = check_tree(root=d)
            self.assertTrue(r.ok, r.errors)

    def test_matching_root_lock_version_is_derived_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_minimum_tree(d)
            _write(
                os.path.join(d, "package-lock.json"),
                '{"version": "0.1.0", "packages": {"": {"version": "0.1.0"}}}',
            )
            r = check_tree(root=d)
            self.assertTrue(r.ok, r.errors)

    def test_root_lock_version_drift_fails(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_minimum_tree(d)
            _write(os.path.join(d, "package-lock.json"), '{"version": "0.2.0"}')
            r = check_tree(root=d)
            self.assertFalse(r.ok)
            self.assertTrue(any("package-lock.json" in e and "VERSION" in e for e in r.errors))

    def test_root_lock_package_version_drift_fails(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_minimum_tree(d)
            _write(
                os.path.join(d, "package-lock.json"),
                '{"version": "0.1.0", "packages": {"": {"version": "0.2.0"}}}',
            )
            r = check_tree(root=d)
            self.assertFalse(r.ok)
            self.assertTrue(any("Root-Paketversion" in e for e in r.errors), r.errors)

    def test_missing_root_lock_package_structure_fails(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_minimum_tree(d)
            _write(os.path.join(d, "package-lock.json"), '{"version": "0.1.0"}')
            r = check_tree(root=d)
            self.assertFalse(r.ok)
            self.assertTrue(any("Root-Paketstruktur" in e for e in r.errors), r.errors)

    def test_parallel_version_file_is_competing(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "VERSION"), "0.1.0\n")
            _write(os.path.join(d, "version.txt"), "0.2.0")
            r = check_tree(root=d)
            self.assertFalse(r.ok)
            self.assertTrue(any("parallele Versionsdatei" in e for e in r.errors))

    def test_pinned_vendor_snapshot_versions_are_dependency_data(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_minimum_tree(d)
            integration = os.path.join(
                d, "integrations", "microsoft-agent-governance-toolkit"
            )
            _write(os.path.join(integration, "upstream.lock.toml"), 'resolved_tag = "v4.1.0"\n')
            _write(os.path.join(integration, "snapshot.files.sha256"), "synthetic fixture\n")
            _write(os.path.join(integration, "upstream", "package.json"), '{"version": "4.1.0"}')

            r = check_tree(root=d)

            self.assertTrue(r.ok, f"Erwartet OK, Fehler: {r.errors}")

    def test_unpinned_vendor_lookalike_version_remains_competing(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_minimum_tree(d)
            _write(
                os.path.join(
                    d,
                    "integrations",
                    "microsoft-agent-governance-toolkit",
                    "upstream",
                    "package.json",
                ),
                '{"version": "4.1.0"}',
            )

            r = check_tree(root=d)

            self.assertFalse(r.ok)
            self.assertTrue(any("konkurrierende version-Deklaration" in e for e in r.errors))

    def test_integration_bridge_version_remains_competing(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_minimum_tree(d)
            integration = os.path.join(
                d, "integrations", "microsoft-agent-governance-toolkit"
            )
            _write(os.path.join(integration, "upstream.lock.toml"), 'resolved_tag = "v4.1.0"\n')
            _write(os.path.join(integration, "snapshot.files.sha256"), "synthetic fixture\n")
            _write(os.path.join(integration, "bridge", "package.json"), '{"version": "0.1.0"}')

            r = check_tree(root=d)

            self.assertFalse(r.ok)
            self.assertTrue(any("konkurrierende version-Deklaration" in e for e in r.errors))


# ═══════════════════════════════════════════════════════════════════════
# Cluster B: CHANGELOG abschnittsweise
# ═══════════════════════════════════════════════════════════════════════

class ChangelogSectionParsing(unittest.TestCase):
    def test_split_sections(self):
        cl = "## [Unreleased]\n### Added\n- x\n\n## [0.1.0]\n### Added\n- y\n"
        sections = _split_changelog_sections(cl)
        self.assertEqual(len(sections), 2)

    def test_parse_section(self):
        meta = _parse_section("## [Unreleased]", "### Added\n- item\n\n**Breaking changes:** none\n")
        self.assertIn("Added", meta["categories"])
        self.assertEqual(meta["marker"], "none")
        self.assertFalse(meta["has_breaking_entries"])


class TreeChangelogSections(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.root = self.d.name
        _write(os.path.join(self.root, "VERSION"), "0.1.0\n")
        _write_documentation_tree(self.root)

    def tearDown(self):
        self.d.cleanup()

    def _cl(self, body):
        _write(os.path.join(self.root, "CHANGELOG.md"), body)

    def test_unreleased_before_release_is_ok(self):
        self._cl(_CHANGELOG_MIN)
        r = check_tree(root=self.root)
        self.assertTrue(r.ok, f"Erwartet OK, Fehler: {r.errors}")

    def test_release_before_unreleased_is_error(self):
        self._cl("## [0.1.0] — 2026-07-27\n### Added\n- history\n\n**Breaking changes:** none\n\n" + _CHANGELOG_MIN)
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("muss vor versionierten" in e for e in r.errors))

    def test_duplicate_unreleased_is_error(self):
        self._cl(_CHANGELOG_MIN + "\n" + _CHANGELOG_MIN)
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("[Unreleased]-Abschnitte" in e for e in r.errors))

    def test_no_unreleased_is_error(self):
        self._cl("## [0.1.0] — 2026-07-27\n### Added\n- history\n\n**Breaking changes:** none\n")
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("[Unreleased]-Abschnitt fehlt" in e for e in r.errors))

    def test_semver_order_descending_is_ok(self):
        _write(os.path.join(self.root, "VERSION"), "0.2.0\n")
        _write_documentation_tree(self.root)
        self._cl(
            "## [Unreleased]\n### Added\n- item\n### Changed\n- Keine.\n"
            "### Fixed\n- Keine.\n### Removed\n- Keine.\n\n**Breaking changes:** none\n\n"
            "## [0.2.0] — 2026-08-01\n### Added\n- newer\n### Changed\n- Keine.\n"
            "### Fixed\n- Keine.\n### Removed\n- Keine.\n\n**Breaking changes:** none\n\n"
            "## [0.1.0] — 2026-07-27\n### Added\n- older\n\n**Breaking changes:** none\n"
        )
        r = check_tree(root=self.root)
        self.assertTrue(r.ok, f"Erwartet OK, Fehler: {r.errors}")

    def test_current_release_requires_an_iso_date(self):
        self._cl(
            "## [Unreleased]\n### Added\n- Keine.\n### Changed\n- Keine.\n"
            "### Fixed\n- Keine.\n### Removed\n- Keine.\n\n**Breaking changes:** none\n\n"
            "## [0.1.0]\n### Added\n- history\n### Changed\n- Keine.\n"
            "### Fixed\n- Keine.\n### Removed\n- Keine.\n\n**Breaking changes:** none\n"
        )
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("gültiges ISO-Datum" in e for e in r.errors), r.errors)

    def test_current_release_requires_all_categories(self):
        self._cl(
            "## [Unreleased]\n### Added\n- Keine.\n### Changed\n- Keine.\n"
            "### Fixed\n- Keine.\n### Removed\n- Keine.\n\n**Breaking changes:** none\n\n"
            "## [0.1.0] — 2026-07-27\n### Added\n- history\n\n**Breaking changes:** none\n"
        )
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("erforderliche Kategorien" in e for e in r.errors), r.errors)

    def test_current_release_must_be_unique(self):
        self._cl(
            _CHANGELOG_MIN + "\n"
            "## [0.1.0] — 2026-07-28\n### Added\n- duplicate\n### Changed\n- Keine.\n"
            "### Fixed\n- Keine.\n### Removed\n- Keine.\n\n**Breaking changes:** none\n"
        )
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("genau einen aktuellen Abschnitt" in error for error in r.errors), r.errors)

    def test_current_release_must_be_the_first_versioned_section(self):
        self._cl(
            "## [Unreleased]\n### Added\n- item\n### Changed\n- Keine.\n"
            "### Fixed\n- Keine.\n### Removed\n- Keine.\n\n**Breaking changes:** none\n\n"
            "## [0.2.0] — 2026-08-01\n### Added\n- newer\n\n**Breaking changes:** none\n\n"
            "## [0.1.0] — 2026-07-27\n### Added\n- current\n### Changed\n- Keine.\n"
            "### Fixed\n- Keine.\n### Removed\n- Keine.\n\n**Breaking changes:** none\n"
        )
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("erste versionierte" in error for error in r.errors), r.errors)

    def test_semver_order_ascending_is_error(self):
        self._cl(
            _CHANGELOG_MIN + "\n"
            "## [0.1.0] — 2026-07-27\n### Added\n- old\n\n**Breaking changes:** none\n\n"
            "## [0.2.0] — 2026-08-01\n### Added\n- new\n\n**Breaking changes:** none\n"
        )
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("absteigend" in e for e in r.errors))

    def test_release_section_present_without_breaking_entry_is_error(self):
        """Release-Sektion mit 'present' aber ohne BREAKING-Eintrag → Fehler."""
        self._cl(
            _CHANGELOG_MIN + "\n"
            "## [0.2.0] — 2026-08-01\n### Added\n- item\n### Changed\n- Keine.\n"
            "**Breaking changes:** present\n"
        )
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("present" in e and "BREAKING:" in e for e in r.errors))


class TreeChangelogCrossSectionLeak(unittest.TestCase):
    """Greptile-Finding #2: Breaking-Marker dürfen nicht abschnittsübergreifend leaken."""

    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.root = self.d.name
        _write(os.path.join(self.root, "VERSION"), "0.2.0\n")

    def tearDown(self):
        self.d.cleanup()

    def test_unreleased_missing_marker_not_rescued_by_release(self):
        """[Unreleased] ohne Marker, Release hat Marker → Fehler für [Unreleased]."""
        _write(os.path.join(self.root, "CHANGELOG.md"),
            "## [Unreleased]\n### Added\n- new\n### Changed\n- Keine.\n"
            "### Fixed\n- Keine.\n### Removed\n- Keine.\n\n"  # Kein Marker hier!
            "## [0.1.0] — 2026-07-27\n### Added\n- old\n\n**Breaking changes:** none\n"
        )
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("fehlt der Marker" in e for e in r.errors))

    def test_unreleased_present_not_rescued_by_release_breaking_entry(self):
        """[Unreleased] mit present aber ohne BREAKING-Eintrag,
        Release hat BREAKING-Eintrag → Fehler für [Unreleased]."""
        _write(os.path.join(self.root, "CHANGELOG.md"),
            "## [Unreleased]\n### Added\n- new\n### Changed\n- Keine.\n"
            "### Fixed\n- Keine.\n### Removed\n- Keine.\n\n"
            "**Breaking changes:** present\n\n"
            "## [0.1.0] — 2026-07-27\n### Changed\n- **BREAKING:** old API\n\n"
            "**Breaking changes:** present\n"
        )
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("kein Eintrag mit" in e for e in r.errors))


# ═══════════════════════════════════════════════════════════════════════
# Cluster D: kanonische README-Dokumentlinks
# ═══════════════════════════════════════════════════════════════════════

class TreeDocumentLinks(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.root = self.d.name
        _write(os.path.join(self.root, "VERSION"), "0.1.0\n")
        _write(os.path.join(self.root, "CHANGELOG.md"), _CHANGELOG_MIN)
        _write_documentation_tree(self.root)

    def tearDown(self):
        self.d.cleanup()

    def test_exact_canonical_links_with_deleted_install_are_ok(self):
        r = check_tree(root=self.root)
        self.assertTrue(r.ok, f"Erwartet OK, Fehler: {r.errors}")

    def test_wrong_host_is_error(self):
        path = _CANONICAL_DOCUMENT_PATHS[0]
        _write_documentation_tree(
            self.root,
            _canonical_readme({path: f"https://example.com/tomtastisch/agent-governance/blob/main/{path}"}),
        )
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("Host" in error for error in r.errors), r.errors)

    def test_non_https_scheme_is_error(self):
        path = _CANONICAL_DOCUMENT_PATHS[0]
        _write_documentation_tree(
            self.root,
            _canonical_readme({path: f"http://github.com/tomtastisch/agent-governance/blob/main/{path}"}),
        )
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("https" in error for error in r.errors), r.errors)

    def test_wrong_owner_or_repository_is_error(self):
        path = _CANONICAL_DOCUMENT_PATHS[0]
        for repository in ("other/agent-governance", "tomtastisch/other"):
            with self.subTest(repository=repository):
                _write_documentation_tree(
                    self.root,
                    _canonical_readme({path: f"https://github.com/{repository}/blob/main/{path}"}),
                )
                r = check_tree(root=self.root)
                self.assertFalse(r.ok)
                self.assertTrue(any("Owner/Repository" in error for error in r.errors), r.errors)

    def test_non_main_ref_is_error(self):
        path = _CANONICAL_DOCUMENT_PATHS[0]
        _write_documentation_tree(
            self.root,
            _canonical_readme({path: f"https://github.com/tomtastisch/agent-governance/blob/dev/{path}"}),
        )
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("main-Ref" in error for error in r.errors), r.errors)

    def test_non_blob_github_view_is_error(self):
        path = _CANONICAL_DOCUMENT_PATHS[0]
        _write_documentation_tree(
            self.root,
            _canonical_readme({path: f"https://github.com/tomtastisch/agent-governance/tree/main/{path}"}),
        )
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("blob-Ansicht" in error for error in r.errors), r.errors)

    def test_missing_canonical_path_is_error(self):
        missing = _CANONICAL_DOCUMENT_PATHS[0]
        _write_documentation_tree(self.root, _canonical_readme(omitted=(missing,)))
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any(missing in error and "fehlt" in error for error in r.errors), r.errors)

    def test_duplicate_canonical_path_is_error(self):
        path = _CANONICAL_DOCUMENT_PATHS[0]
        _write_documentation_tree(
            self.root,
            _canonical_readme(extra=(f"{_BLOB_MAIN}/{path}",)),
        )
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any(path in error and "mehrfach" in error for error in r.errors), r.errors)

    def test_unsupported_markdown_link_forms_cannot_hide_extra_links(self):
        cases = {
            "title": ('- [extra](https://example.com/docs "title")',),
            "reference": (
                "- [extra][external-doc]",
                "[external-doc]: https://example.com/docs",
            ),
            "autolink": ("- <https://example.com/docs>",),
        }
        for name, lines in cases.items():
            with self.subTest(name=name):
                _write_documentation_tree(
                    self.root,
                    _canonical_readme(raw_lines=lines),
                )
                r = check_tree(root=self.root)
                self.assertFalse(r.ok)
                self.assertTrue(
                    any("Markdown-Grammatik" in error for error in r.errors),
                    r.errors,
                )

    def test_unexpected_document_path_is_error(self):
        expected = _CANONICAL_DOCUMENT_PATHS[0]
        unexpected = "docs/unexpected.md"
        _write(os.path.join(self.root, unexpected), "unexpected\n")
        _write_documentation_tree(
            self.root,
            _canonical_readme({expected: f"{_BLOB_MAIN}/{unexpected}"}),
        )
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any(unexpected in error and "unerwartet" in error for error in r.errors), r.errors)

    def test_query_and_fragment_tricks_are_errors(self):
        path = _CANONICAL_DOCUMENT_PATHS[0]
        for suffix in ("?ref=dev", "#../INSTALL.md"):
            with self.subTest(suffix=suffix):
                _write_documentation_tree(
                    self.root,
                    _canonical_readme({path: f"{_BLOB_MAIN}/{path}{suffix}"}),
                )
                r = check_tree(root=self.root)
                self.assertFalse(r.ok)
                self.assertTrue(any("Query/Fragment" in error for error in r.errors), r.errors)

    def test_encoded_and_plain_path_traversal_are_errors(self):
        path = _CANONICAL_DOCUMENT_PATHS[0]
        for target in (
            f"{_BLOB_MAIN}/docs/%2e%2e/CHANGELOG.md",
            f"{_BLOB_MAIN}/docs/../CHANGELOG.md",
        ):
            with self.subTest(target=target):
                _write_documentation_tree(self.root, _canonical_readme({path: target}))
                r = check_tree(root=self.root)
                self.assertFalse(r.ok)
                self.assertTrue(any("Pfad" in error for error in r.errors), r.errors)

    def test_url_case_userinfo_port_and_backslash_are_errors(self):
        path = _CANONICAL_DOCUMENT_PATHS[0]
        cases = {
            "host-case": f"https://GitHub.com/tomtastisch/agent-governance/blob/main/{path}",
            "userinfo": f"https://user@github.com/tomtastisch/agent-governance/blob/main/{path}",
            "port": f"https://github.com:443/tomtastisch/agent-governance/blob/main/{path}",
            "backslash": "https://github.com/tomtastisch/agent-governance/blob/main/"
            "docs\\installer-cli-reference.md",
        }
        for name, url in cases.items():
            with self.subTest(name=name):
                _write_documentation_tree(
                    self.root,
                    _canonical_readme({path: url}),
                )
                r = check_tree(root=self.root)
                self.assertFalse(r.ok, f"{name} darf den exakten URL-Vertrag nicht erfüllen")

    def test_retired_install_file_is_error(self):
        _write(os.path.join(self.root, "INSTALL.md"), "retired\n")
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("INSTALL.md" in error and "entfernt" in error for error in r.errors), r.errors)

    def test_stale_docs_images_directory_is_error(self):
        _write(os.path.join(self.root, "docs", "images", "stale.png"), "stale\n")
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("docs/images" in error for error in r.errors), r.errors)

    def test_missing_local_target_is_error(self):
        missing = _CANONICAL_DOCUMENT_PATHS[0]
        os.unlink(os.path.join(self.root, missing))
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any(missing in error and "lokales Ziel fehlt" in error for error in r.errors), r.errors)

    def test_local_target_must_resolve_beneath_repository(self):
        path = _CANONICAL_DOCUMENT_PATHS[0]
        os.unlink(os.path.join(self.root, path))
        outside = os.path.join(self.d.name + "-outside.md")
        try:
            _write(outside, "outside\n")
            os.symlink(outside, os.path.join(self.root, path))
            r = check_tree(root=self.root)
            self.assertFalse(r.ok)
            self.assertTrue(any(path in error and "Repository" in error for error in r.errors), r.errors)
        finally:
            if os.path.exists(outside):
                os.unlink(outside)

    def test_in_repository_document_target_symlink_is_error(self):
        path = _CANONICAL_DOCUMENT_PATHS[0]
        target = os.path.join(self.root, path)
        actual = os.path.join(self.root, "docs", "installer-cli-reference.actual.md")
        os.rename(target, actual)
        os.symlink(os.path.basename(actual), target)

        r = check_tree(root=self.root)

        self.assertFalse(r.ok)
        self.assertTrue(any(path in error and "Symlink" in error for error in r.errors), r.errors)

    def test_readme_must_resolve_beneath_repository(self):
        readme = os.path.join(self.root, "README.md")
        os.unlink(readme)
        outside = os.path.join(self.d.name + "-outside-readme.md")
        try:
            _write(outside, _canonical_readme())
            os.symlink(outside, readme)
            r = check_tree(root=self.root)
            self.assertFalse(r.ok)
            self.assertTrue(any("README.md" in error and "Repository" in error for error in r.errors), r.errors)
        finally:
            if os.path.exists(outside):
                os.unlink(outside)

    def test_in_repository_readme_symlink_is_error(self):
        readme = os.path.join(self.root, "README.md")
        actual = os.path.join(self.root, "README.actual.md")
        os.rename(readme, actual)
        os.symlink(os.path.basename(actual), readme)

        r = check_tree(root=self.root)

        self.assertFalse(r.ok)
        self.assertTrue(any("README.md" in error and "Symlink" in error for error in r.errors), r.errors)


class DocsRemoteCli(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.commands = os.path.join(self.d.name, "commands")
        os.makedirs(self.commands)
        self.log = os.path.join(self.d.name, "gh.log")
        self.script = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "tools",
            "release_check.py",
        )
        self.repository = os.path.dirname(os.path.dirname(self.script))

    def tearDown(self):
        self.d.cleanup()

    @staticmethod
    def _success_response_script(prefix=""):
        return (
            "#!/bin/sh\n"
            "printf '%s|%s|%s\\n' \"$#\" \"$1\" \"$2\" >> \"$GH_LOG\"\n"
            f"{prefix}"
            "path=${2#repos/tomtastisch/agent-governance/contents/}\n"
            "path=${path%?ref=main}\n"
            "name=${path##*/}\n"
            "printf '{\"name\":\"%s\",\"path\":\"%s\",\"sha\":\"fixture\","
            "\"size\":1,\"url\":\"https://api.github.test/content\","
            "\"html_url\":\"https://github.test/content\","
            "\"git_url\":\"https://api.github.test/git\","
            "\"download_url\":\"https://raw.github.test/content\","
            "\"type\":\"file\",\"content\":\"Zml4dHVyZQ==\","
            "\"encoding\":\"base64\",\"_links\":{\"self\":\"self\","
            "\"git\":\"git\",\"html\":\"html\"}}\\n' \"$name\" \"$path\"\n"
        )

    @staticmethod
    def _fixed_response_script(response):
        return (
            "#!/bin/sh\n"
            "printf '%s|%s|%s\\n' \"$#\" \"$1\" \"$2\" >> \"$GH_LOG\"\n"
            f"printf '%s\\n' '{response}'\n"
        )

    def _run(self, fake_gh=None, command=None):
        if fake_gh is not None:
            gh = os.path.join(self.commands, "gh")
            _write(gh, fake_gh)
            os.chmod(gh, 0o700)
        return subprocess.run(
            command or [sys.executable, self.script, "docs-remote"],
            cwd=self.repository,
            env={
                **os.environ,
                "PATH": self.commands,
                "GH_LOG": self.log,
            },
            capture_output=True,
            text=True,
            check=False,
        )

    def test_checks_every_canonical_path_with_one_argument_safe_endpoint(self):
        result = self._run(self._success_response_script())
        self.assertEqual(result.returncode, 0, result.stderr)
        with open(self.log, encoding="utf-8") as handle:
            calls = handle.read().splitlines()
        self.assertEqual(
            calls,
            [
                "2|api|repos/tomtastisch/agent-governance/contents/"
                f"{path}?ref=main"
                for path in _CANONICAL_DOCUMENT_PATHS
            ],
        )

    def test_missing_gh_cli_fails_closed(self):
        result = self._run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("gh CLI nicht verfügbar", result.stderr)

    def test_api_error_fails_closed_without_skipping_remaining_paths(self):
        failed_path = _CANONICAL_DOCUMENT_PATHS[2]
        result = self._run(
            self._success_response_script(
                f"case \"$2\" in *{failed_path}*) "
                "echo 'synthetic API failure' >&2; exit 1;; esac\n"
            )
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(failed_path, result.stderr)
        self.assertIn("synthetic API failure", result.stderr)
        with open(self.log, encoding="utf-8") as handle:
            calls = handle.read().splitlines()
        self.assertEqual(len(calls), len(_CANONICAL_DOCUMENT_PATHS))

    def test_empty_success_response_fails_closed(self):
        result = self._run(self._fixed_response_script(""))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ungültige JSON-Antwort", result.stderr)

    def test_malformed_success_response_fails_closed(self):
        result = self._run(self._fixed_response_script("not-json"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ungültige JSON-Antwort", result.stderr)

    def test_array_success_response_fails_closed(self):
        result = self._run(self._fixed_response_script("[]"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Dateiobjekt", result.stderr)

    def test_directory_success_response_fails_closed(self):
        result = self._run(
            self._fixed_response_script(
                '{"type":"dir","path":"docs/installer-cli-reference.md"}'
            )
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("type", result.stderr)

    def test_path_mismatch_success_response_fails_closed(self):
        result = self._run(
            self._fixed_response_script(
                '{"type":"file","path":"docs/unexpected.md"}'
            )
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("path", result.stderr)

    def test_timeout_fails_closed(self):
        result = self._run(
            f"#!{sys.executable}\nimport time\ntime.sleep(1)\n",
            command=[
                sys.executable,
                "-c",
                "from tools.release_check import check_docs_remote; "
                "raise SystemExit(check_docs_remote(timeout=0.01).exit())",
            ],
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Timeout", result.stderr)


# ═══════════════════════════════════════════════════════════════════════
# Cluster A: Tag-Konsistenz
# ═══════════════════════════════════════════════════════════════════════

class TagConsistencyBase(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.root = self.d.name
        # Mock verifier: unsigned test tags gelten als OK
        self.mock_verifier = lambda tag, root: (True, "mock ok")

    def tearDown(self):
        self.d.cleanup()

    def _git(self, *args):
        result = subprocess.run(
            ["git", *args],
            cwd=self.root,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"git {' '.join(args)} fehlgeschlagen: {result.stderr.strip()}",
        )
        return result.stdout.strip()

    def _init_git(self, version="0.1.0"):
        self._git("init", "--initial-branch=main")
        self._git("config", "user.email", "test@test")
        self._git("config", "user.name", "Test")
        self._write_version_metadata(version)
        self._git("add", "VERSION", "package.json", "package-lock.json", "CHANGELOG.md")
        self._git("-c", "commit.gpgsign=false", "commit", "-m", "init")

    def _write_version_metadata(self, version):
        _write(os.path.join(self.root, "VERSION"), f"{version}\n")
        _write(os.path.join(self.root, "package.json"), json.dumps({"version": version}))
        _write(
            os.path.join(self.root, "package-lock.json"),
            json.dumps({"version": version, "packages": {"": {"version": version}}}),
        )
        _write(
            os.path.join(self.root, "CHANGELOG.md"),
            "## [Unreleased]\n### Added\n- Keine.\n### Changed\n- Keine.\n"
            "### Fixed\n- Keine.\n### Removed\n- Keine.\n\n**Breaking changes:** none\n\n"
            f"## [{version}] — 2026-08-25\n### Added\n- release\n### Changed\n- Keine.\n"
            "### Fixed\n- Keine.\n### Removed\n- Keine.\n\n**Breaking changes:** none\n",
        )

    def _tag(self, root, name):
        self.assertEqual(root, self.root)
        self._git("-c", "tag.gpgsign=false", "tag", name)


class TagDeterministicSelection(TagConsistencyBase):
    """Greptile-Finding #1: Default wählt deterministisch v{VERSION}, nicht ersten v*-Tag."""

    def test_default_uses_version_based_tag(self):
        self._init_git("0.2.0")
        self._tag(self.root, "v0.1.0")
        self._tag(self.root, "v0.2.0")
        r = check_tag(root=self.root, verifier=self.mock_verifier)
        self.assertTrue(r.ok, f"Erwartet OK (v0.2.0 via VERSION), Fehler: {r.errors}")

    def test_wrong_default_tag_is_error(self):
        self._init_git("0.2.0")
        self._tag(self.root, "v0.1.0")
        self._tag(self.root, "v0.3.0")
        r = check_tag(root=self.root, verifier=self.mock_verifier)
        self.assertFalse(r.ok)
        self.assertTrue(any("nicht gefunden" in e for e in r.errors))


class TagLightweightVsAnnotated(TagConsistencyBase):
    """Greptile-Finding #3: Peeling via ^{commit} für annotierte Tags."""

    def test_lightweight_tag_is_ok(self):
        self._init_git("0.1.0")
        self._tag(self.root, "v0.1.0")
        r = check_tag(root=self.root, tag_ref="v0.1.0", verifier=self.mock_verifier)
        self.assertTrue(r.ok, f"Erwartet OK, Fehler: {r.errors}")

    def test_annotated_tag_is_ok(self):
        self._init_git("0.1.0")
        self._git("-c", "tag.gpgsign=false", "tag", "-m", "release", "v0.1.0")
        r = check_tag(root=self.root, tag_ref="v0.1.0", verifier=self.mock_verifier)
        self.assertTrue(r.ok, f"Erwartet OK (annotiert), Fehler: {r.errors}")

    def test_annotated_tag_on_wrong_commit_is_error(self):
        self._init_git("0.1.0")
        head = self._git("rev-parse", "HEAD")
        self._write_version_metadata("0.2.0")
        self._git("add", "VERSION", "package.json", "package-lock.json", "CHANGELOG.md")
        self._git("-c", "commit.gpgsign=false", "commit", "-m", "bump")
        self._git("-c", "tag.gpgsign=false", "tag", "-m", "release", "v0.2.0")
        r = check_tag(root=self.root, tag_ref="v0.2.0", expected_commit=head, verifier=self.mock_verifier)
        self.assertFalse(r.ok)
        self.assertTrue(any("zeigt auf" in e for e in r.errors))


class TagVersionProjectionBinding(TagConsistencyBase):
    def _assert_drift_is_rejected(self, path, value):
        self._init_git("0.1.0")
        self._tag(self.root, "v0.1.0")
        _write(os.path.join(self.root, path), json.dumps(value))

        r = check_tag(root=self.root, verifier=self.mock_verifier)

        self.assertFalse(r.ok)
        self.assertTrue(any("VERSION" in error for error in r.errors), r.errors)

    def test_tag_rejects_package_projection_drift(self):
        self._assert_drift_is_rejected("package.json", {"version": "0.2.0"})

    def test_tag_rejects_lock_projection_drift(self):
        self._assert_drift_is_rejected(
            "package-lock.json", {"version": "0.2.0", "packages": {"": {"version": "0.1.0"}}}
        )

    def test_tag_rejects_lock_root_projection_drift(self):
        self._assert_drift_is_rejected(
            "package-lock.json", {"version": "0.1.0", "packages": {"": {"version": "0.2.0"}}}
        )


class TagSignature(TagConsistencyBase):
    """Signaturprüfung ist blockierend (Cluster A.7, A.8)."""

    def test_signed_tag_verified_is_ok(self):
        self._init_git("0.1.0")
        self._tag(self.root, "v0.1.0")
        # Injected verifier: returns True
        def always_ok(tag, root):
            return True, "mock ok"
        r = check_tag(root=self.root, tag_ref="v0.1.0", verifier=always_ok)
        self.assertTrue(r.ok, f"Erwartet OK, Fehler: {r.errors}")

    def test_signed_tag_verification_failed_is_error(self):
        self._init_git("0.1.0")
        self._tag(self.root, "v0.1.0")
        def always_fail(tag, root):
            return False, "signature invalid"
        r = check_tag(root=self.root, tag_ref="v0.1.0", verifier=always_fail)
        self.assertFalse(r.ok)
        self.assertTrue(any("Signaturprüfung fehlgeschlagen" in e for e in r.errors))


class ReleaseTrustAnchorTests(unittest.TestCase):
    """Repositorygebundener, fingerprint-gepinnter SSH-Release-Trust-Anchor."""

    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.root = self.d.name
        self.allowed_signers = os.path.join(
            self.root, ".github", "signing", "allowed_signers"
        )

    def tearDown(self):
        self.d.cleanup()

    def _write_allowed_signers(self, content):
        _write(self.allowed_signers, content)

    def _verify_with_successful_git(self):
        with mock.patch.object(
            GitRunner, "run", return_value=("Good signature", "", 0)
        ) as git_run:
            result = GitRunner.verify_signature("v0.3.1", self.root)
        return result, git_run

    def test_missing_trust_anchor_is_rejected_before_git(self):
        (ok, detail), git_run = self._verify_with_successful_git()
        self.assertFalse(ok)
        self.assertIn("allowed_signers", detail)
        git_run.assert_not_called()

    def test_wrong_fingerprint_is_rejected_before_git(self):
        other_blob = base64.b64encode(b"synthetic-different-key-blob").decode()
        self._write_allowed_signers(
            f'{_RELEASE_SIGNER_PRINCIPAL} namespaces="git" '
            f"ssh-ed25519 {other_blob}\n"
        )
        (ok, _detail), git_run = self._verify_with_successful_git()
        self.assertFalse(ok)
        git_run.assert_not_called()

    def test_wrong_principal_is_rejected_before_git(self):
        self._write_allowed_signers(
            f'other-signer namespaces="git" ssh-ed25519 {_RELEASE_SIGNER_KEY}\n'
        )
        (ok, _detail), git_run = self._verify_with_successful_git()
        self.assertFalse(ok)
        git_run.assert_not_called()

    def test_wrong_namespace_is_rejected_before_git(self):
        self._write_allowed_signers(
            f'{_RELEASE_SIGNER_PRINCIPAL} namespaces="file" '
            f"ssh-ed25519 {_RELEASE_SIGNER_KEY}\n"
        )
        (ok, _detail), git_run = self._verify_with_successful_git()
        self.assertFalse(ok)
        git_run.assert_not_called()

    def test_wrong_key_type_is_rejected_before_git(self):
        self._write_allowed_signers(
            f'{_RELEASE_SIGNER_PRINCIPAL} namespaces="git" '
            f"ssh-rsa {_RELEASE_SIGNER_KEY}\n"
        )
        (ok, _detail), git_run = self._verify_with_successful_git()
        self.assertFalse(ok)
        git_run.assert_not_called()

    def test_invalid_base64_key_blob_is_rejected_before_git(self):
        self._write_allowed_signers(
            f'{_RELEASE_SIGNER_PRINCIPAL} namespaces="git" '
            "ssh-ed25519 not+strict/base64!\n"
        )
        (ok, _detail), git_run = self._verify_with_successful_git()
        self.assertFalse(ok)
        git_run.assert_not_called()

    def test_multiple_active_signers_are_rejected_before_git(self):
        self._write_allowed_signers(_RELEASE_ALLOWED_SIGNER * 2)
        (ok, _detail), git_run = self._verify_with_successful_git()
        self.assertFalse(ok)
        git_run.assert_not_called()

    def test_correct_trust_material_is_accepted(self):
        self._write_allowed_signers(_RELEASE_ALLOWED_SIGNER)
        validator = getattr(release_check, "_validate_release_trust_anchor", None)
        self.assertIsNotNone(
            validator, "release_check must expose the trust-anchor validator"
        )
        path, error = validator(self.root)
        self.assertEqual(error, "")
        self.assertEqual(path, os.path.abspath(self.allowed_signers))

    def test_git_uses_absolute_allowed_signers_path_per_invocation(self):
        self._write_allowed_signers(_RELEASE_ALLOWED_SIGNER)
        (ok, detail), git_run = self._verify_with_successful_git()
        self.assertTrue(ok, detail)
        git_run.assert_called_once_with(
            [
                "-c",
                f"gpg.ssh.allowedSignersFile={os.path.abspath(self.allowed_signers)}",
                "tag",
                "-v",
                "v0.3.1",
            ],
            self.root,
        )

    def test_symlink_trust_anchor_is_rejected_before_git(self):
        target = os.path.join(self.root, "synthetic-allowed-signers")
        _write(target, _RELEASE_ALLOWED_SIGNER)
        os.makedirs(os.path.dirname(self.allowed_signers), exist_ok=True)
        os.symlink(target, self.allowed_signers)
        (ok, _detail), git_run = self._verify_with_successful_git()
        self.assertFalse(ok)
        git_run.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════
# Cluster C: Release-Modus
# ═══════════════════════════════════════════════════════════════════════

class FakeGhRunner:
    """Injizierbare gh-Ausgabe für Release-Tests."""

    def __init__(self, data=None, error=None):
        self.data = data
        self.error = error

    def release_view(self, tag, root, timeout=30):
        return self.data, self.error


# ═══════════════════════════════════════════════════════════════════════
# Cluster C: targetCommitish-Resolver
# ═══════════════════════════════════════════════════════════════════════

class TargetCommitishResolver(TagConsistencyBase):
    """Deterministische Auflösung von targetCommitish (SHA, Branch, Remote, Bare)."""

    def test_resolve_sha(self):
        self._init_git("0.1.0")
        head = self._git("rev-parse", "HEAD")
        sha, err = _resolve_target_commitish(head, self.root)
        self.assertIsNone(err)
        self.assertEqual(sha, head)

    def test_resolve_local_branch(self):
        self._init_git("0.1.0")
        head = self._git("rev-parse", "HEAD")
        sha, err = _resolve_target_commitish("main", self.root)
        self.assertIsNone(err)
        self.assertEqual(sha, head)

    def test_resolve_origin_remote_branch(self):
        self._init_git("0.1.0")
        head = self._git("rev-parse", "HEAD")
        # Simuliere detached CI-Checkout: main nur als refs/remotes/origin/main verfügbar
        self._git("update-ref", "refs/remotes/origin/main", head)
        # Lösche den lokalen Branch, damit nur origin/main übrig bleibt
        self._git("checkout", "--detach", head)
        self._git("branch", "-D", "main")
        sha, err = _resolve_target_commitish("main", self.root)
        self.assertIsNone(err)
        self.assertEqual(sha, head)

    def test_unknown_branch_is_error(self):
        self._init_git("0.1.0")
        sha, err = _resolve_target_commitish("nonexistent", self.root)
        self.assertIsNotNone(err)
        self.assertEqual(sha, "")


class ReleaseTargetCommitishTests(TagConsistencyBase):
    """check_release() mit verschiedenen targetCommitish-Formaten."""

    def test_release_sha_match_is_ok(self):
        self._init_git("0.1.0")
        self._tag(self.root, "v0.1.0")
        head = self._git("rev-parse", "HEAD")
        gh = FakeGhRunner(data={"tagName": "v0.1.0", "targetCommitish": head, "isDraft": False, "isPrerelease": False})
        r = check_release(root=self.root, tag_ref="v0.1.0", gh=gh, verifier=self.mock_verifier)
        self.assertTrue(r.ok, f"Erwartet OK, Fehler: {r.errors}")

    def test_release_sha_mismatch_is_error(self):
        self._init_git("0.1.0")
        self._tag(self.root, "v0.1.0")
        wrong_sha = "0" * 40
        gh = FakeGhRunner(data={"tagName": "v0.1.0", "targetCommitish": wrong_sha, "isDraft": False, "isPrerelease": False})
        r = check_release(root=self.root, tag_ref="v0.1.0", gh=gh, verifier=self.mock_verifier)
        self.assertFalse(r.ok)
        self.assertTrue(any("weicht von Tag-Commit" in e for e in r.errors))

    def test_release_local_branch_match_is_ok(self):
        self._init_git("0.1.0")
        self._tag(self.root, "v0.1.0")
        gh = FakeGhRunner(data={"tagName": "v0.1.0", "targetCommitish": "main", "isDraft": False, "isPrerelease": False})
        r = check_release(root=self.root, tag_ref="v0.1.0", gh=gh, verifier=self.mock_verifier)
        self.assertTrue(r.ok, f"Erwartet OK, Fehler: {r.errors}")

    def test_release_local_branch_mismatch_is_error(self):
        self._init_git("0.1.0")
        self._tag(self.root, "v0.1.0")
        # Zweiten Commit auf main (Tag bleibt auf erstem Commit)
        _write(os.path.join(self.root, "extra"), "x\n")
        self._git("add", "extra")
        self._git("-c", "commit.gpgsign=false", "commit", "-m", "extra")
        gh = FakeGhRunner(data={"tagName": "v0.1.0", "targetCommitish": "main", "isDraft": False, "isPrerelease": False})
        r = check_release(root=self.root, tag_ref="v0.1.0", gh=gh, verifier=self.mock_verifier)
        self.assertFalse(r.ok)
        self.assertTrue(any("weicht von Tag-Commit" in e for e in r.errors))

    def test_release_origin_branch_match_is_ok(self):
        self._init_git("0.1.0")
        self._tag(self.root, "v0.1.0")
        head = self._git("rev-parse", "HEAD")
        # Simuliere CI: nur origin/main, kein lokaler main
        self._git("update-ref", "refs/remotes/origin/main", head)
        self._git("checkout", "--detach", head)
        self._git("branch", "-D", "main")
        gh = FakeGhRunner(data={"tagName": "v0.1.0", "targetCommitish": "main", "isDraft": False, "isPrerelease": False})
        r = check_release(root=self.root, tag_ref="v0.1.0", gh=gh, verifier=self.mock_verifier)
        self.assertTrue(r.ok, f"Erwartet OK (origin/main), Fehler: {r.errors}")

    def test_release_unknown_branch_is_error(self):
        self._init_git("0.1.0")
        self._tag(self.root, "v0.1.0")
        gh = FakeGhRunner(data={"tagName": "v0.1.0", "targetCommitish": "ghost", "isDraft": False, "isPrerelease": False})
        r = check_release(root=self.root, tag_ref="v0.1.0", gh=gh, verifier=self.mock_verifier)
        self.assertFalse(r.ok)
        self.assertTrue(any("nicht auflösbar" in e for e in r.errors))

    def test_gh_unavailable_is_error(self):
        self._init_git("0.1.0")
        self._tag(self.root, "v0.1.0")
        gh = FakeGhRunner(error="gh CLI nicht verfügbar")
        r = check_release(root=self.root, tag_ref="v0.1.0", gh=gh, verifier=self.mock_verifier)
        self.assertFalse(r.ok)
        self.assertTrue(any("gh CLI nicht verfügbar" in e for e in r.errors))

    def test_gh_error_is_error(self):
        self._init_git("0.1.0")
        self._tag(self.root, "v0.1.0")
        gh = FakeGhRunner(error="Release nicht gefunden")
        r = check_release(root=self.root, tag_ref="v0.1.0", gh=gh, verifier=self.mock_verifier)
        self.assertFalse(r.ok)
        self.assertTrue(any("Release nicht gefunden" in e for e in r.errors))

    def test_wrong_tagname_is_error(self):
        self._init_git("0.1.0")
        self._tag(self.root, "v0.1.0")
        gh = FakeGhRunner(data={"tagName": "v0.2.0", "targetCommitish": "main", "isDraft": False, "isPrerelease": False})
        r = check_release(root=self.root, tag_ref="v0.1.0", gh=gh, verifier=self.mock_verifier)
        self.assertFalse(r.ok)
        self.assertTrue(any("tagName" in e for e in r.errors))

    def test_draft_release_is_error(self):
        self._init_git("0.1.0")
        self._tag(self.root, "v0.1.0")
        gh = FakeGhRunner(data={"tagName": "v0.1.0", "targetCommitish": "main", "isDraft": True, "isPrerelease": False})
        r = check_release(root=self.root, tag_ref="v0.1.0", gh=gh, verifier=self.mock_verifier)
        self.assertFalse(r.ok)
        self.assertTrue(any("Draft" in e for e in r.errors))

    def _assert_release_metadata_error(self, relative, content, expected_error):
        self._init_git("0.1.0")
        _write(os.path.join(self.root, relative), content)
        r = check_release(
            root=self.root,
            tag_ref="v0.1.0",
            gh=FakeGhRunner(error="must not mask metadata failure"),
            verifier=self.mock_verifier,
        )
        self.assertFalse(r.ok)
        self.assertTrue(any(expected_error in error for error in r.errors), r.errors)

    def test_release_rejects_malformed_version_before_github(self):
        self._assert_release_metadata_error("VERSION", "not-semver\n", "SemVer")

    def test_release_rejects_multiple_version_lines_before_github(self):
        self._assert_release_metadata_error("VERSION", "0.1.0\n\n", "SemVer")

    def test_release_rejects_crlf_version_before_github(self):
        self._assert_release_metadata_error("VERSION", "0.1.0\r\n", "SemVer")

    def test_release_rejects_package_projection_drift(self):
        self._assert_release_metadata_error(
            "package.json", json.dumps({"version": "9.9.9"}), "package.json-Version"
        )

    def test_release_rejects_lock_root_projection_drift(self):
        self._assert_release_metadata_error(
            "package-lock.json",
            json.dumps({"version": "0.1.0", "packages": {"": {"version": "9.9.9"}}}),
            "Root-Paketversion",
        )

    def test_release_rejects_changelog_drift(self):
        self._assert_release_metadata_error("CHANGELOG.md", "## [Unreleased]\n", "CHANGELOG")

    def _assert_release_prerelease_mismatch(self, version, is_prerelease):
        self._init_git(version)
        self._tag(self.root, f"v{version}")
        head = self._git("rev-parse", "HEAD")
        gh = FakeGhRunner(data={
            "tagName": f"v{version}",
            "targetCommitish": head,
            "isDraft": False,
            "isPrerelease": is_prerelease,
        })
        r = check_release(
            root=self.root,
            tag_ref=f"v{version}",
            gh=gh,
            verifier=self.mock_verifier,
        )
        self.assertFalse(r.ok)
        self.assertTrue(any("Prerelease" in error for error in r.errors), r.errors)

    def test_stable_release_rejects_prerelease_flag(self):
        self._assert_release_prerelease_mismatch("0.1.0", True)

    def test_prerelease_rejects_stable_flag(self):
        self._assert_release_prerelease_mismatch("0.1.0-rc.1", False)

    def test_annotated_release_tag_is_ok(self):
        """Greptile-Finding #4: Annotierter Tag + Release mit korrektem SHA."""
        self._init_git("0.1.0")
        head = self._git("rev-parse", "HEAD")
        self._git("-c", "tag.gpgsign=false", "tag", "-m", "release", "v0.1.0")
        gh = FakeGhRunner(data={"tagName": "v0.1.0", "targetCommitish": head, "isDraft": False, "isPrerelease": False})
        r = check_release(root=self.root, tag_ref="v0.1.0", gh=gh, verifier=self.mock_verifier)
        self.assertTrue(r.ok, f"Erwartet OK (annotiert + SHA-match), Fehler: {r.errors}")

    def test_release_rejects_invalid_tag_signature(self):
        self._init_git("0.1.0")
        self._tag(self.root, "v0.1.0")
        head = self._git("rev-parse", "HEAD")
        gh = FakeGhRunner(data={
            "tagName": "v0.1.0",
            "targetCommitish": head,
            "isDraft": False,
            "isPrerelease": False,
        })
        calls = []

        def invalid_signature(tag, root):
            calls.append((tag, root))
            return False, "signature invalid"

        if "verifier" not in inspect.signature(check_release).parameters:
            self.fail("check_release must accept an injectable signature verifier")
        r = check_release(
            root=self.root,
            tag_ref="v0.1.0",
            gh=gh,
            verifier=invalid_signature,
        )
        self.assertFalse(r.ok)
        self.assertEqual(calls, [("v0.1.0", self.root)])
        self.assertTrue(any("Signaturprüfung fehlgeschlagen" in e for e in r.errors))

    def test_version_missing_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            r = check_release(root=d)
            self.assertFalse(r.ok)
            self.assertTrue(any("VERSION fehlt" in e for e in r.errors))


# ═══════════════════════════════════════════════════════════════════════
# Aktueller Repo-Zustand
# ═══════════════════════════════════════════════════════════════════════

class CurrentRepoState(unittest.TestCase):
    def test_tree_check_accepts_version_derived_release_metadata(self):
        r = check_tree()
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "VERSION"), encoding="utf-8") as handle:
            version = handle.read().strip()
        with open(os.path.join(root, "package.json"), encoding="utf-8") as handle:
            package = json.load(handle)
        with open(os.path.join(root, "package-lock.json"), encoding="utf-8") as handle:
            package_lock = json.load(handle)

        self.assertEqual(package["version"], version)
        self.assertEqual(package_lock["version"], version)
        self.assertEqual(package_lock["packages"][""]["version"], version)
        self.assertTrue(r.ok, r.errors)


if __name__ == "__main__":
    unittest.main()
