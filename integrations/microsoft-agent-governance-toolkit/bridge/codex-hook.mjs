import { constants as fsConstants } from "node:fs";
import { open } from "node:fs/promises";
import { createHash } from "node:crypto";
import path from "node:path";

import { evaluateEnvelope } from "./provider.mjs";

const MAX_INPUT_BYTES = 1024 * 1024;
const MAX_BINDINGS_BYTES = 64 * 1024;
const ACTION_BINDINGS_SHA256 = "3ac3c10cf9a57d275f64262b0137e3d881cc6028fcb49a6d0247f7b4ef07cffc";
const OPAQUE_ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$/;
const RESOURCE_ID = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
const BINDING_KEYS = new Set([
  "action",
  "effect",
  "semantic_authorization",
  "requires_approval",
]);

function hookOutput(permissionDecision, decision) {
  const output = {
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision,
    },
  };
  if (permissionDecision === "deny") {
    output.hookSpecificOutput.permissionDecisionReason =
      `agent-governance enforcement blocked: ${decision}`;
  }
  return output;
}

function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function hasExactKeys(value, expected) {
  const keys = Object.keys(value);
  return keys.length === expected.size && keys.every((key) => expected.has(key));
}

async function readHookInput() {
  process.stdin.setEncoding("utf8");
  let payload = "";
  for await (const chunk of process.stdin) {
    payload += chunk;
    if (Buffer.byteLength(payload, "utf8") > MAX_INPUT_BYTES) {
      throw new Error("hook_input_too_large");
    }
  }
  return JSON.parse(payload);
}

async function actionEnvelopeFromHook(input, enforcedToolName, bindingsPath) {
  if (!isPlainObject(input)
      || input.hook_event_name !== "PreToolUse"
      || typeof input.tool_use_id !== "string"
      || !OPAQUE_ID.test(input.tool_use_id)
      || input.tool_name !== enforcedToolName
      || !isPlainObject(input.tool_input)
      || Object.keys(input.tool_input).length !== 1
      || !isPlainObject(input.tool_input.action_request)
      || !hasExactKeys(
        input.tool_input.action_request,
        new Set(["operation", "resource_id"]),
      )) {
    throw new Error("invalid_hook_input");
  }
  const request = input.tool_input.action_request;
  if (typeof request.operation !== "string"
      || !OPAQUE_ID.test(request.operation)
      || typeof request.resource_id !== "string"
      || !RESOURCE_ID.test(request.resource_id)) {
    throw new Error("invalid_action_request");
  }
  if (typeof bindingsPath !== "string" || !path.isAbsolute(bindingsPath)) {
    throw new Error("action_bindings_path");
  }
  const bindingsHandle = await open(
    bindingsPath,
    fsConstants.O_RDONLY | (fsConstants.O_NOFOLLOW ?? 0),
  );
  let bindingsPayload;
  try {
    const bindingsStat = await bindingsHandle.stat();
    if (!bindingsStat.isFile() || (bindingsStat.mode & 0o022) !== 0) {
      throw new Error("action_bindings_file");
    }
    if (bindingsStat.size > MAX_BINDINGS_BYTES) {
      throw new Error("action_bindings_size");
    }
    bindingsPayload = await bindingsHandle.readFile("utf8");
  } finally {
    await bindingsHandle.close();
  }
  if (createHash("sha256").update(bindingsPayload).digest("hex") !== ACTION_BINDINGS_SHA256) {
    throw new Error("action_bindings_integrity");
  }
  const bindings = JSON.parse(bindingsPayload);
  if (!isPlainObject(bindings)
      || !hasExactKeys(
        bindings,
        new Set(["version", "tool_name", "resource_scheme", "operations"]),
      )
      || bindings.version !== 1
      || bindings.tool_name !== enforcedToolName
      || bindings.resource_scheme !== "synthetic"
      || !isPlainObject(bindings.operations)) {
    throw new Error("action_bindings_contract");
  }
  const binding = bindings.operations[request.operation];
  if (!isPlainObject(binding)
      || !hasExactKeys(binding, BINDING_KEYS)
      || typeof binding.action !== "string"
      || binding.action.length < 1
      || binding.action.length > 512
      || typeof binding.effect !== "string"
      || binding.effect.length < 1
      || binding.effect.length > 256
      || !["allow", "deny"].includes(binding.semantic_authorization)
      || typeof binding.requires_approval !== "boolean") {
    throw new Error("action_binding");
  }
  return {
    action_id: `action:${input.tool_use_id}`,
    action: binding.action,
    resource: `${bindings.resource_scheme}://${request.resource_id}`,
    effect: binding.effect,
    semantic_authorization: binding.semantic_authorization,
    approval_context: { valid: false },
    risk_context: { requires_approval: binding.requires_approval },
    evidence_id: `evidence:${input.tool_use_id}`,
  };
}

async function appendEvidence(logPath, input, providerResult) {
  if (typeof logPath !== "string" || !path.isAbsolute(logPath)) {
    throw new Error("evidence_path");
  }
  const flags = fsConstants.O_APPEND
    | fsConstants.O_CREAT
    | fsConstants.O_WRONLY
    | (fsConstants.O_NOFOLLOW ?? 0);
  const handle = await open(logPath, flags, 0o600);
  try {
    const stat = await handle.stat();
    if (!stat.isFile() || (stat.mode & 0o077) !== 0) {
      throw new Error("evidence_file_mode");
    }
    const evidence = {
      action_id: providerResult.action_id,
      evidence_id: providerResult.evidence_id,
      decision: providerResult.decision,
      provider: providerResult.provider,
      provider_reached: providerResult.provider_reached,
      evaluated_before_effect: providerResult.evaluated_before_effect,
      tool_name: input.tool_name,
      tool_use_id: input.tool_use_id,
    };
    await handle.appendFile(`${JSON.stringify(evidence)}\n`, "utf8");
    await handle.sync();
  } finally {
    await handle.close();
  }
}

async function main() {
  let decision = "error";
  try {
    const enforcedToolName = process.env.AGENT_GOVERNANCE_ENFORCED_TOOL_NAME;
    if (typeof enforcedToolName !== "string" || enforcedToolName.length < 1) {
      throw new Error("enforced_tool_name");
    }
    const input = await readHookInput();
    const envelope = await actionEnvelopeFromHook(
      input,
      enforcedToolName,
      process.env.AGENT_GOVERNANCE_ACTION_BINDINGS,
    );
    const providerResult = await evaluateEnvelope(envelope);
    decision = providerResult.decision;
    await appendEvidence(
      process.env.AGENT_GOVERNANCE_EVIDENCE_LOG,
      input,
      providerResult,
    );
    const permissionDecision = decision === "allow" ? "allow" : "deny";
    process.stdout.write(JSON.stringify(hookOutput(permissionDecision, decision)));
  } catch {
    process.stdout.write(JSON.stringify(hookOutput("deny", decision)));
  }
}

await main();
