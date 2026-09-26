import { readFileSync } from "node:fs";
import { join } from "node:path";
import { PACKAGE_RELEASE_ROOT } from "./catalog-paths.ts";

/**
 * Lädt und validiert die sprachneutrale Governance-Contract-Fixture (Issue #90).
 *
 * Die Fixture ist eine reine, deklarative Strukturmetadaten-Quelle (Feldmengen,
 * Domain-/Kataloglisten und Vokabulare). Sie ist keine produktive Authority und
 * enthält keinerlei Validierungslogik; die Validierungslogik bleibt je Sprache
 * unabhängig implementiert.
 */

export interface GovernanceContract {
  readonly manifestFields: readonly string[];
  readonly routingFields: readonly string[];
  readonly ssotManifestFields: readonly string[];
  readonly vocabularyFields: readonly string[];
  readonly moduleFields: readonly string[];
  readonly roleFields: readonly string[];
  readonly toolFields: readonly string[];
  readonly commandFields: readonly string[];
  readonly commandCapabilities: readonly string[];
  readonly commandEffects: readonly string[];
  readonly templateFields: readonly string[];
  readonly templateCategories: readonly string[];
  readonly templateFormats: readonly string[];
  readonly discoveryTopLevelFields: readonly string[];
  readonly discoveryLimitFields: readonly string[];
  readonly discoveryConfidenceFields: readonly string[];
  readonly discoveryCandidateFields: readonly string[];
  readonly discoveryFamilyFields: readonly string[];
  readonly discoverySignalFields: readonly string[];
  readonly workItemClassificationsTopLevelFields: readonly string[];
  readonly workItemDimensionFields: readonly string[];
  readonly workItemClassificationFields: readonly string[];
  readonly workItemProjectionsTopLevelFields: readonly string[];
  readonly workItemProjectionFields: readonly string[];
  readonly workItemTitleMarkerFields: readonly string[];
  readonly ssotDomains: readonly string[];
  readonly ssotDomainCatalogs: Readonly<{
    routing: readonly string[];
    commands: readonly string[];
    discovery: readonly string[];
    work_items: readonly string[];
  }>;
  readonly discoveryEvidenceFamilies: readonly string[];
  readonly discoverySourceKinds: readonly string[];
  readonly discoveryStrengths: readonly string[];
  readonly discoveryCandidateClasses: Readonly<Record<string, string>>;
  readonly workItemCardinalities: typeof CARDINALITIES;
}

const CARDINALITIES = ["one", "many", "at_most_one", "zero_or_more"] as const;

const FIELD_KEYS = [
  "manifest",
  "routing",
  "ssot_manifest",
  "vocabulary",
  "module",
  "role",
  "tool",
  "command",
  "template",
  "discovery_top_level",
  "discovery_limits",
  "discovery_confidence",
  "discovery_candidate",
  "discovery_family",
  "discovery_signal",
  "work_item_classifications_top_level",
  "work_item_dimension",
  "work_item_classification",
  "work_item_projections_top_level",
  "work_item_projection",
  "work_item_title_marker",
] as const;

const SSOT_DOMAIN_KEYS = ["routing", "commands", "discovery", "work_items"] as const;

const VOCABULARY_ARRAY_KEYS = [
  "template_categories",
  "template_formats",
  "command_capabilities",
  "command_effects",
  "discovery_evidence_families",
  "discovery_source_kinds",
  "discovery_strengths",
  "work_item_cardinalities",
] as const;

function fail(message: string): never {
  throw new Error(`governance contract fixture is invalid: ${message}`);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function exactKeys(value: Record<string, unknown>, expected: readonly string[], label: string): void {
  const actual = Object.keys(value).sort().join("\0");
  const wanted = [...expected].sort().join("\0");
  if (actual !== wanted) fail(`${label} has missing or unknown fields`);
}

function stringArray(value: unknown, label: string): readonly string[] {
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string" || item.length === 0)) {
    fail(`${label} must be a nonempty string array`);
  }
  const entries = value as string[];
  if (new Set(entries).size !== entries.length) fail(`${label} contains duplicate values`);
  return Object.freeze([...entries]);
}

function stringMap(value: unknown, label: string): Readonly<Record<string, string>> {
  if (!isRecord(value) || Object.keys(value).length === 0) fail(`${label} must be a nonempty string map`);
  const result: Record<string, string> = {};
  for (const [key, item] of Object.entries(value)) {
    if (typeof item !== "string" || item.length === 0) fail(`${label}.${key} must be a nonempty string`);
    result[key] = item;
  }
  return Object.freeze(result);
}

function loadGovernanceContract(): GovernanceContract {
  const path = join(PACKAGE_RELEASE_ROOT, "contracts", "governance-contract.json");
  let raw: unknown;
  try {
    raw = JSON.parse(readFileSync(path, "utf8"));
  } catch (cause) {
    fail(`missing or unparseable at ${path}`);
    throw cause;
  }
  if (!isRecord(raw)) fail("must be a JSON object");
  exactKeys(raw, ["schema_version", "fields", "domains", "vocabularies"], "fixture top level");
  if (raw.schema_version !== 1) fail("schema_version must be 1");

  const fields = raw.fields;
  if (!isRecord(fields)) fail("fields must be a table");
  exactKeys(fields, FIELD_KEYS, "fields");
  const field = (key: (typeof FIELD_KEYS)[number]) => stringArray(fields[key], `fields.${key}`);

  const domains = raw.domains;
  if (!isRecord(domains)) fail("domains must be a table");
  exactKeys(domains, ["ssot", "ssot_catalogs"], "domains");
  const ssotDomains = stringArray(domains.ssot, "domains.ssot");
  if (ssotDomains.join("\0") !== [...SSOT_DOMAIN_KEYS].join("\0")) fail("domains.ssot must declare the canonical SSOT domains");
  const ssotCatalogs = domains.ssot_catalogs;
  if (!isRecord(ssotCatalogs)) fail("domains.ssot_catalogs must be a table");
  exactKeys(ssotCatalogs, SSOT_DOMAIN_KEYS, "domains.ssot_catalogs");
  const ssotDomainCatalogs = Object.freeze({
    routing: stringArray(ssotCatalogs.routing, "domains.ssot_catalogs.routing"),
    commands: stringArray(ssotCatalogs.commands, "domains.ssot_catalogs.commands"),
    discovery: stringArray(ssotCatalogs.discovery, "domains.ssot_catalogs.discovery"),
    work_items: stringArray(ssotCatalogs.work_items, "domains.ssot_catalogs.work_items"),
  });

  const vocabularies = raw.vocabularies;
  if (!isRecord(vocabularies)) fail("vocabularies must be a table");
  exactKeys(vocabularies, [...VOCABULARY_ARRAY_KEYS, "discovery_candidate_classes"], "vocabularies");
  const vocabulary = (key: (typeof VOCABULARY_ARRAY_KEYS)[number]) =>
    stringArray(vocabularies[key], `vocabularies.${key}`);
  const discoveryCandidateClasses = stringMap(
    vocabularies.discovery_candidate_classes,
    "vocabularies.discovery_candidate_classes",
  );
  const workItemCardinalities = vocabulary("work_item_cardinalities");
  if (workItemCardinalities.join("\0") !== [...CARDINALITIES].join("\0")) {
    fail("vocabularies.work_item_cardinalities must be the canonical cardinality set");
  }

  return Object.freeze({
    manifestFields: field("manifest"),
    routingFields: field("routing"),
    ssotManifestFields: field("ssot_manifest"),
    vocabularyFields: field("vocabulary"),
    moduleFields: field("module"),
    roleFields: field("role"),
    toolFields: field("tool"),
    commandFields: field("command"),
    commandCapabilities: vocabulary("command_capabilities"),
    commandEffects: vocabulary("command_effects"),
    templateFields: field("template"),
    templateCategories: vocabulary("template_categories"),
    templateFormats: vocabulary("template_formats"),
    discoveryTopLevelFields: field("discovery_top_level"),
    discoveryLimitFields: field("discovery_limits"),
    discoveryConfidenceFields: field("discovery_confidence"),
    discoveryCandidateFields: field("discovery_candidate"),
    discoveryFamilyFields: field("discovery_family"),
    discoverySignalFields: field("discovery_signal"),
    workItemClassificationsTopLevelFields: field("work_item_classifications_top_level"),
    workItemDimensionFields: field("work_item_dimension"),
    workItemClassificationFields: field("work_item_classification"),
    workItemProjectionsTopLevelFields: field("work_item_projections_top_level"),
    workItemProjectionFields: field("work_item_projection"),
    workItemTitleMarkerFields: field("work_item_title_marker"),
    ssotDomains,
    ssotDomainCatalogs,
    discoveryEvidenceFamilies: vocabulary("discovery_evidence_families"),
    discoverySourceKinds: vocabulary("discovery_source_kinds"),
    discoveryStrengths: vocabulary("discovery_strengths"),
    discoveryCandidateClasses,
    workItemCardinalities: CARDINALITIES,
  });
}

export const governanceContract: Readonly<GovernanceContract> = loadGovernanceContract();
