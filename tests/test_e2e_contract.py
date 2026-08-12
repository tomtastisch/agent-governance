#!/usr/bin/env python3
"""Clean-Linux-, echter Codex- und Secret-Isolationsverträge."""

from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
E2E = ROOT / "tests" / "e2e"


def read(name: str) -> str:
    path = E2E / name
    if not path.is_file():
        raise AssertionError(f"E2E-Artefakt fehlt: {name}")
    return path.read_text(encoding="utf-8")


class CleanImageContract(unittest.TestCase):
    def test_base_image_is_linux_pinned_codex_and_contains_no_release_or_auth(self):
        dockerfile = read("Dockerfile")
        self.assertRegex(dockerfile, r"(?m)^FROM debian:bookworm-slim$")
        self.assertIn("@openai/codex@0.147.0", dockerfile)
        for package in ("ca-certificates", "git", "python3", "nodejs", "npm"):
            self.assertIn(package, dockerfile)
        self.assertNotRegex(dockerfile, r"(?im)^\s*(?:COPY|ADD)\s+")
        for forbidden in ("auth.json", "AGENTS.md", "bundle/", "integrations/"):
            self.assertNotIn(forbidden, dockerfile)

    def test_runner_creates_identical_baseline_and_governed_resources(self):
        runner = read("run_clean_linux.sh")
        for term in (
            "baseline",
            "governed",
            "agent-governance-e2e",
            "--network none",
            "FRESH",
            "CURRENT",
            "LEGACY",
            "LC_ALL=C",
            "TZ=UTC",
            "init.defaultBranch=master",
            "HOME With Spaces",
        ):
            self.assertIn(term, runner)
        self.assertIn("--verify-secrets", runner)
        self.assertIn("--hostile-matrix", runner)

    def test_runner_canonicalizes_temporary_bind_root(self):
        runner = read("run_clean_linux.sh")
        self.assertRegex(runner, r"(?m)^e2e_tmp=\$\(CDPATH= cd -- \"\$e2e_tmp\" && pwd -P\)$")


class SecretIsolationContract(unittest.TestCase):
    def test_auth_is_runtime_only_strict_mode_and_cleaned(self):
        runner = read("run_clean_linux.sh")
        self.assertRegex(runner, r"(?m)chmod 700 .*(?:auth|codex)")
        self.assertRegex(runner, r"(?m)chmod 600 .*auth\.json")
        self.assertIn("trap cleanup EXIT", runner)
        self.assertIn("auth_cleanup=PASS", runner)
        for forbidden in (
            "sha256sum $auth",
            "shasum $auth",
            "wc -c $auth",
            "stat $auth",
            "cat $auth",
        ):
            self.assertNotIn(forbidden, runner)
        self.assertNotIn("COPY auth.json", runner)


class RealCodexContract(unittest.TestCase):
    def test_local_rules_probe_uses_fresh_codex_exec_not_prompt_debug(self):
        probe = read("run_codex_local_rules.sh")
        self.assertIn("codex exec", probe)
        self.assertIn("--ephemeral", probe)
        self.assertIn("--sandbox workspace-write", probe)
        self.assertIn("--dangerously-bypass-hook-trust", probe)
        self.assertIn("synthetic-local-rules.md", probe)
        self.assertIn("SYNTHETIC_LOCAL_RULE_ACTIVE", probe)
        self.assertNotIn("codex debug prompt-input", probe)
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", probe)

    def test_probe_matrix_contains_all_required_runtime_behaviors(self):
        probes = read("codex_probes.md")
        required = (
            "Governance discovery",
            "Canonical manifest",
            "local_rules runtime",
            "Tool routing",
            "Read-only allow",
            "Workspace mutation allow",
            "Unauthorized external effect deny",
            "Project cannot override governance",
            "Project instruction priority",
            "Provider before effect",
            "Deny prevents effect",
            "Require approval blocks",
            "Provider error fail-closed",
            "Allow is only continuation",
            "Vendored instructions are data",
        )
        for item in required:
            self.assertIn(item, probes)

    def test_synthetic_mcp_effect_is_confined_and_hook_mediated(self):
        server = read("synthetic_effect_mcp.mjs")
        self.assertIn("tools/list", server)
        self.assertIn("tools/call", server)
        self.assertIn("action_envelope", server)
        self.assertIn("SYNTHETIC_EFFECT_ROOT", server)
        self.assertIn("writeFile", server)
        self.assertNotRegex(server, r"https?://")
        probe = read("run_codex_local_rules.sh")
        self.assertIn("mcp__agent_governance__execute", probe)
        self.assertIn("codex-hook.mjs", probe)


class NeutralAndCiContract(unittest.TestCase):
    def test_neutral_runner_has_no_product_environment_default(self):
        runner = read("run_neutral_harness.sh")
        self.assertIn("tests.test_neutral_harness", runner)
        self.assertIn("tests.test_offline_runtime", runner)
        self.assertRegex(runner, r"(?m)^unset CODEX_HOME$")

    def test_ci_runs_container_independent_release_gates(self):
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        for term in (
            "python3 -m unittest discover -s tests -v",
            "python3 tools/release_check.py tree",
            "git diff --check",
            "tests/e2e/run_neutral_harness.sh",
        ):
            self.assertIn(term, ci)
        self.assertNotIn("auth.json", ci)


if __name__ == "__main__":
    unittest.main()
