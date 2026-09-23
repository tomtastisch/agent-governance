import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { access, cp, mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import test from "node:test";

import { installManagedBlock, type GovernanceBinding } from "../../src/managed-block.ts";
import { verifyInstalledRelease, verifyRelease } from "../../src/release.ts";
import { InstallerTransaction } from "../../src/transaction.ts";
import { createPublishedV121ReleaseFixture, createPublishedV130ReleaseFixture, createReleaseFixture } from "../fixtures/installer/release.ts";
import { createTestRoot } from "../fixtures/installer/workspace.ts";

function sha256(value: Buffer): string {
  return createHash("sha256").update(value).digest("hex");
}

async function publishedBinding(releaseRoot: string, installationRoot: string, version: string): Promise<GovernanceBinding> {
  const inventoryText = await readFile(join(releaseRoot, "release.files.sha256"), "utf8");
  const entries = inventoryText.trimEnd().split("\n").map((line) => {
    const [digest, path] = line.split("  ");
    assert.match(digest!, /^[0-9a-f]{64}$/);
    assert.notEqual(path, undefined);
    return [path!, digest!] as const;
  });
  const inventory = new Map(entries);
  const bundleDigest = sha256(Buffer.from(entries.sort(([left], [right]) => left.localeCompare(right)).map(([path, digest]) => `${digest}  ${path}\n`).join("")));
  const base = join(installationRoot, "releases", version, "bundle");
  return {
    version,
    installationRoot,
    governancePath: join(base, "GOVERNANCE.md"),
    manifestPath: join(base, "agent-governance", "manifest.toml"),
    governanceDigest: inventory.get("bundle/GOVERNANCE.md")!,
    manifestDigest: inventory.get("bundle/agent-governance/manifest.toml")!,
    bundleDigest,
  };
}

async function materializePublishedInstallation(input: {
  readonly version: "1.2.1" | "1.3.0";
  readonly root: string;
  readonly targetRoot: string;
  readonly installationRoot: string;
  readonly entry: string;
}): Promise<string> {
  const installable = await createReleaseFixture(join(input.root, `installable-${input.version}`), input.version);
  const request = { targetRoot: input.targetRoot, entryFile: "AGENTS.md", scope: "global" as const, installationRoot: input.installationRoot, releaseRoot: installable, dryRun: false, nonInteractive: true };
  await new InstallerTransaction(request).install();

  const createPublished = input.version === "1.2.1" ? createPublishedV121ReleaseFixture : createPublishedV130ReleaseFixture;
  const published = await createPublished(join(input.root, `published-${input.version}`));
  const installed = join(input.installationRoot, "releases", input.version);
  await rm(join(installed, "bundle"), { recursive: true });
  await cp(join(published, "bundle"), join(installed, "bundle"), { recursive: true });
  await writeFile(join(installed, "VERSION"), await readFile(join(published, "VERSION")));
  await writeFile(join(installed, "release.files.sha256"), await readFile(join(published, "release.files.sha256")));

  const binding = await publishedBinding(published, input.installationRoot, input.version);
  const entry = installManagedBlock(await readFile(input.entry), binding);
  const current = Buffer.from(`${JSON.stringify({ schemaVersion: 1, ...binding, targetRoot: input.targetRoot, entryFile: "AGENTS.md" }, null, 2)}\n`);
  await writeFile(input.entry, entry);
  const bindingIds = await readdir(join(input.installationRoot, "bindings"));
  assert.equal(bindingIds.length, 1);
  const bindingRoot = join(input.installationRoot, "bindings", bindingIds[0]!);
  await writeFile(join(bindingRoot, "current.json"), current);

  const receiptPath = join(bindingRoot, "last-transaction.json");
  const receipt = JSON.parse(await readFile(receiptPath, "utf8")) as Record<string, unknown>;
  receipt.entryAppliedDigest = sha256(entry);
  receipt.currentAppliedDigest = sha256(current);
  await writeFile(join(String(receipt.backupRoot), "entry.applied.bin"), entry);
  await writeFile(join(String(receipt.backupRoot), "current.applied.json"), current);
  const receiptBytes = Buffer.from(`${JSON.stringify(receipt)}\n`);
  await writeFile(receiptPath, receiptBytes);
  await writeFile(join(String(receipt.backupRoot), "receipt.json"), receiptBytes);
  return published;
}

async function rewriteInstalledVersion(installationRoot: string, directoryVersion: string, version: string): Promise<void> {
  const installed = join(installationRoot, "releases", directoryVersion);
  const versionBytes = Buffer.from(`${version}\n`);
  await writeFile(join(installed, "VERSION"), versionBytes);
  const inventoryPath = join(installed, "release.files.sha256");
  const inventory = await readFile(inventoryPath, "utf8");
  await writeFile(inventoryPath, inventory.replace(/^[0-9a-f]{64}  VERSION$/m, `${sha256(versionBytes)}  VERSION`));
}

for (const version of ["1.2.1", "1.3.0"] as const) {
  test(`newer CLI classifies a published valid v${version} installation as outdated and updates it`, async () => {
    const root = await createTestRoot("agent-governance-cross-version-");
    const targetRoot = join(root, "target");
    const installationRoot = join(root, "installation");
    const entry = join(targetRoot, "AGENTS.md");
    await mkdir(targetRoot);
    await materializePublishedInstallation({ version, root, targetRoot, installationRoot, entry });
    const currentRelease = await createReleaseFixture(join(root, "package-1.4.0"), "1.4.0");
    const update = new InstallerTransaction({ targetRoot, entryFile: "AGENTS.md", scope: "global", installationRoot, releaseRoot: currentRelease, dryRun: false, nonInteractive: true });

    assert.equal((await verifyInstalledRelease(join(installationRoot, "releases", version))).version, version);
    await assert.rejects(verifyRelease(join(installationRoot, "releases", version)), /domains|schema/);
    assert.equal((await update.status()).state, "OUTDATED");
    assert.equal((await update.update()).state, "CURRENT");
    assert.equal((await update.verify()).state, "CURRENT");
    assert.match(await readFile(entry, "utf8"), /Governance version: 1\.4\.0/);
  });

  test(`newer CLI keeps a byte-manipulated v${version} installation tampered`, async () => {
    const root = await createTestRoot("agent-governance-cross-version-tamper-");
    const targetRoot = join(root, "target");
    const installationRoot = join(root, "installation");
    const entry = join(targetRoot, "AGENTS.md");
    await mkdir(targetRoot);
    await materializePublishedInstallation({ version, root, targetRoot, installationRoot, entry });
    const installedModule = join(installationRoot, "releases", version, "bundle", "agent-governance", "modules", "evidence.md");
    await writeFile(installedModule, `${await readFile(installedModule, "utf8")}\ntampered\n`);
    const currentRelease = await createReleaseFixture(join(root, "package-1.4.0"), "1.4.0");
    const update = new InstallerTransaction({ targetRoot, entryFile: "AGENTS.md", scope: "global", installationRoot, releaseRoot: currentRelease, dryRun: false, nonInteractive: true });

    assert.equal((await update.status()).state, "TAMPERED");
    await assert.rejects(update.update(), /unsafe install state: TAMPERED/);
    await assert.rejects(access(join(installationRoot, "releases", "1.4.0")));
    assert.ok((await readFile(entry, "utf8")).includes(`Governance version: ${version}`));
  });

  test(`newer CLI rejects a new release version carrying the v${version} historical contract`, async () => {
    const root = await createTestRoot("agent-governance-cross-version-new-version-");
    const targetRoot = join(root, "target");
    const installationRoot = join(root, "installation");
    const entry = join(targetRoot, "AGENTS.md");
    await mkdir(targetRoot);
    await materializePublishedInstallation({ version, root, targetRoot, installationRoot, entry });
    await rewriteInstalledVersion(installationRoot, version, "9.9.9");
    await assert.rejects(verifyInstalledRelease(join(installationRoot, "releases", version)), /ssot manifest domains|release manifest schema/);
    const currentRelease = await createReleaseFixture(join(root, "package-1.4.0"), "1.4.0");
    const update = new InstallerTransaction({ targetRoot, entryFile: "AGENTS.md", scope: "global", installationRoot, releaseRoot: currentRelease, dryRun: false, nonInteractive: true });

    assert.equal((await update.status()).state, "TAMPERED");
    await assert.rejects(update.update(), /unsafe install state: TAMPERED/);
  });

  test(`rollback recovers a valid v${version} release from a split receipt`, async () => {
    const root = await createTestRoot("agent-governance-cross-version-recovery-");
    const targetRoot = join(root, "target");
    const installationRoot = join(root, "installation");
    const entry = join(targetRoot, "AGENTS.md");
    await mkdir(targetRoot);
    await materializePublishedInstallation({ version, root, targetRoot, installationRoot, entry });
    const currentRelease = await createReleaseFixture(join(root, "package-1.4.0"), "1.4.0");
    const request = { targetRoot, entryFile: "AGENTS.md", scope: "global" as const, installationRoot, releaseRoot: currentRelease, dryRun: false, nonInteractive: true };
    const bindingIds = await readdir(join(installationRoot, "bindings"));
    const receiptPath = join(installationRoot, "bindings", bindingIds[0]!, "last-transaction.json");
    const receipt = JSON.parse(await readFile(receiptPath, "utf8")) as Record<string, unknown>;
    const backupReceipt = Buffer.from(`${JSON.stringify({ ...receipt, status: "PREPARED" })}\n`);
    await writeFile(join(String(receipt.backupRoot), "receipt.json"), backupReceipt);

    const transaction = new InstallerTransaction(request);
    assert.equal((await transaction.status()).state, "RECOVERY_REQUIRED");
    assert.equal((await transaction.rollback()).state, "ABSENT");
  });

  test(`v${version} rejects a self-reported version mismatch before rollback mutation`, async () => {
    const root = await createTestRoot("agent-governance-cross-version-mismatch-");
    const targetRoot = join(root, "target");
    const installationRoot = join(root, "installation");
    const entry = join(targetRoot, "AGENTS.md");
    await mkdir(targetRoot);
    await materializePublishedInstallation({ version, root, targetRoot, installationRoot, entry });
    const otherVersion = version === "1.2.1" ? "1.3.0" : "1.2.1";
    const createOther = otherVersion === "1.2.1" ? createPublishedV121ReleaseFixture : createPublishedV130ReleaseFixture;
    const replacement = await createOther(join(root, "replacement"));
    const installed = join(installationRoot, "releases", version);
    await rm(join(installed, "bundle"), { recursive: true });
    await cp(replacement, installed, { recursive: true });
    assert.equal((await verifyInstalledRelease(installed)).version, otherVersion);
    const currentRelease = await createReleaseFixture(join(root, "package-1.4.0"), "1.4.0");
    const transaction = new InstallerTransaction({ targetRoot, entryFile: "AGENTS.md", scope: "global", installationRoot, releaseRoot: currentRelease, dryRun: false, nonInteractive: true });
    const entryBefore = await readFile(entry);
    assert.equal((await transaction.status()).state, "TAMPERED");
    await assert.rejects(transaction.rollback(), /installed release version does not match its directory/);
    assert.deepEqual(await readFile(entry), entryBefore);
    await access(installed);
  });

  test(`v${version} cannot be relabelled as the other historical release`, async () => {
    const root = await createTestRoot("agent-governance-cross-version-relabel-");
    const targetRoot = join(root, "target");
    const installationRoot = join(root, "installation");
    const entry = join(targetRoot, "AGENTS.md");
    await mkdir(targetRoot);
    await materializePublishedInstallation({ version, root, targetRoot, installationRoot, entry });
    await rewriteInstalledVersion(installationRoot, version, version === "1.2.1" ? "1.3.0" : "1.2.1");
    await assert.rejects(verifyInstalledRelease(join(installationRoot, "releases", version)), /domains|schema/);
    const currentRelease = await createReleaseFixture(join(root, "package-1.4.0"), "1.4.0");
    const transaction = new InstallerTransaction({ targetRoot, entryFile: "AGENTS.md", scope: "global", installationRoot, releaseRoot: currentRelease, dryRun: false, nonInteractive: true });
    assert.equal((await transaction.status()).state, "TAMPERED");
    await assert.rejects(transaction.update(), /unsafe install state: TAMPERED/);
  });
}

test("current release stays current and a downgrade remains blocked", async () => {
  const root = await createTestRoot("agent-governance-cross-version-downgrade-");
  const targetRoot = join(root, "target");
  const installationRoot = join(root, "installation");
  await mkdir(targetRoot);
  const currentRelease = await createReleaseFixture(join(root, "package-1.4.0"), "1.4.0");
  const request = { targetRoot, entryFile: "AGENTS.md", scope: "global" as const, installationRoot, releaseRoot: currentRelease, dryRun: false, nonInteractive: true };
  const current = new InstallerTransaction(request);
  await current.install();
  assert.equal((await current.status()).state, "CURRENT");
  const older = await createReleaseFixture(join(root, "package-1.3.0"), "1.3.0");
  const downgrade = new InstallerTransaction({ ...request, releaseRoot: older });
  assert.equal((await downgrade.status()).state, "DOWNGRADE_BLOCKED");
  await assert.rejects(downgrade.update(), /unsafe install state: DOWNGRADE_BLOCKED/);
});
