import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, rm, symlink, truncate, writeFile } from "node:fs/promises";
import { join } from "node:path";
import test from "node:test";

import { verifyRelease } from "../../src/release.ts";
import { createTestRoot } from "../fixtures/installer/workspace.ts";

async function fixture(): Promise<string> {
  const root = await createTestRoot("agent-governance-release-");
  await mkdir(join(root, "bundle", "agent-governance"), { recursive: true });
  const files: Record<string, string> = {
    "VERSION": "1.0.0-rc.1\n",
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
  assert.equal(result.version, "1.0.0-rc.1");
  assert.equal(result.fileCount, 3);
  assert.match(result.governanceDigest, /^[0-9a-f]{64}$/);
  assert.match(result.manifestDigest, /^[0-9a-f]{64}$/);
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

test("release verifier rejects additional unlisted normative bundle files", async () => {
  const root = await fixture();
  await writeFile(join(root, "bundle", "unexpected.md"), "shadow rules\n");
  await assert.rejects(verifyRelease(root), /additional|unlisted|inventory/);
});

test("release verifier rejects missing required files and oversized inventory entries", async () => {
  const missing = await fixture();
  await rm(join(missing, "bundle", "GOVERNANCE.md"));
  await assert.rejects(verifyRelease(missing), /missing|ENOENT/);
  const oversized = await fixture();
  const path = "bundle/oversized.md";
  await writeFile(join(oversized, path), "");
  await truncate(join(oversized, path), 64 * 1024 * 1024 + 1);
  const current = await import("node:fs/promises").then(({ readFile }) => readFile(join(oversized, "release.files.sha256"), "utf8"));
  await writeFile(join(oversized, "release.files.sha256"), `${current}${"0".repeat(64)}  ${path}\n`);
  await assert.rejects(verifyRelease(oversized), /size limit/);
});

test("release verifier rejects actual symlinks and structurally manipulated manifests", async () => {
  const linked = await fixture();
  await symlink(join(linked, "VERSION"), join(linked, "bundle", "linked.md"));
  await assert.rejects(verifyRelease(linked), /symlink/);
  const manipulated = await fixture();
  const files: Record<string, string> = { VERSION: "1.0.0-rc.1\n", "bundle/GOVERNANCE.md": "governance\n", "bundle/agent-governance/manifest.toml": 'schema_version = 2\nlocal_rules = "../escape.md"\n' };
  for (const [path, content] of Object.entries(files)) await writeFile(join(manipulated, path), content);
  await writeFile(join(manipulated, "release.files.sha256"), `${Object.entries(files).sort(([a],[b]) => a.localeCompare(b)).map(([path,content]) => `${createHash("sha256").update(content).digest("hex")}  ${path}`).join("\n")}\n`);
  await assert.rejects(verifyRelease(manipulated), /manifest|local rules/);
});
