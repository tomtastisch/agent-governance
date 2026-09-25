import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { access, link, lstat, mkdir, open, readFile, readdir, rename, rm, symlink, writeFile } from "node:fs/promises";
import { join } from "node:path";
import test from "node:test";
import { InstallerTransaction } from "../../src/transaction.ts";
import { removeManagedBlock } from "../../src/managed-block.ts";
import { createTestRoot } from "../fixtures/installer/workspace.ts";
import { createReleaseFixture } from "../fixtures/installer/release.ts";
import { replaceInstallation, type ReplacementRequest } from "../../src/replacement.ts";

async function fixture() {
  const root = await createTestRoot("replacement-");
  const targetRoot = join(root, "target");
  const sourceInstallationRoot = join(root, "old");
  const installationRoot = join(root, "new");
  const releaseRoot = join(root, "package");
  await mkdir(targetRoot);
  await mkdir(sourceInstallationRoot);
  await createReleaseFixture(releaseRoot);
  const entry = join(targetRoot, "AGENTS.md");
  const user = Buffer.from("\uFEFFprivate prefix\r\nprivate suffix\r\n");
  // The old envelope is recognizable, but its contents are deliberately unusable.
  const original = Buffer.from("\uFEFFprivate prefix\r\n<!-- BEGIN AGENT_GOVERNANCE_MANAGED_V1 -->\r\nopaque old state\r\n<!-- END AGENT_GOVERNANCE_MANAGED_V1 -->private suffix\r\n");
  await writeFile(entry, original);
  const oldReceipt = join(sourceInstallationRoot, "last-transaction.json");
  await writeFile(oldReceipt, "not JSON: opaque historical receipt\n");
  const request = { sourceInstallationRoot, installationRoot, releaseRoot, targetRoot, entryFile: "AGENTS.md" };
  return { root, request, entry, original, user, oldReceipt };
}

test("replacement isolates an opaque old entry and installs a fresh verifiable binding", async () => {
  const f = await fixture();
  const receipt = await readFile(f.oldReceipt);
  const modulePath = "../../src/replacement.ts";
  const replacement = await import(modulePath);
  assert.equal(typeof replacement.replaceInstallation, "function");
  const result = await replacement.replaceInstallation(f.request);
  assert.equal(result.outcome, "SUCCESS");
  assert.equal(result.state, "CURRENT");
  assert.deepEqual(await readFile(result.quarantine.entryPath), f.original);
  assert.deepEqual(await readFile(f.oldReceipt), receipt);
  assert.deepEqual(await readdir(f.request.sourceInstallationRoot), ["last-transaction.json"]);
  assert.deepEqual(removeManagedBlock(await readFile(f.entry)), f.user);
  const tx = new InstallerTransaction({ ...f.request, scope: "global", dryRun: false, nonInteractive: true });
  assert.equal((await tx.verify()).state, "CURRENT");
  assert.equal((await tx.status()).state, "CURRENT");
});

test("dry-run validates without reserving resources or probing by writing", async () => {
  const f = await fixture();
  const before = await lstat(f.request.targetRoot, { bigint: true });
  const result = await replaceInstallation({ ...f.request, dryRun: true });
  assert.equal(result.outcome, "PLANNED");
  assert.equal("state" in result, false);
  await assert.rejects(access(f.request.installationRoot));
  assert.deepEqual(await readdir(f.request.targetRoot), ["AGENTS.md"]);
  assert.equal((await lstat(f.request.targetRoot, { bigint: true })).mtimeNs, before.mtimeNs);
  assert.deepEqual(await readFile(f.entry), f.original);
});

for (const variant of ["missing-source", "filesystem-root-source", "overlap", "target-inside-old", "release-inside-old", "collision", "hardlink", "symlink", "directory", "missing-entry", "missing-markers", "duplicate", "foreign", "malformed", "invalid-utf8", "invalid-rules", "missing-destination-parent"] as const) {
  test(`unsafe ${variant} fails before mutation with private error details suppressed`, async () => {
    const f = await fixture();
    let request: { -readonly [K in keyof ReplacementRequest]: ReplacementRequest[K] } = { ...f.request };
    switch (variant) {
      case "missing-source": request.sourceInstallationRoot = join(f.root, "missing"); break;
      case "filesystem-root-source": request.sourceInstallationRoot = "/"; break;
      case "overlap": request.installationRoot = join(request.sourceInstallationRoot, "new"); break;
      case "target-inside-old": request.sourceInstallationRoot = f.root; break;
      case "release-inside-old": request.releaseRoot = request.sourceInstallationRoot; break;
      case "collision": await mkdir(request.installationRoot); break;
      case "hardlink": await link(f.entry, join(f.root, "alias")); break;
      case "symlink": await rename(f.entry, `${f.entry}.old`); await symlink(`${f.entry}.old`, f.entry); break;
      case "directory": await rm(f.entry); await mkdir(f.entry); break;
      case "missing-entry": await rm(f.entry); break;
      case "missing-markers": await writeFile(f.entry, "private: no markers"); break;
      case "duplicate": await writeFile(f.entry, Buffer.concat([f.original, f.original])); break;
      case "foreign": await writeFile(f.entry, f.original.toString().replaceAll("MANAGED_V1", "MANAGED_V2")); break;
      case "malformed": await writeFile(f.entry, Buffer.concat([f.original, Buffer.from("<!-- BEGIN AGENT_GOVERNANCE_MANAGED_BAD")])); break;
      case "invalid-utf8": await writeFile(f.entry, Buffer.concat([f.original, Buffer.from([0xff])])); break;
      case "invalid-rules": {
        const localRules = join(f.root, "private.md"); await writeFile(localRules, "private\0rule");
        request = { ...request, localRules } as typeof request; break;
      }
      case "missing-destination-parent": request.installationRoot = join(f.root, "missing", "new"); break;
    }
    const before = await readdir(f.request.targetRoot);
    const result = await replaceInstallation(request);
    assert.equal(result.outcome, "FAILURE", variant);
    assert.equal(JSON.stringify(result).includes("private"), false, variant);
    assert.deepEqual(await readdir(f.request.targetRoot), before, variant);
    assert.equal(await readFile(f.oldReceipt, "utf8"), "not JSON: opaque historical receipt\n");
  });
}

test("installer exception is private and the owned user entry is restored", async (t) => {
  const f = await fixture();
  t.mock.method(InstallerTransaction.prototype, "install", async () => { throw new Error("synthetic private exception: user content"); });
  const result = await replaceInstallation(f.request);
  assert.equal(result.outcome, "FAILURE");
  assert.equal(result.recovery, "RESTORED");
  assert.deepEqual(await readFile(f.entry), f.original);
  assert.deepEqual(await readFile(result.quarantine!.entryPath), f.original);
  assert.equal(JSON.stringify(result).includes("synthetic private"), false);
});

for (const race of ["entry", "same-bytes-entry", "target", "source", "destination", "quarantine"] as const) {
  test(`observable ${race} substitution at installer handoff fails closed`, async (t) => {
    const f = await fixture();
    const install = InstallerTransaction.prototype.install;
    t.mock.method(InstallerTransaction.prototype, "install", async function(this: InstallerTransaction) {
      if (race === "entry" || race === "same-bytes-entry") {
        await rename(f.entry, `${f.entry}.retired`);
        await writeFile(f.entry, race === "entry" ? "concurrent writer\n" : f.user);
      } else {
        const path = race === "target" ? f.request.targetRoot : race === "source" ? f.request.sourceInstallationRoot : race === "destination" ? f.request.installationRoot : join(f.request.targetRoot, (await readdir(f.request.targetRoot)).find(n => n.startsWith(".agent-governance-quarantine-"))!);
        await rename(path, `${path}.retired`);
        await mkdir(path);
        await writeFile(join(path, "foreign"), "concurrent owner\n");
        if (race === "target") await writeFile(f.entry, "concurrent writer\n");
      }
      return install.call(this);
    });
    const result = await replaceInstallation(f.request);
    assert.equal(result.outcome, "FAILURE");
    assert.equal(result.recovery, "RETAINED");
    if (race === "entry" || race === "target") assert.equal(await readFile(f.entry, "utf8"), "concurrent writer\n");
    if (race === "same-bytes-entry") assert.deepEqual(await readFile(f.entry), f.user);
  });
}

test("quarantine and resource references are durable before removing the live entry", async (t) => {
  const f = await fixture();
  const handle = await open(f.request.targetRoot, "r");
  const prototype = Object.getPrototypeOf(handle) as { sync: () => Promise<void> };
  const sync = prototype.sync;
  await handle.close();
  let originalProtected = false;
  t.mock.method(prototype, "sync", async function(this: typeof handle) {
    await sync.call(this);
    const names = await readdir(f.request.targetRoot);
    const name = names.find(n => n.startsWith(".agent-governance-quarantine-"));
    if (name === undefined) return;
    const quarantine = join(f.request.targetRoot, name);
    if ((await readdir(quarantine)).includes("resources.json") && (await readdir(quarantine)).includes("entry.bin")) {
      assert.deepEqual(await readFile(f.entry), f.original);
      assert.deepEqual(await readFile(join(quarantine, "entry.bin")), f.original);
      originalProtected = true;
      throw new Error("synthetic durability failure");
    }
  });
  const result = await replaceInstallation(f.request);
  assert.equal(originalProtected, true);
  assert.equal(result.outcome, "FAILURE");
  assert.deepEqual(await readFile(f.entry), f.original);
});

test("two concurrent replacements cannot both take ownership of the selected entry", async () => {
  const f = await fixture();
  const results = await Promise.all([replaceInstallation(f.request), replaceInstallation({ ...f.request, installationRoot: join(f.root, "other-new") })]);
  assert.equal(results.filter(r => r.outcome === "SUCCESS").length, 1);
  for (const result of results) if (result.outcome === "SUCCESS") assert.deepEqual(await readFile(result.quarantine.entryPath), f.original);
});

test("explicit rules are frozen at validation and only that private snapshot is installed", async (t) => {
  const f = await fixture();
  const localRules = join(f.root, "rules.md");
  await writeFile(localRules, "synthetic approved private rule\n");
  const install = InstallerTransaction.prototype.install;
  t.mock.method(InstallerTransaction.prototype, "install", async function(this: InstallerTransaction) {
    await writeFile(localRules, "different later rule\n");
    return install.call(this);
  });
  const result = await replaceInstallation({ ...f.request, localRules });
  assert.equal(result.outcome, "SUCCESS");
  assert.equal(await readFile(join(f.request.installationRoot, "releases", "1.0.0-rc.1", "bundle", "agent-governance", "local", "user-rules.md"), "utf8"), "synthetic approved private rule\n");
  assert.equal(JSON.stringify(result).includes("synthetic approved"), false);
});

test("a final verification exception restores only the attempt-owned entry", async (t) => {
  const f = await fixture();
  t.mock.method(InstallerTransaction.prototype, "verify", async () => { throw new Error("synthetic private diagnostic"); });
  const result = await replaceInstallation(f.request);
  assert.equal(result.outcome, "FAILURE");
  assert.equal(result.recovery, "RESTORED");
  assert.deepEqual(await readFile(f.entry), f.original);
});

test("another binding and its shared private rules stay verifiable and untouched", async () => {
  const f = await fixture();
  const other = join(f.root, "other-target"); await mkdir(other);
  const localRules = join(f.root, "rules.md"); await writeFile(localRules, "shared private rules\n");
  const tx = new InstallerTransaction({ ...f.request, installationRoot: f.request.sourceInstallationRoot, targetRoot: other, scope: "global", nonInteractive: true, dryRun: false, localRules });
  await tx.install();
  const before = await readFile(join(other, "AGENTS.md"));
  const result = await replaceInstallation(f.request);
  assert.equal(result.outcome, "SUCCESS");
  assert.deepEqual(await readFile(join(other, "AGENTS.md")), before);
  assert.equal((await tx.verify()).state, "CURRENT");
  await assert.rejects(access(join(f.request.installationRoot, "releases", "1.0.0-rc.1", "bundle", "agent-governance", "local", "user-rules.md")));
});

for (const fault of ["backup", "stage", "activate", "verify"] as const) {
  test(`real installer failure after ${fault} retains the original without claiming CURRENT`, async (t) => {
    const f = await fixture();
    const install = InstallerTransaction.prototype.install;
    t.mock.method(InstallerTransaction.prototype, "install", async function(this: InstallerTransaction) {
      // Test runner fault injection; the production API never accepts these controls.
      const request = (this as unknown as { request: object }).request;
      return install.call(new InstallerTransaction({ ...request, faultAfter: fault } as ConstructorParameters<typeof InstallerTransaction>[0]));
    });
    const result = await replaceInstallation(f.request);
    assert.equal(result.outcome, "FAILURE");
    assert.deepEqual(await readFile(result.quarantine!.entryPath), f.original);
    assert.equal("state" in result, false);
    if (result.recovery === "RESTORED") assert.deepEqual(await readFile(f.entry), f.original);
  });
}

for (const stage of ["before-detach", "after-detach"] as const) {
  test(`concurrent live writer ${stage} is never overwritten`, async (t) => {
    const f = await fixture();
    const handle = await open(f.request.targetRoot, "r");
    const prototype = Object.getPrototypeOf(handle) as { sync: () => Promise<void> };
    const sync = prototype.sync; await handle.close();
    let raced = false;
    t.mock.method(prototype, "sync", async function(this: typeof handle) {
      await sync.call(this);
      const name = (await readdir(f.request.targetRoot)).find(n => n.startsWith(".agent-governance-quarantine-"));
      if (name === undefined || raced) return;
      const files = await readdir(join(f.request.targetRoot, name));
      if (!files.includes("entry.bin") || files.includes("detached.bin") !== (stage === "after-detach")) return;
      raced = true;
      await writeFile(f.entry, "concurrent live writer\n");
    });
    const result = await replaceInstallation(f.request);
    assert.equal(raced, true);
    assert.equal(result.outcome, "FAILURE");
    assert.equal(await readFile(f.entry, "utf8"), "concurrent live writer\n");
    assert.deepEqual(await readFile(result.quarantine!.entryPath), f.original);
  });
}

test("a writer during the final durability sync cannot receive a false success", async (t) => {
  const f = await fixture();
  const handle = await open(f.request.targetRoot, "r");
  const prototype = Object.getPrototypeOf(handle) as { sync: () => Promise<void> };
  const sync = prototype.sync; await handle.close();
  let verified = false;
  const status = InstallerTransaction.prototype.status;
  t.mock.method(InstallerTransaction.prototype, "status", async function(this: InstallerTransaction) { const result = await status.call(this); verified = true; return result; });
  t.mock.method(prototype, "sync", async function(this: typeof handle) {
    await sync.call(this);
    if (verified) await writeFile(f.entry, "late writer\n");
  });
  const result = await replaceInstallation(f.request);
  assert.equal(result.outcome, "FAILURE");
  assert.equal(result.recovery, "RETAINED");
  assert.equal(await readFile(f.entry, "utf8"), "late writer\n");
});

test("a close failure after native detach cannot claim the live entry was unaffected", async () => {
  const f = await fixture();
  const child = spawnSync(process.execPath, ["--experimental-test-module-mocks", "--experimental-strip-types", join(import.meta.dirname, "../fixtures/installer/replacement-native-fault.ts"), JSON.stringify(f.request)], { encoding: "utf8" });
  assert.equal(child.status, 0, child.stderr);
  const result = JSON.parse(child.stdout);
  assert.equal(result.outcome, "FAILURE");
  assert.notEqual(result.recovery, "NOT_REQUIRED");
  assert.deepEqual(await readFile(result.quarantine!.entryPath), f.original);
});

test("release-local private rules cannot be implicitly imported", async () => {
  const f = await fixture();
  const rules = join(f.request.releaseRoot, "bundle", "agent-governance", "local", "user-rules.md");
  await writeFile(rules, "private release-side rule\n");
  const result = await replaceInstallation(f.request);
  assert.equal(result.outcome, "FAILURE");
  assert.deepEqual(await readFile(f.entry), f.original);
  await assert.rejects(access(f.request.installationRoot));
});

test("a writer during restoration durability sync cannot receive a false RESTORED result", async (t) => {
  const f = await fixture();
  const handle = await open(f.request.targetRoot, "r");
  const prototype = Object.getPrototypeOf(handle) as { sync: () => Promise<void> };
  const sync = prototype.sync; await handle.close();
  let restoring = false;
  t.mock.method(InstallerTransaction.prototype, "install", async () => { restoring = true; throw new Error("synthetic install failure"); });
  t.mock.method(prototype, "sync", async function(this: typeof handle) {
    await sync.call(this);
    if (restoring) await writeFile(f.entry, "restoration-time writer\n");
  });
  const result = await replaceInstallation(f.request);
  assert.equal(result.outcome, "FAILURE");
  assert.equal(result.recovery, "RETAINED");
  assert.equal(await readFile(f.entry, "utf8"), "restoration-time writer\n");
});

test("SIGKILL after detach leaves private original bytes and resource references on disk", async () => {
  const f = await fixture();
  const child = spawnSync(process.execPath, ["--experimental-test-module-mocks", "--experimental-strip-types", join(import.meta.dirname, "../fixtures/installer/replacement-native-fault.ts"), JSON.stringify(f.request), "kill"], { encoding: "utf8" });
  assert.equal(child.signal, "SIGKILL", child.stderr);
  assert.equal(child.stdout, "");
  const name = (await readdir(f.request.targetRoot)).find(n => n.startsWith(".agent-governance-quarantine-"));
  assert.notEqual(name, undefined);
  const directory = join(f.request.targetRoot, name!);
  assert.equal((await lstat(directory)).mode & 0o777, 0o700);
  assert.equal((await lstat(join(directory, "entry.bin"))).mode & 0o777, 0o600);
  assert.deepEqual(await readFile(join(directory, "entry.bin")), f.original);
  assert.deepEqual(await readFile(join(directory, "detached.bin")), f.original);
  const references = JSON.parse(await readFile(join(directory, "resources.json"), "utf8"));
  assert.equal(references.entryPath, f.entry);
  assert.equal(references.installationRoot, f.request.installationRoot);
  await assert.rejects(access(f.entry));
});
