import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class InstallerPackageContract(unittest.TestCase):
    def test_package_is_node24_strict_and_zero_runtime_dependency(self):
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["engines"]["node"], ">=24")
        self.assertNotIn("dependencies", package)
        self.assertEqual(package["devDependencies"]["typescript"], "5.9.2")
        self.assertEqual(package["devDependencies"]["@types/node"], "24.3.0")
        self.assertEqual(package["bin"]["agent-governance"], "dist/cli.js")

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
            "npm pack --dry-run --json",
        ):
            self.assertIn(value, workflow)
        self.assertIn("tests/e2e/run_installer_fixture.sh", workflow)
        self.assertNotIn("$HOME/.codex", workflow)

    def test_installer_fixture_runner_uses_only_temporary_home(self):
        runner = (ROOT / "tests" / "e2e" / "run_installer_fixture.sh").read_text(encoding="utf-8")
        self.assertIn("mktemp -d", runner)
        self.assertIn("--dry-run", runner)
        self.assertIn("dist/cli.js", runner)
        self.assertNotIn("$HOME/.codex", runner)


if __name__ == "__main__":
    unittest.main()
