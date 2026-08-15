import { createInterface } from "node:readline";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const effectRoot = process.env.SYNTHETIC_EFFECT_ROOT;
if (typeof effectRoot !== "string" || !path.isAbsolute(effectRoot)) {
  process.exit(2);
}

function respond(id, result) {
  process.stdout.write(`${JSON.stringify({ jsonrpc: "2.0", id, result })}\n`);
}

function fail(id, code, message) {
  process.stdout.write(`${JSON.stringify({
    jsonrpc: "2.0",
    id,
    error: { code, message },
  })}\n`);
}

const OPERATIONS = new Set(["read", "workspace_write", "external_write", "approval_write"]);

function targetFromRequest(request) {
  if (request === null || typeof request !== "object" || Array.isArray(request)
      || Object.keys(request).length !== 2
      || !OPERATIONS.has(request.operation)
      || typeof request.resource_id !== "string") {
    throw new Error("invalid action request");
  }
  const match = /^([A-Za-z0-9][A-Za-z0-9._-]{0,127})$/.exec(request.resource_id);
  if (!match) {
    throw new Error("resource is outside synthetic namespace");
  }
  const target = path.join(effectRoot, match[1]);
  if (path.dirname(target) !== effectRoot) {
    throw new Error("effect target escaped root");
  }
  return target;
}

async function handle(message) {
  const { id, method, params } = message;
  if (method === "initialize") {
    respond(id, {
      protocolVersion: params?.protocolVersion ?? "2024-11-05",
      capabilities: { tools: {} },
      serverInfo: { name: "synthetic-effect", version: "1" },
    });
    return;
  }
  if (method === "notifications/initialized") {
    return;
  }
  if (method === "ping") {
    respond(id, {});
    return;
  }
  if (method === "tools/list") {
    respond(id, {
      tools: [{
        name: "execute",
        description: "Execute one confined synthetic effect after external hook authorization.",
        inputSchema: {
          type: "object",
          properties: {
            action_request: {
              type: "object",
              properties: {
                operation: {
                  type: "string",
                  enum: ["read", "workspace_write", "external_write", "approval_write"],
                },
                resource_id: { type: "string", pattern: "^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$" },
              },
              required: ["operation", "resource_id"],
              additionalProperties: false,
            },
          },
          required: ["action_request"],
          additionalProperties: false,
        },
      }],
    });
    return;
  }
  if (method === "tools/call") {
    if (params?.name !== "execute") {
      fail(id, -32602, "unknown tool");
      return;
    }
    try {
      const request = params.arguments?.action_request;
      const target = targetFromRequest(request);
      await mkdir(effectRoot, { recursive: true, mode: 0o700 });
      if (request.operation !== "read") {
        await writeFile(target, "synthetic effect after hook allow\n", { flag: "wx", mode: 0o600 });
      }
      respond(id, {
        content: [{ type: "text", text: "SYNTHETIC_OPERATION_COMPLETED" }],
        structuredContent: { executed: request.operation !== "read", operation: request.operation },
      });
    } catch (error) {
      fail(id, -32602, error instanceof Error ? error.message : "invalid effect");
    }
    return;
  }
  if (id !== undefined) {
    fail(id, -32601, "method not found");
  }
}

const input = createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of input) {
  if (!line.trim()) {
    continue;
  }
  try {
    await handle(JSON.parse(line));
  } catch {
    process.exitCode = 1;
    break;
  }
}
