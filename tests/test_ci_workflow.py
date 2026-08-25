#!/usr/bin/env python3
"""Regression contracts for release-critical GitHub Actions jobs."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
    encoding="utf-8"
)
TAG_GATE_PATH = ROOT / ".github" / "workflows" / "release-tag-verify.yml"
PUBLISH_PATH = ROOT / ".github" / "workflows" / "npm-publish.yml"
BOOTSTRAP_PUBLISH_PATH = ROOT / ".github" / "workflows" / "npm-bootstrap-publish.yml"
CHECKOUT_SHA = "de0fac2e4500dabe0009e67214ff5f5447ce83dd"
CHECKOUT_V7_SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"
SETUP_NODE_V7_SHA = "820762786026740c76f36085b0efc47a31fe5020"
SETUP_PYTHON_V7_SHA = "5fda3b95a4ea91299a34e894583c3862153e4b97"


def _job_block(workflow: str, job_name: str) -> str:
    match = re.search(
        rf"(?ms)^  {re.escape(job_name)}:\n"
        rf"(?P<body>.*?)(?=^  [a-z0-9_-]+:\n|\Z)",
        workflow,
    )
    if match is None:
        raise AssertionError(f"CI job not found: {job_name}")
    return match.group("body")


def _run_blocks(job_body: str) -> list[str]:
    return re.findall(
        r"(?m)^        run: \|\n"
        r"((?:          [^\n]*(?:\n|$))*)",
        job_body,
    )


class ReleaseWorkflowSecurityContract(unittest.TestCase):
    def test_installer_job_does_not_use_step_only_contexts_in_job_env(self):
        block = _job_block(CI_WORKFLOW, "installer-package")
        job_configuration = block.split("    steps:\n", 1)[0]

        self.assertNotIn("${{ runner.", job_configuration)

    def test_release_validate_preserves_pinned_main_checkout(self):
        block = _job_block(CI_WORKFLOW, "release-validate")
        checkout_line = (
            f"      - uses: actions/checkout@{CHECKOUT_SHA} # v6.0.2"
        )

        self.assertEqual(block.count("actions/checkout@"), 1)
        self.assertRegex(
            block,
            re.escape(checkout_line)
            + r"\n        with:\n"
            + r"          ref: refs/heads/main\n"
            + r"          fetch-depth: 0(?:\n|\Z)",
        )

    def test_ci_does_not_execute_release_verification_on_tag_push(self):
        self.assertNotIn('    tags: ["v*"]', CI_WORKFLOW)
        self.assertNotIn("\n  release-tag-check:\n", CI_WORKFLOW)

    def test_release_validate_passes_tag_via_env_without_run_interpolation(self):
        block = _job_block(CI_WORKFLOW, "release-validate")

        self.assertIn(
            '      - name: Release gegen Tag und VERSION prüfen\n'
            '        env:\n'
            '          RELEASE_TAG: ${{ github.event.release.tag_name }}\n'
            '        run: |\n'
            '          python3 tools/release_check.py release "$RELEASE_TAG"\n',
            block,
        )

        run_blocks = _run_blocks(block)
        self.assertTrue(run_blocks)
        for run_block in run_blocks:
            self.assertNotIn("${{", run_block)

    def test_manual_tag_gate_is_default_branch_controlled(self):
        self.assertTrue(
            TAG_GATE_PATH.is_file(),
            "trusted manual release-tag workflow is missing",
        )

        trusted = TAG_GATE_PATH.read_text(encoding="utf-8")

        self.assertIn(
            "  workflow_dispatch:\n"
            "    inputs:\n"
            "      tag:\n",
            trusted,
        )
        self.assertIn("        required: true\n", trusted)
        self.assertIn("        type: string\n", trusted)

        self.assertNotIn("\n  push:\n", trusted)
        self.assertNotIn("\n  pull_request:\n", trusted)
        self.assertNotIn("\n  release:\n", trusted)

        self.assertIn(
            "permissions:\n"
            "  contents: read\n",
            trusted,
        )

        block = _job_block(trusted, "release-tag-check")
        checkout_line = (
            f"      - uses: actions/checkout@{CHECKOUT_SHA} # v6.0.2"
        )

        self.assertIn(
            "    if: github.ref == 'refs/heads/main'\n",
            block,
        )
        self.assertEqual(block.count("actions/checkout@"), 1)
        self.assertRegex(
            block,
            re.escape(checkout_line)
            + r"\n        with:\n"
            + r"          ref: refs/heads/main\n"
            + r"          fetch-depth: 0(?:\n|\Z)",
        )
        self.assertIn(
            "          RELEASE_TAG: ${{ inputs.tag }}\n",
            block,
        )
        self.assertIn(
            '          python3 tools/release_check.py tag "$RELEASE_TAG"\n',
            block,
        )

        run_blocks = _run_blocks(block)
        self.assertTrue(run_blocks)
        for run_block in run_blocks:
            self.assertNotIn("${{", run_block)


    def test_node24_action_runtime_contract(self):
        self.assertTrue(
            TAG_GATE_PATH.is_file(),
            "trusted manual release-tag workflow is missing",
        )
        trusted = TAG_GATE_PATH.read_text(encoding="utf-8")
        consistency = _job_block(CI_WORKFLOW, "consistency-tests")
        metadata = _job_block(CI_WORKFLOW, "release-metadata")
        release = _job_block(CI_WORKFLOW, "release-validate")

        self.assertIn(f"actions/checkout@{CHECKOUT_V7_SHA} # v7", consistency)
        self.assertIn(f"actions/setup-python@{SETUP_PYTHON_V7_SHA} # v7", consistency)
        self.assertIn(f"actions/setup-node@{SETUP_NODE_V7_SHA} # v7", consistency)
        self.assertIn('node-version: "24"', consistency)
        self.assertIn("package-manager-cache: false", consistency)

        self.assertIn(f"actions/checkout@{CHECKOUT_V7_SHA} # v7", metadata)
        self.assertIn(f"actions/setup-python@{SETUP_PYTHON_V7_SHA} # v7", metadata)

        self.assertIn(f"actions/setup-python@{SETUP_PYTHON_V7_SHA} # v7", release)
        self.assertIn(f"actions/setup-python@{SETUP_PYTHON_V7_SHA} # v7", trusted)

        self.assertNotIn("actions/checkout@v4", CI_WORKFLOW)
        self.assertNotIn("actions/setup-python@v5", CI_WORKFLOW + trusted)
        self.assertNotIn("actions/setup-node@v4", CI_WORKFLOW)
        self.assertNotIn('node-version: "20"', CI_WORKFLOW)

    def test_all_repository_actions_are_pinned_to_full_commit_shas(self):
        for path in (ROOT / ".github" / "workflows").glob("*.yml"):
            workflow = path.read_text(encoding="utf-8")
            for target in re.findall(r"(?m)^\s*- uses:\s+([^\s#]+)", workflow):
                self.assertRegex(target, r"^[^@]+@[0-9a-f]{40}$", f"unpinned action in {path.name}: {target}")

    def test_npm_publish_is_main_controlled_oidc_and_fail_closed(self):
        self.assertTrue(PUBLISH_PATH.is_file(), "npm publish workflow is missing")
        workflow = PUBLISH_PATH.read_text(encoding="utf-8")
        for value in (
            "workflow_dispatch:",
            "id-token: write",
            "contents: read",
            "ref: refs/heads/main",
            'node-version: "26"',
            "registry-url: https://registry.npmjs.org",
            "npm@12.0.2",
            'python3 tools/release_check.py tag "$RELEASE_TAG"',
            'git checkout --detach "$RELEASE_TAG"',
            "npm ci --ignore-scripts",
            "npm run typecheck",
            "npm test",
            "npm run build",
            "npm run pack:check",
            'npm publish --access public --tag "$NPM_DIST_TAG"',
            "npm audit signatures",
        ):
            self.assertIn(value, workflow)
        self.assertNotIn("NODE_AUTH_TOKEN", workflow)
        self.assertIn("1.0.0-rc.*:next", workflow)
        self.assertIn("1.0.0:latest", workflow)
        for run_block in _run_blocks(_job_block(workflow, "publish")):
            self.assertNotIn("${{", run_block)

    def test_one_time_npm_bootstrap_is_rc2_only_and_secret_is_step_scoped(self):
        self.assertTrue(
            BOOTSTRAP_PUBLISH_PATH.is_file(),
            "one-time npm bootstrap workflow is missing",
        )
        workflow = BOOTSTRAP_PUBLISH_PATH.read_text(encoding="utf-8")
        for value in (
            "workflow_dispatch:",
            "contents: read",
            "ref: refs/heads/main",
            "github.ref == 'refs/heads/main'",
            'RELEASE_TAG: "v1.0.0-rc.2"',
            'NPM_DIST_TAG: "next"',
            'EXPECTED_VERSION: "1.0.0-rc.2"',
            'EXPECTED_COMMIT: "06cb0b041e20c3fda2357f4bfc2f5bc9b99aa9eb"',
            'python3 tools/release_check.py tag "$RELEASE_TAG" "$EXPECTED_COMMIT"',
            'git checkout --detach "$RELEASE_TAG"',
            'test "$(git rev-parse HEAD)" = "$EXPECTED_COMMIT"',
            "REQUIRE_ALL_NATIVE_PREBUILDS=1 npm run pack:check",
            "npm run test:package",
            "tests/e2e/run_installer_fixture.sh",
            "tests/e2e/run_neutral_harness.sh",
            'npm publish --access public --tag "$NPM_DIST_TAG"',
            "NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}",
            "npm audit signatures",
        ):
            self.assertIn(value, workflow)

        publish_block = _job_block(workflow, "publish")
        workflow_permissions = workflow.split("jobs:\n", 1)[0]
        native_block = _job_block(workflow, "native-prebuild")
        self.assertNotIn("id-token: write", workflow_permissions)
        self.assertNotIn("id-token: write", native_block)
        self.assertIn(
            "    permissions:\n"
            "      contents: read\n"
            "      id-token: write\n",
            publish_block,
        )
        before_publish, publish_and_after = publish_block.split(
            "      - name: Publish public package for first-package bootstrap\n",
            1,
        )
        publish_step, after_publish = publish_and_after.split("      - name:", 1)
        self.assertNotIn("NODE_AUTH_TOKEN", before_publish)
        self.assertIn("NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}", publish_step)
        self.assertNotIn("NODE_AUTH_TOKEN", after_publish)
        self.assertNotIn("set -x", workflow)
        self.assertNotIn("env |", workflow)
        self.assertNotIn("printenv", workflow)

        for job_name in ("native-prebuild", "publish"):
            job = _job_block(workflow, job_name)
            self.assertLess(
                job.index('python3 tools/release_check.py tag "$RELEASE_TAG" "$EXPECTED_COMMIT"'),
                job.index('git checkout --detach "$RELEASE_TAG"'),
                f"{job_name} must authenticate the immutable tag with main-controlled code before checkout",
            )

        for run_block in _run_blocks(_job_block(workflow, "publish")):
            self.assertNotIn("${{", run_block)


if __name__ == "__main__":
    unittest.main()
