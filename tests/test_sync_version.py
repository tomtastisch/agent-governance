#!/usr/bin/env python3
"""Contracts for the narrow VERSION-to-npm projection synchronizer."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SYNC_VERSION = ROOT / "tools" / "sync_version.py"


class SyncVersionContract(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self._write_valid_tree()

    def tearDown(self):
        self.directory.cleanup()

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
