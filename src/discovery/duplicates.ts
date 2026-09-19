import { relative, sep } from "node:path";
import type { Candidate, EvidenceRecord } from "./types.ts";

function structuralToken(candidate: Candidate, record: EvidenceRecord): string {
  const source = relative(candidate.root, record.sourcePath).split(sep).join("/");
  return JSON.stringify([
    source,
    record.sourceKind,
    record.family,
    record.signalId,
    record.strength,
    [...new Set(record.metadata.map((item) => item.toLowerCase()))].sort(),
  ]);
}

function structure(candidate: Candidate): ReadonlySet<string> {
  return new Set(candidate.evidence.map((record) => structuralToken(candidate, record)));
}

function similarity(left: Candidate, right: Candidate): number {
  const leftTokens = structure(left);
  const rightTokens = structure(right);
  const union = new Set([...leftTokens, ...rightTokens]);
  if (union.size === 0) return 0;
  let intersection = 0;
  for (const token of leftTokens) if (rightTokens.has(token)) intersection += 1;
  return intersection / union.size;
}

function duplicatePair(left: Candidate, right: Candidate): boolean {
  if (left.candidateClass !== right.candidateClass) return false;
  const densityRange = Math.max(left.evidenceDensity, right.evidenceDensity, 1);
  const densityDifference = Math.abs(left.evidenceDensity - right.evidenceDensity) / densityRange;
  return densityDifference <= 0.5 && (left.evidenceDigest === right.evidenceDigest || similarity(left, right) >= 0.75);
}

function demote(candidate: Candidate): Candidate {
  return candidate.confidence === "UNCERTAIN"
    ? candidate
    : Object.freeze({ ...candidate, confidence: "UNCERTAIN" as const });
}

function preferredCandidate(group: readonly Candidate[]): Candidate | null {
  const ranked = [...group].sort((left, right) => {
    const complete = Number(right.status === "COMPLETE") - Number(left.status === "COMPLETE");
    if (complete !== 0) return complete;
    if (right.score !== left.score) return right.score - left.score;
    if (right.evidenceDensity !== left.evidenceDensity) return right.evidenceDensity - left.evidenceDensity;
    return (right.activityAt ?? -1) - (left.activityAt ?? -1);
  });
  const first = ranked[0]!;
  const second = ranked[1];
  if (second === undefined) return first;
  const distinguishable = first.status !== second.status ||
    first.score !== second.score ||
    first.evidenceDensity !== second.evidenceDensity ||
    first.activityAt !== second.activityAt;
  return distinguishable ? first : null;
}

export function resolveDuplicateCandidates(candidates: readonly Candidate[]): readonly Candidate[] {
  const positive = candidates.filter(({ confidence }) => confidence !== "REJECTED");
  const remaining = new Set(positive);
  const resolved: Candidate[] = [];
  for (const candidate of [...positive].sort((left, right) => left.root.localeCompare(right.root))) {
    if (!remaining.has(candidate)) continue;
    const group = [...remaining].filter((other) => other === candidate || duplicatePair(candidate, other));
    group.forEach((member) => remaining.delete(member));
    if (group.length === 1) {
      resolved.push(candidate);
      continue;
    }
    const preferred = preferredCandidate(group);
    if (preferred === null) resolved.push(...group.map(demote));
    else resolved.push(preferred);
  }
  return Object.freeze(resolved.sort((left, right) => left.root.localeCompare(right.root)));
}
