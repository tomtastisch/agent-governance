import { createHash } from "node:crypto";
import { dirname, isAbsolute, relative, resolve, sep } from "node:path";
import type {
  Candidate,
  ClassificationContext,
  DiscoveryCatalog,
  EvidenceFamily,
  EvidenceRecord,
} from "./types.ts";

const ADDITIONAL_CORROBORATING_FAMILIES = new Set<EvidenceFamily>(["tooling", "ai_metadata"]);

function commonSourceRoot(records: readonly EvidenceRecord[]): string {
  if (records.length === 0) return resolve(sep);
  const directories = records.map(({ sourcePath }) => {
    if (!isAbsolute(sourcePath)) throw new Error("evidence source path must be absolute");
    return dirname(resolve(sourcePath));
  });
  let common = directories[0]!;
  for (const directory of directories.slice(1)) {
    while (directory !== common && !directory.startsWith(`${common}${sep}`)) {
      const parent = dirname(common);
      if (parent === common) break;
      common = parent;
    }
  }
  return common;
}

function normalizedEvidence(root: string, record: EvidenceRecord): string {
  const source = isAbsolute(record.sourcePath) ? relative(root, resolve(record.sourcePath)) : record.sourcePath;
  const metadata = [...new Set(record.metadata.map((item) => item.toLowerCase()))].sort();
  return JSON.stringify([
    source.split(sep).join("/"),
    record.sourceKind,
    record.family,
    record.signalId,
    record.strength,
    record.status,
    metadata,
  ]);
}

function digestEvidence(root: string, records: readonly EvidenceRecord[]): string {
  const normalized = [...new Set(records.map((record) => normalizedEvidence(root, record)))].sort();
  return createHash("sha256").update(JSON.stringify(normalized)).digest("hex").slice(0, 16);
}

function catalogEvidence(records: readonly EvidenceRecord[], catalog: DiscoveryCatalog): readonly EvidenceRecord[] {
  const signals = new Map(catalog.signals.map((signal) => [signal.id, signal]));
  return Object.freeze(records.filter((record) => {
    const signal = signals.get(record.signalId);
    return signal !== undefined &&
      signal.family === record.family &&
      signal.strength === record.strength &&
      signal.sourceKinds.includes(record.sourceKind);
  }));
}

export function classifyEvidence(
  records: readonly EvidenceRecord[],
  catalog: DiscoveryCatalog,
  context: ClassificationContext = {},
): Candidate {
  const root = resolve(context.root ?? commonSourceRoot(records));
  const evidence = catalogEvidence(records, catalog);
  const families = [...new Set(evidence.map(({ family }) => family))].sort();
  const independentSources = new Set(evidence.map(({ sourcePath }) => resolve(sourcePath))).size;
  const score = families.reduce((total, family) => total + catalog.evidenceFamilies[family].weight, 0);
  const candidateClass = context.candidateClass ?? "DIRECTORY";
  const status = context.status ?? (evidence.every(({ status: recordStatus }) => recordStatus === "COMPLETE")
    ? "COMPLETE"
    : "INCOMPLETE");
  const fileCount = context.fileCount ?? independentSources;
  if (!Number.isSafeInteger(fileCount) || fileCount < 0) throw new Error("candidate file count must be a non-negative integer");
  const activityAt = context.activityAt ?? null;
  if (activityAt !== null && (!Number.isFinite(activityAt) || activityAt < 0)) {
    throw new Error("candidate activity must be a non-negative finite number or null");
  }

  const strongRuntime = evidence.some(({ family, strength }) => family === "runtime" && strength === "strong");
  const stateAnchor = evidence.some(({ family, strength }) =>
    family === "state" && (strength === "strong" || strength === "corroborating"));
  const additionalCorroboration = evidence.some(({ family, strength }) =>
    ADDITIONAL_CORROBORATING_FAMILIES.has(family) && (strength === "strong" || strength === "corroborating"));
  const complete = status === "COMPLETE" && evidence.every(({ status: recordStatus }) => recordStatus === "COMPLETE");
  const packageOnly = families.length === 1 && families[0] === "package_metadata";
  const hasAnchor = families.includes("runtime") || families.includes("state") || packageOnly;
  const high = candidateClass === "DIRECTORY" &&
    complete &&
    score >= catalog.confidence.highMinimumScore &&
    families.length >= catalog.confidence.highMinimumFamilies &&
    independentSources >= catalog.confidence.highMinimumIndependentSources &&
    catalog.confidence.highRequiresRuntime &&
    strongRuntime &&
    stateAnchor &&
    additionalCorroboration;
  const plausible = packageOnly || (
    hasAnchor &&
    independentSources >= 2 &&
    score >= catalog.confidence.uncertainMinimumScore
  );
  const confidence = high ? "HIGH_CONFIDENCE" : plausible ? "UNCERTAIN" : "REJECTED";

  return Object.freeze({
    root,
    candidateClass,
    status,
    confidence,
    score,
    families: Object.freeze(families),
    independentSources,
    evidence,
    fileCount,
    evidenceDensity: fileCount === 0 ? 0 : evidence.length / fileCount,
    activityAt,
    evidenceDigest: digestEvidence(root, evidence),
  });
}
