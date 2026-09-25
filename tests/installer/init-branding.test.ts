import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { basename } from "node:path";
import test from "node:test";

import { BRANDING_ASSET_PATH, renderBranding } from "../../src/init/branding.ts";

test("terminal branding is a bounded PNG derived for runtime packaging", async () => {
  const bytes = await readFile(BRANDING_ASSET_PATH);
  assert.deepEqual([...bytes.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10]);
  assert.ok(bytes.readUInt32BE(16) <= 64);
  assert.ok(bytes.readUInt32BE(20) <= 64);
  assert.equal(basename(BRANDING_ASSET_PATH), "agent-governance-terminal.png");
});

test("branding uses a deterministic semantic text fallback", async () => {
  const output: string[] = [];
  await renderBranding({
    write: (value) => output.push(value),
    columns: 60,
    environment: { NO_COLOR: "1" },
  });
  assert.deepEqual(output, ["[AG] Agent Governance\n"]);
});

test("decorative renderer failure remains fail-open and continues with text", async () => {
  const output: string[] = [];
  await renderBranding({
    write: (value) => output.push(value),
    columns: 60,
    environment: {},
    renderImage: async () => { throw new Error("unsupported terminal protocol"); },
  });
  assert.deepEqual(output, ["[AG] Agent Governance\n"]);
});

test("an empty decorative render falls back to the semantic text brand", async () => {
  const output: string[] = [];
  await renderBranding({
    write: (value) => output.push(value),
    columns: 60,
    environment: { NO_COLOR: "1" },
    renderImage: async () => "",
  });
  assert.deepEqual(output, ["[AG] Agent Governance\n"]);
});
