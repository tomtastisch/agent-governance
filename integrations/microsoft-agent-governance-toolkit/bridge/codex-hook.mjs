import { constants as fsConstants } from "node:fs";
import { open } from "node:fs/promises";
import path from "node:path";

import { evaluateEnvelope } from "./provider.mjs";

const MAX_INPUT_BYTES = 1024 * 1024;

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

function actionEnvelopeFromHook(input, enforcedToolName) {
  if (!isPlainObject(input)
      || input.hook_event_name !== "PreToolUse"
      || typeof input.tool_use_id !== "string"
      || input.tool_name !== enforcedToolName
      || !isPlainObject(input.tool_input)
      || Object.keys(input.tool_input).length !== 1
      || !isPlainObject(input.tool_input.action_envelope)) {
    throw new Error("invalid_hook_input");
  }
  const envelope = input.tool_input.action_envelope;
  if (envelope.action_id !== input.tool_use_id) {
    throw new Error("action_binding_mismatch");
  }
  return envelope;
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
    const envelope = actionEnvelopeFromHook(input, enforcedToolName);
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
