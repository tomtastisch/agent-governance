import { createHash } from "node:crypto";
import { validateResumeProjection, type ResumeProjection } from "./resume-toon.ts";

export const MATERIALIZATION_TRIGGERS = [
  "task_identified", "scope_changed", "active_task_changed", "task_started", "task_completed",
  "task_failed", "task_incomplete", "decision_confirmed", "evidence_started", "evidence_completed",
  "evidence_invalidated", "finding_opened", "finding_closed", "exact_state_changed",
  "next_action_changed", "handoff", "effect_prepared", "effect_executed", "effect_readback",
  "compaction_announced", "session_ended",
] as const;
export type MaterializationTrigger = typeof MATERIALIZATION_TRIGGERS[number];
export interface CheckpointIdentity { readonly generation: number; readonly fingerprint: string; }
export interface ExternalEffect {
  readonly operationId: string;
  readonly target: string;
  readonly action: string;
  readonly inputBindings: readonly string[];
  readonly state: "PREPARED" | "UNKNOWN" | "COMMITTED" | "NOT_APPLIED";
  readonly readbackReference: string | null;
}
export interface ResumeState {
  readonly projection: Omit<ResumeProjection, "checkpointFingerprint">;
  readonly identities: Readonly<Record<"scope" | "repository" | "worktree" | "branch" | "dirty" | "dependencies" | "configuration" | "governance" | "environment", string>>;
  readonly authorities: readonly string[];
  readonly activeTask: string;
  readonly taskStatus: "RUNNING" | "COMPLETED" | "FAILED" | "INCOMPLETE";
  readonly decisions: readonly string[];
  readonly evidenceReferences: readonly { readonly id: string; readonly reference: string }[];
  readonly workItem: string | null;
  readonly externalEffects: readonly ExternalEffect[];
}
export interface ResumeCheckpoint extends CheckpointIdentity {
  readonly schemaVersion: 1;
  readonly previousCheckpoint: string | null;
  readonly eventId: string;
  readonly trigger: MaterializationTrigger;
  readonly state: ResumeState;
}
export const MAX_CHECKPOINT_BYTES = 256 * 1024;

export function reject(message: string): never { throw new Error(`invalid resume checkpoint: ${message}`); }
export function record(value: unknown, keys: readonly string[]): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value) || Object.keys(value).sort().join("\0") !== [...keys].sort().join("\0")) reject("closed schema mismatch");
  return value as Record<string, unknown>;
}
// This rejects common credential encodings, not arbitrary secrets disguised as metadata.
// Callers must select non-sensitive references; no raw input or log field exists.
const SENSITIVE = /(?:\b(?:password|passwd|secret|token|credential|api[_-]?key)\s*[:=]|\bBearer\s|-----BEGIN .*PRIVATE KEY|\b(?:gh[pousr]_|github_pat_|sk-live-|AKIA)[a-zA-Z0-9]|:\/\/[^/\s]*@|[?&](?:token|key|secret)=)/i;
export function text(value: unknown): string {
  if (typeof value !== "string" || !value.trim() || value.length > 8192 || /[\x00-\x1f\x7f]/.test(value) || SENSITIVE.test(value)) reject("unsafe metadata string");
  return value;
}
function array(value: unknown): unknown[] { if (!Array.isArray(value) || value.length > 1024) reject("bounded array required"); return value; }
function strings(value: unknown): string[] { return array(value).map(text); }
function unique(values: readonly string[]): void { if (new Set(values).size !== values.length) reject("duplicate identity"); }
export function trigger(value: unknown): MaterializationTrigger {
  if (!(MATERIALIZATION_TRIGGERS as readonly unknown[]).includes(value)) reject("unknown trigger");
  return value as MaterializationTrigger;
}
export function validateState(value: unknown): ResumeState {
  const v = record(value, ["projection", "identities", "authorities", "activeTask", "taskStatus", "decisions", "evidenceReferences", "workItem", "externalEffects"]);
  const p = record(v.projection, ["taskId", "objective", "scope", "exactHead", "evidence", "incompleteEvidence", "openFindings", "nextAtomicAction"]);
  const validated = validateResumeProjection({ ...p, checkpointFingerprint: "derived" });
  const { checkpointFingerprint: _, ...projection } = validated;
  // Bound and screen every leaf, including metadata accepted by the existing codec.
  function safeLeaves(input: unknown): void {
    if (typeof input === "string") { text(input); return; }
    if (Array.isArray(input)) { array(input).forEach(safeLeaves); return; }
    if (typeof input === "object" && input !== null) Object.values(input).forEach(safeLeaves);
  }
  safeLeaves(projection);
  if (projection.scope.length === 0) reject("scope is empty");
  const ids = record(v.identities, ["scope", "repository", "worktree", "branch", "dirty", "dependencies", "configuration", "governance", "environment"]);
  const identities = Object.fromEntries(Object.entries(ids).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0).map(([key, value]) => [key, text(value)])) as ResumeState["identities"];
  const authorities = strings(v.authorities); if (!authorities.length) reject("authorities are missing");
  const taskStatus = v.taskStatus;
  if (!["RUNNING", "COMPLETED", "FAILED", "INCOMPLETE"].includes(taskStatus as string)) reject("task status");
  const evidenceReferences = array(v.evidenceReferences).map(item => { const ref = record(item, ["id", "reference"]); return { id: text(ref.id), reference: text(ref.reference) }; });
  unique(evidenceReferences.map(ref => ref.id));
  unique(projection.evidence.map(item => item.id));
  unique(projection.incompleteEvidence);
  if (projection.evidence.some(item => item.status === "REUSE" && projection.incompleteEvidence.includes(item.id))) reject("incomplete evidence cannot be reused");
  const evidenceIds = [...projection.evidence.map(item => item.id), ...projection.incompleteEvidence];
  if (evidenceIds.some(id => !evidenceReferences.some(ref => ref.id === id))) reject("missing evidence reference");
  const externalEffects = array(v.externalEffects).map(item => {
    const e = record(item, ["operationId", "target", "action", "inputBindings", "state", "readbackReference"]);
    if (!["PREPARED", "UNKNOWN", "COMMITTED", "NOT_APPLIED"].includes(e.state as string)) reject("effect state");
    const confirmed = e.state === "COMMITTED" || e.state === "NOT_APPLIED";
    if (confirmed ? e.readbackReference === null : e.readbackReference !== null) reject("effect readback binding");
    const inputBindings = strings(e.inputBindings); if (!inputBindings.length) reject("effect inputs are unbound");
    return { operationId: text(e.operationId), target: text(e.target), action: text(e.action), inputBindings, state: e.state as ExternalEffect["state"], readbackReference: e.readbackReference === null ? null : text(e.readbackReference) };
  });
  unique(externalEffects.map(e => e.operationId));
  const result: ResumeState = { projection, identities, authorities, activeTask: text(v.activeTask), taskStatus: taskStatus as ResumeState["taskStatus"], decisions: strings(v.decisions), evidenceReferences, workItem: v.workItem === null ? null : text(v.workItem), externalEffects };
  if (Buffer.byteLength(JSON.stringify(result)) > MAX_CHECKPOINT_BYTES - 4096) reject("payload size limit");
  return structuredClone(result);
}
export function fingerprint(value: unknown): string { return createHash("sha256").update(JSON.stringify(value)).digest("hex"); }
export function createCheckpoint(generation: number, previousCheckpoint: string | null, eventId: string, event: MaterializationTrigger, state: ResumeState): ResumeCheckpoint {
  const body = { schemaVersion: 1 as const, generation, previousCheckpoint, eventId: text(eventId), trigger: trigger(event), state: validateState(state) };
  return { ...body, fingerprint: fingerprint(body) };
}
export function validateCheckpoint(input: unknown): ResumeCheckpoint {
  const v = record(input, ["schemaVersion", "generation", "previousCheckpoint", "eventId", "trigger", "state", "fingerprint"]);
  if (v.schemaVersion !== 1) reject("unsupported schema version");
  if (!Number.isSafeInteger(v.generation) || (v.generation as number) < 1) reject("generation");
  if (v.previousCheckpoint !== null && (typeof v.previousCheckpoint !== "string" || !/^[a-f0-9]{64}$/.test(v.previousCheckpoint))) reject("previous checkpoint");
  const cp = createCheckpoint(v.generation as number, v.previousCheckpoint as string | null, text(v.eventId), trigger(v.trigger), validateState(v.state));
  if (v.fingerprint !== cp.fingerprint) reject("corrupted payload fingerprint");
  return cp;
}

export function effectBinding(effect: ExternalEffect): string {
  return JSON.stringify([effect.operationId, effect.target, effect.action, effect.inputBindings]);
}

/** Validate the materialized history, not a second evidence-validity or approval engine. */
export function validateTransition(previous: ResumeCheckpoint | null, next: ResumeCheckpoint): void {
  if (previous !== null && previous.state.projection.taskId !== next.state.projection.taskId) reject("task identity changed");
  for (const old of previous?.state.externalEffects ?? []) {
    const effect = next.state.externalEffects.find(item => item.operationId === old.operationId);
    if (effect === undefined || effectBinding(old) !== effectBinding(effect)) reject("effect binding removed or changed");
    if (JSON.stringify(old) === JSON.stringify(effect)) continue;
    const allowed = (old.state === "PREPARED" || old.state === "UNKNOWN") && next.trigger === "effect_readback" && ["UNKNOWN", "COMMITTED", "NOT_APPLIED"].includes(effect.state)
      || old.state === "PREPARED" && next.trigger === "effect_executed" && effect.state === "UNKNOWN"
      || old.state === "NOT_APPLIED" && next.trigger === "effect_prepared" && effect.state === "PREPARED";
    if (!allowed) reject("invalid effect transition");
  }
  for (const effect of next.state.externalEffects) {
    if (!previous?.state.externalEffects.some(old => old.operationId === effect.operationId) && (effect.state !== "PREPARED" || next.trigger !== "effect_prepared")) reject("effect requires persistent preparation");
  }
}
