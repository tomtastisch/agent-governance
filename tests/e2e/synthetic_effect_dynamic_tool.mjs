import { spawn } from "node:child_process";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { createInterface } from "node:readline";

const TOOL_NAME = "agent_governance__execute";
const [workspace, taskPath, schemaPath, outputPath] = process.argv.slice(2);
const effectRoot = process.env.SYNTHETIC_EFFECT_ROOT;

for (const value of [workspace, taskPath, schemaPath, outputPath, effectRoot]) {
  if (typeof value !== "string" || !path.isAbsolute(value)) {
    throw new Error("dynamic tool client requires absolute paths");
  }
}

const actionRequestSchema = {
  type: "object",
  properties: {
    operation: {
      type: "string",
      enum: ["read", "workspace_write", "external_write", "approval_write"],
    },
    resource_id: {
      type: "string",
      pattern: "^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$",
    },
  },
  required: ["operation", "resource_id"],
  additionalProperties: false,
};

function targetFromRequest(request) {
  if (request === null || typeof request !== "object" || Array.isArray(request)
      || Object.keys(request).length !== 2
      || !actionRequestSchema.properties.operation.enum.includes(request.operation)
      || typeof request.resource_id !== "string"
      || !new RegExp(actionRequestSchema.properties.resource_id.pattern).test(request.resource_id)) {
    throw new Error("invalid action request");
  }
  const target = path.join(effectRoot, request.resource_id);
  if (path.dirname(target) !== effectRoot) {
    throw new Error("effect target escaped root");
  }
  return target;
}

async function executeDynamicTool(params) {
  if (params?.namespace !== null || params?.tool !== TOOL_NAME) {
    throw new Error("unexpected dynamic tool call");
  }
  const request = params.arguments?.action_request;
  const target = targetFromRequest(request);
  if (request.operation !== "read") {
    await writeFile(target, "synthetic effect after hook allow\n", {
      flag: "wx",
      mode: 0o600,
    });
  }
  return {
    contentItems: [{ type: "inputText", text: "SYNTHETIC_OPERATION_COMPLETED" }],
    success: true,
  };
}

const timeoutMs = Number.parseInt(
  process.env.AGENT_GOVERNANCE_E2E_TIMEOUT_MS ?? "180000",
  10,
);
if (!Number.isSafeInteger(timeoutMs) || timeoutMs < 100 || timeoutMs > 300000) {
  throw new Error("invalid E2E timeout");
}

const server = spawn(
  "codex",
  ["--dangerously-bypass-hook-trust", "app-server", "--stdio"],
  {
  cwd: workspace,
  env: process.env,
  stdio: ["pipe", "pipe", "inherit"],
  },
);
const lines = createInterface({ input: server.stdout, crlfDelay: Infinity });
let nextId = 1;
const pending = new Map();
let finalMessage = null;
let expectedTurnId = null;
let terminal = false;
let completionTimer = null;
let completeTurn;
let failTurn;
const completed = new Promise((resolve, reject) => {
  completeTurn = resolve;
  failTurn = reject;
});

function failPending(error) {
  if (terminal) return;
  terminal = true;
  clearTimeout(completionTimer);
  for (const { reject, timer } of pending.values()) {
    clearTimeout(timer);
    reject(error);
  }
  pending.clear();
  failTurn(error);
}

server.once("error", (error) => failPending(error));
server.once("exit", (code, signal) => {
  if (!terminal) {
    failPending(new Error(`app-server exited before completion: ${code ?? signal}`));
  }
});

function send(message) {
  server.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", ...message })}\n`);
}

function request(method, params) {
  const id = nextId;
  nextId += 1;
  send({ id, method, params });
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      failPending(new Error(`app-server request timed out: ${method}`));
    }, timeoutMs);
    pending.set(id, { resolve, reject, timer });
  });
}

const reader = (async () => {
  for await (const line of lines) {
    if (!line.trim()) continue;
    const message = JSON.parse(line);
    if (message.id !== undefined && message.method === "item/tool/call") {
      try {
        send({ id: message.id, result: await executeDynamicTool(message.params) });
      } catch (error) {
        send({
          id: message.id,
          error: {
            code: -32602,
            message: error instanceof Error ? error.message : "dynamic tool error",
          },
        });
      }
      continue;
    }
    if (message.id !== undefined && (message.result !== undefined || message.error !== undefined)) {
      const waiter = pending.get(message.id);
      if (waiter) {
        pending.delete(message.id);
        clearTimeout(waiter.timer);
        if (message.error !== undefined) waiter.reject(new Error(JSON.stringify(message.error)));
        else waiter.resolve(message.result);
      }
      continue;
    }
    if (message.method === "item/completed" && message.params?.item?.type === "agentMessage") {
      finalMessage = message.params.item.text;
    }
    if (message.method === "turn/completed") {
      const turn = message.params?.turn;
      if (turn?.id !== expectedTurnId || turn?.status !== "completed") {
        failPending(new Error("unexpected turn completion"));
      } else if (!terminal) {
        terminal = true;
        clearTimeout(completionTimer);
        completeTurn(turn);
      }
    }
  }
  if (!terminal) failPending(new Error("app-server output ended before completion"));
})();

try {
  await request("initialize", {
    clientInfo: { name: "agent-governance-e2e", title: "Agent Governance E2E", version: "0.5.0" },
    capabilities: { experimentalApi: true },
  });
  send({ method: "initialized", params: {} });
  const started = await request("thread/start", {
    cwd: workspace,
    approvalPolicy: "never",
    sandbox: "dangerFullAccess",
    ephemeral: true,
    dynamicTools: [{
      type: "function",
      name: TOOL_NAME,
      description: "Execute one confined synthetic effect after governance authorization.",
      inputSchema: {
        type: "object",
        properties: { action_request: actionRequestSchema },
        required: ["action_request"],
        additionalProperties: false,
      },
    }],
  });
  const turnStarted = await request("turn/start", {
    threadId: started.thread.id,
    input: [{ type: "text", text: await readFile(taskPath, "utf8") }],
    outputSchema: JSON.parse(await readFile(schemaPath, "utf8")),
  });
  expectedTurnId = turnStarted.turn.id;
  completionTimer = setTimeout(() => {
    failPending(new Error("app-server turn completion timed out"));
  }, timeoutMs);
  await completed;
  if (typeof finalMessage !== "string") throw new Error("missing final agent message");
  await writeFile(outputPath, finalMessage, { flag: "wx", mode: 0o600 });
} finally {
  server.stdin.end();
  if (server.exitCode === null && server.signalCode === null) server.kill("SIGTERM");
  await reader;
}
