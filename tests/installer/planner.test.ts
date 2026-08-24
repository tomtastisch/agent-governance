import assert from "node:assert/strict";
import test from "node:test";
import { planInstallation } from "../../src/planner.ts";
test("generic plan is deterministic and excludes every harness-specific effect", () => {
  const input = { command: "install" as const, state: "FRESH" as const, entryPath: "/target/AGENTS.md", installationRoot: "/install", version: "1.0.0-rc.1", localRules: false };
  const first = planInstallation(input); assert.deepEqual(first, planInstallation(input));
  assert.equal(first.architecture, "GLOBAL_EXPLICIT_PATH_MANAGED_BLOCK"); assert.equal(first.harnessSpecificMutation, false); assert.equal(first.mcpMutation, false); assert.equal(first.hookMutation, false); assert.equal(first.approvalExpansion, false);
  assert.deepEqual(first.resources.map((resource) => resource.id), ["release", "current-metadata", "entry-file", "backup", "receipt"]);
});
test("generic plan fails closed for tampered and recovery-required states", () => {
  for (const state of ["TAMPERED", "RECOVERY_REQUIRED"] as const) assert.throws(() => planInstallation({ command: "install", state, entryPath: "/target/A.md", installationRoot: "/install", version: "1.0.0", localRules: false }), /unsafe state/);
});
test("uninstall plan preserves releases while removing only active metadata and the managed block", () => {
  const plan = planInstallation({ command: "uninstall", state: "CURRENT", entryPath: "/target/A.md", installationRoot: "/install", version: "1.0.0", localRules: false });
  assert.deepEqual(Object.fromEntries(plan.resources.map((resource) => [resource.id, resource.operation])), { release: "preserve", "current-metadata": "remove", "entry-file": "remove", backup: "create", receipt: "replace" });
});
test("update plan replaces an outdated binding and an explicitly supplied local-rules file", () => {
  const plan = planInstallation({ command: "update", state: "OUTDATED", entryPath: "/target/A.md", installationRoot: "/install", version: "1.0.0", localRules: true, localRulesPath: "local/custom-rules.md" });
  assert.deepEqual(Object.fromEntries(plan.resources.map((resource) => [resource.id, resource.operation])), { release: "create", "current-metadata": "replace", "entry-file": "replace", backup: "create", receipt: "replace", "local-rules": "replace" });
  assert.equal(plan.resources.find((resource) => resource.id === "local-rules")?.target, "/install/releases/1.0.0/bundle/agent-governance/local/custom-rules.md");
});
