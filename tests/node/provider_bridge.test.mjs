import assert from "node:assert/strict";
import { access, mkdtemp, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

const testDirectory = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(testDirectory, "..", "..");
const providerUrl = pathToFileURL(path.join(
  root,
  "integrations",
  "microsoft-agent-governance-toolkit",
  "bridge",
  "provider.mjs",
));
const policyPath = path.join(
  root,
  "integrations",
  "microsoft-agent-governance-toolkit",
  "bridge",
  "policy.json",
);
const unknownPolicyPath = path.join(root, "tests", "fixtures", "provider", "unknown-policy.json");
const invalidPolicyPath = path.join(root, "tests", "fixtures", "provider", "invalid-policy.json");
const policyModulePath = process.env.AGENT_GOVERNANCE_MSAGT_POLICY_MODULE;

assert.ok(policyModulePath, "AGENT_GOVERNANCE_MSAGT_POLICY_MODULE is required");

const { evaluateEnvelope } = await import(providerUrl);

function envelope(overrides = {}) {
  return {
    action_id: "action-synthetic-001",
    action: "workspace.read",
    resource: "workspace://synthetic-target",
    effect: "read",
    semantic_authorization: "allow",
    approval_context: { valid: false },
    risk_context: { requires_approval: false },
    evidence_id: "evidence-synthetic-001",
    ...overrides,
  };
}

function options(overrides = {}) {
  return { policyModulePath, policyPath, ...overrides };
}

async function effectExists(target) {
  try {
    await access(target);
    return true;
  } catch {
    return false;
  }
}

async function evaluateThenWrite(actionEnvelope, target, providerOptions = options()) {
  const result = await evaluateEnvelope(actionEnvelope, providerOptions);
  if (result.decision === "allow") {
    await writeFile(target, "synthetic harmless effect\n", { flag: "wx" });
  }
  return result;
}

test("real Microsoft PolicyEngine is the only allow continuation path", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "agent-governance-effects-"));
  try {
    const allowTarget = path.join(directory, "allow-created");
    const denyTarget = path.join(directory, "deny-not-created");
    const approvalTarget = path.join(directory, "approval-not-created");
    const errorTarget = path.join(directory, "error-not-created");

    const allowed = await evaluateThenWrite(envelope(), allowTarget);
    const denied = await evaluateThenWrite(
      envelope({ action: "network.publish", effect: "external_write" }),
      denyTarget,
    );
    const approval = await evaluateThenWrite(
      envelope({
        action: "workspace.change",
        effect: "workspace_write",
        risk_context: { requires_approval: true },
      }),
      approvalTarget,
    );
    const failed = await evaluateThenWrite(envelope(), errorTarget, options({
      policyPath: invalidPolicyPath,
    }));

    assert.equal(allowed.decision, "allow");
    assert.equal(denied.decision, "deny");
    assert.equal(approval.decision, "require_approval");
    assert.equal(failed.decision, "error");
    assert.equal(await effectExists(allowTarget), true);
    assert.equal(await effectExists(denyTarget), false);
    assert.equal(await effectExists(approvalTarget), false);
    assert.equal(await effectExists(errorTarget), false);
    for (const result of [allowed, denied, approval, failed]) {
      assert.equal(result.evaluated_before_effect, true);
    }
  } finally {
    await rm(directory, { recursive: true });
  }
});

test("governance deny cannot be expanded by the provider", async () => {
  const result = await evaluateEnvelope(
    envelope({ semantic_authorization: "deny" }),
    options(),
  );
  assert.equal(result.decision, "deny");
  assert.equal(result.provider_reached, false);
});

test("valid existing approval permits provider reevaluation", async () => {
  const result = await evaluateEnvelope(
    envelope({
      action: "workspace.change",
      effect: "workspace_write",
      approval_context: { valid: true, approval_id: "approval-synthetic-001" },
      risk_context: { requires_approval: true },
    }),
    options(),
  );
  assert.equal(result.decision, "allow");
  assert.equal(result.provider_reached, true);
});

test("unexpected Microsoft decisions normalize to unknown", async () => {
  const result = await evaluateEnvelope(envelope(), options({ policyPath: unknownPolicyPath }));
  assert.equal(result.decision, "unknown");
});

test("invalid or oversized envelopes fail before the provider", async () => {
  const missing = envelope();
  delete missing.evidence_id;
  const extra = envelope({ untrusted_extra: "not permitted" });

  for (const candidate of [missing, extra]) {
    const result = await evaluateEnvelope(candidate, options());
    assert.equal(result.decision, "error");
    assert.equal(result.provider_reached, false);
  }
});
