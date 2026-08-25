#!/usr/bin/env python3
"""Contracts for the narrow VERSION-to-npm projection synchronizer."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SYNC_VERSION = ROOT / "tools" / "sync_version.py"
SYNC_SPEC = importlib.util.spec_from_file_location("sync_version_under_test", SYNC_VERSION)
SYNC_MODULE = importlib.util.module_from_spec(SYNC_SPEC)
assert SYNC_SPEC.loader is not None
SYNC_SPEC.loader.exec_module(SYNC_MODULE)


class SyncVersionContract(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.external_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.external_root = Path(self.external_directory.name)
        self._write_valid_tree()

    def tearDown(self):
        self.directory.cleanup()
        self.external_directory.cleanup()

    def _write_valid_tree(self, version="7.8.9"):
        (self.root / "VERSION").write_text(f"{version}\n", encoding="utf-8")
        self.package = {
            "name": "fixture-package",
            "version": "0.0.0",
            "scripts": {"test": "fixture-test"},
            "engines": {"node": ">=24"},
            "publishConfig": {"access": "public"},
            "dependencies": {"fixture-dependency": "1.2.3"},
        }
        self.lock = {
            "name": "fixture-package",
            "version": "0.0.0",
            "lockfileVersion": 3,
            "packages": {
                "": {"name": "fixture-package", "version": "0.0.0", "license": "Apache-2.0"},
                "node_modules/fixture-dependency": {"version": "1.2.3"},
            },
        }
        (self.root / "package.json").write_text(json.dumps(self.package, indent=2) + "\n", encoding="utf-8")
        (self.root / "package-lock.json").write_text(json.dumps(self.lock, indent=2) + "\n", encoding="utf-8")

    def _run(self):
        return subprocess.run(
            [sys.executable, str(SYNC_VERSION), "--root", str(self.root)],
            capture_output=True,
            text=True,
        )

    def _projection_bytes(self):
        return tuple((self.root / name).read_bytes() for name in ("VERSION", "package.json", "package-lock.json"))

    def _existing_projection_bytes(self):
        return {
            name: (self.root / name).read_bytes()
            for name in ("VERSION", "package.json", "package-lock.json")
            if (self.root / name).exists()
        }

    def test_valid_single_line_semver_updates_only_the_three_projection_fields(self):
        expected_package = copy.deepcopy(self.package)
        expected_lock = copy.deepcopy(self.lock)
        expected_package["version"] = "7.8.9"
        expected_lock["version"] = "7.8.9"
        expected_lock["packages"][""]["version"] = "7.8.9"

        result = self._run()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((self.root / "package.json").read_text(encoding="utf-8")), expected_package)
        self.assertEqual(json.loads((self.root / "package-lock.json").read_text(encoding="utf-8")), expected_lock)

    def test_second_run_is_idempotent(self):
        first = self._run()
        after_first = self._projection_bytes()
        second = self._run()

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self._projection_bytes(), after_first)

    def test_noncanonical_json_preserves_every_non_projection_byte(self):
        package = (
            b"{\r\n"
            b"  \"description\": \"0.0.0\",\r\n"
            b"\t\"version\" : \"0.0.0\",\r\n"
            b"  \"scripts\" : { \"test\" : \"fixture-test\" }\r\n"
            b"}\r\n"
        )
        lock = (
            b"{\r\n"
            b"\t\"version\" : \"0.0.0\",\r\n"
            b"  \"metadata\" : \"0.0.0\",\r\n"
            b"\t\"packages\" : { \"\" : { \"version\":\"0.0.0\", \"note\":\"0.0.0\" } }\r\n"
            b"}\r\n"
        )
        (self.root / "package.json").write_bytes(package)
        (self.root / "package-lock.json").write_bytes(lock)

        result = self._run()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            (self.root / "package.json").read_bytes(),
            package.replace(b'\"version\" : \"0.0.0\"', b'\"version\" : \"7.8.9\"'),
        )
        self.assertEqual(
            (self.root / "package-lock.json").read_bytes(),
            lock.replace(b'\"version\" : \"0.0.0\"', b'\"version\" : \"7.8.9\"').replace(
                b'\"version\":\"0.0.0\"', b'\"version\":\"7.8.9\"'
            ),
        )

    def test_second_target_replace_failure_rolls_back_every_target_file(self):
        before = self._projection_bytes()
        real_replace = SYNC_MODULE.os.replace
        lock_path = self.root / "package-lock.json"

        def fail_lock_replace(source, destination):
            if Path(destination) == lock_path:
                raise OSError("injected lock replacement failure")
            return real_replace(source, destination)

        with mock.patch.object(SYNC_MODULE.os, "replace", side_effect=fail_lock_replace):
            with self.assertRaises(OSError):
                SYNC_MODULE.synchronize(self.root)

        self.assertEqual(self._projection_bytes(), before)
        self.assertEqual(list(self.root.glob(".sync-version-*")), [])

    def test_backup_cleanup_failure_never_rolls_back_committed_projections(self):
        real_unlink = SYNC_MODULE.Path.unlink
        existing_backup_unlinks = 0

        def fail_second_backup_unlink(path, *args, **kwargs):
            nonlocal existing_backup_unlinks
            if path.name.startswith(".sync-version-") and path.exists():
                existing_backup_unlinks += 1
                if existing_backup_unlinks == 2:
                    raise OSError("injected backup cleanup failure")
            return real_unlink(path, *args, **kwargs)

        with mock.patch.object(SYNC_MODULE.Path, "unlink", new=fail_second_backup_unlink):
            with self.assertRaisesRegex(OSError, "Backup-Bereinigung"):
                SYNC_MODULE.synchronize(self.root)

        package = json.loads((self.root / "package.json").read_text(encoding="utf-8"))
        lock = json.loads((self.root / "package-lock.json").read_text(encoding="utf-8"))
        self.assertEqual(package["version"], "7.8.9")
        self.assertEqual(lock["version"], "7.8.9")
        self.assertEqual(lock["packages"][""]["version"], "7.8.9")
        self.assertEqual(len(list(self.root.glob(".sync-version-*"))), 1)

        committed = self._projection_bytes()
        with self.assertRaisesRegex(OSError, "Restdateien"):
            SYNC_MODULE.synchronize(self.root)
        self.assertEqual(self._projection_bytes(), committed)

    def _assert_symlink_input_is_rejected(self, name):
        input_path = self.root / name
        external = self.external_root / name
        external.write_bytes(input_path.read_bytes())
        input_path.unlink()
        input_path.symlink_to(external)
        external_before = external.read_bytes()
        regular_before = {
            path.name: path.read_bytes()
            for path in (self.root / "VERSION", self.root / "package.json", self.root / "package-lock.json")
            if not path.is_symlink()
        }

        result = self._run()

        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(input_path.is_symlink())
        self.assertEqual(input_path.readlink(), external)
        self.assertEqual(external.read_bytes(), external_before)
        self.assertEqual(
            {
                path.name: path.read_bytes()
                for path in (self.root / "VERSION", self.root / "package.json", self.root / "package-lock.json")
                if not path.is_symlink()
            },
            regular_before,
        )
        self.assertEqual(list(self.root.glob(".sync-version-*")), [])

    def test_symlinked_version_is_rejected_before_any_write(self):
        self._assert_symlink_input_is_rejected("VERSION")

    def test_symlinked_package_json_is_rejected_before_any_write(self):
        self._assert_symlink_input_is_rejected("package.json")

    def test_symlinked_package_lock_is_rejected_before_any_write(self):
        self._assert_symlink_input_is_rejected("package-lock.json")

    def test_invalid_or_multiline_version_fails_without_writes(self):
        for version in ("not-semver\n", "7.8.9\nextra\n"):
            with self.subTest(version=version):
                (self.root / "VERSION").write_text(version, encoding="utf-8")
                before = self._projection_bytes()

                result = self._run()

                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self._projection_bytes(), before)

    def test_missing_or_invalid_package_json_fails_without_writes(self):
        for content in (None, "{invalid"):
            with self.subTest(content=content):
                package = self.root / "package.json"
                if content is None:
                    package.unlink()
                else:
                    package.write_text(content, encoding="utf-8")
                before = self._existing_projection_bytes()

                result = self._run()

                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self._existing_projection_bytes(), before)

    def test_missing_or_invalid_lock_root_structure_fails_without_writes(self):
        cases = (None, "{invalid", json.dumps({"version": "0.0.0"}), json.dumps({"version": "0.0.0", "packages": {}}))
        for content in cases:
            with self.subTest(content=content):
                lock = self.root / "package-lock.json"
                if content is None:
                    lock.unlink()
                else:
                    lock.write_text(content, encoding="utf-8")
                before = self._existing_projection_bytes()

                result = self._run()

                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self._existing_projection_bytes(), before)


if __name__ == "__main__":
    unittest.main()
