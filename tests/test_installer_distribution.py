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
        self.assertEqual(
            package["dependencies"],
            {"@clack/prompts": "1.7.0", "smol-toml": "1.8.0"},
        )
        self.assertEqual(
            package["keywords"],
            ["agent-governance", "governance", "installer", "ai", "llm"],
        )
        self.assertIn("interactive", package["description"].lower())
        self.assertNotIn("terminal-image", package["dependencies"])
        self.assertNotIn("chalk", package["dependencies"])
        self.assertNotIn("boxen", package["dependencies"])
        self.assertNotIn("log-update", package["dependencies"])
        self.assertEqual(package["devDependencies"]["typescript"], "5.9.2")
        self.assertEqual(package["devDependencies"]["@types/node"], "24.3.0")
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
        self.assertEqual(len(packages), 11)
        self.assertEqual(len(production), 7)
        self.assertEqual(len(development), 3)
        self.assertIn("11 = 1 Root + 7 Production ohne Root + 3 Development", evidence)

    def test_dependency_evidence_matches_declared_runtime_dependencies(self):
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        evidence = (ROOT / "docs" / "dependency-evidence.md").read_text(encoding="utf-8")
        own_dependencies = evidence.split("## Eigene Paketabhängigkeiten", 1)[1]
        self.assertNotIn("keine Third-Party-Runtime-Abhängigkeiten", own_dependencies)
        self.assertNotIn("insgesamt vier Pakete", own_dependencies)
        for name, version in package["dependencies"].items():
            self.assertIn(name, own_dependencies)
            self.assertIn(version, own_dependencies)

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
            "npm run pack:check",
            "npm run test:package",
            "npm run license:check",
            'node: ["24", "26"]',
        ):
            self.assertIn(value, workflow)
        self.assertIn("tests/e2e/run_installer_fixture.sh", workflow)
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
