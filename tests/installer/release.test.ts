import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import test from "node:test";

import { verifyRelease } from "../../src/release.ts";
import { createTestRoot } from "../fixtures/installer/workspace.ts";

async function fixture(): Promise<string> {
  const root = await createTestRoot("agent-governance-release-");
  await mkdir(join(root, "bundle", "agent-governance"), { recursive: true });
  const files: Record<string, string> = {
    "VERSION": "0.6.0\n",
    "bundle/GOVERNANCE.md": "governance\n",
    "bundle/agent-governance/manifest.toml": "schema_version = 2\n",
  };
  for (const [path, content] of Object.entries(files)) {
    await writeFile(join(root, path), content);
  }
  const inventory = Object.entries(files)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([path, content]) => `${createHash("sha256").update(content).digest("hex")}  ${path}`)
    .join("\n");
  await writeFile(join(root, "release.files.sha256"), `${inventory}\n`);
  return root;
}

test("release verifier accepts complete digest-bound fixture", async () => {
  const root = await fixture();
  const result = await verifyRelease(root);
  assert.equal(result.version, "0.6.0");
  assert.equal(result.fileCount, 3);
});

test("release verifier rejects manipulated bundled file", async () => {
  const root = await fixture();
  await writeFile(join(root, "bundle", "GOVERNANCE.md"), "tampered\n");
  await assert.rejects(verifyRelease(root), /digest mismatch/);
});

test("release verifier rejects traversal and symlink inventory entries", async () => {
  const root = await fixture();
  await writeFile(join(root, "release.files.sha256"), `${"0".repeat(64)}  ../outside\n`);
  await assert.rejects(verifyRelease(root), /inventory path/);
});
