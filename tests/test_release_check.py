#!/usr/bin/env python3
"""Tests für tools/release_check.py — Tree-, Tag- und Release-Konsistenz.

Alle Tests verwenden synthetische Fixtures (tempfile.TemporaryDirectory) für reproduzierbare
Negativ-/Positivszenarien. Keine echten Tags oder GitHub-Releases werden erzeugt.

Abdeckung:
  Cluster A: Tag-Auflösung, Peel, Signaturprüfung, deterministische Tag-Wahl
  Cluster B: CHANGELOG-Abschnittsweise Validierung (kein Cross-Section-Leak)
  Cluster C: Release-Modus via injizierte gh-Ausgaben
  Cluster D: README/INSTALL/VERSION fail-closed
"""

import os
import re
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    "### Fixed\n- Keine.\n### Removed\n- Keine.\n\n**Breaking changes:** none\n"
)
_README_MIN = "**Version:** [`0.1.0`](VERSION)\n"
_INSTALL_MIN = "See [`VERSION`](VERSION)\n"


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
            self.assertTrue(any("nichtleere Zeilen" in e for e in r.errors))

    def test_multiline_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "VERSION"), "0.1.0\nextra text\n")
            r = check_tree(root=d)
            self.assertFalse(r.ok)
            self.assertTrue(any("nichtleere Zeilen" in e for e in r.errors))

    def test_bad_semver_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "VERSION"), "not.a.version\n")
            r = check_tree(root=d)
            self.assertFalse(r.ok)
            self.assertTrue(any("kein gültiges SemVer" in e for e in r.errors))

    def test_single_line_with_newline_is_ok(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "VERSION"), "0.1.0\n")
            _write(os.path.join(d, "CHANGELOG.md"), _CHANGELOG_MIN)
            _write(os.path.join(d, "README.md"), _README_MIN)
            _write(os.path.join(d, "INSTALL.md"), _INSTALL_MIN)
            r = check_tree(root=d)
            self.assertTrue(r.ok, f"Erwartet OK, Fehler: {r.errors}")


# ═══════════════════════════════════════════════════════════════════════
# Cluster D: Konkurrierende Quelle
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
        _write(os.path.join(self.root, "README.md"), "**Version:** [`0.1.0`](VERSION)\n")
        _write(os.path.join(self.root, "INSTALL.md"), "See [`VERSION`](VERSION)\n")

    def tearDown(self):
        self.d.cleanup()

    def _cl(self, body):
        _write(os.path.join(self.root, "CHANGELOG.md"), body)

    def test_unreleased_before_release_is_ok(self):
        self._cl(_CHANGELOG_MIN + "\n## [0.1.0] — 2026-07-27\n### Added\n- history\n\n**Breaking changes:** none\n")
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
        self._cl(
            _CHANGELOG_MIN + "\n"
            "## [0.2.0] — 2026-08-01\n### Added\n- newer\n\n**Breaking changes:** none\n\n"
            "## [0.1.0] — 2026-07-27\n### Added\n- older\n\n**Breaking changes:** none\n"
        )
        r = check_tree(root=self.root)
        self.assertTrue(r.ok, f"Erwartet OK, Fehler: {r.errors}")

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
# Cluster D: README / INSTALL
# ═══════════════════════════════════════════════════════════════════════

class TreeReadmeDrift(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.root = self.d.name
        _write(os.path.join(self.root, "VERSION"), "0.2.0\n")
        _write(os.path.join(self.root, "CHANGELOG.md"), _CHANGELOG_MIN.replace("0.1.0", "0.2.0"))

    def tearDown(self):
        self.d.cleanup()

    def test_readme_version_drift_is_error(self):
        _write(os.path.join(self.root, "README.md"), "**Version:** [`0.1.0`](VERSION)\n")
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("zeigt Version '0.1.0'" in e for e in r.errors))

    def test_readme_matching_version_is_ok(self):
        _write(os.path.join(self.root, "README.md"), "**Version:** [`0.2.0`](VERSION)\n")
        _write(os.path.join(self.root, "INSTALL.md"), _INSTALL_MIN)
        r = check_tree(root=self.root)
        self.assertTrue(r.ok, f"Erwartet OK, Fehler: {r.errors}")

    def test_readme_bare_version_without_link_is_error(self):
        _write(os.path.join(self.root, "README.md"), "**Version:** `0.2.0`\n")
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("ohne VERSION-Link" in e for e in r.errors))

    def test_readme_no_version_reference_is_error(self):
        _write(os.path.join(self.root, "README.md"), "# Title\n\nNo version here.\n")
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("referenziert keine versionierte" in e for e in r.errors))

    def test_readme_missing_is_error(self):
        _write(os.path.join(self.root, "INSTALL.md"), _INSTALL_MIN)
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("README.md fehlt" in e for e in r.errors))


class TreeInstallContracts(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.root = self.d.name
        _write(os.path.join(self.root, "VERSION"), "0.1.0\n")
        _write(os.path.join(self.root, "CHANGELOG.md"), _CHANGELOG_MIN)
        _write(os.path.join(self.root, "README.md"), _README_MIN)

    def tearDown(self):
        self.d.cleanup()

    def test_install_wrong_path_is_error(self):
        _write(os.path.join(self.root, "INSTALL.md"), "See [`VERSION`](../VERSION)\n")
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("korrekter Pfad ist 'VERSION'" in e for e in r.errors))

    def test_install_missing_is_error(self):
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("INSTALL.md fehlt" in e for e in r.errors))

    def test_install_without_version_contract_is_error(self):
        _write(os.path.join(self.root, "INSTALL.md"), "# Install\n\nJust do it.\n")
        r = check_tree(root=self.root)
        self.assertFalse(r.ok)
        self.assertTrue(any("keinen Hinweis auf versionierte" in e for e in r.errors))

    def test_install_correct_is_ok(self):
        _write(os.path.join(self.root, "INSTALL.md"), _INSTALL_MIN)
        r = check_tree(root=self.root)
        self.assertTrue(r.ok, f"Erwartet OK, Fehler: {r.errors}")


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
        _write(os.path.join(self.root, "VERSION"), f"{version}\n")
        self._git("add", "VERSION")
        self._git("-c", "commit.gpgsign=false", "commit", "-m", "init")

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
        _write(os.path.join(self.root, "VERSION"), "0.2.0\n")
        self._git("add", "VERSION")
        self._git("-c", "commit.gpgsign=false", "commit", "-m", "bump")
        self._git("-c", "tag.gpgsign=false", "tag", "-m", "release", "v0.2.0")
        r = check_tag(root=self.root, tag_ref="v0.2.0", expected_commit=head, verifier=self.mock_verifier)
        self.assertFalse(r.ok)
        self.assertTrue(any("zeigt auf" in e for e in r.errors))


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
        r = check_release(root=self.root, tag_ref="v0.1.0", gh=gh)
        self.assertTrue(r.ok, f"Erwartet OK, Fehler: {r.errors}")

    def test_release_sha_mismatch_is_error(self):
        self._init_git("0.1.0")
        self._tag(self.root, "v0.1.0")
        wrong_sha = "0" * 40
        gh = FakeGhRunner(data={"tagName": "v0.1.0", "targetCommitish": wrong_sha, "isDraft": False, "isPrerelease": False})
        r = check_release(root=self.root, tag_ref="v0.1.0", gh=gh)
        self.assertFalse(r.ok)
        self.assertTrue(any("weicht von Tag-Commit" in e for e in r.errors))

    def test_release_local_branch_match_is_ok(self):
        self._init_git("0.1.0")
        self._tag(self.root, "v0.1.0")
        gh = FakeGhRunner(data={"tagName": "v0.1.0", "targetCommitish": "main", "isDraft": False, "isPrerelease": False})
        r = check_release(root=self.root, tag_ref="v0.1.0", gh=gh)
        self.assertTrue(r.ok, f"Erwartet OK, Fehler: {r.errors}")

    def test_release_local_branch_mismatch_is_error(self):
        self._init_git("0.1.0")
        self._tag(self.root, "v0.1.0")
        # Zweiten Commit auf main (Tag bleibt auf erstem Commit)
        _write(os.path.join(self.root, "extra"), "x\n")
        self._git("add", "extra")
        self._git("-c", "commit.gpgsign=false", "commit", "-m", "extra")
        gh = FakeGhRunner(data={"tagName": "v0.1.0", "targetCommitish": "main", "isDraft": False, "isPrerelease": False})
        r = check_release(root=self.root, tag_ref="v0.1.0", gh=gh)
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
        r = check_release(root=self.root, tag_ref="v0.1.0", gh=gh)
        self.assertTrue(r.ok, f"Erwartet OK (origin/main), Fehler: {r.errors}")

    def test_release_unknown_branch_is_error(self):
        self._init_git("0.1.0")
        self._tag(self.root, "v0.1.0")
        gh = FakeGhRunner(data={"tagName": "v0.1.0", "targetCommitish": "ghost", "isDraft": False, "isPrerelease": False})
        r = check_release(root=self.root, tag_ref="v0.1.0", gh=gh)
        self.assertFalse(r.ok)
        self.assertTrue(any("nicht auflösbar" in e for e in r.errors))

    def test_gh_unavailable_is_error(self):
        self._init_git("0.1.0")
        self._tag(self.root, "v0.1.0")
        gh = FakeGhRunner(error="gh CLI nicht verfügbar")
        r = check_release(root=self.root, tag_ref="v0.1.0", gh=gh)
        self.assertFalse(r.ok)
        self.assertTrue(any("gh CLI nicht verfügbar" in e for e in r.errors))

    def test_gh_error_is_error(self):
        self._init_git("0.1.0")
        self._tag(self.root, "v0.1.0")
        gh = FakeGhRunner(error="Release nicht gefunden")
        r = check_release(root=self.root, tag_ref="v0.1.0", gh=gh)
        self.assertFalse(r.ok)
        self.assertTrue(any("Release nicht gefunden" in e for e in r.errors))

    def test_wrong_tagname_is_error(self):
        self._init_git("0.1.0")
        self._tag(self.root, "v0.1.0")
        gh = FakeGhRunner(data={"tagName": "v0.2.0", "targetCommitish": "main", "isDraft": False, "isPrerelease": False})
        r = check_release(root=self.root, tag_ref="v0.1.0", gh=gh)
        self.assertFalse(r.ok)
        self.assertTrue(any("tagName" in e for e in r.errors))

    def test_draft_release_is_error(self):
        self._init_git("0.1.0")
        self._tag(self.root, "v0.1.0")
        gh = FakeGhRunner(data={"tagName": "v0.1.0", "targetCommitish": "main", "isDraft": True, "isPrerelease": False})
        r = check_release(root=self.root, tag_ref="v0.1.0", gh=gh)
        self.assertFalse(r.ok)
        self.assertTrue(any("Draft" in e for e in r.errors))

    def test_annotated_release_tag_is_ok(self):
        """Greptile-Finding #4: Annotierter Tag + Release mit korrektem SHA."""
        self._init_git("0.1.0")
        head = self._git("rev-parse", "HEAD")
        self._git("-c", "tag.gpgsign=false", "tag", "-m", "release", "v0.1.0")
        gh = FakeGhRunner(data={"tagName": "v0.1.0", "targetCommitish": head, "isDraft": False, "isPrerelease": False})
        r = check_release(root=self.root, tag_ref="v0.1.0", gh=gh)
        self.assertTrue(r.ok, f"Erwartet OK (annotiert + SHA-match), Fehler: {r.errors}")

    def test_version_missing_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            r = check_release(root=d)
            self.assertFalse(r.ok)
            self.assertTrue(any("VERSION fehlt" in e for e in r.errors))


# ═══════════════════════════════════════════════════════════════════════
# Aktueller Repo-Zustand
# ═══════════════════════════════════════════════════════════════════════

class CurrentRepoState(unittest.TestCase):
    def test_tree_check_has_version_and_changelog(self):
        r = check_tree()
        has_version_error = any("VERSION fehlt" in e for e in r.errors)
        self.assertFalse(has_version_error, "VERSION sollte vorhanden sein (Green)")
        has_changelog_error = any("CHANGELOG.md fehlt" in e for e in r.errors)
        self.assertFalse(has_changelog_error, "CHANGELOG.md sollte vorhanden sein (Green)")
        # CHANGELOG sollte keinen vorzeitigen Release-Link haben
        has_link_error = any("Release-Links" in e for e in r.errors)
        self.assertFalse(has_link_error, "CHANGELOG sollte keine vorzeitigen Release-Links haben")


if __name__ == "__main__":
    unittest.main()
