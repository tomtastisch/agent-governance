"""Prepare muss reale Metadaten vollständig materialisieren oder unverändert lassen."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from test_release_check import _CHANGELOG_MIN, _write_documentation_tree
from tools.release_check import check_tree
from tools import prepare_release, sync_version

ROOT = Path(__file__).resolve().parents[1]
FILES = ("VERSION", "CHANGELOG.md", "package.json", "package-lock.json", "CITATION.cff", "release.files.sha256")


class PrepareReleaseContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "VERSION").write_text("0.1.0\n")
        (self.root / "CHANGELOG.md").write_text(_CHANGELOG_MIN)
        _write_documentation_tree(str(self.root))
        (self.root / "release.files.sha256").write_text("stale manifest\n")

    def snapshot(self):
        return {name: (self.root / name).read_bytes() for name in FILES}

    def run_prepare(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "tools/prepare_release.py"), "--root", str(self.root), *args], capture_output=True, text=True)

    def test_bump_und_explizites_ziel_materialisieren_alle_projektionen(self):
        before = self.snapshot()
        for args, version in ((["--bump", "patch"], "0.1.1"), (["--bump", "minor"], "0.2.0"), (["--bump", "major"], "1.0.0"), (["--target", "2.0.0"], "2.0.0")):
            with self.subTest(args=args):
                for name, data in before.items():
                    (self.root / name).write_bytes(data)
                result = self.run_prepare(*args, "--date", "2026-09-30")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((self.root / "VERSION").read_text(), version + "\n")
                self.assertEqual(json.loads((self.root / "package.json").read_text())["version"], version)
                lock = json.loads((self.root / "package-lock.json").read_text())
                self.assertEqual((lock["version"], lock["packages"][""]["version"]), (version, version))
                self.assertIn(f"version: {version}\n", (self.root / "CITATION.cff").read_text())
                self.assertIn("date-released: '2026-09-30'", (self.root / "CITATION.cff").read_text())
                changelog = (self.root / "CHANGELOG.md").read_text()
                old_body = _CHANGELOG_MIN.split("## [Unreleased]\n", 1)[1].split("## [0.1.0]", 1)[0]
                self.assertIn(f"## [{version}] — 2026-09-30\n" + old_body, changelog)
                self.assertNotIn("- item", changelog.split(f"## [{version}]")[0])
                self.assertTrue(changelog.endswith("## [0.1.0]" + _CHANGELOG_MIN.split("## [0.1.0]", 1)[1]))
                self.assertTrue(check_tree(str(self.root)).ok)
                self.assertIn("  VERSION\n", (self.root / "release.files.sha256").read_text())

    def test_gleiches_explizites_ziel_ist_bytegleich_und_datumgebunden(self):
        first = self.run_prepare("--target", "0.2.0", "--date", "2026-09-30")
        self.assertEqual(first.returncode, 0, first.stderr)
        before = self.snapshot()
        second = self.run_prepare("--target", "0.2.0", "--date", "2026-09-30")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertNotEqual(self.run_prepare("--target", "0.2.0", "--date", "2026-10-01").returncode, 0)
        self.assertEqual(self.snapshot(), before)

    def test_ungueltige_ruecklaeufige_und_mehrdeutige_eingaben_schreiben_nichts(self):
        before = self.snapshot()
        for args in (("--target", "0.0.9"), ("--target", "01.2.3"), ("--target", "0.1.0+other"), ("--target", "0.1.1\n"), ("--bump", "minor", "--target", "0.2.0")):
            with self.subTest(args=args):
                self.assertNotEqual(self.run_prepare(*args, "--date", "2026-09-30").returncode, 0)
                self.assertEqual(self.snapshot(), before)

    def test_fehler_in_citation_changelog_oder_version_lassen_alle_dateien_unveraendert(self):
        for name, invalid in (("VERSION", b"0.1.0\r\n"), ("CITATION.cff", b"version: [\n"), ("CHANGELOG.md", (_CHANGELOG_MIN + "\n## [Unreleased]\n").encode()), ("CHANGELOG.md", _CHANGELOG_MIN.replace("### Added", "### Added\n### Added", 1).encode())):
            with self.subTest(name=name):
                original = (self.root / name).read_bytes()
                (self.root / name).write_bytes(invalid)
                before = self.snapshot()
                self.assertNotEqual(self.run_prepare("--bump", "minor", "--date", "2026-09-30").returncode, 0)
                self.assertEqual(self.snapshot(), before)
                (self.root / name).write_bytes(original)

    def test_ungueltiges_datum_schreibt_nichts(self):
        before = self.snapshot()
        self.assertNotEqual(self.run_prepare("--bump", "minor", "--date", "2026-02-30").returncode, 0)
        self.assertEqual(self.snapshot(), before)

    def test_fehler_nach_projektion_und_beim_commit_rollen_vollstaendig_zurueck(self):
        before = self.snapshot()
        with mock.patch.object(prepare_release.release_manifest, "render", side_effect=ValueError("Manifestfehler")):
            with self.assertRaisesRegex(ValueError, "Manifestfehler"):
                prepare_release.prepare(self.root, bump="minor", release_date="2026-09-30")
        self.assertEqual(self.snapshot(), before)
        real_replace = sync_version.os.replace
        calls = []

        def fail_third(source, destination):
            if Path(destination).parent == self.root:
                calls.append(destination)
                if len(calls) == 3:
                    raise OSError("simulierter Schreibfehler")
            return real_replace(source, destination)

        with mock.patch.object(sync_version.os, "replace", side_effect=fail_third):
            with self.assertRaisesRegex(OSError, "simulierter Schreibfehler"):
                prepare_release.prepare(self.root, bump="minor", release_date="2026-09-30")
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(list(self.root.glob(".sync-version-*")), [])

    def test_symlinks_in_metadaten_und_payload_schreiben_nichts(self):
        for name in (*FILES, "bundle/GOVERNANCE.md"):
            with self.subTest(name=name):
                path = self.root / name
                original = path.read_bytes()
                target = self.root / "outside-fixture"
                target.write_bytes(original)
                path.unlink()
                path.symlink_to(target)
                before = self.snapshot()
                self.assertNotEqual(self.run_prepare("--bump", "minor", "--date", "2026-09-30").returncode, 0)
                self.assertEqual(self.snapshot(), before)
                self.assertEqual(target.read_bytes(), original)
                path.unlink()
                path.write_bytes(original)
                target.unlink()

    def test_nebenlaeufige_aenderung_wird_nicht_ueberschrieben(self):
        before = self.snapshot()
        original_render = prepare_release.release_manifest.render

        def concurrent_write(candidate):
            (self.root / "CHANGELOG.md").write_bytes(b"konkurrierender Inhalt\n")
            return original_render(candidate)

        with mock.patch.object(prepare_release.release_manifest, "render", side_effect=concurrent_write):
            with self.assertRaisesRegex(ValueError, "Quellbaum"):
                prepare_release.prepare(self.root, bump="minor", release_date="2026-09-30")
        after = self.snapshot()
        self.assertEqual(after.pop("CHANGELOG.md"), b"konkurrierender Inhalt\n")
        before.pop("CHANGELOG.md")
        self.assertEqual(after, before)

    def test_explizite_prereleases_nutzen_bestehende_semver_praezedenz(self):
        first = self.run_prepare("--target", "1.0.0-rc.2", "--date", "2026-09-30")
        self.assertEqual(first.returncode, 0, first.stderr)
        before = self.snapshot()
        self.assertNotEqual(self.run_prepare("--target", "1.0.0-rc.1", "--date", "2026-09-30").returncode, 0)
        self.assertEqual(self.snapshot(), before)
        final = self.run_prepare("--target", "1.0.0", "--date", "2026-09-30")
        self.assertEqual(final.returncode, 0, final.stderr)

    def test_semver_validierung_verwirft_trailing_lf_auch_im_release_gate(self):
        self.assertFalse(prepare_release.release_check._is_valid_semver("1.2.3\n"))

    def test_kategorieordnung_optionale_kategorien_und_breaking_inhalt_bleiben_erhalten(self):
        original = _CHANGELOG_MIN.replace("### Added\n- item", "### Security\n- Sicherheitsänderung.\n### Added\n- **BREAKING:** geänderter Vertrag", 1).replace("**Breaking changes:** none", "**Breaking changes:** present", 1)
        (self.root / "CHANGELOG.md").write_text(original)
        result = self.run_prepare("--bump", "major", "--date", "2026-09-30")
        self.assertEqual(result.returncode, 0, result.stderr)
        content = (self.root / "CHANGELOG.md").read_text()
        body = original.split("## [Unreleased]\n", 1)[1].split("## [0.1.0]", 1)[0]
        self.assertIn("## [1.0.0] — 2026-09-30\n" + body, content)
        unreleased = content.split("## [1.0.0]")[0]
        self.assertLess(unreleased.index("### Security"), unreleased.index("### Added"))
        self.assertNotIn("**BREAKING:**", unreleased)

    def test_mehrdeutige_historische_abschnitte_werden_vor_jeder_mutation_abgelehnt(self):
        original = _CHANGELOG_MIN.replace("## [0.1.0]", "## [0.1.0]").replace("### Added", "### Added\n### Added", 2)
        # Nur der historische Bereich ist mehrdeutig; Unreleased bleibt gültig.
        original = _CHANGELOG_MIN.split("## [0.1.0]")[0] + "## [0.1.0]" + original.split("## [0.1.0]")[1]
        (self.root / "CHANGELOG.md").write_text(original)
        before = self.snapshot()
        result = self.run_prepare("--bump", "minor", "--date", "2026-09-30")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.snapshot(), before)

    def test_sec_payload_unter_buildnamen_bleibt_im_manifest(self):
        directory = self.root / "bundle" / "dist"
        directory.mkdir()
        (directory / "fixture.md").write_text("Payload\n")
        result = self.run_prepare("--bump", "minor", "--date", "2026-09-30")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "release.files.sha256").read_text(), prepare_release.release_manifest.render(self.root))

    def test_sec_leere_verzeichnisse_und_versteckte_payload_links_blockieren(self):
        before = self.snapshot()
        empty = self.root / "docs" / "images"
        empty.mkdir()
        self.assertNotEqual(self.run_prepare("--bump", "minor", "--date", "2026-09-30").returncode, 0)
        self.assertEqual(self.snapshot(), before)
        empty.rmdir()
        link = self.root / "bundle" / "dist"
        with tempfile.TemporaryDirectory() as outside:
            link.symlink_to(outside, target_is_directory=True)
            self.assertNotEqual(self.run_prepare("--bump", "minor", "--date", "2026-09-30").returncode, 0)
            self.assertEqual(self.snapshot(), before)

    @unittest.skipIf(os.geteuid() == 0, "root kann chmod(0)-Fixture weiterhin lesen")
    def test_sec_unlesbarer_payload_bricht_vor_mutation_ab(self):
        directory = self.root / "bundle" / "unreadable"
        directory.mkdir()
        (directory / "fixture.md").write_text("Payload\n")
        before = self.snapshot()
        directory.chmod(0)
        try:
            self.assertNotEqual(self.run_prepare("--bump", "minor", "--date", "2026-09-30").returncode, 0)
            self.assertEqual(self.snapshot(), before)
        finally:
            directory.chmod(0o700)

    def test_sec_nichtkanonische_kategorie_trenner_blockieren(self):
        for separator in ("\t", "  "):
            with self.subTest(separator=separator):
                (self.root / "CHANGELOG.md").write_text(_CHANGELOG_MIN.replace("### Added\n", f"### Added\n###{separator}Added\n", 1))
                before = self.snapshot()
                self.assertNotEqual(self.run_prepare("--bump", "minor", "--date", "2026-09-30").returncode, 0)
                self.assertEqual(self.snapshot(), before)

    def test_sec_eingerueckte_und_tabgetrennte_atx_ueberschriften_blockieren(self):
        initial = self.snapshot()
        for heading in (" ### Added", "  ### Added", "   ### Added", " ## [Unreleased]", "  ## [Unreleased]", "   ## [Unreleased]", "##\t[Unreleased]"):
            with self.subTest(heading=heading):
                for name, data in initial.items():
                    (self.root / name).write_bytes(data)
                (self.root / "CHANGELOG.md").write_text(_CHANGELOG_MIN.replace("### Added\n", f"### Added\n{heading}\n", 1))
                before = self.snapshot()
                self.assertNotEqual(self.run_prepare("--bump", "minor", "--date", "2026-09-30").returncode, 0)
                self.assertEqual(self.snapshot(), before)

    def test_sec_noop_prueft_identitaeten_nach_finalem_snapshot(self):
        prepare_release.prepare(self.root, target="0.2.0", release_date="2026-09-30")
        read = sync_version._read_regular_bytes
        reads = 0

        def mutate_after_read(path):
            nonlocal reads
            result = read(path)
            if path == self.root / "VERSION":
                reads += 1
                if reads == 3:
                    path.write_text("9.9.9\n")
            return result

        with mock.patch.object(sync_version, "_read_regular_bytes", side_effect=mutate_after_read):
            with self.assertRaises(OSError):
                prepare_release.prepare(self.root, target="0.2.0", release_date="2026-09-30")
        self.assertEqual((self.root / "VERSION").read_text(), "9.9.9\n")

    def test_sec_bekannte_private_dateien_werden_nicht_in_kandidaten_kopiert(self):
        private = (".env", "profile/profile.md", "bundle/agent-governance/local/user-rules.md")
        for relative in private:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetische private Fixture\n")
        original_render = prepare_release.release_manifest.render

        def inspect(candidate):
            for relative in private:
                self.assertFalse((candidate / relative).exists(), relative)
            return original_render(candidate)

        with mock.patch.object(prepare_release.release_manifest, "render", side_effect=inspect):
            prepare_release.prepare(self.root, target="0.2.0", release_date="2026-09-30")


if __name__ == "__main__":
    unittest.main()
