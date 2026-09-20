import { decode, encode } from "@toon-format/toon";

/**
 * Granulare Evidence-Bindung innerhalb einer Resume-Projektion. `bindings` hält die
 * Fingerprints der Identitäten, an die das Ergebnis fachlich gebunden ist.
 */
export interface ResumeEvidenceBinding {
  readonly id: string;
  readonly bindings: readonly string[];
  readonly status: "REUSE" | "INVALIDATE" | "RERUN";
}

/**
 * Kanonische, strikt schemagebundene Projektion des bestätigten Resume-Zustands.
 * Dies ist die einzige fachlich autorisierte Form einer `.toon`-Projektion; sie besitzt
 * keine eigenen semantischen Felder außerhalb dieses Vertrags.
 */
export interface ResumeProjection {
  readonly taskId: string;
  readonly objective: string;
  readonly scope: readonly string[];
  readonly exactHead: string;
  readonly checkpointFingerprint: string;
  readonly evidence: readonly ResumeEvidenceBinding[];
  readonly incompleteEvidence: readonly string[];
  readonly openFindings: readonly string[];
  readonly nextAtomicAction: string;
}

export interface DecodeResumeOptions {
  readonly expectedCheckpoint?: string;
}

const TOP_LEVEL_FIELDS = new Set([
  "taskId",
  "objective",
  "scope",
  "exactHead",
  "checkpointFingerprint",
  "evidence",
  "incompleteEvidence",
  "openFindings",
  "nextAtomicAction",
] as const);

const EVIDENCE_FIELDS = new Set(["id", "bindings", "status"] as const);
const EVIDENCE_STATUSES = new Set<string>(["REUSE", "INVALIDATE", "RERUN"]);

const SECRET_FIELD_RE =
  /(secret|password|passwd|token|credential|private|rawchat|transcript|apikey|api_key)/i;

/** Fehlerklasse für die Domänenvalidierung einer Resume-Projektion. */
export class ResumeProjectionError extends Error {
  readonly reason: string;
  constructor(reason: string) {
    super(`invalid resume projection: ${reason}`);
    this.name = "ResumeProjectionError";
    this.reason = reason;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function reject(reason: string): never {
  throw new ResumeProjectionError(reason);
}

function requireString(value: unknown, field: string): string {
  if (typeof value !== "string" || value.trim() === "") {
    reject(`${field} must be a non-empty string`);
  }
  return value as string;
}

function requireStringArray(value: unknown, field: string): string[] {
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string")) {
    reject(`${field} must be an array of strings`);
  }
  return value as string[];
}

function validateFieldNames(keys: readonly string[], allowed: ReadonlySet<string>, context: string): void {
  for (const key of keys) {
    if (SECRET_FIELD_RE.test(key)) {
      reject(`${context} contains a secret or private field: ${key}`);
    }
    if (!allowed.has(key)) {
      reject(`${context} contains an unknown field: ${key}`);
    }
  }
}

/**
 * Validiert einen beliebigen dekodierten Wert fail-closed gegen das Domänenschema und
 * gibt die typisierte Resume-Projektion zurück. Unbekannte, geheime oder falsch typisierte
 * Felder führen zu einem kontrollierten Abbruch; es wird keine partielle Projektion gebildet.
 */
export function validateResumeProjection(value: unknown): ResumeProjection {
  if (!isRecord(value)) {
    reject("projection must be an object");
  }
  const keys = Object.keys(value);
  validateFieldNames(keys, TOP_LEVEL_FIELDS, "projection");

  const taskId = requireString(value["taskId"], "taskId");
  const objective = requireString(value["objective"], "objective");
  const scope = requireStringArray(value["scope"], "scope");
  const exactHead = requireString(value["exactHead"], "exactHead");
  const checkpointFingerprint = requireString(value["checkpointFingerprint"], "checkpointFingerprint");
  const nextAtomicAction = requireString(value["nextAtomicAction"], "nextAtomicAction");
  const incompleteEvidence = requireStringArray(value["incompleteEvidence"], "incompleteEvidence");
  const openFindings = requireStringArray(value["openFindings"], "openFindings");

  if (typeof value["evidence"] === "undefined") {
    reject("projection requires evidence");
  }
  const rawEvidence = value["evidence"];
  if (!Array.isArray(rawEvidence)) {
    reject("evidence must be an array");
  }
  const evidence: ResumeEvidenceBinding[] = rawEvidence.map((entry, index) => {
    if (!isRecord(entry)) {
      reject(`evidence[${index}] must be an object`);
    }
    validateFieldNames(Object.keys(entry), EVIDENCE_FIELDS, `evidence[${index}]`);
    const id = requireString(entry["id"], `evidence[${index}].id`);
    const bindings = requireStringArray(entry["bindings"], `evidence[${index}].bindings`);
    const rawStatus = entry["status"];
    if (typeof rawStatus !== "string" || !EVIDENCE_STATUSES.has(rawStatus)) {
      reject(`evidence[${index}].status must be REUSE, INVALIDATE or RERUN`);
    }
    const status = rawStatus as ResumeEvidenceBinding["status"];
    return { id, bindings, status };
  });

  return {
    taskId,
    objective,
    scope,
    exactHead,
    checkpointFingerprint,
    evidence,
    incompleteEvidence,
    openFindings,
    nextAtomicAction,
  };
}

/**
 * Erzeugt aus einem bestätigten Resume-Zustand deterministisch eine `.toon`-Projektion.
 * Der Zustand wird vor der Kodierung validiert, sodass keine ungültige Projektion entstehen kann.
 */
export function encodeResumeProjection(state: ResumeProjection): string {
  validateResumeProjection(state);
  return encode(state);
}

/**
 * Dekodiert eine `.toon`-Projektion und validiert sie strikt fail-closed. Bei beschädigter
 * Syntax, unbekannten oder geheimen Feldern, falscher Struktur oder einer von `expectedCheckpoint`
 * abweichenden Checkpoint-Bindung wird ein Fehler geworfen.
 */
export function decodeResumeProjection(input: string, options?: DecodeResumeOptions): ResumeProjection {
  const decoded = decode(input);
  const projection = validateResumeProjection(decoded);
  if (options?.expectedCheckpoint !== undefined) {
    if (projection.checkpointFingerprint !== options.expectedCheckpoint) {
      reject("checkpoint binding does not match the expected checkpoint");
    }
  }
  return projection;
}
