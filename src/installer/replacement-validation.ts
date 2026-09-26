import { lstat, realpath } from "node:fs/promises";
import { dirname, isAbsolute, join, resolve, sep } from "node:path";
import { captureIdentity } from "../filesystem.ts";
import { removeOpaqueManagedEnvelope } from "../managed-block.ts";
import type { ReplacementRequest } from "../replacement.ts";
import { verifyRelease } from "../release.ts";
import { inspectTarget } from "../target.ts";
import { readCanonicalLocalRules } from "./local-rules.ts";
import { assertEntry, assertMissing, entrySnapshot } from "./replacement-guards.ts";

function inside(path: string, root: string): boolean { return path === root || path.startsWith(root.endsWith(sep) ? root : `${root}${sep}`); }

export async function canonicalDirectory(path: string): Promise<void> {
  if (typeof path !== "string" || !isAbsolute(path) || resolve(path) !== path || /[\u0000-\u001f\u007f]/.test(path)) throw new Error("invalid directory");
  const stat = await lstat(path);
  if (!stat.isDirectory() || stat.isSymbolicLink() || await realpath(path) !== path) throw new Error("unsafe directory");
}

export async function validateReplacement(request: ReplacementRequest) {
  for (const path of [request.sourceInstallationRoot, request.installationRoot, request.releaseRoot, request.targetRoot]) {
    if (typeof path !== "string" || !isAbsolute(path) || resolve(path) !== path || /[\u0000-\u001f\u007f]/.test(path)) throw new Error("invalid path");
  }
  if (typeof request.entryFile !== "string" || /[\u0000-\u001f\u007f]/.test(request.entryFile) || request.dryRun !== undefined && typeof request.dryRun !== "boolean") throw new Error("invalid request");
  const old = request.sourceInstallationRoot;
  const fresh = request.installationRoot;
  if (inside(old, fresh) || inside(fresh, old) || inside(request.targetRoot, old) || inside(request.targetRoot, fresh) || inside(request.releaseRoot, old) || inside(request.releaseRoot, fresh)) throw new Error("overlapping roots");
  await canonicalDirectory(old);
  await canonicalDirectory(dirname(old));
  await canonicalDirectory(dirname(fresh));
  try { await lstat(fresh); } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    const target = await inspectTarget(request.targetRoot, request.entryFile, fresh);
    if (inside(target.entryPath, old) || inside(target.entryPath, fresh)) throw new Error("overlapping entry");
    const sourceIdentity = await captureIdentity(old);
    const sourceParentIdentity = await captureIdentity(dirname(old));
    const destinationParentIdentity = await captureIdentity(dirname(fresh));
    const release = await verifyRelease(request.releaseRoot);
    const releaseRules = join(request.releaseRoot, "bundle", "agent-governance", release.localRulesPath);
    assertMissing(releaseRules);
    const original = entrySnapshot(target.entryPath);
    const stat = await lstat(target.entryPath, { bigint: true });
    if (stat.nlink !== 1n || stat.dev !== original.identity.device || stat.ino !== original.identity.inode) throw new Error("unsafe entry identity");
    const user = removeOpaqueManagedEnvelope(original.bytes);
    const localRules = request.localRules === undefined ? undefined : await readCanonicalLocalRules(request.localRules);
    assertEntry(target.entryPath, original);
    return { target, sourceIdentity, sourceParentIdentity, destinationParentIdentity, original, user, release, releaseRules, localRules };
  }
  throw new Error("destination exists");
}
