import { lstat, opendir, realpath } from "node:fs/promises";
import { isAbsolute, join, resolve } from "node:path";
import type {
  DiscoveredCandidate,
  DiscoveryIssue,
  DiscoveryLimits,
  DiscoveryZone,
} from "./types.ts";

interface Counters {
  entries: number;
  files: number;
}

interface MutableCandidate {
  root: string;
  candidateClass: DiscoveryZone["candidateClass"];
  files: string[];
  entriesVisited: number;
  filesVisited: number;
  issues: Set<DiscoveryIssue>;
}

export async function canonicalizeLiveCandidate(
  path: string,
  canonicalize: (path: string) => Promise<string> = realpath,
): Promise<string | null> {
  try {
    return await canonicalize(path);
  } catch (error) {
    const code = (error as NodeJS.ErrnoException).code;
    if (["EACCES", "ELOOP", "ENOENT", "ENOTDIR", "EPERM"].includes(code ?? "")) return null;
    throw error;
  }
}

function validateLimits(limits: DiscoveryLimits): void {
  for (const [name, value] of Object.entries(limits)) {
    if (!Number.isSafeInteger(value) || value <= 0) throw new Error(`${name} must be a positive integer`);
  }
}

async function requireCanonicalDirectory(path: string, label: string): Promise<string> {
  if (!isAbsolute(path)) throw new Error(`${label} must be absolute`);
  const normalized = resolve(path);
  const metadata = await lstat(normalized);
  if (metadata.isSymbolicLink() || !metadata.isDirectory()) {
    throw new Error(`${label} must be a non-symlink directory`);
  }
  if ((await realpath(normalized)) !== normalized) throw new Error(`${label} must be canonical and contain no symlinks`);
  return normalized;
}

function issueFor(error: unknown): DiscoveryIssue {
  const code = (error as NodeJS.ErrnoException).code;
  return code === "EACCES" || code === "EPERM" ? "PERMISSION_DENIED" : "IO_ERROR";
}

async function traverseCandidate(
  candidate: MutableCandidate,
  limits: DiscoveryLimits,
  counters: Counters,
  zoneEntryStart: number,
  zoneEntryLimit: number,
  zoneFileStart: number,
  zoneFileLimit: number,
  expired: () => boolean,
): Promise<void> {
  const visitDirectory = async (directory: string, depth: number): Promise<boolean> => {
    if (expired()) {
      candidate.issues.add("TIME_LIMIT");
      return false;
    }
    let handle;
    try {
      handle = await opendir(directory);
    } catch (error) {
      candidate.issues.add(issueFor(error));
      return true;
    }
    try {
      for await (const entry of handle) {
        if (expired()) {
          candidate.issues.add("TIME_LIMIT");
          return false;
        }
        if (
          counters.entries - zoneEntryStart >= zoneEntryLimit
          || counters.entries >= limits.maxEntries
        ) {
          candidate.issues.add("ENTRY_LIMIT");
          return false;
        }
        counters.entries += 1;
        candidate.entriesVisited += 1;
        const path = join(directory, entry.name);
        let metadata;
        try {
          metadata = await lstat(path);
        } catch (error) {
          candidate.issues.add(issueFor(error));
          continue;
        }
        if (metadata.isSymbolicLink()) {
          candidate.issues.add("SYMLINK_SKIPPED");
          continue;
        }
        if (metadata.isDirectory()) {
          if (depth >= limits.maxDepth) {
            candidate.issues.add("DEPTH_LIMIT");
            continue;
          }
          if (!(await visitDirectory(path, depth + 1))) return false;
          continue;
        }
        if (!metadata.isFile()) continue;
        if (counters.files - zoneFileStart >= zoneFileLimit) {
          candidate.issues.add("FILE_LIMIT");
          return false;
        }
        if (counters.files >= limits.maxFiles) {
          candidate.issues.add("FILE_LIMIT");
          return false;
        }
        counters.files += 1;
        candidate.filesVisited += 1;
        if (metadata.size > limits.maxFileBytes) {
          candidate.issues.add("FILE_SIZE_LIMIT");
          continue;
        }
        try {
          if ((await realpath(path)) !== path) {
            candidate.issues.add("SYMLINK_SKIPPED");
            continue;
          }
        } catch (error) {
          candidate.issues.add(issueFor(error));
          continue;
        }
        candidate.files.push(path);
      }
    } catch (error) {
      candidate.issues.add(issueFor(error));
    }
    return true;
  };

  await visitDirectory(candidate.root, 0);
}

function complete(candidate: MutableCandidate): DiscoveredCandidate {
  return Object.freeze({
    root: candidate.root,
    candidateClass: candidate.candidateClass,
    status: candidate.issues.size === 0 ? "COMPLETE" : "INCOMPLETE",
    files: Object.freeze([...candidate.files].sort()),
    filesVisited: candidate.filesVisited,
    entriesVisited: candidate.entriesVisited,
    issues: Object.freeze([...candidate.issues]),
  });
}

export async function enumerateCandidates(
  zones: readonly DiscoveryZone[],
  limits: DiscoveryLimits,
  clock: () => number,
  deadline = clock() + limits.maxDurationMs,
): Promise<readonly DiscoveredCandidate[]> {
  validateLimits(limits);
  const expired = (): boolean => clock() >= deadline;
  const counters: Counters = { entries: 0, files: 0 };
  const candidates: DiscoveredCandidate[] = [];
  const seen = new Set<string>();

  for (const [zoneIndex, zone] of zones.entries()) {
    if (expired()) break;
    const zoneEntryStart = counters.entries;
    const zoneFileStart = counters.files;
    const remainingZones = zones.length - zoneIndex;
    const zoneStarted = clock();
    const zoneDeadline = zoneStarted + Math.max(0, deadline - zoneStarted) / remainingZones;
    const zoneExpired = (): boolean => clock() >= zoneDeadline;
    const zoneEntryLimit = Math.floor((limits.maxEntries - counters.entries) / remainingZones);
    const zoneFileLimit = Math.floor((limits.maxFiles - counters.files) / remainingZones);
    const enumerationEntryLimit = Math.floor(zoneEntryLimit / 2);
    const zoneStart = candidates.length;
    const zoneCandidates: MutableCandidate[] = [];
    const root = await requireCanonicalDirectory(zone.root, `discovery zone ${zone.id}`);
    let handle;
    try {
      handle = await opendir(root);
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "EACCES" || (error as NodeJS.ErrnoException).code === "EPERM") {
        continue;
      }
      throw error;
    }
    for await (const entry of handle) {
      if (counters.entries - zoneEntryStart >= enumerationEntryLimit) break;
      if (counters.files - zoneFileStart >= zoneFileLimit) break;
      if (counters.entries >= limits.maxEntries || counters.files >= limits.maxFiles || zoneExpired()) break;
      counters.entries += 1;
      const path = join(root, entry.name);
      let metadata;
      try {
        metadata = await lstat(path);
      } catch {
        continue;
      }
      if (metadata.isSymbolicLink() || !metadata.isDirectory()) continue;
      if (zone.candidateClass === "APP_BUNDLE" && !entry.name.toLowerCase().endsWith(".app")) continue;
      const canonicalPath = await canonicalizeLiveCandidate(path);
      const seenIdentity = `${zone.candidateClass}\0${path}`;
      if (canonicalPath !== path || seen.has(seenIdentity)) continue;
      seen.add(seenIdentity);
      const candidate: MutableCandidate = {
        root: path,
        candidateClass: zone.candidateClass,
        files: [],
        entriesVisited: 0,
        filesVisited: 0,
        issues: new Set(),
      };
      zoneCandidates.push(candidate);
    }
    for (const [candidateIndex, candidate] of zoneCandidates.entries()) {
      const remainingCandidates = zoneCandidates.length - candidateIndex;
      const candidateStarted = clock();
      const candidateDeadline = Math.min(zoneDeadline,
        candidateStarted + Math.max(0, zoneDeadline - candidateStarted) / remainingCandidates);
      const candidateEntryStart = counters.entries;
      const candidateFileStart = counters.files;
      const candidateEntryLimit = Math.floor(
        (zoneEntryLimit - (counters.entries - zoneEntryStart)) / remainingCandidates,
      );
      const candidateFileLimit = Math.floor(
        (zoneFileLimit - (counters.files - zoneFileStart)) / remainingCandidates,
      );
      await traverseCandidate(
        candidate,
        limits,
        counters,
        candidateEntryStart,
        candidateEntryLimit,
        candidateFileStart,
        candidateFileLimit,
        () => clock() >= candidateDeadline,
      );
      candidates.push(complete(candidate));
    }
    const sortedZoneCandidates = candidates.slice(zoneStart).sort((left, right) => left.root.localeCompare(right.root));
    candidates.splice(zoneStart, sortedZoneCandidates.length, ...sortedZoneCandidates);
    if (counters.entries >= limits.maxEntries || counters.files >= limits.maxFiles || expired()) break;
  }

  return Object.freeze(candidates);
}
