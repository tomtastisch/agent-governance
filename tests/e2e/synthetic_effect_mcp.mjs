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

function targetFromEnvelope(envelope) {
  if (envelope === null || typeof envelope !== "object" || Array.isArray(envelope)) {
    throw new Error("invalid envelope");
  }
  const match = /^synthetic:\/\/([A-Za-z0-9._-]+)$/.exec(envelope.resource);
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
            action_envelope: {
              type: "object",
              properties: {
                action_id: { type: "string" },
                action: { type: "string" },
                resource: { type: "string" },
                effect: { type: "string" },
                semantic_authorization: { type: "string", enum: ["allow", "deny"] },
                approval_context: { type: "object" },
                risk_context: { type: "object" },
                evidence_id: { type: "string" },
              },
              required: [
                "action_id",
                "action",
                "resource",
                "effect",
                "semantic_authorization",
                "approval_context",
                "risk_context",
                "evidence_id",
              ],
              additionalProperties: false,
            },
          },
          required: ["action_envelope"],
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
      const envelope = params.arguments?.action_envelope;
      const target = targetFromEnvelope(envelope);
      await mkdir(effectRoot, { recursive: true, mode: 0o700 });
      await writeFile(target, "synthetic effect after hook allow\n", { flag: "wx", mode: 0o600 });
      respond(id, {
        content: [{ type: "text", text: "SYNTHETIC_EFFECT_EXECUTED" }],
        structuredContent: { executed: true, action_id: envelope.action_id },
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
