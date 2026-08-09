#!/usr/bin/env python3
"""Scope-Grenzen des schlanken Governance-Regelwerks."""

from __future__ import annotations

from pathlib import Path
import re
import unittest

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - CI erfordert Python 3.11+
    tomllib = None


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "bundle"
MANIFEST = BUNDLE / "agent-governance" / "manifest.toml"

OPERATIVE_ARTIFACTS = (
    "project.toml",
    "tools/tools.md",
    "tools/Brewfile",
    "tools/Brewfile.optional",
    "tests/check_links.py",
)

OUT_OF_SCOPE_TRIGGERS = {
    "installation",
    "migration",
    "deployment",
    "provisioning",
    "runtime_bootstrap",
    "backup",
    "restore",
    "session_orchestration",
}

NORMATIVE_OPERATION_PATTERNS = {
    "Installation materialisiert": re.compile(r"Installation\s+materialisiert", re.I),
    "Migration bewahrt": re.compile(r"Migration\s+bewahrt", re.I),
    "atomare Aktivierung": re.compile(r"atomar\s+aktiviert", re.I),
    "Backup-Lifecycle": re.compile(r"Backups?\s+(?:werden|wird)", re.I),
    "Paketmanager-Aufruf": re.compile(r"(?:brew|pip|npm|uv)\s+(?:install|add|bundle)\b", re.I),
}


def normative_files() -> list[Path]:
    manifest = tomllib.loads(MANIFEST.read_text(encoding="utf-8"))
    root = MANIFEST.parent
    paths = [BUNDLE / "GOVERNANCE.md"]
    paths.extend(root / entry["path"] for entry in manifest["modules"].values())
    paths.extend(root / entry["path"] for entry in manifest["roles"].values())
    return paths


class GovernanceScopeContract(unittest.TestCase):
    def test_repository_contains_no_operational_subsystem_contracts(self):
        present = [path for path in OPERATIVE_ARTIFACTS if (ROOT / path).exists()]
        self.assertEqual(present, [])

    def test_manifest_routes_governance_work_not_operations(self):
        if tomllib is None:
            self.skipTest("tomllib requires Python 3.11+")
        data = tomllib.loads(MANIFEST.read_text(encoding="utf-8"))
        triggers = set(data["routing"]["known_triggers"])
        self.assertEqual(triggers & OUT_OF_SCOPE_TRIGGERS, set())

    def test_normative_bundle_contains_no_operational_execution_contract(self):
        if tomllib is None:
            self.skipTest("tomllib requires Python 3.11+")
        offenders = []
        for path in normative_files():
            text = path.read_text(encoding="utf-8")
            for label, pattern in NORMATIVE_OPERATION_PATTERNS.items():
                if pattern.search(text):
                    offenders.append((path.relative_to(ROOT).as_posix(), label))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
