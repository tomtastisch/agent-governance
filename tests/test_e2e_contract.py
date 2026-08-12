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
        self.assertRegex(
            dockerfile,
            r"(?m)^FROM debian:bookworm-slim@sha256:[0-9a-f]{64}$",
        )
        self.assertIn("snapshot.debian.org/archive/debian/20260803T000000Z", dockerfile)
        self.assertRegex(dockerfile, r"(?m)^\s+bubblewrap=0\.8\.0-2\+deb12u1")
        self.assertIn("npm ci", dockerfile)
        self.assertIn("package-lock.json", dockerfile)
        for package in ("bubblewrap", "ca-certificates", "git", "python3", "nodejs", "npm"):
            self.assertIn(package, dockerfile)
        self.assertRegex(dockerfile, r"(?m)^COPY package\.json package-lock\.json \.\/$")
        for forbidden in ("auth.json", "AGENTS.md", "bundle/", "integrations/"):
            self.assertNotIn(forbidden, dockerfile)

    def test_runner_creates_identical_baseline_and_governed_resources(self):
        runner = read("run_clean_linux.sh")
        for term in (
            "baseline",
            "governed",
            "agent-governance-e2e",
            "--network none",
            "codex_fresh=PASS",
            "fixture_current=PASS",
            "fixture_legacy=PASS",
            "LC_ALL=C",
            "TZ=UTC",
            "init.defaultBranch=master",
            "HOME With Spaces",
        ):
            self.assertIn(term, runner)
        self.assertNotRegex(runner, r"(?m)^\s*'CURRENT=PASS'")
        self.assertNotRegex(runner, r"(?m)^\s*'LEGACY=PASS'")
        self.assertIn("--verify-secrets", runner)
        self.assertIn("--hostile-matrix", runner)

    def test_runner_uses_runtime_shared_temporary_bind_root(self):
        runner = read("run_clean_linux.sh")
        self.assertIn(
            'shared_tmp_root=${AGENT_GOVERNANCE_E2E_TMP_ROOT:-$(dirname -- "$repository_root")}',
            runner,
        )
        self.assertNotIn('${TMPDIR:-/tmp}', runner)
        self.assertRegex(
            runner,
            r'(?m)^e2e_tmp=\$\(mktemp -d "\$shared_tmp_root/agent-governance-e2e\.XXXXXX"\)$',
        )
        self.assertRegex(runner, r"(?m)^e2e_tmp=\$\(CDPATH= cd -- \"\$e2e_tmp\" && pwd -P\)$")

    def test_real_codex_containers_keep_outer_runtime_security_boundaries(self):
        runner = read("run_clean_linux.sh")
        self.assertNotIn("seccomp=unconfined", runner)
        self.assertNotIn("apparmor=unconfined", runner)
        self.assertNotIn("--privileged", runner)
        self.assertNotIn("--cap-add", runner)

    def test_runner_requires_exact_signed_source_before_auth_mount(self):
        runner = read("run_clean_linux.sh")
        self.assertRegex(runner, r"source_ref.+\^\[0-9a-f\].+40")
        self.assertIn("git -C \"$repository_root\" verify-commit \"$source_sha\"", runner)
        self.assertNotIn("source_ref=HEAD", runner)

    def test_offline_path_reuses_materialized_provider_state_without_network(self):
        runner = read("run_clean_linux.sh")
        entrypoint = read("container_entrypoint.sh")
        offline_probe = read("run_materialized_offline.sh")
        self.assertIn("governed_state", runner)
        self.assertRegex(
            runner,
            r"(?s)--network none.+governed_state.+container_entrypoint\.sh offline",
        )
        self.assertIn("run_materialized_offline.sh", entrypoint)
        self.assertIn("microsoft-provider", offline_probe)
        self.assertIn("provider.mjs", offline_probe)
        self.assertIn("offline_materialized_provider=PASS", offline_probe)

    def test_offline_routing_probe_references_only_materialized_bundle_files(self):
        offline_probe = read("run_materialized_offline.sh")
        referenced_bundle_files = re.findall(
            r'"((?:modules|roles)/[^"\n]+\.md)"',
            offline_probe,
        )
        self.assertTrue(referenced_bundle_files)
        manifest_dir = ROOT / "bundle" / "agent-governance"
        for relative in referenced_bundle_files:
            with self.subTest(relative=relative):
                self.assertTrue((manifest_dir / relative).is_file(), relative)

    def test_persistent_governed_volume_is_initialized_for_unprivileged_runtime(self):
        entrypoint = read("container_entrypoint.sh")
        self.assertRegex(
            entrypoint,
            r'(?m)^mkdir -p .*"\$run_root/effects" "\$run_root/install"',
        )
        self.assertRegex(
            entrypoint,
            r'(?m)^chown -R e2e:e2e .*"\$run_root/effects" "\$run_root/install"',
        )
        self.assertIn('chown e2e:e2e "$run_root"', entrypoint)


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
        self.assertIn("--sandbox danger-full-access", probe)
        self.assertNotIn("--sandbox workspace-write", probe)
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
        self.assertIn("action_request", server)
        self.assertIn("operation", server)
        self.assertIn("resource_id", server)
        self.assertNotIn("semantic_authorization", server)
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
