import assert from "node:assert/strict";
import { access, mkdtemp, mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const client = path.join(root, "tests", "e2e", "synthetic_effect_dynamic_tool.mjs");
const fakeServer = String.raw`#!/usr/bin/env node
const readline = require("node:readline");
const mode = process.env.FAKE_APP_SERVER_MODE;
function send(message) { process.stdout.write(JSON.stringify({ jsonrpc: "2.0", ...message }) + "\n"); }
if (mode === "early_exit") process.exit(7);
const input = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
input.on("line", (line) => {
  const message = JSON.parse(line);
  if (message.method === "initialize") {
    if (mode === "timeout") return;
    if (mode === "rpc_error") return send({ id: message.id, error: { code: -32600, message: "no" } });
    return send({ id: message.id, result: { userAgent: "fake" } });
  }
  if (message.method === "initialized") return;
  if (message.method === "thread/start") {
    if (message.params.dynamicTools?.[0]?.name !== "agent_governance__execute") process.exit(8);
    return send({ id: message.id, result: { thread: { id: "thread-1" } } });
  }
  if (message.method === "turn/start") {
    send({ id: message.id, result: { turn: { id: "turn-1" } } });
    if (mode === "no_completion") return;
    if (mode === "allow") return send({ id: 900, method: "item/tool/call", params: {
      namespace: null, tool: "agent_governance__execute",
      arguments: { action_request: { operation: "workspace_write", resource_id: "allow-effect" } },
    } });
    finish(mode);
    return;
  }
  if (message.id === 900) finish(mode);
});
function finish(currentMode) {
  const text = JSON.stringify({ tool_attempted: currentMode === "allow", reported_outcome: "synthetic" });
  send({ method: "item/completed", params: { item: { type: "agentMessage", text } } });
  send({ method: "turn/completed", params: { turn: {
    id: currentMode === "wrong_turn" ? "turn-other" : "turn-1",
    status: currentMode === "failed_turn" ? "failed" : "completed",
  } } });
}
`;

async function runClient(mode) {
  const directory = await mkdtemp(path.join(os.tmpdir(), "dynamic-tool-client-"));
  const bin = path.join(directory, "bin");
  const workspace = path.join(directory, "workspace");
  const effects = path.join(directory, "effects");
  await mkdir(bin);
  await mkdir(workspace);
  await mkdir(effects);
  await writeFile(path.join(bin, "codex"), fakeServer, { mode: 0o700 });
  const task = path.join(directory, "task.md");
  const schema = path.join(directory, "schema.json");
  const output = path.join(directory, "output.json");
  await writeFile(task, "synthetic task\n");
  await writeFile(schema, '{"type":"object"}\n');
  const result = spawnSync(process.execPath, [client, workspace, task, schema, output], {
    env: {
      ...process.env,
      PATH: `${bin}${path.delimiter}${process.env.PATH ?? ""}`,
      SYNTHETIC_EFFECT_ROOT: effects,
      AGENT_GOVERNANCE_E2E_TIMEOUT_MS: "1000",
      FAKE_APP_SERVER_MODE: mode,
    },
    encoding: "utf8",
    timeout: 8_000,
  });
  return { effects, output, result };
}

async function exists(target) {
  try { await access(target); return true; } catch { return false; }
}

test("client completes one confined effect for an allowed dynamic tool call", async () => {
  const { effects, output, result } = await runClient("allow");
  assert.equal(result.status, 0, result.stderr);
  assert.equal(await exists(path.join(effects, "allow-effect")), true);
  assert.equal(JSON.parse(await readFile(output, "utf8")).reported_outcome, "synthetic");
});

test("client performs no effect when app-server sends no dynamic tool call", async () => {
  const { effects, result } = await runClient("no_call");
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(await readdir(effects), []);
});

for (const mode of [
  "early_exit",
  "rpc_error",
  "timeout",
  "no_completion",
  "wrong_turn",
  "failed_turn",
]) {
  test(`client fails closed for ${mode}`, async () => {
    const { effects, result } = await runClient(mode);
    assert.equal(result.signal, null, `client hung for ${mode}`);
    assert.notEqual(result.status, 0);
    assert.deepEqual(await readdir(effects), []);
  });
}
