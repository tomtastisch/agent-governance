import { lstat, readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const PROVIDER_NAME = "microsoft-agent-governance-toolkit";
const AGENT_DID = "did:agent-governance:enforcement-provider";
const REQUIRED_KEYS = new Set([
  "action_id",
  "action",
  "resource",
  "effect",
  "semantic_authorization",
  "approval_context",
  "risk_context",
  "evidence_id",
]);
const STRING_LIMITS = {
  action: 512,
  resource: 4096,
  effect: 256,
};
const OPAQUE_ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$/;

function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function hasExactKeys(value, expected) {
  const keys = Object.keys(value);
  return keys.length === expected.size && keys.every((key) => expected.has(key));
}

function validateEnvelope(envelope) {
  if (!isPlainObject(envelope) || !hasExactKeys(envelope, REQUIRED_KEYS)) {
    return false;
  }
  for (const [key, limit] of Object.entries(STRING_LIMITS)) {
    const value = envelope[key];
    if (typeof value !== "string" || value.length < 1 || value.length > limit) {
      return false;
    }
  }
  if (!OPAQUE_ID.test(envelope.action_id) || !OPAQUE_ID.test(envelope.evidence_id)) {
    return false;
  }
  if (!["allow", "deny"].includes(envelope.semantic_authorization)) {
    return false;
  }
  if (!isPlainObject(envelope.risk_context)
      || !hasExactKeys(envelope.risk_context, new Set(["requires_approval"]))
      || typeof envelope.risk_context.requires_approval !== "boolean") {
    return false;
  }
  if (!isPlainObject(envelope.approval_context)) {
    return false;
  }
  const approvalKeys = new Set(Object.keys(envelope.approval_context));
  if (![...approvalKeys].every((key) => ["valid", "approval_id"].includes(key))) {
    return false;
  }
  if (!approvalKeys.has("valid")) {
    return false;
  }
  if (typeof envelope.approval_context.valid !== "boolean") {
    return false;
  }
  if (envelope.approval_context.valid) {
    const approvalId = envelope.approval_context.approval_id;
    if (typeof approvalId !== "string" || approvalId.length < 1 || approvalId.length > 256) {
      return false;
    }
  } else if ("approval_id" in envelope.approval_context) {
    return false;
  }
  return true;
}

function evidence(envelope, decision, providerReached, details = {}, includeIds = true) {
  const result = {
    decision,
    provider: PROVIDER_NAME,
    provider_reached: providerReached,
    evaluated_before_effect: true,
    ...details,
  };
  if (includeIds && typeof envelope?.action_id === "string") {
    result.action_id = envelope.action_id;
  }
  if (includeIds && typeof envelope?.evidence_id === "string") {
    result.evidence_id = envelope.evidence_id;
  }
  return result;
}

async function requireRegularAbsoluteFile(candidate, label) {
  if (typeof candidate !== "string" || !path.isAbsolute(candidate)) {
    throw new Error(`${label}-path`);
  }
  const stat = await lstat(candidate);
  if (!stat.isFile() || stat.isSymbolicLink()) {
    throw new Error(`${label}-file`);
  }
}

function normalizeProviderDecision(action) {
  if (["allow", "deny", "require_approval"].includes(action)) {
    return action;
  }
  return "unknown";
}

export async function evaluateEnvelope(envelope, options = {}) {
  if (!validateEnvelope(envelope)) {
    return evidence(
      envelope,
      "error",
      false,
      { error_code: "invalid_envelope" },
      false,
    );
  }
  if (envelope.semantic_authorization !== "allow") {
    return evidence(envelope, "deny", false, { matched_rule: "governance-deny" });
  }

  let effectiveEnvelope = envelope;
  if (envelope.approval_context.valid) {
    let verified = false;
    try {
      if (typeof options.approvalVerifier === "function") {
        verified = await options.approvalVerifier({
          action_id: envelope.action_id,
          evidence_id: envelope.evidence_id,
          approval_id: envelope.approval_context.approval_id,
        }) === true;
      }
    } catch {
      return evidence(envelope, "error", false, { error_code: "approval_verification" });
    }
    if (!verified) {
      effectiveEnvelope = {
        ...envelope,
        approval_context: { valid: false },
      };
    }
  }

  let providerReached = false;
  try {
    const policyModulePath = options.policyModulePath
      ?? process.env.AGENT_GOVERNANCE_MSAGT_POLICY_MODULE;
    const policyPath = options.policyPath
      ?? fileURLToPath(new URL("./policy.json", import.meta.url));
    await requireRegularAbsoluteFile(policyModulePath, "policy-module");
    await requireRegularAbsoluteFile(policyPath, "policy");
    const policyContent = await readFile(policyPath, "utf8");
    if (policyContent.length > 256 * 1024) {
      throw new Error("policy-size");
    }

    const require = createRequire(policyModulePath);
    const imported = require(policyModulePath);
    if (typeof imported.PolicyEngine !== "function") {
      throw new Error("policy-engine-export");
    }
    const engine = new imported.PolicyEngine();
    providerReached = true;
    engine.loadJson(policyContent);
    const providerResult = engine.evaluatePolicy(AGENT_DID, effectiveEnvelope);
    const decision = normalizeProviderDecision(providerResult?.action);
    const details = {};
    if (typeof providerResult?.matchedRule === "string") {
      details.matched_rule = providerResult.matchedRule;
    }
    return evidence(envelope, decision, providerReached, details);
  } catch {
    return evidence(envelope, "error", providerReached, { error_code: "provider_error" });
  }
}
