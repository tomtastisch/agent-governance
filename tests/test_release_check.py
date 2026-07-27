#!/usr/bin/env python3
"""Tests für tools/release_check.py — Tree-, Tag- und Release-Konsistenz.

Alle Tests verwenden synthetische Fixtures (tempfile.TemporaryDirectory) für reproduzierbare
Negativ-/Positivszenarien. Keine echten Tags oder GitHub-Releases werden erzeugt.
"""

import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.release_check import (  # noqa: E402
    CheckResult,
    check_tree,
    check_tag,
    check_release,
    _is_valid_semver,
    _read,
    REQUIRED_CATEGORIES,
)


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# ═══════════════════════════════════════════════════════════════════════
# Unit: SemVer-Parsing
# ═══════════════════════════════════════════════════════════════════════

class SemVerParsing(unittest.TestCase):
    def test_valid_versions(self):
        for v in ("0.0.0", "0.1.0", "1.0.0", "10.20.30", "0.1.0-alpha", "0.1.0-alpha.1",
                  "1.0.0+build.1", "1.0.0-alpha+001"):
            self.assertTrue(_is_valid_semver(v), f"'{v}' sollte gültig sein")

    def test_invalid_versions(self):
        for v in ("1", "1.0", "01.0.0", "1.0.0-", "v1.0.0", "abc", ""):
            self.assertFalse(_is_valid_semver(v), f"'{v}' sollte ungültig sein")


# ═══════════════════════════════════════════════════════════════════════
# Tree: VERSION
# ═══════════════════════════════════════════════════════════════════════

class TreeVersionMissing(unittest.TestCase):
    def test_version_missing_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            r = check_tree(root=d)
            self.assertFalse(r.ok)
            self.assertTrue(any("VERSION fehlt" in e for e in r.errors))


class TreeVersionInvalid(unittest.TestCase):
    def test_empty_version_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "VERSION"), "\n")
            r = check_tree(root=d)
            self.assertFalse(r.ok)
            self.assertTrue(any("ist leer" in e for e in r.errors))

    def test_bad_semver_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "VERSION"), "not.a.version")
            r = check_tree(root=d)
            self.assertFalse(r.ok)
            self.assertTrue(any("kein gültiges SemVer" in e for e in r.errors))


# ═══════════════════════════════════════════════════════════════════════
# Tree: konkurrierende Versionsquelle
# ═══════════════════════════════════════════════════════════════════════

class TreeCompetingSource(unittest.TestCase):
    def test_toml_version_is_competing(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "VERSION"), "0.1.0\n")
            _write(os.path.join(d, "config.toml"), 'version = "0.2.0"\n')
            r = check_tree(root=d)
            self.assertFalse(r.ok)
            self.assertTrue(any("konkurrierende version-Deklaration" in e for e in r.errors))

    def test_json_version_is_competing(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "VERSION"), "0.1.0\n")
            _write(os.path.join(d, "package.json"), '{"version": "0.2.0"}')
            r = check_tree(root=d)
            self.assertFalse(r.ok)
            self.assertTrue(any("konkurrierende version-Deklaration" in e for e in r.errors))

    def test_parallel_version_file_is_competing(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "VERSION"), "0.1.0\n")
            _write(os.path.join(d, "version.txt"), "0.2.0")
            r = check_tree(root=d)
            self.assertFalse(r.ok)
            self.assertTrue(any("parallele Versionsdatei" in e for e in r.errors))


# ═══════════════════════════════════════════════════════════════════════
# Tree: CHANGELOG
# ═══════════════════════════════════════════════════════════════════════

class TreeChangelogMissing(unittest.TestCase):
    def test_changelog_missing_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "VERSION"), "0.1.0\n")
            r = check_tree(root=d)
            self.assertFalse(r.ok)
            self.assertTrue(any("CHANGELOG.md fehlt" in e for e in r.errors))


class TreeChangelogCategories(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.root = self.d.name
        _write(os.path.join(self.root, "VERSION"), "0.1.0\n")

    def tearDown(self):
        self.d.cleanup()

    def _changelog(self, body):
        _write(os.path.join(self.root, "CHANGELOG.md"), body)

    def test_unknown_category_is_error(self):
        self._changelog("## [Unreleased]\n### Bogus\n- item\n\n**Breaking changes:** none\n")
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("unbekannte Kategorien" in e for e in r.errors))

    def test_missing_required_category_in_unreleased_is_error(self):
        self._changelog("## [Unreleased]\n### Added\n- item\n\n**Breaking changes:** none\n")
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("fehlen erforderliche Kategorien" in e for e in r.errors))

    def test_all_required_categories_with_keine_placeholder_is_ok(self):
        self._changelog(
            "## [Unreleased]\n"
            "### Added\n- item\n"
            "### Changed\n- Keine.\n"
            "### Fixed\n- Keine.\n"
            "### Removed\n- Keine.\n\n"
            "**Breaking changes:** none\n"
        )
        r = check_tree(root=self.root)
        self.assertTrue(r.ok, f"Erwartet OK, Fehler: {r.errors}")


class TreeChangelogBreakingMarker(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.root = self.d.name
        _write(os.path.join(self.root, "VERSION"), "0.1.0\n")

    def tearDown(self):
        self.d.cleanup()

    def _cl(self, body):
        _write(os.path.join(self.root, "CHANGELOG.md"), body)

    def test_missing_breaking_marker_is_error(self):
        self._cl("## [Unreleased]\n### Added\n- item\n")
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("fehlt der Marker" in e for e in r.errors))

    def test_present_without_breaking_entry_is_error(self):
        self._cl("## [Unreleased]\n### Added\n- item\n\n**Breaking changes:** present\n")
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("kein Eintrag mit" in e for e in r.errors))

    def test_present_with_breaking_entry_is_ok(self):
        self._cl(
            "## [Unreleased]\n### Added\n- Keine.\n### Changed\n- **BREAKING:** altered API\n"
            "### Fixed\n- Keine.\n### Removed\n- Keine.\n\n**Breaking changes:** present\n"
        )
        r = check_tree(root=self.root)
        self.assertTrue(r.ok, f"Erwartet OK, Fehler: {r.errors}")

    def test_none_marker_is_ok(self):
        self._cl("## [Unreleased]\n### Added\n- item\n"
                 "### Changed\n- Keine.\n### Fixed\n- Keine.\n### Removed\n- Keine.\n\n"
                 "**Breaking changes:** none\n")
        r = check_tree(root=self.root)
        self.assertTrue(r.ok, f"Erwartet OK, Fehler: {r.errors}")


class TreeChangelogHistory(unittest.TestCase):
    """Mehrere Versionseinträge werden akzeptiert (keine künstliche 1-Eintrag-Grenze)."""

    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.root = self.d.name
        _write(os.path.join(self.root, "VERSION"), "0.2.0\n")

    def tearDown(self):
        self.d.cleanup()

    def test_two_releases_is_valid(self):
        cl = (
            "## [Unreleased]\n### Added\n- new\n### Changed\n- Keine.\n"
            "### Fixed\n- Keine.\n### Removed\n- Keine.\n\n**Breaking changes:** none\n\n"
            "## [0.2.0] — 2026-08-01\n### Added\n- item2\n\n**Breaking changes:** none\n\n"
            "## [0.1.0] — 2026-07-27\n### Added\n- item1\n\n**Breaking changes:** none\n"
        )
        _write(os.path.join(self.root, "CHANGELOG.md"), cl)
        r = check_tree(root=self.root)
        self.assertTrue(r.ok, f"Erwartet OK, Fehler: {r.errors}")

    def test_duplicate_version_headings_is_error(self):
        cl = (
            "## [0.1.0] — 2026-07-27\n### Added\n- first\n\n**Breaking changes:** none\n\n"
            "## [0.1.0] — 2026-07-28\n### Added\n- dup\n\n**Breaking changes:** none\n"
        )
        _write(os.path.join(self.root, "CHANGELOG.md"), cl)
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("doppelte Versionsüberschrift" in e for e in r.errors))

    def test_invalid_semver_in_history_is_error(self):
        cl = (
            "## [Unreleased]\n### Added\n- item\n\n**Breaking changes:** none\n\n"
            "## [01.0.0] — 2026-08-01\n### Added\n- bad\n\n**Breaking changes:** none\n"
        )
        _write(os.path.join(self.root, "CHANGELOG.md"), cl)
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("kein gültiges SemVer" in e for e in r.errors))

    def test_version_mismatch_with_no_unreleased_is_error(self):
        """Ohne [Unreleased] muss der neueste CHANGELOG-Eintrag mit VERSION übereinstimmen."""
        _write(os.path.join(self.root, "VERSION"), "0.3.0\n")
        cl = (
            "## [0.2.0] — 2026-08-01\n### Added\n- old\n\n**Breaking changes:** none\n"
        )
        _write(os.path.join(self.root, "CHANGELOG.md"), cl)
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("weicht von aktuellstem" in e for e in r.errors))


# ═══════════════════════════════════════════════════════════════════════
# Tree: README
# ═══════════════════════════════════════════════════════════════════════

class TreeReadmeDrift(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.root = self.d.name
        _write(os.path.join(self.root, "VERSION"), "0.2.0\n")
        _write(os.path.join(self.root, "CHANGELOG.md"),
               "## [Unreleased]\n### Added\n- x\n### Changed\n- Keine.\n"
               "### Fixed\n- Keine.\n### Removed\n- Keine.\n\n**Breaking changes:** none\n")

    def tearDown(self):
        self.d.cleanup()

    def test_readme_version_drift_is_error(self):
        _write(os.path.join(self.root, "README.md"),
               "**Version:** [`0.1.0`](VERSION)\n")
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("zeigt Version '0.1.0'" in e for e in r.errors))

    def test_readme_matching_version_is_ok(self):
        _write(os.path.join(self.root, "README.md"),
               "**Version:** [`0.2.0`](VERSION)\n")
        r = check_tree(root=self.root)
        self.assertTrue(r.ok, f"Erwartet OK, Fehler: {r.errors}")

    def test_readme_bare_version_without_link_is_error(self):
        _write(os.path.join(self.root, "README.md"),
               "**Version:** `0.2.0`\n")
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("ohne VERSION-Link" in e for e in r.errors))

    def test_readme_no_version_reference_is_error(self):
        _write(os.path.join(self.root, "README.md"), "# Title\n\nNo version here.\n")
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("referenziert keine versionierte Auslieferung" in e for e in r.errors))


# ═══════════════════════════════════════════════════════════════════════
# Tree: INSTALL
# ═══════════════════════════════════════════════════════════════════════

class TreeInstallLink(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.root = self.d.name
        _write(os.path.join(self.root, "VERSION"), "0.1.0\n")
        _write(os.path.join(self.root, "CHANGELOG.md"),
               "## [Unreleased]\n### Added\n- x\n### Changed\n- Keine.\n"
               "### Fixed\n- Keine.\n### Removed\n- Keine.\n\n**Breaking changes:** none\n")
        _write(os.path.join(self.root, "README.md"),
               "**Version:** [`0.1.0`](VERSION)\n")

    def tearDown(self):
        self.d.cleanup()

    def test_install_wrong_path_is_error(self):
        _write(os.path.join(self.root, "INSTALL.md"),
               "See [`VERSION`](../VERSION)\n")
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("korrekter Pfad ist 'VERSION'" in e for e in r.errors))

    def test_install_correct_path_is_ok(self):
        _write(os.path.join(self.root, "INSTALL.md"),
               "See [`VERSION`](VERSION)\n")
        r = check_tree(root=self.root)
        self.assertTrue(r.ok, f"Erwartet OK, Fehler: {r.errors}")


# ═══════════════════════════════════════════════════════════════════════
# Tag-Konsistenz
# ═══════════════════════════════════════════════════════════════════════

class TagConsistency(unittest.TestCase):
    """Nutzt temporäre Git-Repositories — keine echten Tags im Projekt-Repo."""

    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.root = self.d.name

    def tearDown(self):
        self.d.cleanup()

    def _init_git(self, version="0.1.0"):
        subprocess.run(["git", "init"], cwd=self.root, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test"], cwd=self.root, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.root, capture_output=True)
        _write(os.path.join(self.root, "VERSION"), f"{version}\n")
        subprocess.run(["git", "add", "VERSION"], cwd=self.root, capture_output=True)
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"],
            cwd=self.root, capture_output=True,
        )

    @staticmethod
    def _tag(root, name):
        """Leichter Tag ohne GPG-Signierung im Test-Repo."""
        subprocess.run(
            ["git", "-c", "tag.gpgsign=false", "tag", name],
            cwd=root, capture_output=True,
        )

    def test_tag_name_mismatch_is_error(self):
        self._init_git("0.1.0")
        self._tag(self.root, "v0.2.0")
        r = check_tag(root=self.root, tag_ref="v0.2.0")
        self.assertFalse(r.ok)
        self.assertTrue(any("entspricht nicht" in e for e in r.errors))

    def test_tag_name_match_is_ok(self):
        self._init_git("0.1.0")
        self._tag(self.root, "v0.1.0")
        r = check_tag(root=self.root, tag_ref="v0.1.0")
        self.assertTrue(r.ok, f"Erwartet OK, Fehler: {r.errors}")

    def test_tag_on_wrong_commit_is_error(self):
        self._init_git("0.1.0")
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.root,
                              capture_output=True, text=True).stdout.strip()
        _write(os.path.join(self.root, "VERSION"), "0.2.0\n")
        subprocess.run(["git", "add", "VERSION"], cwd=self.root, capture_output=True)
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "commit", "-m", "bump"],
            cwd=self.root, capture_output=True,
        )
        self._tag(self.root, "v0.2.0")
        r = check_tag(root=self.root, tag_ref="v0.2.0", expected_commit=head)
        self.assertFalse(r.ok)
        self.assertTrue(any("zeigt auf" in e for e in r.errors))

    def test_missing_tag_is_error(self):
        self._init_git("0.1.0")
        r = check_tag(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("Kein v*-Tag gefunden" in e for e in r.errors))

    def test_version_missing_for_tag_check(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(["git", "init"], cwd=d, capture_output=True)
            r = check_tag(root=d)
            self.assertFalse(r.ok)
            self.assertTrue(any("VERSION fehlt" in e for e in r.errors))


# ═══════════════════════════════════════════════════════════════════════
# Aktueller Repo-Zustand (Red: origin/main hat keine Artefakte)
# ═══════════════════════════════════════════════════════════════════════

class CurrentRepoState(unittest.TestCase):
    """Prüft den aktuellen Repository-Zustand — dient als Red-Nachweis vor Implementierung."""

    def test_tree_check_fails_without_version(self):
        """Ohne VERSION und CHANGELOG muss check_tree() Fehler liefern."""
        r = check_tree()
        self.assertFalse(r.ok, "Erwartet FAIL: VERSION/CHANGELOG fehlen auf origin/main")
        self.assertTrue(any("VERSION fehlt" in e for e in r.errors))


if __name__ == "__main__":
    unittest.main()
