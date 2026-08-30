import { isAbsolute, relative, resolve, sep } from "node:path";
import { loadDiscoveryCatalog } from "./catalog.ts";
import { classifyEvidence } from "./classifier.ts";
import type { Candidate, DiscoveryCatalog, EvidenceRecord } from "./types.ts";

function childRoot(root: string, sourcePath: string): string | null {
  if (!isAbsolute(sourcePath)) return null;
  const remainder = relative(root, resolve(sourcePath));
  if (remainder === "" || remainder === ".." || remainder.startsWith(`..${sep}`)) return null;
  const parts = remainder.split(sep);
  return parts.length > 1 ? resolve(root, parts[0]!) : null;
}

function splitBroadCandidate(candidate: Candidate, catalog: DiscoveryCatalog): readonly Candidate[] {
  if (candidate.confidence === "REJECTED") return [];
  const groups = new Map<string, EvidenceRecord[]>();
  for (const record of candidate.evidence) {
    const root = childRoot(candidate.root, record.sourcePath);
    if (root === null) return [candidate];
    const group = groups.get(root) ?? [];
    group.push(record);
    groups.set(root, group);
  }
  if (groups.size === 0) return [candidate];

  const refined = [...groups.entries()].map(([root, evidence]) => classifyEvidence(evidence, catalog, {
    root,
    candidateClass: candidate.candidateClass,
    status: candidate.status,
    fileCount: new Set(evidence.map(({ sourcePath }) => sourcePath)).size,
    activityAt: candidate.activityAt,
  })).filter(({ confidence }) => confidence !== "REJECTED");
  return refined.length === groups.size ? refined : [candidate];
}

function isDescendant(parent: string, child: string): boolean {
  const remainder = relative(parent, child);
  return remainder !== "" && remainder !== ".." && !remainder.startsWith(`..${sep}`) && !isAbsolute(remainder);
}

export function refineCandidateRoots(
  candidates: readonly Candidate[],
  catalog: DiscoveryCatalog = loadDiscoveryCatalog(),
): readonly Candidate[] {
  const byRoot = new Map<string, Candidate>();
  for (const candidate of candidates.flatMap((item) => splitBroadCandidate(item, catalog))) {
    const current = byRoot.get(candidate.root);
    if (current === undefined || candidate.score > current.score) byRoot.set(candidate.root, candidate);
  }
  const unique = [...byRoot.values()];
  return Object.freeze(unique
    .filter((candidate) => !unique.some((other) => isDescendant(candidate.root, other.root)))
    .sort((left, right) => left.root.localeCompare(right.root)));
}
