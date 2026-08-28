import { lstat } from "node:fs/promises";
import { basename, extname } from "node:path";
import { refineCandidateRoots } from "./boundary.ts";
import { loadDiscoveryCatalog } from "./catalog.ts";
import { classifyEvidence } from "./classifier.ts";
import { resolveDuplicateCandidates } from "./duplicates.ts";
import { enumerateCandidates } from "./filesystem.ts";
import { analyzePackageMetadata } from "./package-metadata.ts";
import { analyzeSqliteSchema } from "./sqlite.ts";
import { analyzeStructuredFile } from "./structured.ts";
import type { Candidate, DiscoverCandidatesOptions, DiscoveryStatus, EvidenceRecord } from "./types.ts";
import { discoverZones } from "./zones.ts";

const SQLITE_EXTENSIONS = new Set([".db", ".sqlite", ".sqlite3"]);
const STRUCTURED_EXTENSIONS = new Set([".json", ".toml", ".plist"]);

async function analyzeCandidateFiles(
  files: readonly string[],
  limits: ReturnType<typeof loadDiscoveryCatalog>["limits"],
  catalog: ReturnType<typeof loadDiscoveryCatalog>,
): Promise<{ readonly evidence: readonly EvidenceRecord[]; readonly status: DiscoveryStatus; readonly activityAt: number | null }> {
  const evidence: EvidenceRecord[] = [];
  let status: DiscoveryStatus = "COMPLETE";
  let activityAt: number | null = null;
  for (const path of files) {
    try {
      const metadata = await lstat(path);
      activityAt = Math.max(activityAt ?? 0, metadata.mtimeMs);
      const extension = extname(path).toLowerCase();
      const records = basename(path).toLowerCase() === "package.json"
        ? await analyzePackageMetadata(path, limits, catalog)
        : SQLITE_EXTENSIONS.has(extension)
          ? await analyzeSqliteSchema(path, limits, catalog)
          : STRUCTURED_EXTENSIONS.has(extension)
            ? await analyzeStructuredFile(path, limits, catalog)
            : [];
      evidence.push(...records.map((record) => Object.freeze({ ...record, sourcePath: path })));
      if (records.some(({ status: recordStatus }) => recordStatus === "INCOMPLETE")) status = "INCOMPLETE";
    } catch {
      status = "INCOMPLETE";
    }
  }
  return Object.freeze({ evidence: Object.freeze(evidence), status, activityAt });
}

export async function discoverCandidates(options: DiscoverCandidatesOptions): Promise<readonly Candidate[]> {
  const catalog = loadDiscoveryCatalog(options.releaseRoot);
  const enumerated = await enumerateCandidates(
    discoverZones(options.environment),
    catalog.limits,
    options.clock ?? Date.now,
  );
  const classified: Candidate[] = [];
  for (const candidate of enumerated) {
    const analysis = await analyzeCandidateFiles(candidate.files, catalog.limits, catalog);
    const status = candidate.status === "INCOMPLETE" || analysis.status === "INCOMPLETE" ? "INCOMPLETE" : "COMPLETE";
    classified.push(classifyEvidence(analysis.evidence, catalog, {
      root: candidate.root,
      candidateClass: candidate.candidateClass,
      status,
      fileCount: candidate.filesVisited,
      activityAt: analysis.activityAt,
    }));
  }
  const positive = classified.filter(({ confidence }) => confidence !== "REJECTED");
  return resolveDuplicateCandidates(refineCandidateRoots(positive, catalog));
}

export { refineCandidateRoots } from "./boundary.ts";
export { classifyEvidence } from "./classifier.ts";
export { resolveDuplicateCandidates } from "./duplicates.ts";
export { resolveCandidateIdentity } from "./identity.ts";
export type {
  Candidate,
  CandidateConfidence,
  CandidateDisplay,
  ClassificationContext,
  DiscoverCandidatesOptions,
} from "./types.ts";
