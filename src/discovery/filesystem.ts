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
        if (counters.entries >= limits.maxEntries) {
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
): Promise<readonly DiscoveredCandidate[]> {
  validateLimits(limits);
  const startedAt = clock();
  const expired = (): boolean => clock() - startedAt >= limits.maxDurationMs;
  const counters: Counters = { entries: 0, files: 0 };
  const candidates: DiscoveredCandidate[] = [];
  const seen = new Set<string>();

  for (const zone of zones) {
    const zoneStart = candidates.length;
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
      if (counters.entries >= limits.maxEntries || expired()) break;
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
      if ((await realpath(path)) !== path || seen.has(path)) continue;
      seen.add(path);
      const candidate: MutableCandidate = {
        root: path,
        candidateClass: zone.candidateClass,
        files: [],
        entriesVisited: 0,
        filesVisited: 0,
        issues: new Set(),
      };
      await traverseCandidate(candidate, limits, counters, expired);
      candidates.push(complete(candidate));
      if (
        candidate.issues.has("ENTRY_LIMIT") ||
        candidate.issues.has("FILE_LIMIT") ||
        candidate.issues.has("TIME_LIMIT")
      ) {
        break;
      }
    }
    const sortedZoneCandidates = candidates.slice(zoneStart).sort((left, right) => left.root.localeCompare(right.root));
    candidates.splice(zoneStart, sortedZoneCandidates.length, ...sortedZoneCandidates);
    if (counters.entries >= limits.maxEntries || counters.files >= limits.maxFiles || expired()) break;
  }

  return Object.freeze(candidates);
}
