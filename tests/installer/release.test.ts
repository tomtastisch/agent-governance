import assert from "node:assert/strict";
import { mkdir, readFile, rm, symlink, truncate, writeFile } from "node:fs/promises";
import { join } from "node:path";
import test from "node:test";

import { verifyRelease } from "../../src/release.ts";
import { createTestRoot } from "../fixtures/installer/workspace.ts";
import { createReleaseFixture, writeInventory } from "../fixtures/installer/release.ts";

async function fixture(): Promise<string> {
  const root = await createTestRoot("agent-governance-release-");
  return createReleaseFixture(root);
}

test("release verifier accepts complete digest-bound fixture", async () => {
  const root = await fixture();
  const result = await verifyRelease(root);
  assert.equal(result.version, "1.0.0-rc.1");
  assert.equal(result.fileCount > 3, true);
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
  const manifestPath = join(manipulated, "bundle", "agent-governance", "manifest.toml");
  await writeFile(manifestPath, (await readFile(manifestPath, "utf8")).replace('local_rules = "local/user-rules.md"', 'local_rules = "../escape.md"'));
  await writeInventory(manipulated);
  await assert.rejects(verifyRelease(manipulated), /manifest|local rules/);
});

test("release verifier rejects unknown manifest fields even when inventory digests match", async () => {
  const root = await fixture();
  const manifestPath = join(root, "bundle", "agent-governance", "manifest.toml");
  await writeFile(manifestPath, `${await readFile(manifestPath, "utf8")}unknown_normative_source = "shadow.md"\n`);
  await writeInventory(root);
  await assert.rejects(verifyRelease(root), /manifest|unknown/i);
});

test("release verifier rejects listed but unreferenced normative bundle files", async () => {
  const root = await fixture();
  await writeFile(join(root, "bundle", "agent-governance", "modules", "shadow.md"), "unreferenced normative source\n");
  await writeInventory(root);
  await assert.rejects(verifyRelease(root), /unknown|unreferenced|normative/i);
});

test("release verifier rejects symlinked release and bundle roots", async () => {
  for (const component of ["release", "bundle"] as const) {
    const physical = await fixture();
    const parent = await createTestRoot(`agent-governance-${component}-link-`);
    const linked = component === "release" ? join(parent, "linked-release") : join(parent, "release");
    if (component === "release") await symlink(physical, linked);
    else {
      await mkdir(linked);
      await symlink(join(physical, "bundle"), join(linked, "bundle"));
      for (const name of ["VERSION", "release.files.sha256"]) await writeFile(join(linked, name), await readFile(join(physical, name)));
    }
    await assert.rejects(verifyRelease(linked), /symlink|canonical/i);
  }
});

test("release verifier rejects TOML forms rejected by conforming parsers", async () => {
  for (const mutate of [
    (text: string) => text.replace("schema_version = 2", "schema_version = 02"),
    (text: string) => `${text}\n[catalogs]\n`,
  ]) {
    const root = await fixture(); const manifestPath = join(root, "bundle", "agent-governance", "manifest.toml"); await writeFile(manifestPath, mutate(await readFile(manifestPath, "utf8"))); await writeInventory(root);
    await assert.rejects(verifyRelease(root), /TOML|manifest|duplicate|table/i);
  }
  for (const replacement of ['label = "Analysis\\/invalid"', 'label = "\\ud800"', 'label = "\\udc00"']) { const escaped = await fixture(); const catalogPath = join(escaped, "bundle", "agent-governance", "catalogs", "triggers.toml"); const catalog = await readFile(catalogPath, "utf8"); const changed = catalog.replace('label = "Analysis"', replacement); assert.notEqual(changed, catalog); await writeFile(catalogPath, changed); await writeInventory(escaped); await assert.rejects(verifyRelease(escaped), /TOML|invalid/i); }
  const multiline = await fixture(); const multilinePath = join(multiline, "bundle", "agent-governance", "catalogs", "triggers.toml"); const multilineCatalog = await readFile(multilinePath, "utf8"); await writeFile(multilinePath, multilineCatalog.replace('description = """', 'description = """\\q')); await writeInventory(multiline); await assert.rejects(verifyRelease(multiline), /TOML|invalid/i);
  const nul = await fixture(); const nulPath = join(nul, "bundle", "agent-governance", "catalogs", "triggers.toml"); await writeFile(nulPath, (await readFile(nulPath, "utf8")).replace('description = """', 'description = """\0')); await writeInventory(nul); await assert.rejects(verifyRelease(nul), /TOML|control|invalid/i);
  const malformed = await fixture(); const malformedPath = join(malformed, "bundle", "agent-governance", "catalogs", "triggers.toml"); const malformedBytes = await readFile(malformedPath); const label = malformedBytes.indexOf(Buffer.from("Analysis")); assert.notEqual(label, -1); malformedBytes[label] = 0xff; await writeFile(malformedPath, malformedBytes); await writeInventory(malformed); await assert.rejects(verifyRelease(malformed), /UTF-8|encoding|TOML|invalid/i);
});
