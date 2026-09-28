"""Regressionen der deterministischen CFF-Releaseprojektion."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_release_check import _CHANGELOG_MIN, _write_documentation_tree
from tools.release_check import check_tree

ROOT = Path(__file__).resolve().parents[1]
CITATION = "# erhalten\ncff-version: 1.2.0\ntitle: Beispiel\nauthors:\n  - family-names: Beispiel\nversion: 0.1.0\ndate-released: '2026-07-27'\n"


class CitationContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'VERSION').write_text('0.1.0\n')
        (self.root / 'CHANGELOG.md').write_text(_CHANGELOG_MIN)
        _write_documentation_tree(str(self.root))
        self.cff = self.root / 'CITATION.cff'
        self.cff.write_text(CITATION)

    def run_sync(self):
        return subprocess.run([sys.executable, str(ROOT / 'tools/sync_citation.py'), '--root', str(self.root)], capture_output=True, text=True)

    def test_konsistenter_tree_ist_gueltig(self):
        result = check_tree(str(self.root))
        self.assertTrue(result.ok, result.errors)

    def test_gate_blockiert_versions_datums_und_commit_drift(self):
        for text in (CITATION.replace('version: 0.1.0', 'version: 0.0.9'), CITATION.replace('2026-07-27', '2026-07-26'), CITATION + 'commit: abc123\n'):
            with self.subTest(text=text):
                self.cff.write_text(text)
                result = check_tree(str(self.root))
                self.assertFalse(result.ok)
                self.assertTrue(any('CITATION.cff' in e for e in result.errors), result.errors)

    def test_sync_erhaelt_andere_bytes_und_entfernt_commit_idempotent(self):
        self.cff.write_text(CITATION.replace('version: 0.1.0', 'version: 0.0.9').replace('2026-07-27', '2020-01-01') + 'commit: abc123\n')
        sources = {name: (self.root / name).read_bytes() for name in ('VERSION', 'CHANGELOG.md', 'package.json', 'package-lock.json')}
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.cff.read_text(), CITATION)
        second = self.run_sync()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.cff.read_text(), CITATION)
        for name, original in sources.items():
            self.assertEqual((self.root / name).read_bytes(), original)
        self.assertTrue(check_tree(str(self.root)).ok)

    def test_gate_und_sync_verwerfen_mehrdeutige_cff(self):
        for extra in ('version: 0.1.0\n', 'date-released: 2026-07-27\n', '"commit": abc\n', '<<: *metadata\n', '---\nversion: 0.1.0\n', '  fortsetzung\n'):
            with self.subTest(extra=extra):
                self.cff.write_text(CITATION + extra)
                original = self.cff.read_bytes()
                self.assertFalse(check_tree(str(self.root)).ok)
                result = self.run_sync()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.cff.read_bytes(), original)

    def test_ungueltiger_oder_mehrfacher_changelog_bleibt_ohne_mutation(self):
        for text in (_CHANGELOG_MIN.replace('2026-07-27', '2026-02-30'), _CHANGELOG_MIN.replace(' — 2026-07-27', ''), _CHANGELOG_MIN + _CHANGELOG_MIN, _CHANGELOG_MIN.replace('[0.1.0]', '[0.0.9]')):
            with self.subTest(text=text):
                (self.root / 'CHANGELOG.md').write_text(text)
                before = self.cff.read_bytes()
                result = self.run_sync()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.cff.read_bytes(), before)

    def test_fehlende_cff_wird_vom_gate_blockiert(self):
        self.cff.unlink()
        self.assertFalse(check_tree(str(self.root)).ok)
        self.assertNotEqual(self.run_sync().returncode, 0)

    def test_symlink_eingaben_werden_ohne_mutation_verworfen(self):
        for name in ('VERSION', 'CHANGELOG.md', 'CITATION.cff'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as external:
                path = self.root / name
                original = path.read_bytes()
                target = Path(external) / name
                target.write_bytes(original)
                path.unlink()
                path.symlink_to(target)
                result = self.run_sync()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(target.read_bytes(), original)
                path.unlink()
                path.write_bytes(original)

    def test_naechster_release_nutzt_version_und_datierten_abschnitt(self):
        (self.root / 'VERSION').write_text('0.1.1\n')
        current = _CHANGELOG_MIN.split('## [0.1.0]', 1)[1]
        (self.root / 'CHANGELOG.md').write_text(_CHANGELOG_MIN.replace('## [0.1.0]', '## [0.1.1]').replace('2026-07-27', '2026-08-04') + '## [0.1.0]' + current)
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.cff.read_text(), CITATION.replace('version: 0.1.0', 'version: 0.1.1').replace('2026-07-27', '2026-08-04'))

    def test_crlf_und_quotierte_releasewerte_werden_sicher_projiziert(self):
        self.cff.write_bytes(CITATION.replace('version: 0.1.0', 'version: "0.0.9" # alt').replace("'2026-07-27'", '"2020-01-01"').replace('\n', '\r\n').encode())
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.cff.read_bytes(), CITATION.replace('\n', '\r\n').encode())

    def test_gate_lehnt_symlink_cff_ab(self):
        with tempfile.TemporaryDirectory() as external:
            target = Path(external) / 'CITATION.cff'
            target.write_text(CITATION)
            self.cff.unlink()
            self.cff.symlink_to(target)
            self.assertFalse(check_tree(str(self.root)).ok)
