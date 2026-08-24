import assert from "node:assert/strict";
import { access, mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { basename, dirname, join } from "node:path";
import { mkdirSync, readFileSync, readdirSync, renameSync, rmSync, statSync, symlinkSync, writeFileSync } from "node:fs";
import test from "node:test";
import { InstallerTransaction } from "../../src/transaction.ts";
import { InstallerFailure, InterruptedFailure } from "../../src/errors.ts";
import type { CatchableSignal, SignalSource } from "../../src/signals.ts";
import { createTestRoot } from "../fixtures/installer/workspace.ts";
import { createReleaseFixture, writeInventory } from "../fixtures/installer/release.ts";

class TestSignals implements SignalSource { private readonly values = new Map<CatchableSignal, Set<() => void>>(); on(signal: CatchableSignal, listener: () => void): void { const set = this.values.get(signal) ?? new Set(); set.add(listener); this.values.set(signal, set); } off(signal: CatchableSignal, listener: () => void): void { this.values.get(signal)?.delete(listener); } emit(signal: CatchableSignal): void { for (const listener of this.values.get(signal) ?? []) listener(); } count(): number { return [...this.values.values()].reduce((sum, set) => sum + set.size, 0); } }
class StartInterruptedSignals implements SignalSource { private readonly values = new Map<CatchableSignal, Set<() => void>>(); on(signal: CatchableSignal, listener: () => void): void { const set = this.values.get(signal) ?? new Set(); set.add(listener); this.values.set(signal, set); if (signal === "SIGTERM") listener(); } off(signal: CatchableSignal, listener: () => void): void { this.values.get(signal)?.delete(listener); } count(): number { return [...this.values.values()].reduce((sum, set) => sum + set.size, 0); } }

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
test("explicit local rules reject unknown formats and invalid text bytes", async () => { for (const [name, bytes] of [["rules.txt", Buffer.from("plain\n")], ["nul.md", Buffer.from("nul\0\n")], ["malformed.md", Buffer.from([0xff])]] as const) { const f = await fixture(); const localRules = join(f.root, name); await writeFile(localRules, bytes); await assert.rejects(new InstallerTransaction({ ...f.request, localRules }).install(), /local rules|Markdown|UTF-8|control|format/i); await assert.rejects(access(f.entry)); } });
test("explicit local rules permit tab, LF, and CR", async () => { const f = await fixture(); const localRules = join(f.root, "controls.md"); const content = Buffer.from("rule\tvalue\r\nnext\n"); await writeFile(localRules, content); await new InstallerTransaction({ ...f.request, localRules }).install(); assert.deepEqual(await readFile(join(f.installationRoot, "releases", "1.0.0-rc.1", "bundle", "agent-governance", "local", "user-rules.md")), content); });
test("explicit local rules remain bound to the opened regular file", async () => { const f = await fixture(); const localRules = join(f.root, "race.md"); const retired = join(f.root, "race-retired.md"); const replacement = join(f.root, "replacement.md"); await writeFile(localRules, "trusted\n"); await writeFile(replacement, "replacement\n"); const tx = new InstallerTransaction({ ...f.request, localRules, onCheckpoint: (checkpoint) => { if (checkpoint === "afterLocalRulesSourceOpen") { renameSync(localRules, retired); symlinkSync(replacement, localRules); } } }); await assert.rejects(tx.install(), /local rules|identity|changed|symlink|canonical/i); await assert.rejects(access(f.entry)); });
test("update preserves installed local rules when no new source is supplied", async () => { const f = await fixture(); const first = await releaseFixture(f.root, "1.0.0-rc.1"); const second = await releaseFixture(f.root, "1.0.0-rc.2"); const localRules = join(f.root, "private-rules.md"); await writeFile(localRules, "preserve this private rule\n"); await new InstallerTransaction({ ...f.request, releaseRoot: first, localRules }).install(); await new InstallerTransaction({ ...f.request, releaseRoot: second }).update(); assert.equal(await readFile(join(f.installationRoot, "releases", "1.0.0-rc.2", "bundle", "agent-governance", "local", "user-rules.md"), "utf8"), "preserve this private rule\n"); });
test("update rejects invalid installed local rules before carrying them forward", async () => { const f = await fixture(); const first = await releaseFixture(f.root, "1.0.0-rc.1"); const second = await releaseFixture(f.root, "1.0.0-rc.2"); const localRules = join(f.root, "private-rules.md"); await writeFile(localRules, "valid\n"); await new InstallerTransaction({ ...f.request, releaseRoot: first, localRules }).install(); const installed = join(f.installationRoot, "releases", "1.0.0-rc.1", "bundle", "agent-governance", "local", "user-rules.md"); await writeFile(installed, Buffer.from([0xff])); const update = new InstallerTransaction({ ...f.request, releaseRoot: second }); assert.equal((await update.status()).state, "TAMPERED"); await assert.rejects(update.update(), /unsafe install state: TAMPERED/); await assert.rejects(access(join(f.installationRoot, "releases", "1.0.0-rc.2"))); });
test("carry-forward binds local-rules presence to the inspected snapshot", async () => { for (const transition of ["removed", "created"] as const) { const f = await fixture(); const first = await releaseFixture(f.root, "1.0.0-rc.1"); const second = await releaseFixture(f.root, "1.0.0-rc.2"); const source = join(f.root, "private-rules.md"); if (transition === "removed") await writeFile(source, "preserve\n"); await new InstallerTransaction({ ...f.request, releaseRoot: first, ...(transition === "removed" ? { localRules: source } : {}) }).install(); const installed = join(f.installationRoot, "releases", "1.0.0-rc.1", "bundle", "agent-governance", "local", "user-rules.md"); const update = new InstallerTransaction({ ...f.request, releaseRoot: second, onCheckpoint: (checkpoint) => { if (checkpoint === "beforeMutation") { if (transition === "removed") rmSync(installed); else writeFileSync(installed, "appeared\n"); } } }); await assert.rejects(update.update(), /local rules.*changed|snapshot|stale/i); assert.match(await readFile(f.entry, "utf8"), /1\.0\.0-rc\.1/); await assert.rejects(access(join(f.installationRoot, "releases", "1.0.0-rc.2"))); } });
test("fresh bindings reject invalid shared local rules before mutation", async () => { for (const replace of [false, true]) { const f = await fixture(); const localRules = join(f.root, "initial.md"); await writeFile(localRules, "valid\n"); await new InstallerTransaction({ ...f.request, localRules }).install(); const installed = join(f.installationRoot, "releases", "1.0.0-rc.1", "bundle", "agent-governance", "local", "user-rules.md"); await writeFile(installed, Buffer.from([0xff])); const targetRoot = join(f.root, replace ? "replacement-target" : "shared-target"); await mkdir(targetRoot); const replacement = join(f.root, "replacement-rules.md"); await writeFile(replacement, "replacement\n"); const request = { ...f.request, targetRoot, ...(replace ? { localRules: replacement } : {}) }; await assert.rejects(new InstallerTransaction(request).install(), /local rules|UTF-8|encoding|text/i); await assert.rejects(access(join(targetRoot, "AGENTS.md"))); } });
test("update replaces local rules only from a new explicit source and rollback restores them", async () => { const f = await fixture(); const original = join(f.root, "original-rules.md"); const replacement = join(f.root, "replacement-rules.md"); await writeFile(original, "original private rule\n"); await writeFile(replacement, "replacement private rule\n"); const target = join(f.installationRoot, "releases", "1.0.0-rc.1", "bundle", "agent-governance", "local", "user-rules.md"); await new InstallerTransaction({ ...f.request, localRules: original }).install(); const update = new InstallerTransaction({ ...f.request, localRules: replacement }); await update.update(); assert.equal(await readFile(target, "utf8"), "replacement private rule\n"); assert.equal((await update.rollback()).state, "CURRENT"); assert.equal(await readFile(target, "utf8"), "original private rule\n"); });
for (const phase of ["backup", "stage", "activate", "verify"] as const) test(`failure after ${phase} restores the complete previous entry`, async () => { const f = await fixture(); const original = Buffer.from("user bytes\r\n"); await writeFile(f.entry, original); await assert.rejects(new InstallerTransaction({ ...f.request, faultAfter: phase }).install(), /rolled back|injected|verification/i); assert.deepEqual(await readFile(f.entry), original); });
test("target root replacement between backup and mutation fails closed", async () => { const f = await fixture(); const retired = `${f.targetRoot}-retired`; let replaced = false; const tx = new InstallerTransaction({ ...f.request, onCheckpoint: (checkpoint) => { if (!replaced && checkpoint === "afterReceipt") { replaced = true; renameSync(f.targetRoot, retired); mkdirSync(f.targetRoot); } } }); await assert.rejects(tx.install(), /identity changed|rolled back/); await assert.rejects(access(f.entry)); });
test("entry parent replacement between backup and mutation fails closed", async () => { const f = await fixture(); const parent = join(f.targetRoot, "nested"); const outside = join(f.root, "outside"); await mkdir(parent); await mkdir(outside); const request = { ...f.request, entryFile: "nested/AGENTS.md" }; let replaced = false; const tx = new InstallerTransaction({ ...request, onCheckpoint: (checkpoint) => { if (!replaced && checkpoint === "afterReceipt") { replaced = true; renameSync(parent, `${parent}-retired`); symlinkSync(outside, parent); } } }); await assert.rejects(tx.install(), /identity changed|symlink|rolled back/); await assert.rejects(access(join(outside, "AGENTS.md"))); });
test("entry replacement between backup and mutation fails closed without overwriting the replacement", async () => { const f = await fixture(); await writeFile(f.entry, "original user bytes\n"); let replaced = false; const tx = new InstallerTransaction({ ...f.request, onCheckpoint: (checkpoint) => { if (!replaced && checkpoint === "afterReceipt") { replaced = true; renameSync(f.entry, `${f.entry}-retired`); writeFileSync(f.entry, "concurrent replacement\n"); } } }); await assert.rejects(tx.install(), /identity changed|rolled back/); assert.equal(await readFile(f.entry, "utf8"), "concurrent replacement\n"); });
test("an entry created after an absent snapshot is never overwritten", async () => { const f = await fixture(); const concurrent = Buffer.from("concurrent user bytes\n"); const tx = new InstallerTransaction({ ...f.request, onCheckpoint: (checkpoint) => { if (checkpoint === "afterReceipt") writeFileSync(f.entry, concurrent, { flag: "wx" }); } }); await assert.rejects(tx.install(), /entry changed|no longer absent|rolled back/); assert.deepEqual(await readFile(f.entry), concurrent); });
test("same-inode entry changes after backup are detected before mutation", async () => { const f = await fixture(); await writeFile(f.entry, "original user bytes\n"); const tx = new InstallerTransaction({ ...f.request, onCheckpoint: (checkpoint) => { if (checkpoint === "afterReceipt") writeFileSync(f.entry, "same inode concurrent bytes\n"); } }); await assert.rejects(tx.install(), /entry changed|rolled back/); assert.equal(await readFile(f.entry, "utf8"), "same inode concurrent bytes\n"); });
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

test("a signal at the verification boundary rolls back and reports interruption", async () => {
  const f = await fixture(); const signals = new TestSignals(); const original = Buffer.from("original\n"); await writeFile(f.entry, original); let emitted = false;
  const tx = new InstallerTransaction({ ...f.request, signalSource: signals, onCheckpoint: (checkpoint) => { if (!emitted && checkpoint === "beforeVerification") { emitted = true; signals.emit("SIGTERM"); } } });
  await assert.rejects(tx.install(), (error: unknown) => error instanceof InterruptedFailure && error.signal === "SIGTERM" && error.rollbackStatus === "SUCCEEDED");
  assert.deepEqual(await readFile(f.entry), original); assert.equal(signals.count(), 0);
});

test("missing receipt evidence makes installed state tampered without rollback capability", async () => {
  const f = await fixture(); const tx = new InstallerTransaction(f.request); await tx.install(); const stateRoot = await bindingStateRoot(f.installationRoot); await rm(join(stateRoot, "last-transaction.json"));
  const status = await tx.status(); assert.equal(status.state, "TAMPERED"); assert.equal(status.rollbackStatus, "NOT_REQUIRED"); assert.deepEqual(status.capabilities, []);
  await assert.rejects(tx.verify(), /TAMPERED/); await assert.rejects(tx.rollback(), /receipt is missing/);
});

test("rollback of one binding preserves a shared release and local rules used by another binding", async () => {
  const f = await fixture(); const secondTarget = join(f.root, "second-target"); await mkdir(secondTarget); const localRules = join(f.root, "private.md"); await writeFile(localRules, "shared private rule\n");
  const first = new InstallerTransaction({ ...f.request, localRules }); const second = new InstallerTransaction({ ...f.request, targetRoot: secondTarget });
  await first.install(); await second.install(); await first.rollback();
  assert.equal((await second.verify()).state, "CURRENT");
  assert.equal(await readFile(join(f.installationRoot, "releases", "1.0.0-rc.1", "bundle", "agent-governance", "local", "user-rules.md"), "utf8"), "shared private rule\n");
});

test("rollback rejects a stale local-rules snapshot instead of overwriting newer bytes", async () => {
  const f = await fixture(); const first = join(f.root, "first.md"); const second = join(f.root, "second.md"); await writeFile(first, "first\n"); await writeFile(second, "second\n"); const tx = new InstallerTransaction({ ...f.request, localRules: first }); await tx.install();
  const target = join(f.installationRoot, "releases", "1.0.0-rc.1", "bundle", "agent-governance", "local", "user-rules.md"); await writeFile(target, "newer external bytes\n");
  await assert.rejects(tx.rollback(), /local rules changed|stale shared state/); assert.equal(await readFile(target, "utf8"), "newer external bytes\n");
});

test("a pre-existing installation-root transaction lock fails closed without target mutation", async () => {
  const f = await fixture(); await mkdir(f.installationRoot); await mkdir(join(f.installationRoot, ".transaction.lock"));
  await assert.rejects(new InstallerTransaction(f.request).install(), /transaction lock/); await assert.rejects(access(f.entry));
});

test("local-rules changes after their snapshot are not overwritten", async () => {
  const f = await fixture(); const original = join(f.root, "original-lock.md"); const replacement = join(f.root, "replacement-lock.md"); await writeFile(original, "original\n"); await writeFile(replacement, "replacement\n"); await new InstallerTransaction({ ...f.request, localRules: original }).install(); const target = join(f.installationRoot, "releases", "1.0.0-rc.1", "bundle", "agent-governance", "local", "user-rules.md");
  const update = new InstallerTransaction({ ...f.request, localRules: replacement, onCheckpoint: (checkpoint) => { if (checkpoint === "afterReceipt") writeFileSync(target, "concurrent local rules\n"); } });
  await assert.rejects(update.update(), /local rules changed/); assert.equal(await readFile(target, "utf8"), "concurrent local rules\n");
});

test("current metadata created after an absent snapshot is never overwritten", async () => {
  const f = await fixture(); const concurrent = Buffer.from("concurrent current metadata\n");
  const tx = new InstallerTransaction({ ...f.request, onCheckpoint: (checkpoint) => { if (checkpoint === "afterReceipt") { const binding = readdirSync(join(f.installationRoot, "bindings"))[0]!; writeFileSync(join(f.installationRoot, "bindings", binding, "current.json"), concurrent, { flag: "wx" }); } } });
  await assert.rejects(tx.install(), /current metadata changed|rolled back/); const currentPath = join(await bindingStateRoot(f.installationRoot), "current.json"); assert.deepEqual(await readFile(currentPath), concurrent); await assert.rejects(access(f.entry));
});

test("existing current metadata changed after its snapshot is never overwritten", async () => {
  const f = await fixture(); const first = await releaseFixture(f.root, "1.0.0-rc.1"); const second = await releaseFixture(f.root, "1.0.0-rc.2"); await new InstallerTransaction({ ...f.request, releaseRoot: first }).install(); const concurrent = Buffer.from("concurrent existing current metadata\n");
  const tx = new InstallerTransaction({ ...f.request, releaseRoot: second, onCheckpoint: (checkpoint) => { if (checkpoint === "afterReceipt") { const binding = readdirSync(join(f.installationRoot, "bindings"))[0]!; writeFileSync(join(f.installationRoot, "bindings", binding, "current.json"), concurrent); } } });
  await assert.rejects(tx.update(), /current metadata changed/); assert.deepEqual(await readFile(join(await bindingStateRoot(f.installationRoot), "current.json")), concurrent); assert.match(await readFile(f.entry, "utf8"), /Governance version: 1\.0\.0-rc\.1/);
});

test("current and local-rules postimages are verified before commit", async () => {
  for (const resource of ["current", "local-rules"] as const) {
    const f = await fixture(); const rules = join(f.root, "postimage-rules.md"); await writeFile(rules, "expected rules\n"); const concurrent = Buffer.from(`concurrent ${resource}\n`);
    const tx = new InstallerTransaction({ ...f.request, localRules: rules, onCheckpoint: (checkpoint) => { if (checkpoint !== "afterCurrent") return; const binding = readdirSync(join(f.installationRoot, "bindings"))[0]!; const path = resource === "current" ? join(f.installationRoot, "bindings", binding, "current.json") : join(f.installationRoot, "releases", "1.0.0-rc.1", "bundle", "agent-governance", "local", "user-rules.md"); writeFileSync(path, concurrent); } });
    await assert.rejects(tx.install(), /ROLLBACK_FAILED|postimage|changed/); const path = resource === "current" ? join(await bindingStateRoot(f.installationRoot), "current.json") : join(f.installationRoot, "releases", "1.0.0-rc.1", "bundle", "agent-governance", "local", "user-rules.md"); assert.deepEqual(await readFile(path), concurrent);
  }
});

test("entry, current, and local-rules postimages are jointly revalidated after both commit receipts", async () => {
  for (const resource of ["entry", "current", "local-rules"] as const) {
    const f = await fixture(); const rules = join(f.root, `final-${resource}.md`); await writeFile(rules, "rules\n"); const concurrent = Buffer.from(`concurrent ${resource}\n`); let changedPath = ""; let applied = Buffer.alloc(0);
    const tx = new InstallerTransaction({ ...f.request, localRules: rules, onCheckpoint: (checkpoint) => { if (checkpoint !== "afterCommitTopReceipt") return; const binding = readdirSync(join(f.installationRoot, "bindings"))[0]!; changedPath = resource === "entry" ? f.entry : resource === "current" ? join(f.installationRoot, "bindings", binding, "current.json") : join(f.installationRoot, "releases", "1.0.0-rc.1", "bundle", "agent-governance", "local", "user-rules.md"); applied = readFileSync(changedPath); writeFileSync(changedPath, concurrent); } });
    await assert.rejects(tx.install(), (error: unknown) => error instanceof InstallerFailure && error.outcome === "ROLLBACK_FAILED"); assert.deepEqual(await readFile(changedPath), concurrent); assert.equal((await tx.status()).state, "RECOVERY_REQUIRED"); await writeFile(changedPath, applied); assert.equal((await tx.rollback()).state, "ABSENT");
  }
});

test("entry changes after current activation are detected and preserved", async () => {
  const f = await fixture(); await writeFile(f.entry, "original\n"); let changed = false; const tx = new InstallerTransaction({ ...f.request, onCheckpoint: (checkpoint) => { if (!changed && checkpoint === "afterCurrent") { changed = true; writeFileSync(f.entry, "late concurrent entry\n"); } } });
  await assert.rejects(tx.install(), /entry changed|rolled back/); assert.equal(await readFile(f.entry, "utf8"), "late concurrent entry\n");
});

test("explicit rollback rejects a changed applied entry without partial restore", async () => {
  const f = await fixture(); await writeFile(f.entry, "original\n"); const tx = new InstallerTransaction(f.request); await tx.install(); await writeFile(f.entry, "newer user entry\n"); const currentBefore = await readFile(join(await bindingStateRoot(f.installationRoot), "current.json"));
  await assert.rejects(tx.rollback(), /entry changed|stale/); assert.equal(await readFile(f.entry, "utf8"), "newer user entry\n"); assert.deepEqual(await readFile(join(await bindingStateRoot(f.installationRoot), "current.json")), currentBefore);
});

test("rollback revalidates the entry immediately before restoring it", async () => {
  const f = await fixture(); await writeFile(f.entry, "original\n"); await new InstallerTransaction(f.request).install(); const concurrent = Buffer.from("concurrent entry\n");
  const tx = new InstallerTransaction({ ...f.request, onCheckpoint: (checkpoint) => { if (checkpoint === "beforeRollbackEntry") writeFileSync(f.entry, concurrent); } });
  await assert.rejects(tx.rollback(), /entry changed|stale rollback state/); assert.deepEqual(await readFile(f.entry), concurrent);
});

test("rollback never overwrites an entry changed after its final validation", async () => {
  const f = await fixture(); await writeFile(f.entry, "original\n"); await new InstallerTransaction(f.request).install(); const concurrent = Buffer.from("concurrent entry after validation\n");
  const tx = new InstallerTransaction({ ...f.request, onCheckpoint: (checkpoint) => { if (checkpoint === "afterRollbackEntryValidation") writeFileSync(f.entry, concurrent); } });
  await assert.rejects(tx.rollback(), /entry changed|stale rollback state/); assert.deepEqual(await readFile(f.entry), concurrent);
});

test("rollback resumes a deterministic same-filesystem entry detach after interruption", async () => {
  const f = await fixture(); const original = Buffer.from("original\n"); await writeFile(f.entry, original); await new InstallerTransaction(f.request).install(); const applied = await readFile(f.entry); let detached: string | undefined;
  const interrupted = new InstallerTransaction({ ...f.request, onCheckpoint: (checkpoint) => { if (checkpoint !== "afterRollbackEntryDetach") return; detached = readdirSync(dirname(f.entry)).find((name) => name.startsWith(`.${basename(f.entry)}.agent-governance-`) && name.endsWith(".restore")); assert.notEqual(detached, undefined); assert.equal(statSync(join(dirname(f.entry), detached!, "entry.bin")).dev, statSync(dirname(f.entry)).dev); throw new Error("injected interruption after entry detach"); } });
  await assert.rejects(interrupted.rollback(), /interruption after entry detach/); await assert.rejects(access(f.entry)); assert.notEqual(detached, undefined);
  assert.equal((await new InstallerTransaction(f.request).rollback()).state, "FRESH"); assert.deepEqual(await readFile(f.entry), original); assert.deepEqual(await readFile(join(dirname(f.entry), detached!, "entry.bin")), applied);
});

test("rollback resumes after interruption immediately after detach reservation", async () => {
  const f = await fixture(); const original = Buffer.from("original\n"); await writeFile(f.entry, original); await new InstallerTransaction(f.request).install(); let interrupted = false;
  const reserving = new InstallerTransaction({ ...f.request, onCheckpoint: (checkpoint) => { if (checkpoint !== "afterRollbackEntryDetachReservation") return; interrupted = true; throw new Error("injected interruption after detach reservation"); } });
  await assert.rejects(reserving.rollback(), /interruption after detach reservation/); assert.equal(interrupted, true); assert.equal((await new InstallerTransaction(f.request).rollback()).state, "FRESH"); assert.deepEqual(await readFile(f.entry), original);
});

test("rollback never overwrites a detach-path collision", async () => {
  const f = await fixture(); await writeFile(f.entry, "original\n"); await new InstallerTransaction(f.request).install(); const foreign = Buffer.from("foreign detach bytes\n"); let detached: string | undefined;
  const colliding = new InstallerTransaction({ ...f.request, onCheckpoint: (checkpoint) => { if (checkpoint !== "beforeRollbackEntryDetach") return; const receipt = JSON.parse(readFileSync(join(f.installationRoot, "bindings", readdirSync(join(f.installationRoot, "bindings"))[0]!, "last-transaction.json"), "utf8")) as { id: string }; detached = `.${basename(f.entry)}.agent-governance-${receipt.id}.restore`; writeFileSync(join(dirname(f.entry), detached), foreign); } });
  await assert.rejects(colliding.rollback()); assert.deepEqual(await readFile(join(dirname(f.entry), detached!)), foreign);
});

test("rollback never moves the entry through a substituted reserved detach root", async () => {
  const f = await fixture(); const applied = Buffer.from("original\n"); await writeFile(f.entry, applied); await new InstallerTransaction(f.request).install(); const installed = await readFile(f.entry); const foreign = join(f.targetRoot, "foreign-detach"); await mkdir(foreign); await writeFile(join(foreign, "foreign.bin"), "foreign\n"); let moved: string | undefined;
  const substituted = new InstallerTransaction({ ...f.request, onCheckpoint: (checkpoint) => { if (checkpoint !== "afterRollbackNativeDirectoriesBound") return; const detached = readdirSync(dirname(f.entry)).find((name) => name.startsWith(`.${basename(f.entry)}.agent-governance-`) && name.endsWith(".restore")); assert.notEqual(detached, undefined); moved = `${detached}.moved`; renameSync(join(dirname(f.entry), detached!), join(dirname(f.entry), moved)); symlinkSync(foreign, join(dirname(f.entry), detached!)); } });
  await assert.rejects(substituted.rollback()); assert.deepEqual(await readFile(f.entry), installed); assert.notEqual(moved, undefined); assert.deepEqual(await readFile(join(dirname(f.entry), moved!, "entry.bin")), installed); assert.deepEqual(readdirSync(foreign), ["foreign.bin"]); assert.equal(await readFile(join(foreign, "foreign.bin"), "utf8"), "foreign\n");
});

test("rollback never follows a substituted detach root during finalization", async () => {
  const f = await fixture(); await writeFile(f.entry, "original\n"); await new InstallerTransaction(f.request).install(); let moved: string | undefined;
  const substituted = new InstallerTransaction({ ...f.request, onCheckpoint: (checkpoint) => { if (checkpoint !== "beforeRollbackDetachFinalization") return; const detached = readdirSync(dirname(f.entry)).find((name) => name.startsWith(`.${basename(f.entry)}.agent-governance-`) && name.endsWith(".restore")); assert.notEqual(detached, undefined); moved = `${detached}.moved`; renameSync(join(dirname(f.entry), detached!), join(dirname(f.entry), moved)); symlinkSync(join(dirname(f.entry), moved), join(dirname(f.entry), detached!)); } });
  await assert.rejects(substituted.rollback(), /identity changed|symlink/); assert.notEqual(moved, undefined); await access(join(dirname(f.entry), moved!, "entry.bin"));
});

test("stale local-rules rollback fails before restoring entry or current", async () => {
  const f = await fixture(); const rules = join(f.root, "rules-atomic.md"); await writeFile(f.entry, "original\n"); await writeFile(rules, "installed\n"); const tx = new InstallerTransaction({ ...f.request, localRules: rules }); await tx.install(); const entryBefore = await readFile(f.entry); const currentPath = join(await bindingStateRoot(f.installationRoot), "current.json"); const currentBefore = await readFile(currentPath); const target = join(f.installationRoot, "releases", "1.0.0-rc.1", "bundle", "agent-governance", "local", "user-rules.md"); await writeFile(target, "newer rules\n");
  await assert.rejects(tx.rollback(), /local rules changed|stale shared state/); assert.deepEqual(await readFile(f.entry), entryBefore); assert.deepEqual(await readFile(currentPath), currentBefore);
});

test("rollback reclaims a well-formed stale dead-owner lock", async () => {
  const f = await fixture(); const tx = new InstallerTransaction(f.request); await tx.install(); const lock = join(f.installationRoot, ".transaction.lock"); await mkdir(lock); await writeFile(join(lock, "owner.json"), `${JSON.stringify({ schemaVersion: 1, pid: 2147483647, token: "a".repeat(64) })}\n`);
  assert.equal((await tx.rollback()).state, "ABSENT"); await assert.rejects(access(lock));
});

test("a first signal during rollback is reported after successful restoration", async () => {
  const f = await fixture(); const signals = new TestSignals(); const original = Buffer.from("original\n"); await writeFile(f.entry, original); let emitted = false; const tx = new InstallerTransaction({ ...f.request, faultAfter: "activate", signalSource: signals, onCheckpoint: (checkpoint) => { if (!emitted && checkpoint === "duringRollback") { emitted = true; signals.emit("SIGTERM"); } } });
  await assert.rejects(tx.install(), (error: unknown) => error instanceof InterruptedFailure && error.signal === "SIGTERM" && error.rollbackStatus === "SUCCEEDED"); assert.deepEqual(await readFile(f.entry), original);
});

test("explicit rollback latches a signal and finishes restoration before reporting interruption", async () => {
  const f = await fixture(); const signals = new TestSignals(); const original = Buffer.from("original\n"); await writeFile(f.entry, original); await new InstallerTransaction(f.request).install(); let emitted = false;
  const tx = new InstallerTransaction({ ...f.request, signalSource: signals, onCheckpoint: (checkpoint) => { if (!emitted && checkpoint === "afterRollbackEntry") { emitted = true; signals.emit("SIGTERM"); signals.emit("SIGINT"); } } });
  await assert.rejects(tx.rollback(), (error: unknown) => error instanceof InterruptedFailure && error.signal === "SIGTERM" && error.rollbackStatus === "SUCCEEDED"); assert.deepEqual(await readFile(f.entry), original); await assert.rejects(access(join(await bindingStateRoot(f.installationRoot), "current.json"))); assert.equal(signals.count(), 0);
});

test("explicit rollback never reports successful restoration when interrupted before restore", async () => {
  const f = await fixture(); await new InstallerTransaction(f.request).install(); const signals = new StartInterruptedSignals(); const tx = new InstallerTransaction({ ...f.request, signalSource: signals });
  await assert.rejects(tx.rollback(), (error: unknown) => error instanceof InterruptedFailure && error.signal === "SIGTERM" && error.rollbackStatus === "NOT_REQUIRED"); assert.equal((await new InstallerTransaction(f.request).status()).state, "CURRENT"); assert.equal(signals.count(), 0);
});

test("explicit rollback resumes after entry was already restored", async () => {
  const f = await fixture(); const original = Buffer.from("original\n"); await writeFile(f.entry, original); const installed = new InstallerTransaction(f.request); await installed.install(); let failed = false;
  const interrupted = new InstallerTransaction({ ...f.request, onCheckpoint: (checkpoint) => { if (!failed && checkpoint === "afterRollbackEntry") { failed = true; throw new Error("injected partial restore failure"); } } });
  await assert.rejects(interrupted.rollback(), /partial restore/); assert.deepEqual(await readFile(f.entry), original); assert.equal((await installed.rollback()).state, "FRESH"); assert.deepEqual(await readFile(f.entry), original);
});

test("rollback revalidates current immediately before restoring it", async () => {
  const f = await fixture(); await writeFile(f.entry, "original\n"); await new InstallerTransaction(f.request).install(); const stateRoot = await bindingStateRoot(f.installationRoot); const currentPath = join(stateRoot, "current.json"); const concurrent = Buffer.from("concurrent current during restore\n");
  const tx = new InstallerTransaction({ ...f.request, onCheckpoint: (checkpoint) => { if (checkpoint === "afterRollbackEntry") writeFileSync(currentPath, concurrent); } }); await assert.rejects(tx.rollback(), /current metadata changed|stale rollback state/); assert.deepEqual(await readFile(currentPath), concurrent); assert.equal(await readFile(f.entry, "utf8"), "original\n");
});

test("rollback revalidates local rules immediately before restoring them", async () => {
  const f = await fixture(); const original = join(f.root, "restore-original.md"); const replacement = join(f.root, "restore-replacement.md"); await writeFile(original, "original rules\n"); await writeFile(replacement, "replacement rules\n"); await new InstallerTransaction({ ...f.request, localRules: original }).install(); await new InstallerTransaction({ ...f.request, localRules: replacement }).update(); const target = join(f.installationRoot, "releases", "1.0.0-rc.1", "bundle", "agent-governance", "local", "user-rules.md"); const concurrent = Buffer.from("concurrent local rules during restore\n");
  const tx = new InstallerTransaction({ ...f.request, onCheckpoint: (checkpoint) => { if (checkpoint === "afterRollbackCurrent") writeFileSync(target, concurrent); } }); await assert.rejects(tx.rollback(), /local rules changed|stale shared state/); assert.deepEqual(await readFile(target), concurrent);
});

test("rollback keeps its receipt recoverable when a final joint postimage changes", async () => {
  const f = await fixture(); await writeFile(f.entry, "original\n"); await new InstallerTransaction(f.request).install(); const stateRoot = await bindingStateRoot(f.installationRoot); const currentPath = join(stateRoot, "current.json"); const receiptPath = join(stateRoot, "last-transaction.json"); const concurrent = Buffer.from("late concurrent current\n");
  const tx = new InstallerTransaction({ ...f.request, onCheckpoint: (checkpoint) => { if (checkpoint === "afterRollbackCurrent") writeFileSync(currentPath, concurrent); } }); await assert.rejects(tx.rollback(), /current metadata|postimage|rollback verification/); assert.deepEqual(await readFile(currentPath), concurrent); assert.equal(JSON.parse(await readFile(receiptPath, "utf8")).status, "COMMITTED");
  await rm(currentPath); assert.equal((await new InstallerTransaction(f.request).rollback()).state, "FRESH"); assert.equal(await readFile(f.entry, "utf8"), "original\n");
});

test("rollback recovers a commit receipt split between adjacent statuses", async () => {
  const f = await fixture(); await writeFile(f.entry, "original\n"); let split = false; const tx = new InstallerTransaction({ ...f.request, faultDuringRollback: true, onCheckpoint: (checkpoint) => { if (checkpoint === "afterCommitTopReceipt") { split = true; throw new Error("injected commit receipt split"); } } });
  await assert.rejects(tx.install(), (error: unknown) => error instanceof InstallerFailure && error.outcome === "ROLLBACK_FAILED"); assert.equal(split, true); assert.equal((await new InstallerTransaction(f.request).status()).state, "RECOVERY_REQUIRED"); assert.equal((await new InstallerTransaction(f.request).rollback()).state, "FRESH"); assert.equal(await readFile(f.entry, "utf8"), "original\n");
});

test("rollback recovers a rolled-back receipt split between adjacent statuses", async () => {
  const f = await fixture(); await writeFile(f.entry, "original\n"); await new InstallerTransaction(f.request).install(); let split = false; const tx = new InstallerTransaction({ ...f.request, onCheckpoint: (checkpoint) => { if (checkpoint === "afterRollbackBackupReceipt") { split = true; throw new Error("injected rollback receipt split"); } } });
  await assert.rejects(tx.rollback(), /rollback receipt split/); assert.equal(split, true); assert.equal((await new InstallerTransaction(f.request).status()).state, "RECOVERY_REQUIRED"); assert.equal((await new InstallerTransaction(f.request).rollback()).state, "FRESH"); assert.equal(await readFile(f.entry, "utf8"), "original\n");
});

test("tampered backup payload and symlinked backup root fail before restore mutation", async () => {
  for (const tamper of ["payload", "ancestor"] as const) { const f = await fixture(); await writeFile(f.entry, "original\n"); const tx = new InstallerTransaction(f.request); await tx.install(); const stateRoot = await bindingStateRoot(f.installationRoot); const receipt = JSON.parse(await readFile(join(stateRoot, "last-transaction.json"), "utf8")) as { backupRoot: string }; const entryBefore = await readFile(f.entry);
    if (tamper === "payload") await writeFile(join(receipt.backupRoot, "entry.bin"), "tampered backup\n"); else { const moved = `${receipt.backupRoot}-moved`; renameSync(receipt.backupRoot, moved); symlinkSync(moved, receipt.backupRoot); }
    await assert.rejects(tx.rollback(), /backup|symlink|digest|canonical/i); assert.deepEqual(await readFile(f.entry), entryBefore);
  }
});
