import { randomUUID } from "node:crypto";
import { basename, dirname, join } from "node:path";
import type { PathIdentity } from "./filesystem.ts";
import { installManagedBlock } from "./managed-block.ts";
import { probeNativeFilesystemCapability, secureCreateDirectory, secureRemoveFile, secureRenameNoReplace, type CreatedDirectoryIdentity } from "./native-filesystem.ts";
import { buildBinding } from "./installer/context.ts";
import { atomicCreate } from "./installer/mutation.ts";
import { assertDirectory, assertEntry, assertMissing, assertPrivateDirectory, entrySnapshot, syncDirectory, type EntrySnapshot } from "./installer/replacement-guards.ts";
import { validateReplacement } from "./installer/replacement-validation.ts";
import { InstallerTransaction } from "./transaction.ts";

export interface ReplacementRequest {
  readonly sourceInstallationRoot: string;
  readonly installationRoot: string;
  readonly releaseRoot: string;
  readonly targetRoot: string;
  readonly entryFile: string;
  readonly localRules?: string;
  readonly dryRun?: boolean;
}

export interface QuarantineReference {
  readonly directory: string;
  readonly entryPath: string;
}

export type ReplacementResult = {
  readonly outcome: "SUCCESS";
  readonly state: "CURRENT";
  readonly quarantine: QuarantineReference;
} | {
  readonly outcome: "PLANNED";
  readonly plan: { readonly installationRoot: string; readonly entryPath: string; readonly quarantineParent: string };
} | {
  readonly outcome: "FAILURE";
  readonly code: "REPLACEMENT_FAILED";
  readonly phase: "validation" | "reserve" | "quarantine" | "detach" | "install" | "verify";
  readonly recovery: "NOT_REQUIRED" | "RESTORED" | "RETAINED";
  readonly installationRoot?: string;
  readonly quarantine?: QuarantineReference;
};

/** Forward-only replacement. Failures deliberately never expose caught exceptions or content. */
export async function replaceInstallation(input: ReplacementRequest): Promise<ReplacementResult> {
  let phase: Extract<ReplacementResult, { outcome: "FAILURE" }>["phase"] = "validation";
  let quarantine: QuarantineReference | undefined;
  let installationRoot: string | undefined;
  let detached = false;
  let restore: (() => Promise<void>) | undefined;
  try {
    // Copy only supported inputs; callers cannot inject transaction controls.
    const request: ReplacementRequest = { sourceInstallationRoot: input.sourceInstallationRoot, installationRoot: input.installationRoot, releaseRoot: input.releaseRoot, targetRoot: input.targetRoot, entryFile: input.entryFile, ...(input.localRules === undefined ? {} : { localRules: input.localRules }), ...(input.dryRun === undefined ? {} : { dryRun: input.dryRun }) };
    const context = await validateReplacement(request);
    const { target, original, user } = context;
    const parent = dirname(target.entryPath);
    if (request.dryRun) return { outcome: "PLANNED", plan: { installationRoot: request.installationRoot, entryPath: target.entryPath, quarantineParent: parent } };
    const directories: [string, PathIdentity][] = [
      [request.sourceInstallationRoot, context.sourceIdentity],
      [dirname(request.sourceInstallationRoot), context.sourceParentIdentity],
      [dirname(request.installationRoot), context.destinationParentIdentity],
      [target.targetRoot, target.targetIdentity], [parent, target.entryParentIdentity],
    ];
    const privateDirectories: [string, CreatedDirectoryIdentity][] = [];
    const guard = () => {
      for (const [path, identity] of directories) assertDirectory(path, identity);
      for (const [path, identity] of privateDirectories) assertPrivateDirectory(path, identity);
    };
    guard(); assertEntry(target.entryPath, original);
    phase = "reserve";
    await probeNativeFilesystemCapability(parent, target.entryParentIdentity);
    await probeNativeFilesystemCapability(dirname(request.installationRoot), context.destinationParentIdentity);
    guard(); assertEntry(target.entryPath, original);
    installationRoot = request.installationRoot;
    const installationIdentity = await secureCreateDirectory({ directory: dirname(request.installationRoot), name: basename(request.installationRoot), directoryIdentity: context.destinationParentIdentity });
    privateDirectories.push([installationRoot, installationIdentity]);
    guard();
    await syncDirectory(dirname(installationRoot), context.destinationParentIdentity);
    phase = "quarantine";
    guard();
    const directory = join(parent, `.agent-governance-quarantine-${randomUUID()}`);
    quarantine = { directory, entryPath: join(directory, "entry.bin") };
    const identity = await secureCreateDirectory({ directory: parent, name: basename(directory), directoryIdentity: target.entryParentIdentity });
    privateDirectories.push([directory, identity]);
    guard();
    await syncDirectory(parent, target.entryParentIdentity);
    guard();
    await atomicCreate(join(directory, "resources.json"), `${JSON.stringify({ schemaVersion: 1, sourceInstallationRoot: request.sourceInstallationRoot, installationRoot, entryPath: target.entryPath, originalEntry: "entry.bin", detachedEntry: "detached.bin" })}\n`, identity);
    await atomicCreate(quarantine.entryPath, original.bytes, identity);
    const backup = entrySnapshot(quarantine.entryPath);
    const rulesPath = join(directory, "local-rules.md");
    let rulesSnapshot: EntrySnapshot | undefined;
    if (context.localRules !== undefined) {
      await atomicCreate(rulesPath, context.localRules, identity);
      rulesSnapshot = entrySnapshot(rulesPath);
    }
    await syncDirectory(directory, identity);
    guard(); assertEntry(target.entryPath, original); assertEntry(quarantine.entryPath, backup);
    phase = "detach";
    // A native operation may take effect and then fail while closing its handles.
    // Once attempted, absence of a successful return cannot prove non-mutation.
    detached = true;
    await secureRenameNoReplace({ sourceDirectory: parent, sourceName: basename(target.entryPath), sourceDirectoryIdentity: target.entryParentIdentity, destinationDirectory: directory, destinationName: "detached.bin", destinationDirectoryIdentity: identity });
    // Renaming changes ctime. All other bound identity/content fields must match.
    assertEntry(join(directory, "detached.bin"), original, true);
    let owned: EntrySnapshot | undefined;
    const backupPath = quarantine.entryPath;
    restore = async () => {
      guard(); assertEntry(backupPath, backup);
      if (owned !== undefined) {
        assertEntry(target.entryPath, owned);
        await secureRemoveFile({ directory: parent, name: basename(target.entryPath), directoryIdentity: target.entryParentIdentity, objectIdentity: owned.identity });
      }
      // No-clobber is mandatory even when we observed an absent live name.
      await atomicCreate(target.entryPath, original.bytes, target.entryParentIdentity);
      const restored = entrySnapshot(target.entryPath);
      await syncDirectory(parent, target.entryParentIdentity);
      guard(); assertEntry(target.entryPath, restored); assertEntry(backupPath, backup);
    };
    await syncDirectory(directory, identity);
    await syncDirectory(parent, target.entryParentIdentity);
    guard();
    await atomicCreate(target.entryPath, user, target.entryParentIdentity);
    owned = entrySnapshot(target.entryPath);
    const expectedApplied = installManagedBlock(user, buildBinding(context.release, installationRoot));
    const installedRules = join(installationRoot, "releases", context.release.version, "bundle", "agent-governance", context.release.localRulesPath);
    let activated = false;
    const guardInstalledRules = () => {
      if (!activated || context.localRules === undefined) assertMissing(installedRules);
      else if (!entrySnapshot(installedRules).bytes.equals(context.localRules)) throw new Error("installed local rules changed");
    };
    phase = "install";
    const tx = new InstallerTransaction({ installationRoot, releaseRoot: request.releaseRoot, targetRoot: request.targetRoot, entryFile: request.entryFile, scope: "global", nonInteractive: true, dryRun: false, ...(rulesSnapshot === undefined ? {} : { localRules: rulesPath }), onCheckpoint: checkpoint => {
      guard(); assertEntry(backupPath, backup);
      if (checkpoint === "afterCurrent") activated = true;
      guardInstalledRules();
      assertMissing(context.releaseRules);
      if (rulesSnapshot !== undefined) assertEntry(rulesPath, rulesSnapshot);
      if (checkpoint === "afterEntry") {
        const applied = entrySnapshot(target.entryPath);
        if (!applied.bytes.equals(expectedApplied)) throw new Error("replacement postimage changed");
        owned = applied;
      } else if (checkpoint !== "duringRollback") {
        assertEntry(target.entryPath, owned!);
      }
    } });
    await tx.install();
    phase = "verify";
    guard(); guardInstalledRules(); assertEntry(target.entryPath, owned!);
    await tx.verify();
    if ((await tx.status()).state !== "CURRENT") throw new Error("replacement verification failed");
    guard(); guardInstalledRules(); assertEntry(target.entryPath, owned!); assertEntry(backupPath, backup);
    await syncDirectory(parent, target.entryParentIdentity);
    guard(); guardInstalledRules(); assertEntry(target.entryPath, owned!); assertEntry(backupPath, backup);
    return { outcome: "SUCCESS", state: "CURRENT", quarantine };
  } catch {
    let recovery: "NOT_REQUIRED" | "RESTORED" | "RETAINED" = detached ? "RETAINED" : "NOT_REQUIRED";
    if (detached && restore !== undefined) {
      try { await restore(); recovery = "RESTORED"; } catch { /* Ownership is unproved: retain isolation, never force restoration. */ }
    }
    return { outcome: "FAILURE", code: "REPLACEMENT_FAILED", phase, recovery, ...(installationRoot === undefined ? {} : { installationRoot }), ...(quarantine === undefined ? {} : { quarantine }) };
  }
}
