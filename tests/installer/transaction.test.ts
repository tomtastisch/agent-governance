import assert from "node:assert/strict";
import { access, mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { mkdirSync, readdirSync, renameSync, statSync, symlinkSync, writeFileSync } from "node:fs";
import test from "node:test";
import { InstallerTransaction } from "../../src/transaction.ts";
import { InstallerFailure, InterruptedFailure } from "../../src/errors.ts";
import type { CatchableSignal, SignalSource } from "../../src/signals.ts";
import { createTestRoot } from "../fixtures/installer/workspace.ts";
import { createReleaseFixture, writeInventory } from "../fixtures/installer/release.ts";

class TestSignals implements SignalSource { private readonly values = new Map<CatchableSignal, Set<() => void>>(); on(signal: CatchableSignal, listener: () => void): void { const set = this.values.get(signal) ?? new Set(); set.add(listener); this.values.set(signal, set); } off(signal: CatchableSignal, listener: () => void): void { this.values.get(signal)?.delete(listener); } emit(signal: CatchableSignal): void { for (const listener of this.values.get(signal) ?? []) listener(); } count(): number { return [...this.values.values()].reduce((sum, set) => sum + set.size, 0); } }

async function fixture() {
  const root = await createTestRoot("agent-governance-generic-"); const targetRoot = join(root, "target"); const releaseRoot = join(root, "package"); const installationRoot = join(root, "installation"); await mkdir(targetRoot); await createReleaseFixture(releaseRoot);
  const request = { targetRoot, entryFile: "AGENTS.md", scope: "global" as const, installationRoot, releaseRoot, dryRun: false, nonInteractive: true };
  return { root, targetRoot, releaseRoot, installationRoot, request, entry: join(targetRoot, "AGENTS.md") };
}

async function releaseFixture(root: string, version: string): Promise<string> {
  const releaseRoot = join(root, `package-${version}`);
  return createReleaseFixture(releaseRoot, version);
}

async function bindingStateRoot(installationRoot: string): Promise<string> {
  const ids = await readdir(join(installationRoot, "bindings"));
  assert.equal(ids.length, 1);
  return join(installationRoot, "bindings", ids[0]!);
}

function findNamed(root: string, name: string): string | undefined {
  for (const entry of readdirSync(root)) {
    const path = join(root, entry); const stat = statSync(path);
    if (stat.isDirectory()) { const nested = findNamed(path, name); if (nested !== undefined) return nested; }
    else if (entry === name) return path;
  }
  return undefined;
}

test("dry-run plans without filesystem mutation", async () => { const f = await fixture(); const result = await new InstallerTransaction({ ...f.request, dryRun: true }).install(); assert.equal(result.phase, "plan"); await assert.rejects(access(f.entry)); await assert.rejects(access(f.installationRoot)); });
test("install preserves user bytes, materializes binding, verifies, and is idempotent", async () => { const f = await fixture(); const user = Buffer.from("personal prefix without newline", "utf8"); await writeFile(f.entry, user); const tx = new InstallerTransaction(f.request); const result = await tx.install(); assert.equal(result.state, "CURRENT"); assert.equal((await readFile(f.entry)).subarray(0, user.length).equals(user), true); assert.equal((await tx.verify()).state, "CURRENT"); const before = await readFile(f.entry); assert.equal((await tx.install()).state, "CURRENT"); assert.deepEqual(await readFile(f.entry), before); });
test("uninstall removes only the managed block and rollback restores the complete previous file", async () => { const f = await fixture(); const original = Buffer.from("before\r\nafter\r\n", "utf8"); await writeFile(f.entry, original); const tx = new InstallerTransaction(f.request); await tx.install(); await tx.uninstall(); assert.deepEqual(await readFile(f.entry), original); assert.equal((await tx.rollback()).state, "CURRENT"); assert.equal((await readFile(f.entry)).includes(Buffer.from("AGENT_GOVERNANCE_MANAGED_V1")), true); assert.equal((await tx.rollback()).state, "CURRENT"); });
test("update recognizes a valid older release and atomically installs the newer release", async () => { const f = await fixture(); const first = await releaseFixture(f.root, "1.0.0-rc.1"); const second = await releaseFixture(f.root, "1.0.0-rc.2"); await new InstallerTransaction({ ...f.request, releaseRoot: first }).install(); const update = new InstallerTransaction({ ...f.request, releaseRoot: second }); const outdated = await update.status(); assert.equal(outdated.state, "OUTDATED"); assert.deepEqual(outdated.capabilities, ["FILESYSTEM_INSTALLED", "BINDING_MATERIALIZED", "DIGEST_VERIFIED", "ROLLBACK_AVAILABLE"]); assert.equal(outdated.rollbackStatus, "AVAILABLE"); assert.equal((await update.update()).state, "CURRENT"); assert.match(await readFile(f.entry, "utf8"), /Governance version: 1\.0\.0-rc\.2/); assert.equal((await update.verify()).state, "CURRENT"); });
test("downgrade remains blocked without an explicit downgrade contract", async () => { const f = await fixture(); const older = await releaseFixture(f.root, "1.0.0-rc.1"); const newer = await releaseFixture(f.root, "1.0.0-rc.2"); await new InstallerTransaction({ ...f.request, releaseRoot: newer }).install(); const downgrade = new InstallerTransaction({ ...f.request, releaseRoot: older }); assert.equal((await downgrade.status()).state, "DOWNGRADE_BLOCKED"); await assert.rejects(downgrade.update(), /unsafe install state: DOWNGRADE_BLOCKED/); assert.match(await readFile(f.entry, "utf8"), /Governance version: 1\.0\.0-rc\.2/); });
test("tampered managed binding fails closed without replacing user bytes", async () => { const f = await fixture(); const tx = new InstallerTransaction(f.request); await tx.install(); await writeFile(f.entry, (await readFile(f.entry, "utf8")).replace("Expected manifest SHA-256", "Tampered manifest SHA-256")); const before = await readFile(f.entry); await assert.rejects(tx.update(), /unsafe install state/); assert.deepEqual(await readFile(f.entry), before); });
test("signal after receipt performs one rollback and removes listeners", async () => { const f = await fixture(); const signals = new TestSignals(); let emitted = false; const tx = new InstallerTransaction({ ...f.request, signalSource: signals, onCheckpoint: (checkpoint) => { if (!emitted && checkpoint === "afterReceipt") { emitted = true; signals.emit("SIGTERM"); signals.emit("SIGINT"); } } }); await assert.rejects(tx.install(), (error: unknown) => { assert.equal(error instanceof InterruptedFailure, true); assert.equal((error as InterruptedFailure).signal, "SIGTERM"); assert.equal((error as InterruptedFailure).rollbackStatus, "SUCCEEDED"); return true; }); assert.equal(signals.count(), 0); await assert.rejects(access(f.entry)); assert.notEqual((await tx.status()).state, "RECOVERY_REQUIRED"); });
test("signal before mutation leaves both target and installation root absent", async () => { const f = await fixture(); const signals = new TestSignals(); const tx = new InstallerTransaction({ ...f.request, signalSource: signals, onCheckpoint: (checkpoint) => { if (checkpoint === "beforeMutation") signals.emit("SIGINT"); } }); await assert.rejects(tx.install(), (error: unknown) => error instanceof InterruptedFailure && error.signal === "SIGINT"); await assert.rejects(access(f.entry)); await assert.rejects(access(f.installationRoot)); });
test("signal during mutation rolls back once and ignores a repeated signal during rollback", async () => { const f = await fixture(); const signals = new TestSignals(); const original = Buffer.from("original\n"); await writeFile(f.entry, original); let emitted = false; const tx = new InstallerTransaction({ ...f.request, signalSource: signals, onCheckpoint: (checkpoint) => { if (!emitted && checkpoint === "afterEntry") { emitted = true; signals.emit("SIGTERM"); } else if (checkpoint === "duringRollback") signals.emit("SIGINT"); } }); await assert.rejects(tx.install(), (error: unknown) => error instanceof InterruptedFailure && error.signal === "SIGTERM" && error.rollbackStatus === "SUCCEEDED"); assert.deepEqual(await readFile(f.entry), original); assert.equal(signals.count(), 0); });
test("rollback failure leaves a recoverable prepared receipt and explicit recovery restores prior bytes", async () => { const f = await fixture(); const original = Buffer.from("recover me\n"); await writeFile(f.entry, original); const failed = new InstallerTransaction({ ...f.request, faultAfter: "activate", faultDuringRollback: true }); await assert.rejects(failed.install(), (error: unknown) => error instanceof InstallerFailure && error.outcome === "ROLLBACK_FAILED"); assert.equal((await new InstallerTransaction(f.request).status()).state, "RECOVERY_REQUIRED"); assert.equal((await new InstallerTransaction(f.request).rollback()).state, "FRESH"); assert.deepEqual(await readFile(f.entry), original); });
test("rollback rejects receipt traversal and non-direct release or local-rules targets", async () => { for (const mutation of [
  (receipt: Record<string, unknown>, f: Awaited<ReturnType<typeof fixture>>) => { receipt.backupRoot = join(f.installationRoot, "backups", "..", "escape"); },
  (receipt: Record<string, unknown>) => { receipt.releasePath = join(String(receipt.releasePath), "nested"); },
  (receipt: Record<string, unknown>) => { receipt.localRulesPath = join(String(receipt.releasePath), "VERSION.md"); },
]) { const f = await fixture(); const tx = new InstallerTransaction(f.request); await tx.install(); const receiptPath = join(await bindingStateRoot(f.installationRoot), "last-transaction.json"); const receipt = JSON.parse(await readFile(receiptPath, "utf8")) as Record<string, unknown>; mutation(receipt, f); await writeFile(receiptPath, `${JSON.stringify(receipt)}\n`); await assert.rejects(tx.rollback(), /receipt has invalid values|receipt copies differ/); assert.equal((await readFile(f.entry, "utf8")).includes("AGENT_GOVERNANCE_MANAGED_V1"), true); } });
test("rollback revalidates the explicit target before restoring bytes", async () => { const f = await fixture(); await writeFile(f.entry, "original\n"); const tx = new InstallerTransaction(f.request); await tx.install(); const retired = `${f.targetRoot}-retired`; const outside = join(f.root, "rollback-outside"); await mkdir(outside); renameSync(f.targetRoot, retired); symlinkSync(outside, f.targetRoot); await assert.rejects(tx.rollback(), /symlink|canonical/); await assert.rejects(access(join(outside, "AGENTS.md"))); });
test("explicit local rules are installed at the manifest path without entering output metadata", async () => { const f = await fixture(); const localRules = join(f.root, "private-rules.md"); await writeFile(localRules, "synthetic private rule\n"); const result = await new InstallerTransaction({ ...f.request, localRules }).install(); assert.equal(result.state, "CURRENT"); assert.equal(await readFile(join(f.installationRoot, "releases", "1.0.0-rc.1", "bundle", "agent-governance", "local", "user-rules.md"), "utf8"), "synthetic private rule\n"); assert.equal(JSON.stringify(result).includes("synthetic private rule"), false); });
test("update preserves installed local rules when no new source is supplied", async () => { const f = await fixture(); const first = await releaseFixture(f.root, "1.0.0-rc.1"); const second = await releaseFixture(f.root, "1.0.0-rc.2"); const localRules = join(f.root, "private-rules.md"); await writeFile(localRules, "preserve this private rule\n"); await new InstallerTransaction({ ...f.request, releaseRoot: first, localRules }).install(); await new InstallerTransaction({ ...f.request, releaseRoot: second }).update(); assert.equal(await readFile(join(f.installationRoot, "releases", "1.0.0-rc.2", "bundle", "agent-governance", "local", "user-rules.md"), "utf8"), "preserve this private rule\n"); });
test("update replaces local rules only from a new explicit source and rollback restores them", async () => { const f = await fixture(); const original = join(f.root, "original-rules.md"); const replacement = join(f.root, "replacement-rules.md"); await writeFile(original, "original private rule\n"); await writeFile(replacement, "replacement private rule\n"); const target = join(f.installationRoot, "releases", "1.0.0-rc.1", "bundle", "agent-governance", "local", "user-rules.md"); await new InstallerTransaction({ ...f.request, localRules: original }).install(); const update = new InstallerTransaction({ ...f.request, localRules: replacement }); await update.update(); assert.equal(await readFile(target, "utf8"), "replacement private rule\n"); assert.equal((await update.rollback()).state, "CURRENT"); assert.equal(await readFile(target, "utf8"), "original private rule\n"); });
for (const phase of ["backup", "stage", "activate", "verify"] as const) test(`failure after ${phase} restores the complete previous entry`, async () => { const f = await fixture(); const original = Buffer.from("user bytes\r\n"); await writeFile(f.entry, original); await assert.rejects(new InstallerTransaction({ ...f.request, faultAfter: phase }).install(), /rolled back|injected|verification/i); assert.deepEqual(await readFile(f.entry), original); });
test("target root replacement between backup and mutation fails closed", async () => { const f = await fixture(); const retired = `${f.targetRoot}-retired`; let replaced = false; const tx = new InstallerTransaction({ ...f.request, onCheckpoint: (checkpoint) => { if (!replaced && checkpoint === "afterReceipt") { replaced = true; renameSync(f.targetRoot, retired); mkdirSync(f.targetRoot); } } }); await assert.rejects(tx.install(), /identity changed|rolled back/); await assert.rejects(access(f.entry)); });
test("entry parent replacement between backup and mutation fails closed", async () => { const f = await fixture(); const parent = join(f.targetRoot, "nested"); const outside = join(f.root, "outside"); await mkdir(parent); await mkdir(outside); const request = { ...f.request, entryFile: "nested/AGENTS.md" }; let replaced = false; const tx = new InstallerTransaction({ ...request, onCheckpoint: (checkpoint) => { if (!replaced && checkpoint === "afterReceipt") { replaced = true; renameSync(parent, `${parent}-retired`); symlinkSync(outside, parent); } } }); await assert.rejects(tx.install(), /identity changed|symlink|rolled back/); await assert.rejects(access(join(outside, "AGENTS.md"))); });
test("entry replacement between backup and mutation fails closed without overwriting the replacement", async () => { const f = await fixture(); await writeFile(f.entry, "original user bytes\n"); let replaced = false; const tx = new InstallerTransaction({ ...f.request, onCheckpoint: (checkpoint) => { if (!replaced && checkpoint === "afterReceipt") { replaced = true; renameSync(f.entry, `${f.entry}-retired`); writeFileSync(f.entry, "concurrent replacement\n"); } } }); await assert.rejects(tx.install(), /identity changed|rolled back/); assert.equal(await readFile(f.entry, "utf8"), "concurrent replacement\n"); });
test("installation root replacement after backup fails closed before activation", async () => { const f = await fixture(); const outside = join(f.root, "outside-installation"); await mkdir(outside); let replaced = false; const tx = new InstallerTransaction({ ...f.request, onCheckpoint: (checkpoint) => { if (!replaced && checkpoint === "afterReceipt") { replaced = true; renameSync(f.installationRoot, `${f.installationRoot}-retired`); symlinkSync(outside, f.installationRoot); } } }); await assert.rejects(tx.install(), /identity changed|symlink|rolled back/); await assert.rejects(access(join(outside, "current.json"))); await assert.rejects(access(f.entry)); });
test("symlinked internal backup or release directories are rejected without writing outside", async () => { for (const internal of ["backups", "releases"]) { const f = await fixture(); const outside = join(f.root, `outside-${internal}`); await mkdir(f.installationRoot); await mkdir(outside); symlinkSync(outside, join(f.installationRoot, internal)); await assert.rejects(new InstallerTransaction(f.request).install(), /symlink|canonical/); assert.deepEqual(await readFile(f.entry).catch(() => Buffer.alloc(0)), Buffer.alloc(0)); assert.deepEqual(await import("node:fs/promises").then(({ readdir }) => readdir(outside)), []); } });

test("one installation root supports independent explicit target bindings", async () => {
  const f = await fixture(); const secondTarget = join(f.root, "second-target"); await mkdir(secondTarget);
  const first = new InstallerTransaction(f.request);
  const secondRequest = { ...f.request, targetRoot: secondTarget, entryFile: "CLAUDE.md" };
  const second = new InstallerTransaction(secondRequest);
  await first.install(); await second.install();
  assert.equal((await first.status()).state, "CURRENT"); assert.equal((await second.verify()).state, "CURRENT");
  assert.equal((await readdir(join(f.installationRoot, "bindings"))).length, 2);
  await second.uninstall(); assert.equal((await first.verify()).state, "CURRENT"); assert.equal((await second.rollback()).state, "CURRENT");
});

test("same version with changed normative module is rejected as content drift", async () => {
  const f = await fixture(); await new InstallerTransaction(f.request).install();
  const changed = await releaseFixture(f.root, "1.0.0-rc.1-changed");
  await writeFile(join(changed, "VERSION"), "1.0.0-rc.1\n");
  const modulePath = join(changed, "bundle", "agent-governance", "modules", "evidence.md");
  await writeFile(modulePath, `${await readFile(modulePath, "utf8")}\nchanged same-version module\n`); await writeInventory(changed);
  assert.equal((await new InstallerTransaction({ ...f.request, releaseRoot: changed }).status()).state, "TAMPERED");
});

test("update refuses a fresh target instead of installing it", async () => {
  const f = await fixture(); await assert.rejects(new InstallerTransaction(f.request).update(), /update requires OUTDATED|unsafe update state/); await assert.rejects(access(f.entry));
});

test("local-rules backup is read back before productive mutation", async () => {
  const f = await fixture(); const original = join(f.root, "original.md"); const replacement = join(f.root, "replacement.md"); await writeFile(original, "original\n"); await writeFile(replacement, "replacement\n"); await new InstallerTransaction({ ...f.request, localRules: original }).install();
  let corrupted = false;
  const update = new InstallerTransaction({ ...f.request, localRules: replacement, onCheckpoint: (checkpoint) => { if (checkpoint === "afterLocalRulesBackup") { const backup = findNamed(join(f.installationRoot, "backups"), "local-rules.bin"); assert.notEqual(backup, undefined); writeFileSync(backup!, "corrupt\n"); corrupted = true; } } });
  await assert.rejects(update.update(), /backup readback failed/); assert.equal(corrupted, true);
});

test("rollback rejects receipts that differ from their backup copy", async () => {
  const f = await fixture(); const tx = new InstallerTransaction(f.request); await tx.install(); const stateRoot = await bindingStateRoot(f.installationRoot); const top = join(stateRoot, "last-transaction.json"); const receipt = JSON.parse(await readFile(top, "utf8")) as Record<string, unknown>; receipt.status = "PREPARED"; await writeFile(top, `${JSON.stringify(receipt)}\n`); await assert.rejects(tx.rollback(), /receipt copies differ/);
});

test("a later target update preserves already updated shared local rules", async () => {
  const f = await fixture(); const secondTarget = join(f.root, "second-target"); await mkdir(secondTarget); const original = join(f.root, "original.md"); const replacement = join(f.root, "replacement.md"); await writeFile(original, "original\n"); await writeFile(replacement, "replacement\n");
  const firstRelease = await releaseFixture(f.root, "1.0.0-rc.1"); const secondRelease = await releaseFixture(f.root, "1.0.0-rc.2"); const firstRequest = { ...f.request, releaseRoot: firstRelease }; const otherRequest = { ...firstRequest, targetRoot: secondTarget };
  await new InstallerTransaction({ ...firstRequest, localRules: original }).install(); await new InstallerTransaction(otherRequest).install();
  await new InstallerTransaction({ ...firstRequest, releaseRoot: secondRelease, localRules: replacement }).update(); await new InstallerTransaction({ ...otherRequest, releaseRoot: secondRelease }).update();
  assert.equal(await readFile(join(f.installationRoot, "releases", "1.0.0-rc.2", "bundle", "agent-governance", "local", "user-rules.md"), "utf8"), "replacement\n");
});

test("absent backup sentinels are read back before productive mutation", async () => {
  const f = await fixture(); let corrupted = false; const tx = new InstallerTransaction({ ...f.request, onCheckpoint: (checkpoint) => { if (checkpoint === "afterBackupWrites") { const marker = findNamed(join(f.installationRoot, "backups"), "entry.absent"); assert.notEqual(marker, undefined); writeFileSync(marker!, "corrupt\n"); corrupted = true; } } });
  await assert.rejects(tx.install(), /backup readback failed/); assert.equal(corrupted, true); await assert.rejects(access(f.entry));
});
