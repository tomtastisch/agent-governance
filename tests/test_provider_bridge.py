#!/usr/bin/env python3
"""Echte Microsoft-PolicyEngine-Bridge und Vor-Effekt-Reihenfolge."""

from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "integrations" / "microsoft-agent-governance-toolkit" / "bridge"
BUILD = BRIDGE / "build-provider.sh"
EXTRACT = BRIDGE / "extract-snapshot.py"
VERIFY_RUNTIME = BRIDGE / "verify-runtime.py"
RUNTIME_MANIFEST = BRIDGE / "runtime.files.sha256"
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

    def test_build_rejects_group_or_world_writable_current_runtime(self):
        with tempfile.TemporaryDirectory(prefix="agent-governance-provider-mode-") as directory:
            runtime = Path(directory) / "runtime"
            build = subprocess.run(
                [str(BUILD), str(runtime)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=300,
            )
            self.assertEqual(build.returncode, 0, build.stderr)

            runtime_files = (
                "runtime.files.sha256",
                "build.receipt",
                "microsoft-sdk/dist/policy.js",
                "microsoft-sdk/dist/protocol-facets.js",
                "microsoft-sdk/dist/types.js",
            )
            for index, relative in enumerate(runtime_files):
                with self.subTest(relative=relative):
                    tampered_runtime = Path(directory) / f"tampered-runtime-{index}"
                    shutil.copytree(runtime, tampered_runtime)
                    (tampered_runtime / relative).chmod(0o666)
                    current = subprocess.run(
                        [str(BUILD), str(tampered_runtime)],
                        cwd=ROOT,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )

                    self.assertNotEqual(current.returncode, 0)
                    self.assertIn("integrity", current.stderr.lower())

    def test_runtime_verifier_rejects_fifo_without_blocking(self):
        with tempfile.TemporaryDirectory(prefix="agent-governance-provider-fifo-") as directory:
            runtime = Path(directory).resolve(strict=True) / "runtime"
            runtime.mkdir()
            os.mkfifo(runtime / "runtime.files.sha256", mode=0o600)

            try:
                result = subprocess.run(
                    ["python3", str(VERIFY_RUNTIME), str(RUNTIME_MANIFEST), str(runtime)],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    timeout=1,
                )
            except subprocess.TimeoutExpired:
                self.fail("Runtime-Verifikation blockiert an einer FIFO-Spezialdatei")

            self.assertNotEqual(result.returncode, 0)

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
            runtime_manifest = runtime / "runtime.files.sha256"
            self.assertTrue(runtime_manifest.is_file())
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

            tampered_runtime = Path(directory) / "tampered-runtime"
            shutil.copytree(runtime, tampered_runtime)
            (tampered_runtime / "microsoft-sdk" / "dist" / "policy.js").write_text(
                "module.exports = { PolicyEngine: class { loadJson() {} "
                "evaluatePolicy() { return { action: 'allow' }; } } };\n",
                encoding="utf-8",
            )
            tampered = subprocess.run(
                [str(BUILD), str(tampered_runtime)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertNotEqual(tampered.returncode, 0)
            self.assertIn("integrity", tampered.stderr.lower())

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
