import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { access, cp, mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import test from "node:test";

import { installManagedBlock, type GovernanceBinding } from "../../src/managed-block.ts";
import { InstallerTransaction } from "../../src/transaction.ts";
import { createPublishedV130ReleaseFixture, createReleaseFixture } from "../fixtures/installer/release.ts";
import { createTestRoot } from "../fixtures/installer/workspace.ts";

function sha256(value: Buffer): string {
  return createHash("sha256").update(value).digest("hex");
}

async function publishedBinding(releaseRoot: string, installationRoot: string): Promise<GovernanceBinding> {
  const inventoryText = await readFile(join(releaseRoot, "release.files.sha256"), "utf8");
  const entries = inventoryText.trimEnd().split("\n").map((line) => {
    const [digest, path] = line.split("  ");
    assert.match(digest!, /^[0-9a-f]{64}$/);
    assert.notEqual(path, undefined);
    return [path!, digest!] as const;
  });
  const inventory = new Map(entries);
  const bundleDigest = sha256(Buffer.from(entries.sort(([left], [right]) => left.localeCompare(right)).map(([path, digest]) => `${digest}  ${path}\n`).join("")));
  const base = join(installationRoot, "releases", "1.3.0", "bundle");
  return {
    version: "1.3.0",
    installationRoot,
    governancePath: join(base, "GOVERNANCE.md"),
    manifestPath: join(base, "agent-governance", "manifest.toml"),
    governanceDigest: inventory.get("bundle/GOVERNANCE.md")!,
    manifestDigest: inventory.get("bundle/agent-governance/manifest.toml")!,
    bundleDigest,
  };
}

async function materializePublishedV130Installation(input: {
  readonly root: string;
  readonly targetRoot: string;
  readonly installationRoot: string;
  readonly entry: string;
}): Promise<string> {
  const installable = await createReleaseFixture(join(input.root, "installable-1.3.0"), "1.3.0");
  const request = { targetRoot: input.targetRoot, entryFile: "AGENTS.md", scope: "global" as const, installationRoot: input.installationRoot, releaseRoot: installable, dryRun: false, nonInteractive: true };
  await new InstallerTransaction(request).install();

  const published = await createPublishedV130ReleaseFixture(join(input.root, "published-1.3.0"));
  const installed = join(input.installationRoot, "releases", "1.3.0");
  await rm(join(installed, "bundle"), { recursive: true });
  await cp(join(published, "bundle"), join(installed, "bundle"), { recursive: true });
  await writeFile(join(installed, "VERSION"), await readFile(join(published, "VERSION")));
  await writeFile(join(installed, "release.files.sha256"), await readFile(join(published, "release.files.sha256")));

  const binding = await publishedBinding(published, input.installationRoot);
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

async function rewriteInstalledVersion(installationRoot: string, version: string): Promise<void> {
  const installed = join(installationRoot, "releases", "1.3.0");
  const versionBytes = Buffer.from(`${version}\n`);
  await writeFile(join(installed, "VERSION"), versionBytes);
  const inventoryPath = join(installed, "release.files.sha256");
  const inventory = await readFile(inventoryPath, "utf8");
  await writeFile(inventoryPath, inventory.replace(/^[0-9a-f]{64}  VERSION$/m, `${sha256(versionBytes)}  VERSION`));
}

test("newer CLI classifies a published valid v1.3.0 installation as outdated and updates it", async () => {
  const root = await createTestRoot("agent-governance-cross-version-");
  const targetRoot = join(root, "target");
  const installationRoot = join(root, "installation");
  const entry = join(targetRoot, "AGENTS.md");
  await mkdir(targetRoot);
  await materializePublishedV130Installation({ root, targetRoot, installationRoot, entry });
  const currentRelease = await createReleaseFixture(join(root, "package-1.4.0"), "1.4.0");
  const update = new InstallerTransaction({ targetRoot, entryFile: "AGENTS.md", scope: "global", installationRoot, releaseRoot: currentRelease, dryRun: false, nonInteractive: true });

  assert.equal((await update.status()).state, "OUTDATED");
  assert.equal((await update.update()).state, "CURRENT");
  assert.equal((await update.verify()).state, "CURRENT");
  assert.match(await readFile(entry, "utf8"), /Governance version: 1\.4\.0/);
});

test("newer CLI keeps a byte-manipulated v1.3.0 installation tampered", async () => {
  const root = await createTestRoot("agent-governance-cross-version-tamper-");
  const targetRoot = join(root, "target");
  const installationRoot = join(root, "installation");
  const entry = join(targetRoot, "AGENTS.md");
  await mkdir(targetRoot);
  await materializePublishedV130Installation({ root, targetRoot, installationRoot, entry });
  const installedModule = join(installationRoot, "releases", "1.3.0", "bundle", "agent-governance", "modules", "evidence.md");
  await writeFile(installedModule, `${await readFile(installedModule, "utf8")}\ntampered\n`);
  const currentRelease = await createReleaseFixture(join(root, "package-1.4.0"), "1.4.0");
  const update = new InstallerTransaction({ targetRoot, entryFile: "AGENTS.md", scope: "global", installationRoot, releaseRoot: currentRelease, dryRun: false, nonInteractive: true });

  assert.equal((await update.status()).state, "TAMPERED");
  await assert.rejects(update.update(), /unsafe install state: TAMPERED/);
  await assert.rejects(access(join(installationRoot, "releases", "1.4.0")));
  assert.match(await readFile(entry, "utf8"), /Governance version: 1\.3\.0/);
});

test("newer CLI rejects a new release version carrying the historical three-domain contract", async () => {
  const root = await createTestRoot("agent-governance-cross-version-new-version-");
  const targetRoot = join(root, "target");
  const installationRoot = join(root, "installation");
  const entry = join(targetRoot, "AGENTS.md");
  await mkdir(targetRoot);
  await materializePublishedV130Installation({ root, targetRoot, installationRoot, entry });
  await rewriteInstalledVersion(installationRoot, "9.9.9");
  const currentRelease = await createReleaseFixture(join(root, "package-1.4.0"), "1.4.0");
  const update = new InstallerTransaction({ targetRoot, entryFile: "AGENTS.md", scope: "global", installationRoot, releaseRoot: currentRelease, dryRun: false, nonInteractive: true });

  assert.equal((await update.status()).state, "TAMPERED");
  await assert.rejects(update.update(), /unsafe install state: TAMPERED/);
});

test("rollback recovers a valid historical release from a split receipt", async () => {
  const root = await createTestRoot("agent-governance-cross-version-recovery-");
  const targetRoot = join(root, "target");
  const installationRoot = join(root, "installation");
  const entry = join(targetRoot, "AGENTS.md");
  await mkdir(targetRoot);
  await materializePublishedV130Installation({ root, targetRoot, installationRoot, entry });
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
