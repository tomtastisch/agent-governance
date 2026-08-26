import { basename } from "node:path";
import { sanitizeDisplay } from "./structured.ts";
import type { Candidate, CandidateDisplay } from "./types.ts";

const COPY_SUFFIX = /(?:[-_. ]?(?:copy|backup|snapshot)(?:[-_. ]?\d+)?)$/i;

function candidateLabel(candidate: Candidate): string {
  const withoutBundleSuffix = basename(candidate.root).replace(/\.app$/i, "");
  return sanitizeDisplay(withoutBundleSuffix, 96) || "Unnamed candidate";
}

export function normalizedCandidateIdentity(candidate: Candidate): string {
  if (candidate.confidence === "REJECTED") throw new Error("candidate identity requires positive classification");
  return candidateLabel(candidate).replace(COPY_SUFFIX, "").trim().toLowerCase();
}

export function resolveCandidateIdentity(candidate: Candidate): CandidateDisplay {
  if (candidate.confidence === "REJECTED") throw new Error("candidate identity requires positive classification");
  return Object.freeze({
    root: candidate.root,
    label: candidateLabel(candidate),
    candidateClass: candidate.candidateClass,
    confidence: candidate.confidence,
  });
}
