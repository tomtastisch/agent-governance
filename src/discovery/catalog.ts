import { readFileSync } from "node:fs";
import { parse } from "smol-toml";
import { resolveCatalogPath, resolveManifestPath } from "../catalog-paths.ts";
import {
  EVIDENCE_FAMILIES,
  type CandidateClass,
  type CandidateClassDefinition,
  type DiscoveryCatalog,
  type DiscoveryConfidence,
  type DiscoveryLimits,
  type DiscoverySignal,
  type EvidenceFamily,
  type EvidenceFamilyDefinition,
  type EvidenceSourceKind,
  type EvidenceStrength,
} from "./types.ts";

const TOP_LEVEL_FIELDS = new Set([
  "schema_version",
  "limits",
  "confidence",
  "candidate_classes",
  "evidence_families",
  "signals",
]);
const LIMIT_FIELDS = new Set([
  "max_depth",
  "max_files",
  "max_entries",
  "max_file_bytes",
  "max_sqlite_objects",
  "max_sqlite_columns",
  "max_duration_ms",
  "max_metadata_length",
]);
const CONFIDENCE_FIELDS = new Set([
  "high_minimum_score",
  "high_minimum_families",
  "high_minimum_independent_sources",
  "high_requires_runtime",
  "uncertain_minimum_score",
]);
const CANDIDATE_CLASS_FIELDS = new Set(["class", "label"]);
const FAMILY_FIELDS = new Set(["default_strength", "weight"]);
const SIGNAL_FIELDS = new Set(["id", "family", "source_kinds", "keys", "minimum_matches", "strength"]);
const CANDIDATE_CLASS_IDS = ["directory", "app_bundle"] as const;
const CANDIDATE_CLASSES = ["DIRECTORY", "APP_BUNDLE"] as const;
const STRENGTHS = ["strong", "corroborating", "weak"] as const;
const SOURCE_KINDS = ["json", "toml", "plist", "sqlite_schema", "package_metadata"] as const;

function record(value: unknown, context: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${context} must be a table`);
  }
  return value as Record<string, unknown>;
}

function exactFields(value: Record<string, unknown>, fields: ReadonlySet<string>, context: string): void {
  const unknown = Object.keys(value).filter((field) => !fields.has(field));
  const missing = [...fields].filter((field) => !(field in value));
  if (unknown.length > 0) throw new Error(`${context} contains unknown fields: ${unknown.join(", ")}`);
  if (missing.length > 0) throw new Error(`${context} contains missing fields: ${missing.join(", ")}`);
}

function positiveInteger(value: unknown, context: string): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value <= 0) {
    throw new Error(`${context} must be a positive integer`);
  }
  return value;
}

function nonemptyText(value: unknown, context: string): string {
  if (typeof value !== "string" || value.trim().length === 0 || /[\0\r\n\x1b]/.test(value)) {
    throw new Error(`${context} must be nonempty sanitized text`);
  }
  return value;
}

function id(value: unknown, context: string): string {
  const result = nonemptyText(value, context);
  if (!/^[a-z][a-z0-9_]*$/.test(result)) throw new Error(`${context} is invalid`);
  return result;
}

function enumValue<T extends string>(value: unknown, allowed: readonly T[], context: string): T {
  if (typeof value !== "string" || !allowed.includes(value as T)) throw new Error(`${context} is invalid`);
  return value as T;
}

function uniqueStringArray(value: unknown, context: string): readonly string[] {
  if (!Array.isArray(value) || value.length === 0 || value.some((item) => typeof item !== "string")) {
    throw new Error(`${context} must be a nonempty string array`);
  }
  const entries = value as string[];
  if (new Set(entries).size !== entries.length) throw new Error(`${context} contains duplicate values`);
  return Object.freeze([...entries]);
}

function parseCatalog(path: string): Record<string, unknown> {
  try {
    return record(parse(readFileSync(path, "utf8")), "discovery catalog");
  } catch (cause) {
    if (cause instanceof Error && cause.message.startsWith("discovery catalog ")) throw cause;
    throw new Error("discovery catalog is invalid TOML", { cause });
  }
}

function parseLimits(raw: unknown): DiscoveryLimits {
  const limits = record(raw, "discovery limits");
  exactFields(limits, LIMIT_FIELDS, "discovery limits");
  return Object.freeze({
    maxDepth: positiveInteger(limits.max_depth, "max_depth"),
    maxFiles: positiveInteger(limits.max_files, "max_files"),
    maxEntries: positiveInteger(limits.max_entries, "max_entries"),
    maxFileBytes: positiveInteger(limits.max_file_bytes, "max_file_bytes"),
    maxSqliteObjects: positiveInteger(limits.max_sqlite_objects, "max_sqlite_objects"),
    maxSqliteColumns: positiveInteger(limits.max_sqlite_columns, "max_sqlite_columns"),
    maxDurationMs: positiveInteger(limits.max_duration_ms, "max_duration_ms"),
    maxMetadataLength: positiveInteger(limits.max_metadata_length, "max_metadata_length"),
  });
}

function parseConfidence(raw: unknown): DiscoveryConfidence {
  const confidence = record(raw, "discovery confidence");
  exactFields(confidence, CONFIDENCE_FIELDS, "discovery confidence");
  if (typeof confidence.high_requires_runtime !== "boolean") {
    throw new Error("high_requires_runtime must be boolean");
  }
  const result = Object.freeze({
    highMinimumScore: positiveInteger(confidence.high_minimum_score, "high_minimum_score"),
    highMinimumFamilies: positiveInteger(confidence.high_minimum_families, "high_minimum_families"),
    highMinimumIndependentSources: positiveInteger(
      confidence.high_minimum_independent_sources,
      "high_minimum_independent_sources",
    ),
    highRequiresRuntime: confidence.high_requires_runtime,
    uncertainMinimumScore: positiveInteger(confidence.uncertain_minimum_score, "uncertain_minimum_score"),
  });
  if (result.uncertainMinimumScore >= result.highMinimumScore) {
    throw new Error("uncertain_minimum_score must be less than high_minimum_score");
  }
  return result;
}

function parseCandidateClasses(raw: unknown): DiscoveryCatalog["candidateClasses"] {
  const entries = record(raw, "candidate classes");
  exactFields(entries, new Set(CANDIDATE_CLASS_IDS), "candidate classes");
  const result = {} as Record<(typeof CANDIDATE_CLASS_IDS)[number], CandidateClassDefinition>;
  CANDIDATE_CLASS_IDS.forEach((entryId, index) => {
    const entry = record(entries[entryId], `candidate class ${entryId}`);
    exactFields(entry, CANDIDATE_CLASS_FIELDS, `candidate class ${entryId}`);
    const candidateClass = enumValue(entry.class, CANDIDATE_CLASSES, `candidate class ${entryId}.class`);
    if (candidateClass !== CANDIDATE_CLASSES[index]) throw new Error(`candidate class ${entryId} semantics are invalid`);
    result[entryId] = Object.freeze({
      class: candidateClass as CandidateClass,
      label: nonemptyText(entry.label, `candidate class ${entryId}.label`),
    });
  });
  return Object.freeze(result);
}

function parseFamilies(raw: unknown): DiscoveryCatalog["evidenceFamilies"] {
  const entries = record(raw, "evidence families");
  exactFields(entries, new Set(EVIDENCE_FAMILIES), "evidence families");
  const result = {} as Record<EvidenceFamily, EvidenceFamilyDefinition>;
  for (const family of EVIDENCE_FAMILIES) {
    const entry = record(entries[family], `evidence family ${family}`);
    exactFields(entry, FAMILY_FIELDS, `evidence family ${family}`);
    result[family] = Object.freeze({
      defaultStrength: enumValue(entry.default_strength, STRENGTHS, `evidence family ${family}.default_strength`),
      weight: positiveInteger(entry.weight, `evidence family ${family}.weight`),
    });
  }
  return Object.freeze(result);
}

function parseSignals(raw: unknown, families: DiscoveryCatalog["evidenceFamilies"]): readonly DiscoverySignal[] {
  if (!Array.isArray(raw) || raw.length === 0) throw new Error("discovery signals must be a nonempty array");
  const seen = new Set<string>();
  const signals = raw.map((item, index): DiscoverySignal => {
    const signal = record(item, `discovery signal ${index}`);
    exactFields(signal, SIGNAL_FIELDS, `discovery signal ${index}`);
    const signalId = id(signal.id, `discovery signal ${index}.id`);
    if (seen.has(signalId)) throw new Error("discovery signals contain duplicate IDs");
    seen.add(signalId);
    const family = id(signal.family, `discovery signal ${signalId}.family`) as EvidenceFamily;
    if (!(family in families)) throw new Error(`discovery signal ${signalId}.family is unknown`);
    const sourceKinds = uniqueStringArray(signal.source_kinds, `discovery signal ${signalId}.source_kinds`).map(
      (source) => enumValue(source, SOURCE_KINDS, `discovery signal ${signalId}.source_kinds`),
    );
    const keys = uniqueStringArray(signal.keys, `discovery signal ${signalId}.keys`).map((key) =>
      id(key, `discovery signal ${signalId}.keys`),
    );
    const minimumMatches = positiveInteger(signal.minimum_matches, `discovery signal ${signalId}.minimum_matches`);
    if (minimumMatches > keys.length) throw new Error(`discovery signal ${signalId}.minimum_matches exceeds keys`);
    return Object.freeze({
      id: signalId,
      family,
      sourceKinds: Object.freeze(sourceKinds),
      keys: Object.freeze(keys),
      minimumMatches,
      strength: enumValue(signal.strength, STRENGTHS, `discovery signal ${signalId}.strength`) as EvidenceStrength,
    });
  });
  return Object.freeze(signals);
}

export function loadDiscoveryCatalog(releaseRoot?: string): DiscoveryCatalog {
  const manifestPath = resolveManifestPath(releaseRoot);
  const manifest = parseCatalog(manifestPath);
  const catalogs = record(manifest.catalogs, "discovery manifest catalogs");
  const catalogPath = resolveCatalogPath(manifestPath, catalogs.discovery_signals);
  const catalog = parseCatalog(catalogPath);
  exactFields(catalog, TOP_LEVEL_FIELDS, "discovery catalog");
  if (catalog.schema_version !== 1) throw new Error("discovery catalog schema_version must be integer 1");
  const evidenceFamilies = parseFamilies(catalog.evidence_families);
  return Object.freeze({
    schemaVersion: 1,
    limits: parseLimits(catalog.limits),
    confidence: parseConfidence(catalog.confidence),
    candidateClasses: parseCandidateClasses(catalog.candidate_classes),
    evidenceFamilies,
    signals: parseSignals(catalog.signals, evidenceFamilies),
  });
}
