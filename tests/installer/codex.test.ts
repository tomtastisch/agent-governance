import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { inspectCodex, classifyCodex } from "../../src/codex.ts";

async function home(): Promise<string> {
  return mkdtemp(join(tmpdir(), "agent-governance-codex-"));
}

test("Codex classifies empty home as FRESH", async () => {
  const codexHome = await home();
  assert.equal(classifyCodex(await inspectCodex(codexHome, join(codexHome, "governance"))), "FRESH");
});

test("Codex recognizes only enumerated legacy imports", async () => {
  const codexHome = await home();
  await writeFile(join(codexHome, "AGENTS.md"), "@~/agent-governance/adapters/AGENTS.md\n");
  assert.equal(classifyCodex(await inspectCodex(codexHome, join(codexHome, "governance"))), "LEGACY");
});

test("Codex fails closed for override instructions and conflicting markers", async () => {
  const codexHome = await home();
  await writeFile(join(codexHome, "AGENTS.override.md"), "other\n");
  assert.equal(classifyCodex(await inspectCodex(codexHome, join(codexHome, "governance"))), "UNKNOWN");

  await writeFile(join(codexHome, "AGENTS.md"), "@~/agent-governance/adapters/AGENTS.md\n");
  await mkdir(join(codexHome, "governance", "bundle", "agent-governance"), { recursive: true });
  await writeFile(join(codexHome, "governance", "bundle", "agent-governance", "manifest.toml"), "schema_version = 2\n");
  assert.equal(classifyCodex(await inspectCodex(codexHome, join(codexHome, "governance"))), "UNKNOWN");
});

test("unsupported harness is explicit and mutation-free", () => {
  assert.throws(() => classifyCodex({ harness: "opencode" }), /unsupported harness/);
});
