import assert from "node:assert/strict";
import { mkdir, readFile, rename, rm, symlink, truncate, writeFile } from "node:fs/promises";
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

test("release verifier rejects a digest-bound semantically invalid discovery catalog", async () => {
  const root = await fixture();
  const catalogPath = join(root, "bundle", "agent-governance", "catalogs", "discovery-signals.toml");
  const catalog = await readFile(catalogPath, "utf8");
  const changed = catalog.replace("max_files = 256", "max_files = 0");
  assert.notEqual(changed, catalog);
  await writeFile(catalogPath, changed);
  await writeInventory(root);

  await assert.rejects(verifyRelease(root), /discovery|max_files|positive|invalid/i);
});

test("release verifier rejects a digest-bound semantically invalid command catalog", async () => {
  const root = await fixture();
  const catalogPath = join(root, "bundle", "agent-governance", "catalogs", "commands.toml");
  const catalog = await readFile(catalogPath, "utf8");
  const changed = catalog.replace('effect = "read"', 'effect = "write"');
  assert.notEqual(changed, catalog);
  await writeFile(catalogPath, changed);
  await writeInventory(root);

  await assert.rejects(verifyRelease(root), /command|semantics|invalid/i);
});

test("release verifier accepts only the legacy or complete init catalog sets", async () => {
  const full = await fixture();
  await assert.doesNotReject(verifyRelease(full));

  const legacy = await fixture();
  const legacyManifestPath = join(legacy, "bundle", "agent-governance", "manifest.toml");
  const legacyManifest = (await readFile(legacyManifestPath, "utf8"))
    .replace('commands = "catalogs/commands.toml"\n', "")
    .replace('discovery_signals = "catalogs/discovery-signals.toml"\n', "");
  await writeFile(legacyManifestPath, legacyManifest);
  await Promise.all([
    rm(join(legacy, "bundle", "agent-governance", "catalogs", "commands.toml")),
    rm(join(legacy, "bundle", "agent-governance", "catalogs", "discovery-signals.toml")),
  ]);
  await writeInventory(legacy);
  await assert.doesNotReject(verifyRelease(legacy));

  for (const missing of ["discovery_signals", "commands"] as const) {
    const partial = await fixture();
    const manifestPath = join(partial, "bundle", "agent-governance", "manifest.toml");
    const catalogFile = missing === "commands" ? "commands.toml" : "discovery-signals.toml";
    const manifestLine = missing === "commands"
      ? 'commands = "catalogs/commands.toml"\n'
      : 'discovery_signals = "catalogs/discovery-signals.toml"\n';
    await writeFile(manifestPath, (await readFile(manifestPath, "utf8")).replace(manifestLine, ""));
    await rm(join(partial, "bundle", "agent-governance", "catalogs", catalogFile));
    await writeInventory(partial);
    await assert.rejects(verifyRelease(partial), /catalogs|missing|unknown/i, `${missing} missing`);
  }
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

test("release verifier rejects invalid UTF-8 and raw controls in normative text files", async () => {
  for (const [relative, mutation] of [
    ["bundle/GOVERNANCE.md", "malformed"],
    ["bundle/GOVERNANCE.md", "nul"],
    ["bundle/agent-governance/modules/invariants.md", "nul"],
    ["bundle/agent-governance/roles/security-review.md", "nul"],
  ] as const) {
    const root = await fixture(); const path = join(root, relative); const bytes = await readFile(path); if (mutation === "malformed") { const index = bytes.indexOf(0x47); assert.notEqual(index, -1); bytes[index] = 0xff; await writeFile(path, bytes); } else await writeFile(path, Buffer.concat([bytes, Buffer.from([0])])); await writeInventory(root);
    await assert.rejects(verifyRelease(root), /UTF-8|control|normative|text/i);
  }
});

test("release verifier rejects unknown formats for manifest-referenced sources", async () => {
  for (const [from, to, mutation] of [
    ["catalogs/triggers.toml", "catalogs/triggers.txt", "plain"],
    ["modules/invariants.md", "modules/invariants.txt", "nul"],
    ["roles/security-review.md", "roles/security-review.txt", "malformed"],
  ] as const) {
    const root = await fixture(); const manifestPath = join(root, "bundle", "agent-governance", "manifest.toml"); const manifest = await readFile(manifestPath, "utf8"); await writeFile(manifestPath, manifest.replace(from, to)); const source = join(root, "bundle", "agent-governance", from); const target = join(root, "bundle", "agent-governance", to); await rename(source, target); const bytes = await readFile(target); if (mutation === "nul") await writeFile(target, Buffer.concat([bytes, Buffer.from([0])])); else if (mutation === "malformed") await writeFile(target, Buffer.concat([bytes, Buffer.from([0xff])])); await writeInventory(root);
    await assert.rejects(verifyRelease(root), /format|extension|catalog|module|role|manifest/i);
  }
});

test("release verifier permits only tab, LF, and CR from the raw C0 controls", async () => {
  const root = await fixture(); const path = join(root, "bundle", "GOVERNANCE.md"); await writeFile(path, Buffer.concat([await readFile(path), Buffer.from("\t\r\n")])); await writeInventory(root);
  await assert.doesNotReject(verifyRelease(root));
});
