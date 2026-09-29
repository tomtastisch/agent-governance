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

    def test_reine_cr_zeilenenden_bleiben_erhalten(self):
        self.cff.write_bytes(CITATION.replace('version: 0.1.0', 'version: 0.0.9').replace('\n', '\r').encode())
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.cff.read_bytes(), CITATION.replace('\n', '\r').encode())

    def test_ungueltige_syntax_in_erhaltenen_feldern_blockiert_gate_und_sync(self):
        for invalid in ('title: [', 'title: "offen', 'title: !tag Inhalt', 'title: &anchor Inhalt', 'title: falsch: wert', 'abstract: >-\n    Text\n  falsche Einrückung', 'title: Steuerzeichen\x81'):
            with self.subTest(invalid=invalid):
                self.cff.write_text(CITATION.replace('title: Beispiel', invalid))
                before = self.cff.read_bytes()
                self.assertFalse(check_tree(str(self.root)).ok)
                self.assertNotEqual(self.run_sync().returncode, 0)
                self.assertEqual(self.cff.read_bytes(), before)

    def test_isolierte_surrogat_escapes_blockieren_gate_und_sync(self):
        for value in (r'"\ud800"', r'"\udbff"', r'"\udc00"', r'"\udfff"', r'"Text\ud800Ende"', r'"\udc00\ud800"'):
            for field in ('title: ' + value, 'authors:\n  - family-names: ' + value, 'keywords:\n  - ' + value):
                with self.subTest(field=field):
                    source = CITATION.replace('title: Beispiel\nauthors:\n  - family-names: Beispiel', field)
                    self.cff.write_text(source)
                    before = self.cff.read_bytes()
                    result = check_tree(str(self.root))
                    self.assertFalse(result.ok, result.errors)
                    self.assertTrue(any('YAML-Skalar' in error for error in result.errors), result.errors)
                    self.assertNotEqual(self.run_sync().returncode, 0)
                    self.assertEqual(self.cff.read_bytes(), before)

    def test_gueltige_unicode_skalare_bleiben_bytegleich(self):
        for value in ('"Grüße 日本語 😀"', r'"Gr\u00fc\u00dfe"', r'"\ud7ff\ue000"', r'"\ud83d\ude00"', r'"\\ud800"'):
            with self.subTest(value=value):
                source = CITATION.replace('title: Beispiel', 'title: ' + value)
                self.cff.write_text(source)
                before = self.cff.read_bytes()
                result = check_tree(str(self.root))
                self.assertTrue(result.ok, result.errors)
                sync = self.run_sync()
                self.assertEqual(sync.returncode, 0, sync.stderr)
                self.assertEqual(self.cff.read_bytes(), before)

    def test_gate_blockiert_austausch_zwischen_stat_und_lesen(self):
        from unittest import mock
        import tools.release_check as checker
        real_lstat = checker.os.lstat
        with tempfile.TemporaryDirectory() as external:
            target = Path(external) / 'CITATION.cff'
            target.write_text(CITATION)
            swapped = False
            def swap(path, *args, **kwargs):
                nonlocal swapped
                info = real_lstat(path, *args, **kwargs)
                if Path(path) == self.cff and not swapped:
                    swapped = True
                    self.cff.unlink()
                    self.cff.symlink_to(target)
                return info
            with mock.patch.object(checker.os, 'lstat', side_effect=swap):
                result = check_tree(str(self.root))
            self.assertTrue(swapped)
            self.assertFalse(result.ok)

    def test_noop_prueft_quellidentitaeten_vor_erfolgreicher_rueckkehr(self):
        from unittest import mock
        sys.path.insert(0, str(ROOT / 'tools'))
        import sync_citation
        original_parser = sync_citation.citation_fields
        for name in ('VERSION', 'CHANGELOG.md', 'CITATION.cff'):
            with self.subTest(name=name):
                path = self.root / name
                before = path.read_bytes()
                def change(source):
                    result = original_parser(source)
                    path.write_bytes(before + b'\n')
                    return result
                try:
                    with mock.patch.object(sync_citation, 'citation_fields', side_effect=change):
                        with self.assertRaises(OSError):
                            sync_citation.synchronize(self.root)
                    self.assertEqual(path.read_bytes(), before + b'\n')
                finally:
                    path.write_bytes(before)

    def test_eingerueckte_yaml_strukturen_werden_validiert(self):
        for invalid in ('authors:\n  - family-names: [', 'authors:\n  - family-names: Beispiel\n    family-names: doppelt', 'keywords:\n    - Beispiel', 'title: Beispiel\n  fortsetzung', 'keywords:\n  - *alias'):
            with self.subTest(invalid=invalid):
                self.cff.write_text(CITATION.replace('authors:\n  - family-names: Beispiel', invalid))
                before = self.cff.read_bytes()
                self.assertFalse(check_tree(str(self.root)).ok)
                self.assertNotEqual(self.run_sync().returncode, 0)
                self.assertEqual(self.cff.read_bytes(), before)

    def test_textblock_interpunktion_bleibt_gueltiger_text(self):
        source = CITATION.replace('title: Beispiel', 'title: Beispiel\nabstract: >-\n  Text mit [Klammern], {Formen}: und !Zeichen.\n  \"Zitate\" sind hier ebenfalls Text.')
        self.cff.write_text(source)
        self.assertTrue(check_tree(str(self.root)).ok)
        self.assertEqual(self.run_sync().returncode, 0)
        self.assertEqual(self.cff.read_text(), source)


from test_release_check import TagConsistencyBase
from tools.release_check import check_tag


class CitationTagTreeContract(TagConsistencyBase):
    def assert_tag_drift_rejected(self, name, transform):
        self._init_git()
        path = Path(self.root) / name
        original = path.read_text()
        path.write_text(transform(original))
        self._git('add', name)
        self._git('-c', 'commit.gpgsign=false', 'commit', '-m', 'abweichende Tag-Metadaten')
        self._tag(self.root, 'v0.1.0')
        path.write_text(original)
        self._git('add', name)
        self._git('-c', 'commit.gpgsign=false', 'commit', '-m', 'nur main korrigiert')
        result = check_tag(root=self.root, verifier=self.mock_verifier)
        self.assertFalse(result.ok, result.errors)

    def test_tag_commit_feld_wird_nicht_durch_main_korrektur_verdeckt(self):
        self.assert_tag_drift_rejected('CITATION.cff', lambda source: source + 'commit: abc\n')

    def test_tag_versionsdrift_wird_nicht_durch_main_korrektur_verdeckt(self):
        self.assert_tag_drift_rejected('CITATION.cff', lambda source: source.replace('version: 0.1.0', 'version: 0.0.9'))

    def test_tag_datumsdrift_wird_nicht_durch_main_korrektur_verdeckt(self):
        self.assert_tag_drift_rejected('CITATION.cff', lambda source: source.replace('2026-08-25', '2020-01-01'))

    def test_tag_changelog_wird_als_datumsquelle_geprueft(self):
        self.assert_tag_drift_rejected('CHANGELOG.md', lambda source: source.replace('2026-08-25', '2026-08-26'))
