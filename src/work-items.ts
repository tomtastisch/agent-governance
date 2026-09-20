import { readFileSync } from "node:fs";
import { loadSsotIndex } from "./ssot-manifest.ts";
import { exact, parseClosedToml, table, text, type TomlTable } from "./closed-toml.ts";

/**
 * Statische Work-Item-Klassifikation und plattformbezogene Projektionen (Issue #53).
 *
 * Der kanonische Classifier ist ausschließlich `classifications.toml`. GitHub-Labels und
 * Titelmarker sind deterministische Projektionen derselben SSOT und niemals eine zweite
 * fachliche Authority. Tool-/Effect-Tags (`policy_tags`) bleiben eine getrennte Domain.
 * Dieses Modul führt keine GitHub-Mutation aus; es liest nur und erzeugt Pläne.
 */

export const CARDINALITIES = ["one", "many", "at_most_one", "zero_or_more"] as const;
export type Cardinality = (typeof CARDINALITIES)[number];

export interface ClassificationDimension {
  readonly id: string;
  readonly label: string;
  readonly cardinality: Cardinality;
  readonly description: string;
}

export interface ClassificationValue {
  /** Stabile kanonische ID `<dimension>.<value>`, z. B. `type.refactor`. */
  readonly id: string;
  readonly dimension: string;
  readonly value: string;
  readonly label: string;
  readonly description: string;
}

export interface ClassificationIndex {
  readonly schemaVersion: 1;
  readonly dimensions: Readonly<Record<string, ClassificationDimension>>;
  readonly classifications: Readonly<Record<string, ClassificationValue>>;
  readonly valuesByDimension: Readonly<Record<string, Readonly<Record<string, ClassificationValue>>>>;
}

export interface LabelProjection {
  /** Registrierte Projektions-ID, z. B. `semver_patch`. */
  readonly id: string;
  /** Kanonische Classification-ID, z. B. `semver.patch`. */
  readonly classification: string;
  readonly name: string;
  readonly description: string;
  readonly color: string;
  readonly aliases: readonly string[];
}

export interface TitleMarkerProjection {
  readonly id: string;
  readonly classification: string;
  readonly marker: string;
}

export interface ProjectionIndex {
  readonly schemaVersion: 1;
  readonly projections: Readonly<Record<string, LabelProjection>>;
  readonly titleMarkers: Readonly<Record<string, TitleMarkerProjection>>;
}

/** Read-only GitHub-Label-Inventar. `managed: false` kennzeichnet ein ausdrücklich fremdes Label. */
export interface GitHubLabel {
  readonly name: string;
  readonly color: string;
  readonly description: string;
  readonly managed?: boolean;
}

export type PlanAction = "NOOP" | "CREATE" | "UPDATE" | "CONFLICT" | "UNMANAGED" | "CANDIDATE";

export interface ProjectionPlanEntry {
  readonly action: PlanAction;
  /** Kanonische Classification-ID, sofern projektionsbezogen; sonst null. */
  readonly classification: string | null;
  readonly labelName: string;
  readonly reason: string;
}

export interface LabelProjectionPlan {
  readonly entries: readonly ProjectionPlanEntry[];
}

export interface CardinalityViolation {
  readonly dimension: string;
  readonly cardinality: Cardinality;
  readonly values: readonly string[];
}

export interface WorkItemClassification {
  readonly ids: readonly string[];
  readonly violations: readonly CardinalityViolation[];
}

export interface ProjectionDrift {
  readonly dimension: string;
  readonly values: readonly string[];
}

const ID_PATTERN = /^[a-z][a-z0-9_]*$/;
const COLOR_PATTERN = /^[0-9A-Fa-f]{6}$/;
const MARKER_PATTERN = /^\[[A-Z][A-Z0-9_-]*\]$/;

function fail(message: string): never {
  throw new Error(`work-item classification is invalid: ${message}`);
}

function validateDimensionId(id: string): void {
  if (!ID_PATTERN.test(id)) fail(`invalid dimension ID: ${id}`);
}

function validateValueId(value: string): void {
  if (!ID_PATTERN.test(value)) fail(`invalid classification value: ${value}`);
}

function readId(raw: unknown, label: string): string {
  if (typeof raw !== "string" || !ID_PATTERN.test(raw)) fail(`${label} is not a valid ID`);
  return raw;
}

function readClassificationReference(raw: unknown, label: string): string {
  if (typeof raw !== "string" || !/^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$/.test(raw)) {
    fail(`${label} is not a valid classification reference`);
  }
  return raw;
}

function readAliases(raw: unknown, label: string): string[] {
  if (!Array.isArray(raw)) fail(`${label} must be an array`);
  const result: string[] = [];
  for (const item of raw) {
    if (typeof item !== "string" || item.trim() === "" || /[\x00\x1b\r\n]/.test(item)) {
      fail(`${label} contains an invalid alias`);
    }
    result.push(item);
  }
  if (new Set(result).size !== result.length) fail(`${label} contains duplicate aliases`);
  return result;
}

function isCardinality(raw: unknown): raw is Cardinality {
  return typeof raw === "string" && (CARDINALITIES as readonly string[]).includes(raw);
}

export function parseClassificationsText(content: string): ClassificationIndex {
  const root = parseClosedToml(content, "classifications catalog");
  exact(root, ["schema_version", "dimensions", "classifications"], "classifications catalog");
  if (root.schema_version !== 1) fail("classifications schema must be 1");

  const rawDimensions = table(root.dimensions, "classifications dimensions");
  if (Object.keys(rawDimensions).length === 0) fail("classifications dimensions must not be empty");
  const dimensions: Record<string, ClassificationDimension> = {};
  for (const [dimensionId, raw] of Object.entries(rawDimensions)) {
    validateDimensionId(dimensionId);
    const entry = table(raw, `dimensions.${dimensionId}`);
    exact(entry, ["label", "cardinality", "description"], `dimensions.${dimensionId}`);
    const cardinality = entry.cardinality;
    if (!isCardinality(cardinality)) fail(`dimensions.${dimensionId}.cardinality is unknown`);
    dimensions[dimensionId] = Object.freeze({
      id: dimensionId,
      label: text(entry.label, `dimensions.${dimensionId}.label`),
      cardinality,
      description: text(entry.description, `dimensions.${dimensionId}.description`),
    });
  }

  const rawClassifications = table(root.classifications, "classifications values");
  if (Object.keys(rawClassifications).length === 0) fail("classifications values must not be empty");
  const classifications: Record<string, ClassificationValue> = {};
  const valuesByDimension: Record<string, Record<string, ClassificationValue>> = {};
  for (const [dimensionId, rawValues] of Object.entries(rawClassifications)) {
    validateDimensionId(dimensionId);
    if (!Object.hasOwn(dimensions, dimensionId)) fail(`unknown dimension referenced by classifications: ${dimensionId}`);
    const valueTable = table(rawValues, `classifications.${dimensionId}`);
    if (Object.keys(valueTable).length === 0) fail(`classifications.${dimensionId} must not be empty`);
    const bucket: Record<string, ClassificationValue> = {};
    for (const [valueId, raw] of Object.entries(valueTable)) {
      validateValueId(valueId);
      const entry = table(raw, `classifications.${dimensionId}.${valueId}`);
      exact(entry, ["label", "description"], `classifications.${dimensionId}.${valueId}`);
      const id = `${dimensionId}.${valueId}`;
      if (Object.hasOwn(classifications, id)) fail(`duplicate classification ID: ${id}`);
      const value: ClassificationValue = Object.freeze({
        id,
        dimension: dimensionId,
        value: valueId,
        label: text(entry.label, `${id}.label`),
        description: text(entry.description, `${id}.description`),
      });
      classifications[id] = value;
      bucket[valueId] = value;
    }
    valuesByDimension[dimensionId] = Object.freeze(bucket);
  }

  for (const dimensionId of Object.keys(dimensions)) {
    if (!Object.hasOwn(valuesByDimension, dimensionId)) {
      fail(`dimension has no classification values: ${dimensionId}`);
    }
  }

  return Object.freeze({
    schemaVersion: 1,
    dimensions: Object.freeze(dimensions),
    classifications: Object.freeze(classifications),
    valuesByDimension: Object.freeze(valuesByDimension),
  });
}

export function parseProjectionsText(content: string, index: ClassificationIndex): ProjectionIndex {
  const root = parseClosedToml(content, "github labels projection catalog");
  exact(root, ["schema_version", "projections", "title_markers"], "github labels projection catalog");
  if (root.schema_version !== 1) fail("projection schema must be 1");

  const rawProjections = table(root.projections, "label projections");
  if (Object.keys(rawProjections).length === 0) fail("label projections must not be empty");
  const projections: Record<string, LabelProjection> = {};
  const classificationToProjection = new Map<string, string>();
  const occupiedNames = new Set<string>();
  for (const [projectionId, raw] of Object.entries(rawProjections)) {
    readId(projectionId, "projection id");
    const entry = table(raw, `projections.${projectionId}`);
    exact(entry, ["classification", "name", "description", "color", "aliases"], `projections.${projectionId}`);
    const classification = readClassificationReference(entry.classification, `projections.${projectionId}.classification`);
    if (!Object.hasOwn(index.classifications, classification)) fail(`unknown projection classification: ${classification}`);
    if (classificationToProjection.has(classification)) fail(`duplicate projection for classification: ${classification}`);
    classificationToProjection.set(classification, projectionId);
    const name = text(entry.name, `projections.${projectionId}.name`);
    if (occupiedNames.has(name)) fail(`projection collision on label name: ${name}`);
    occupiedNames.add(name);
    const color = text(entry.color, `projections.${projectionId}.color`);
    if (!COLOR_PATTERN.test(color)) fail(`projections.${projectionId}.color is invalid`);
    const aliases = readAliases(entry.aliases, `projections.${projectionId}.aliases`);
    for (const alias of aliases) {
      if (occupiedNames.has(alias)) fail(`projection alias collides with a label name: ${alias}`);
      occupiedNames.add(alias);
    }
    projections[projectionId] = Object.freeze({
      id: projectionId,
      classification,
      name,
      description: text(entry.description, `projections.${projectionId}.description`),
      color,
      aliases: Object.freeze([...aliases]),
    });
  }

  const rawMarkers = table(root.title_markers, "title markers");
  const titleMarkers: Record<string, TitleMarkerProjection> = {};
  const markerToClassification = new Map<string, string>();
  for (const [markerId, raw] of Object.entries(rawMarkers)) {
    readId(markerId, "title marker id");
    const entry = table(raw, `title_markers.${markerId}`);
    exact(entry, ["classification", "marker"], `title_markers.${markerId}`);
    const classification = readClassificationReference(entry.classification, `title_markers.${markerId}.classification`);
    if (!Object.hasOwn(index.classifications, classification)) fail(`unknown title marker classification: ${classification}`);
    const marker = text(entry.marker, `title_markers.${markerId}.marker`);
    if (!MARKER_PATTERN.test(marker)) fail(`title_markers.${markerId}.marker is not a recognizable bracket marker`);
    if (markerToClassification.has(marker)) fail(`title marker collision: ${marker}`);
    markerToClassification.set(marker, classification);
    titleMarkers[markerId] = Object.freeze({ id: markerId, classification, marker });
  }

  return Object.freeze({
    schemaVersion: 1,
    projections: Object.freeze(projections),
    titleMarkers: Object.freeze(titleMarkers),
  });
}

export interface WorkItemSsot {
  readonly classifications: ClassificationIndex;
  readonly projections: ProjectionIndex;
}

export function loadWorkItemSsot(releaseRoot?: string): WorkItemSsot {
  const ssot = loadSsotIndex(releaseRoot);
  const entries = ssot.index.domains.work_items;
  if (entries === undefined) fail("ssot manifest does not register work_items");
  const classificationsPath = entries.classifications;
  const projectionsPath = entries.github_labels;
  if (classificationsPath === undefined || projectionsPath === undefined) fail("work_items domain has missing catalogs");
  const classifications = parseClassificationsText(readFileSync(ssot.catalogFile("work_items", "classifications"), "utf8"));
  const projections = parseProjectionsText(readFileSync(ssot.catalogFile("work_items", "github_labels"), "utf8"), classifications);
  return { classifications, projections };
}

export function resolveClassification(index: ClassificationIndex, id: string): ClassificationValue {
  if (!Object.hasOwn(index.classifications, id)) fail(`unknown classification ID: ${id}`);
  const value = index.classifications[id]!;
  return value;
}

export function validateWorkItemClassification(index: ClassificationIndex, ids: readonly string[]): WorkItemClassification {
  const resolved: string[] = [];
  const perDimension = new Map<string, string[]>();
  for (const id of ids) {
    const value = resolveClassification(index, id);
    resolved.push(value.id);
    const bucket = perDimension.get(value.dimension) ?? [];
    bucket.push(value.id);
    perDimension.set(value.dimension, bucket);
  }
  const violations: CardinalityViolation[] = [];
  for (const [dimensionId, dimension] of Object.entries(index.dimensions)) {
    const values = perDimension.get(dimensionId) ?? [];
    if (values.length > 1 && (dimension.cardinality === "one" || dimension.cardinality === "at_most_one")) {
      violations.push(Object.freeze({ dimension: dimensionId, cardinality: dimension.cardinality, values: Object.freeze([...values]) }));
    }
    if (values.length === 0 && (dimension.cardinality === "one" || dimension.cardinality === "many")) {
      violations.push(Object.freeze({ dimension: dimensionId, cardinality: dimension.cardinality, values: Object.freeze([]) }));
    }
  }
  return { ids: Object.freeze([...resolved]), violations: Object.freeze(violations) };
}

export function buildLabelProjectionPlan(projections: ProjectionIndex, inventory: readonly GitHubLabel[]): LabelProjectionPlan {
  const entries: ProjectionPlanEntry[] = [];
  const byName = new Map<string, GitHubLabel>();
  for (const label of inventory) byName.set(label.name, label);
  const aliasToProjection = new Map<string, LabelProjection>();
  for (const projection of Object.values(projections.projections)) {
    for (const alias of projection.aliases) aliasToProjection.set(alias, projection);
  }
  const consumed = new Set<string>();

  for (const projectionId of Object.keys(projections.projections).sort()) {
    const projection = projections.projections[projectionId]!;
    const existing = byName.get(projection.name);
    if (existing === undefined) {
      entries.push({ action: "CREATE", classification: projection.classification, labelName: projection.name, reason: "managed projection is missing from GitHub" });
      continue;
    }
    consumed.add(existing.name);
    if (existing.managed === false) {
      entries.push({ action: "CONFLICT", classification: projection.classification, labelName: existing.name, reason: "external label collides with a managed projection" });
      continue;
    }
    if (existing.color !== projection.color || existing.description !== projection.description) {
      entries.push({ action: "UPDATE", classification: projection.classification, labelName: existing.name, reason: "managed label drifted in color or description" });
    } else {
      entries.push({ action: "NOOP", classification: projection.classification, labelName: existing.name, reason: "managed label matches the projection" });
    }
  }

  for (const labelName of [...byName.keys()].sort()) {
    if (consumed.has(labelName)) continue;
    const label = byName.get(labelName)!;
    const aliasProjection = aliasToProjection.get(labelName);
    if (aliasProjection !== undefined) {
      entries.push({ action: "CANDIDATE", classification: aliasProjection.classification, labelName, reason: "legacy label is a candidate mapping to a managed projection" });
    } else {
      entries.push({ action: "UNMANAGED", classification: null, labelName, reason: "label has no canonical projection ownership" });
    }
  }

  return { entries: Object.freeze(entries) };
}

export function deriveTitleMarkers(projections: ProjectionIndex, classificationIds: readonly string[]): readonly string[] {
  const markers = new Set<string>();
  for (const marker of Object.values(projections.titleMarkers)) {
    if (classificationIds.includes(marker.classification)) markers.add(marker.marker);
  }
  return Object.freeze([...markers].sort());
}

export function classifyLabels(projections: ProjectionIndex, labels: readonly GitHubLabel[]): readonly string[] {
  const byName = new Map<string, string>();
  for (const projection of Object.values(projections.projections)) {
    byName.set(projection.name, projection.classification);
    for (const alias of projection.aliases) byName.set(alias, projection.classification);
  }
  const ids = new Set<string>();
  for (const label of labels) {
    const classification = byName.get(label.name);
    if (classification !== undefined) ids.add(classification);
  }
  return Object.freeze([...ids].sort());
}

export function classifyTitleMarkers(projections: ProjectionIndex, title: string): readonly string[] {
  const ids = new Set<string>();
  const byMarker = new Map<string, string>();
  for (const marker of Object.values(projections.titleMarkers)) byMarker.set(marker.marker, marker.classification);
  const re = /\[([A-Z][A-Z0-9_-]*)\]/g;
  let match: RegExpExecArray | null;
  while ((match = re.exec(title)) !== null) {
    const classification = byMarker.get(match[0]!);
    if (classification !== undefined) ids.add(classification);
  }
  return Object.freeze([...ids].sort());
}

/**
 * Read-only Diagnoseparser für Legacy-Titelmarker. Erkennt alle `[UPPERCASE]`-Marker eines
 * Titels, bildet sie aber NICHT auf Classification-IDs ab: Titelmarker sind Menschenoberfläche
 * und Projektion, niemals eine fachliche Authority. Diese Funktion dient ausschließlich der
 * Migration und Diagnose bestehender Titel.
 */
export function parseTitleMarkers(title: string): readonly string[] {
  const markers = new Set<string>();
  const re = /\[([A-Z][A-Z0-9_-]*)\]/g;
  let match: RegExpExecArray | null;
  while ((match = re.exec(title)) !== null) markers.add(match[0]!);
  return Object.freeze([...markers].sort());
}

export function detectProjectionDrift(index: ClassificationIndex, a: readonly string[], b: readonly string[]): readonly ProjectionDrift[] {
  const collect = (ids: readonly string[]): Map<string, Set<string>> => {
    const byDimension = new Map<string, Set<string>>();
    for (const id of ids) {
      const value = resolveClassification(index, id);
      const bucket = byDimension.get(value.dimension) ?? new Set<string>();
      bucket.add(value.id);
      byDimension.set(value.dimension, bucket);
    }
    return byDimension;
  };
  const left = collect(a);
  const right = collect(b);
  const drift: ProjectionDrift[] = [];
  for (const dimensionId of Object.keys(index.dimensions).sort()) {
    const l = left.get(dimensionId);
    const r = right.get(dimensionId);
    if (l === undefined || r === undefined) continue;
    const onlyLeft = [...l].filter((value) => !r!.has(value)).sort();
    const onlyRight = [...r].filter((value) => !l!.has(value)).sort();
    if (onlyLeft.length > 0 || onlyRight.length > 0) {
      drift.push(Object.freeze({ dimension: dimensionId, values: Object.freeze([...onlyLeft, ...onlyRight]) }));
    }
  }
  return Object.freeze(drift);
}
