import { constants as fsConstants } from "node:fs";
import { open } from "node:fs/promises";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const PROVIDER_NAME = "microsoft-agent-governance-toolkit";
const AGENT_DID = "did:agent-governance:enforcement-provider";
const DEFAULT_POLICY_SHA256 = "2809bcda1f47390d6c9e47ac10a9cdc6a7f8014a0a95e71434aa6335652740eb";
const DEFAULT_RUNTIME_MANIFEST_SHA256 = "be2a0921e8083657ab5ae0c18ac1de7a0d06d8d299c350aa07155ffb86dab2b3";
const RUNTIME_FILES = new Set([
  "build.receipt",
  "microsoft-sdk/dist/policy.js",
  "microsoft-sdk/dist/protocol-facets.js",
  "microsoft-sdk/dist/types.js",
]);
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

async function readHandleBoundFile(candidate, label, expectedSha256, limit = 2 * 1024 * 1024) {
  if (typeof candidate !== "string" || !path.isAbsolute(candidate)) {
    throw new Error(`${label}-path`);
  }
  if (typeof expectedSha256 !== "string" || !/^[0-9a-f]{64}$/.test(expectedSha256)) {
    throw new Error(`${label}-digest`);
  }
  const flags = fsConstants.O_RDONLY | (fsConstants.O_NOFOLLOW ?? 0);
  const handle = await open(candidate, flags);
  try {
    const stat = await handle.stat();
    if (!stat.isFile() || stat.size > limit || (stat.mode & 0o022) !== 0) {
      throw new Error(`${label}-file`);
    }
    const content = await handle.readFile();
    const digest = createHash("sha256").update(content).digest("hex");
    if (digest !== expectedSha256) {
      throw new Error(`${label}-integrity`);
    }
    return content;
  } finally {
    await handle.close();
  }
}

function parseRuntimeManifest(content) {
  const expected = new Map();
  for (const line of content.toString("ascii").split("\n")) {
    if (line === "") {
      continue;
    }
    const match = /^([0-9a-f]{64})  ([A-Za-z0-9._/-]+)$/.exec(line);
    if (!match || expected.has(match[2])) {
      throw new Error("runtime-manifest-format");
    }
    expected.set(match[2], match[1]);
  }
  if (expected.size !== RUNTIME_FILES.size
      || [...RUNTIME_FILES].some((relative) => !expected.has(relative))) {
    throw new Error("runtime-manifest-files");
  }
  return expected;
}

async function loadVerifiedPolicyEngine(
  policyModulePath,
  expectedManifestPath,
  expectedManifestSha256,
) {
  const manifestHandle = await open(
    expectedManifestPath,
    fsConstants.O_RDONLY | (fsConstants.O_NOFOLLOW ?? 0),
  );
  let manifestContent;
  try {
    const stat = await manifestHandle.stat();
    if (!stat.isFile() || stat.size > 64 * 1024 || (stat.mode & 0o022) !== 0) {
      throw new Error("runtime-manifest-file");
    }
    manifestContent = await manifestHandle.readFile();
  } finally {
    await manifestHandle.close();
  }
  if (createHash("sha256").update(manifestContent).digest("hex") !== expectedManifestSha256) {
    throw new Error("runtime-manifest-integrity");
  }
  const expected = parseRuntimeManifest(manifestContent);
  const runtimeRoot = path.resolve(path.dirname(policyModulePath), "..", "..");
  if (path.normalize(policyModulePath) !== path.join(
    runtimeRoot,
    "microsoft-sdk",
    "dist",
    "policy.js",
  )) {
    throw new Error("policy-module-contract");
  }
  const installedManifest = await open(
    path.join(runtimeRoot, "runtime.files.sha256"),
    fsConstants.O_RDONLY | (fsConstants.O_NOFOLLOW ?? 0),
  );
  try {
    const stat = await installedManifest.stat();
    const installed = await installedManifest.readFile();
    if (!stat.isFile() || (stat.mode & 0o022) !== 0 || !installed.equals(manifestContent)) {
      throw new Error("installed-runtime-manifest");
    }
  } finally {
    await installedManifest.close();
  }

  await readHandleBoundFile(
    path.join(runtimeRoot, "build.receipt"),
    "build-receipt",
    expected.get("build.receipt"),
  );
  const moduleSources = new Map();
  for (const name of ["policy.js", "protocol-facets.js", "types.js"]) {
    const relative = `microsoft-sdk/dist/${name}`;
    moduleSources.set(name, await readHandleBoundFile(
      path.join(runtimeRoot, relative),
      `runtime-${name}`,
      expected.get(relative),
    ));
  }

  const cache = new Map();
  const builtins = createRequire(import.meta.url);
  function loadModule(name) {
    if (cache.has(name)) {
      return cache.get(name).exports;
    }
    const source = moduleSources.get(name);
    if (source === undefined) {
      throw new Error("runtime-module-not-pinned");
    }
    const module = { exports: {} };
    cache.set(name, module);
    const filename = path.join(runtimeRoot, "microsoft-sdk", "dist", name);
    const localRequire = (specifier) => {
      if (specifier === "fs" || specifier === "node:fs") {
        return builtins("node:fs");
      }
      if (specifier === "./types") {
        return loadModule("types.js");
      }
      if (specifier === "./protocol-facets") {
        return loadModule("protocol-facets.js");
      }
      throw new Error("runtime-require-not-pinned");
    };
    const wrapper = vm.runInThisContext(
      `(function (exports, require, module, __filename, __dirname) {\n${source.toString("utf8")}\n})`,
      { filename },
    );
    wrapper(module.exports, localRequire, module, filename, path.dirname(filename));
    return module.exports;
  }
  const imported = loadModule("policy.js");
  if (typeof imported.PolicyEngine !== "function") {
    throw new Error("policy-engine-export");
  }
  return imported.PolicyEngine;
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
    const expectedRuntimeManifestPath = options.expectedRuntimeManifestPath
      ?? fileURLToPath(new URL("./runtime.files.sha256", import.meta.url));
    const expectedRuntimeManifestSha256 = options.expectedRuntimeManifestSha256
      ?? DEFAULT_RUNTIME_MANIFEST_SHA256;
    const expectedPolicySha256 = options.expectedPolicySha256 ?? DEFAULT_POLICY_SHA256;
    const PolicyEngine = await loadVerifiedPolicyEngine(
      policyModulePath,
      expectedRuntimeManifestPath,
      expectedRuntimeManifestSha256,
    );
    const policyContent = await readHandleBoundFile(
      policyPath,
      "policy",
      expectedPolicySha256,
      256 * 1024,
    );
    const engine = new PolicyEngine();
    providerReached = true;
    engine.loadJson(policyContent.toString("utf8"));
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
