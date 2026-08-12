#!/usr/bin/env python3
"""Echte Microsoft-PolicyEngine-Bridge und Vor-Effekt-Reihenfolge."""

from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "integrations" / "microsoft-agent-governance-toolkit" / "bridge"
BUILD = BRIDGE / "build-provider.sh"
EXTRACT = BRIDGE / "extract-snapshot.py"
PROVIDER = BRIDGE / "provider.mjs"
CODEX_HOOK = BRIDGE / "codex-hook.mjs"
POLICY = BRIDGE / "policy.json"
NODE_TEST = ROOT / "tests" / "node" / "provider_bridge.test.mjs"


class ProviderBridgeContract(unittest.TestCase):
    def test_bridge_files_are_explicit_and_repository_runtime_is_clean(self):
        for path in (BUILD, EXTRACT, PROVIDER, CODEX_HOOK, POLICY):
            self.assertTrue(path.is_file(), path.relative_to(ROOT))
        self.assertTrue(os.access(BUILD, os.X_OK))
        self.assertFalse((BRIDGE / "runtime").exists())
        self.assertFalse((BRIDGE / "node_modules").exists())

    def test_build_rejects_relative_output(self):
        self.assertTrue(BUILD.is_file())
        result = subprocess.run(
            [str(BUILD), "relative-output"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("absolute", result.stderr.lower())

    def test_extractor_rejects_traversal_and_link_entries(self):
        self.assertTrue(EXTRACT.is_file())
        for kind in ("traversal", "symlink"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                archive = root / "hostile.tar.gz"
                manifest = root / "snapshot.files.sha256"
                destination = root / "destination"
                outside = root / "outside"
                with tarfile.open(archive, "w:gz") as handle:
                    if kind == "traversal":
                        payload = b"hostile"
                        member = tarfile.TarInfo("synthetic-release/../../outside")
                        member.size = len(payload)
                        handle.addfile(member, io.BytesIO(payload))
                    else:
                        member = tarfile.TarInfo("synthetic-release/link")
                        member.type = tarfile.SYMTYPE
                        member.linkname = "../../outside"
                        handle.addfile(member)
                archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
                manifest.write_text("", encoding="utf-8")

                result = subprocess.run(
                    [
                        "python3",
                        str(EXTRACT),
                        str(archive),
                        str(manifest),
                        str(destination),
                        archive_hash,
                    ],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(destination.exists())
                self.assertFalse(outside.exists())


class RealMicrosoftProviderBridge(unittest.TestCase):
    def test_real_policy_engine_decisions_and_effect_order(self):
        self.assertTrue(BUILD.is_file(), "Providerbuild fehlt")
        self.assertTrue(NODE_TEST.is_file(), "Node-Providerprüfung fehlt")
        with tempfile.TemporaryDirectory(prefix="agent-governance-provider-") as directory:
            runtime = Path(directory) / "runtime"
            build = subprocess.run(
                [str(BUILD), str(runtime)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=300,
            )
            self.assertEqual(
                build.returncode,
                0,
                f"Providerbuild fehlgeschlagen\nSTDOUT:\n{build.stdout}\nSTDERR:\n{build.stderr}",
            )
            policy_module = runtime / "microsoft-sdk" / "dist" / "policy.js"
            self.assertTrue(policy_module.is_file())
            receipt = runtime / "build.receipt"
            before = (policy_module.stat().st_mtime_ns, receipt.read_bytes())
            current = subprocess.run(
                [str(BUILD), str(runtime)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(current.returncode, 0, current.stderr)
            self.assertIn("current", current.stdout)
            self.assertEqual(
                (policy_module.stat().st_mtime_ns, receipt.read_bytes()),
                before,
            )

            environment = os.environ.copy()
            environment["AGENT_GOVERNANCE_MSAGT_POLICY_MODULE"] = str(policy_module)
            result = subprocess.run(
                ["node", "--test", str(NODE_TEST)],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(
                result.returncode,
                0,
                f"Node-Providerprüfung fehlgeschlagen\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}",
            )


if __name__ == "__main__":
    unittest.main()
