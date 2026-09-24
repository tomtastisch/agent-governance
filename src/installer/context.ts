import { createHash } from "node:crypto";
import { join } from "node:path";
import type { InstallResult } from "../contracts.ts";
import { verifyManagedBlock, type GovernanceBinding } from "../managed-block.ts";
import { verifyRelease, type VerifiedRelease } from "../release.ts";
import { inspectTarget, type TargetInspection } from "../target.ts";
import type { TransactionRequest } from "./contracts.ts";
import { optionalCanonicalLocalRules } from "./local-rules.ts";
import { optionalBytes, requiredBytes } from "./snapshot.ts";
import { parseCurrentObject, receiptWithMatchingBackup, type CurrentMetadata } from "./receipts.ts";
import { compareSemver, SEMVER } from "./version.ts";

export interface Context { readonly target: TargetInspection; readonly release: VerifiedRelease; readonly binding: GovernanceBinding; readonly current?: CurrentMetadata; readonly installedLocalRules?: Buffer; readonly entry: Buffer; readonly state: InstallResult["state"]; }

export function bindingIdFor(targetRoot: string, entryFile: string): string { return createHash("sha256").update(targetRoot).update("\0").update(entryFile).digest("hex"); }

export function buildBinding(release: VerifiedRelease, installationRoot: string): GovernanceBinding { const base = join(installationRoot, "releases", release.version, "bundle"); return { version: release.version, installationRoot, governancePath: join(base, "GOVERNANCE.md"), manifestPath: join(base, "agent-governance", "manifest.toml"), governanceDigest: release.governanceDigest, manifestDigest: release.manifestDigest, bundleDigest: release.bundleDigest }; }

export async function resolveContext(request: TransactionRequest, bindingId: string, currentPath: string, receiptPath: string): Promise<Context> {
  const target = await inspectTarget(request.targetRoot, request.entryFile, request.installationRoot); const release = await verifyRelease(request.releaseRoot); const binding = buildBinding(release, request.installationRoot); const entry = (await optionalBytes(target.entryPath)) ?? Buffer.alloc(0); const currentBytes = await optionalBytes(currentPath); const receiptBytes = await optionalBytes(receiptPath);
  if (receiptBytes !== undefined) { try { const receipt = await receiptWithMatchingBackup(receiptBytes, request, bindingId); const backupReceipt = await requiredBytes(join(receipt.backupRoot, "receipt.json"), "backup receipt"); if (receipt.status === "PREPARED" || !receiptBytes.equals(backupReceipt)) return { target, release, binding, entry, state: "RECOVERY_REQUIRED" }; } catch { return { target, release, binding, entry, state: "TAMPERED" }; } }
  if (currentBytes !== undefined && receiptBytes === undefined) return { target, release, binding, entry, state: "TAMPERED" };
  if (currentBytes === undefined) { const hasMarker = entry.includes(Buffer.from("AGENT_GOVERNANCE_MANAGED_")); return { target, release, binding, entry, state: hasMarker ? "TAMPERED" : target.entryExists ? "FRESH" : "ABSENT" }; }
  let current: CurrentMetadata; try { current = parseCurrentObject(currentBytes); } catch { return { target, release, binding, entry, state: "TAMPERED" }; }
  try {
    if (current.schemaVersion !== 1 || current.installationRoot !== request.installationRoot || current.targetRoot !== request.targetRoot || current.entryFile !== request.entryFile || !SEMVER.test(current.version)) throw new Error("current metadata mismatch");
    const installed = await verifyRelease(join(request.installationRoot, "releases", current.version)); const installedLocalRules = await optionalCanonicalLocalRules(join(request.installationRoot, "releases", current.version, "bundle", "agent-governance", installed.localRulesPath)); const installedBinding = buildBinding(installed, request.installationRoot); const expected: CurrentMetadata = { schemaVersion: 1, ...installedBinding, targetRoot: request.targetRoot, entryFile: request.entryFile };
    for (const key of Object.keys(expected) as (keyof CurrentMetadata)[]) if (current[key] !== expected[key]) throw new Error("current metadata mismatch");
    verifyManagedBlock(entry, installedBinding); const comparison = compareSemver(release.version, installed.version); if (comparison === 0 && release.bundleDigest !== installed.bundleDigest) throw new Error("release content changed without a version change");
    return { target, release, binding, current, ...(installedLocalRules === undefined ? {} : { installedLocalRules }), entry, state: comparison === 0 ? "CURRENT" : comparison > 0 ? "OUTDATED" : "DOWNGRADE_BLOCKED" };
  } catch { return { target, release, binding, current, entry, state: "TAMPERED" }; }
}
