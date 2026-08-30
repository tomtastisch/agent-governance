import { basename } from "node:path";
import { sanitizeDisplay } from "./structured.ts";
import type { Candidate, CandidateDisplay } from "./types.ts";

function candidateLabel(candidate: Candidate): string {
  const withoutBundleSuffix = basename(candidate.root).replace(/\.app$/i, "");
  return sanitizeDisplay(withoutBundleSuffix, 96) || "Unnamed candidate";
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
