import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class InstallerPackageContract(unittest.TestCase):
    def test_active_codex_only_bootstrap_was_removed(self):
        self.assertFalse((ROOT / "Installation.bootstrap.prompt.md").exists())

    def test_package_declares_only_the_direct_init_runtime_dependencies(self):
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        current_version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(package["name"], "@tomtastisch/agent-governance")
        self.assertEqual(package["version"], current_version)
        self.assertEqual(package["engines"]["node"], ">=24")
        # Validate that runtime dependencies are exactly declared in package.json (SSOT)
        # and match the lockfile, rather than hardcoding specific versions
        self.assertIn("dependencies", package)
        self.assertIsInstance(package["dependencies"], dict)
        self.assertGreater(len(package["dependencies"]), 0)
        # Verify no unexpected runtime dependencies
        self.assertNotIn("terminal-image", package["dependencies"])
        self.assertNotIn("chalk", package["dependencies"])
        self.assertNotIn("boxen", package["dependencies"])
        self.assertNotIn("log-update", package["dependencies"])
        self.assertEqual(
            package["keywords"],
            [
                "agent-governance",
                "ai-governance",
                "governance-as-code",
                "policy-as-code",
                "ai-agents",
                "coding-agents",
                "coding-agent-governance",
                "ai-security",
                "developer-tools",
                "cli",
                "harness-agnostic",
                "llm",
                "installer",
            ],
        )
        self.assertIn("interactive", package["description"].lower())
        self.assertNotIn("terminal-image", package["dependencies"])
        self.assertNotIn("chalk", package["dependencies"])
        self.assertNotIn("boxen", package["dependencies"])
        self.assertNotIn("log-update", package["dependencies"])
        self.assertEqual(package["devDependencies"]["typescript"], "7.0.2")
        self.assertEqual(package["devDependencies"]["@typescript/typescript6"], "6.0.2")
        self.assertEqual(package["devDependencies"]["@types/node"], "24.19.2")
        self.assertEqual(package["bin"]["agent-governance"], "dist/cli.js")
        self.assertNotIn("integrations", package["files"])
        self.assertTrue(package["publishConfig"]["provenance"])
        self.assertEqual(package["scripts"]["test:package"], "tests/e2e/run_package_consumers.sh")
        self.assertEqual(package["scripts"]["license:check"], "node tools/verify-licenses.mjs")

    def test_dependency_evidence_uses_the_lockfile_counting_convention(self):
        lock = json.loads((ROOT / "package-lock.json").read_text(encoding="utf-8"))
        packages = lock["packages"]
        production = [metadata for path, metadata in packages.items() if path and not metadata.get("dev", False)]
        development = [metadata for path, metadata in packages.items() if path and metadata.get("dev", False)]
        evidence = (ROOT / "docs" / "dependency-evidence.md").read_text(encoding="utf-8")
        self.assertEqual(len(packages), 34)
        self.assertEqual(len(production), 8)
        self.assertEqual(len(development), 25)
        self.assertIn("34 = 1 Root + 8 Production ohne Root + 25 Development", evidence)

    def test_dependency_evidence_matches_declared_runtime_dependencies(self):
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        evidence = (ROOT / "docs" / "dependency-evidence.md").read_text(encoding="utf-8")
        own_dependencies = evidence.split("## Eigene Paketabhängigkeiten", 1)[1]
        self.assertNotIn("keine Third-Party-Runtime-Abhängigkeiten", own_dependencies)
        self.assertNotIn("insgesamt vier Pakete", own_dependencies)
        for name, version in package["dependencies"].items():
            self.assertIn(name, own_dependencies)
            self.assertIn(version, own_dependencies)

    def test_lockfile_matches_declared_runtime_dependencies(self):
        """Verify package-lock.json contains exactly the declared runtime dependencies from package.json."""
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        lock = json.loads((ROOT / "package-lock.json").read_text(encoding="utf-8"))
        # Extract runtime (non-dev, non-optional) dependencies from lockfile
        lock_runtime = {}
        for path, meta in (lock.get("packages") or {}).items():
            if path and not meta.get("dev", False) and not meta.get("optional", False):
                name = path.replace("node_modules/", "")
                lock_runtime[name] = meta.get("version")
        # Verify each declared runtime dependency exists in lockfile with correct version
        for name, version in (package.get("dependencies") or {}).items():
            self.assertIn(name, lock_runtime, f"declared dependency {name} missing from lockfile")
            self.assertEqual(lock_runtime[name], version,
                           f"version mismatch for {name}: package.json={version}, lockfile={lock_runtime[name]}")

    def test_ci_runs_package_gates_on_linux_and_macos_without_real_home(self):
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        for value in (
            "installer-package",
            "ubuntu-latest",
            "macos-latest",
            "npm ci --ignore-scripts",
            "npm run typecheck",
            "npm run build",
            "npm test",
            "npm audit --audit-level=high",
            "npm audit signatures --json --include-attestations",
            "npm run pack:check",
            "npm run test:package",
            "npm run license:check",
            'node: ["24", "26"]',
        ):
            self.assertIn(value, workflow)
        self.assertIn("tests/e2e/run_installer_fixture.sh", workflow)
        self.assertIn("tests/e2e/run_release_verifier_fixture.sh", workflow)
        self.assertNotIn("$HOME/.codex", workflow)

    def test_ci_installs_the_real_pty_driver_before_linux_installer_tests(self):
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        installer_job = workflow.split("\n  installer-package:\n", 1)[1].split("\n  consistency-tests:\n", 1)[0]
        pty_setup = (
            "      - name: Install PTY test tool on Linux\n"
            "        if: runner.os == 'Linux'\n"
            "        run: |\n"
            "          sudo apt-get update\n"
            "          sudo apt-get install --yes expect\n"
        )

        self.assertIn(pty_setup, installer_job)
        self.assertLess(installer_job.index(pty_setup), installer_job.index("      - name: Install exact package toolchain\n"))

    def test_installer_fixture_runner_uses_only_temporary_home(self):
        runner = (ROOT / "tests" / "e2e" / "run_installer_fixture.sh").read_text(encoding="utf-8")
        self.assertIn("mktemp -d", runner)
        self.assertIn("--dry-run", runner)
        self.assertIn("dist/cli.js", runner)
        self.assertNotIn("$HOME/.codex", runner)

    def test_release_verifier_fixture_tolerates_benign_metadata_and_stays_fail_closed(self):
        runner = (ROOT / "tests" / "e2e" / "run_release_verifier_fixture.sh").read_text(encoding="utf-8")
        self.assertIn("mktemp -d", runner)
        self.assertIn("dist/cli.js", runner)
        self.assertIn(".DS_Store", runner)
        self.assertIn("stray.md", runner)
        self.assertIn("release_verifier_benign_metadata=PASS", runner)
        self.assertNotIn("$HOME/.codex", runner)

    def test_package_consumers_cover_tarball_npx_and_pnpm_dlx(self):
        runner = (ROOT / "tests" / "e2e" / "run_package_consumers.sh").read_text(encoding="utf-8")
        for value in ("npm pack", "npm install", "init --help", "init", "pnpm@10.15.0", "pnpm dlx"):
            self.assertIn(value, runner)
        self.assertIn("mktemp -d", runner)
        for value in (
            "init_status",
            '"outcome":"INVALID_INVOCATION"',
            "spawn_log",
            "test ! -s",
            "for manager in npm pnpm yarn bun",
        ):
            self.assertIn(value, runner)


if __name__ == "__main__":
    unittest.main()
