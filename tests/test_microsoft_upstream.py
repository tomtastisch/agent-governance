#!/usr/bin/env python3
"""Reproduzierbare Provenienz- und Instruction-Boundary-Verträge für Microsoft AGT."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
import unittest

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.11 ist Repositoryvertrag
    tomllib = None


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "integrations" / "microsoft-agent-governance-toolkit"
LOCK = INTEGRATION / "upstream.lock.toml"
SNAPSHOT = INTEGRATION / "upstream"
SNAPSHOT_MANIFEST = INTEGRATION / "snapshot.files.sha256"
MANIFEST = ROOT / "bundle" / "agent-governance" / "manifest.toml"


def load_lock() -> dict:
    if tomllib is None:
        raise unittest.SkipTest("tomllib erfordert Python 3.11+")
    if not LOCK.is_file():
        raise AssertionError("Microsoft-Upstream-Lock fehlt")
    with LOCK.open("rb") as handle:
        return tomllib.load(handle)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_integration_text(relative: str) -> str:
    path = INTEGRATION / relative
    if not path.is_file():
        raise AssertionError(f"Integrationsdatei fehlt: {relative}")
    return path.read_text(encoding="utf-8")


def read_integration_bytes(relative: str) -> bytes:
    path = INTEGRATION / relative
    if not path.is_file():
        raise AssertionError(f"Integrationsdatei fehlt: {relative}")
    return path.read_bytes()


class MicrosoftUpstreamLockContract(unittest.TestCase):
    def test_lock_pins_official_stable_release(self):
        lock = load_lock()
        self.assertEqual(
            lock,
            {
                "repository": "https://github.com/microsoft/agent-governance-toolkit",
                "resolved_version": "4.1.0",
                "resolved_tag": "v4.1.0",
                "resolved_commit": "0de71ca6c95cf8b9b975ac96f48eaa7826bbe258",
                "resolved_at": lock["resolved_at"],
                "archive_source": "https://codeload.github.com/microsoft/agent-governance-toolkit/tar.gz/refs/tags/v4.1.0",
                "release_url": "https://github.com/microsoft/agent-governance-toolkit/releases/tag/v4.1.0",
                "archive_sha256": "f087836d4e6cbad246c728c76454dd573a701f35d7560cbf869c250b3862d473",
                "license": "MIT",
                "upstream_status": "Public Preview",
                "tag_signature_status": "lightweight-tag",
                "commit_signature_status": "verified-valid",
                "archive_signature_status": "not-provided",
                "materialization_strategy": "complete-release-snapshot",
            },
        )
        self.assertRegex(lock["resolved_at"], r"^2026-08-12T\d{2}:\d{2}:\d{2}Z$")

    def test_integration_documents_upstream_version_drift(self):
        readme = read_integration_text("README.md")
        self.assertIn("Public Preview", readme)
        self.assertIn("v4.1.0", readme)
        self.assertIn("0de71ca6c95cf8b9b975ac96f48eaa7826bbe258", readme)
        self.assertRegex(readme, r"(?is)VERSION.+3\.7\.0.+GitHub Release.+maßgeblich")
        self.assertNotRegex(readme, r"(?i)Microsoft-certified|Microsoft-approved|\bGA\b")


class MicrosoftSnapshotContract(unittest.TestCase):
    def test_complete_snapshot_is_materialized_without_git_metadata(self):
        self.assertTrue(SNAPSHOT.is_dir())
        files = sorted(path for path in SNAPSHOT.rglob("*") if path.is_file())
        self.assertEqual(len(files), 4633)
        self.assertFalse(any(path.is_symlink() for path in SNAPSHOT.rglob("*")))
        self.assertFalse(any(".git" == part for path in files for part in path.parts))
        self.assertFalse(any(path.stat().st_size >= 100 * 1024 * 1024 for path in files))
        for required in (
            "README.md",
            "LICENSE",
            "NOTICE",
            "TRADEMARKS.md",
            "VERSION",
            "AGENTS.md",
            "GOVERNANCE.md",
            "docs/specs/FRAMEWORK-ADAPTER-CONTRACT-1.0.md",
            "agent-governance-typescript/package-lock.json",
        ):
            self.assertTrue((SNAPSHOT / required).is_file(), required)

    def test_snapshot_manifest_covers_every_regular_file(self):
        self.assertTrue(SNAPSHOT_MANIFEST.is_file())
        entries: dict[str, str] = {}
        for line in SNAPSHOT_MANIFEST.read_text(encoding="utf-8").splitlines():
            digest, separator, raw_path = line.partition("  ")
            self.assertEqual(separator, "  ")
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
            pure = PurePosixPath(raw_path)
            self.assertFalse(pure.is_absolute())
            self.assertNotIn("..", pure.parts)
            self.assertNotIn(raw_path, entries)
            entries[raw_path] = digest

        present = {
            path.relative_to(INTEGRATION).as_posix(): path
            for path in SNAPSHOT.rglob("*")
            if path.is_file()
        }
        self.assertEqual(set(entries), set(present))
        for raw_path, path in present.items():
            self.assertEqual(sha256(path), entries[raw_path], raw_path)

    def test_license_notice_and_trademark_copies_are_exact(self):
        for local_name, upstream_name in (
            ("LICENSE.upstream", "LICENSE"),
            ("NOTICE.upstream", "NOTICE"),
            ("TRADEMARKS.upstream.md", "TRADEMARKS.md"),
        ):
            self.assertEqual(
                read_integration_bytes(local_name),
                read_integration_bytes(f"upstream/{upstream_name}"),
                local_name,
            )

    def test_snapshot_contains_no_generated_dependency_tree(self):
        self.assertTrue(SNAPSHOT.is_dir())
        forbidden_parts = {".git", "node_modules", "__pycache__", ".pytest_cache"}
        offenders = [
            path.relative_to(SNAPSHOT).as_posix()
            for path in SNAPSHOT.rglob("*")
            if forbidden_parts.intersection(path.relative_to(SNAPSHOT).parts)
        ]
        self.assertEqual(offenders, [])


class MicrosoftInstructionBoundaryContract(unittest.TestCase):
    def test_manifest_never_traverses_vendored_upstream(self):
        text = MANIFEST.read_text(encoding="utf-8")
        self.assertNotIn("integrations/", text)
        self.assertNotIn("microsoft-agent-governance-toolkit", text)

    def test_integration_labels_all_upstream_files_as_untrusted_data(self):
        readme = read_integration_text("README.md")
        for name in ("AGENTS.md", "GOVERNANCE.md", "README.md", "*.prompt.md", "examples/"):
            self.assertIn(f"`{name}`", readme)
        self.assertRegex(readme, r"(?is)untrusted data.+keine.+Instruktionsquelle")
        self.assertRegex(readme, r"(?is)Prompt Injection.+fail-closed")


if __name__ == "__main__":
    unittest.main()
