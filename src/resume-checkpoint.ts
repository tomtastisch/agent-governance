import { constants } from "node:fs";
import { lstat, open, readdir, realpath } from "node:fs/promises";
import { isAbsolute, join, resolve } from "node:path";
import { randomUUID } from "node:crypto";
import { assertIdentity, captureIdentity, type PathIdentity } from "./filesystem.ts";
import { secureCreateNoReplace, secureRenameNoReplace } from "./native-filesystem.ts";
import { sameFileSnapshot } from "./installer/snapshot.ts";
import { decodeResumeProjection, encodeResumeProjection, type ResumeProjection } from "./resume-toon.ts";
import { createCheckpoint, effectBinding, MAX_CHECKPOINT_BYTES, record, reject, text, trigger, validateCheckpoint, validateState, validateTransition, type CheckpointIdentity, type ExternalEffect, type ResumeCheckpoint, type ResumeState } from "./resume-checkpoint-schema.ts";
export { MATERIALIZATION_TRIGGERS } from "./resume-checkpoint-schema.ts";
export type { CheckpointIdentity, ResumeCheckpoint, ResumeState, ExternalEffect, MaterializationTrigger } from "./resume-checkpoint-schema.ts";

export interface MaterializationRequest {
  readonly eventId: string;
  readonly trigger: string;
  readonly expected: CheckpointIdentity | null;
  readonly state: ResumeState;
}
/** Diagnostic boundary callback; never a harness hook or an authorization provider. */
export type PersistencePoint = "beforeStage" | "afterStage" | "beforePublish" | "afterPublish" | "afterSync";
export type PersistenceObserver = (point: PersistencePoint) => void | Promise<void>;
export interface EffectReadback {
  readonly operationId: string;
  readonly target: string;
  readonly action: string;
  readonly inputBindings: readonly string[];
  /** NOT_APPLIED must prove both absence of the effect and absence of an active execution. */
  readonly outcome: "APPLIED" | "NOT_APPLIED" | "UNKNOWN";
  readonly reference: string | null;
}
export type ReadEffect = (operation: ExternalEffect) => Promise<EffectReadback>;

function matches(actual: CheckpointIdentity | null, expected: CheckpointIdentity | null): boolean {
  return actual === null ? expected === null : expected !== null && actual.generation === expected.generation && actual.fingerprint === expected.fingerprint;
}

function snapshotIdentity(expected: CheckpointIdentity): CheckpointIdentity {
  return { generation: expected.generation, fingerprint: expected.fingerprint };
}

/** Append-only checkpoint projections. Canonical authorities and RES-003..015 still own revalidation. */
export class ResumeCheckpointStore {
  private readonly directory: string;
  private readonly identity: PathIdentity;
  private constructor(directory: string, identity: PathIdentity) { this.directory = directory; this.identity = identity; }

  /** The caller explicitly creates a private directory; no inferred paths or network access. */
  static async open(directory: string): Promise<ResumeCheckpointStore> {
    if (!isAbsolute(directory) || resolve(directory) !== directory || await realpath(directory) !== directory) reject("non-canonical directory");
    const stat = await lstat(directory);
    if (!stat.isDirectory() || stat.isSymbolicLink() || (stat.mode & 0o777) !== 0o700 || stat.uid !== process.getuid?.()) reject("private directory required");
    return new ResumeCheckpointStore(directory, await captureIdentity(directory));
  }

  private async bound(): Promise<void> {
    await assertIdentity(this.directory, this.identity);
    if (await realpath(this.directory) !== this.directory) reject("directory changed");
  }

  private async sync(): Promise<void> {
    await this.bound();
    const handle = await open(this.directory, constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW);
    try {
      const stat = await handle.stat({ bigint: true });
      if (stat.dev !== this.identity.device || stat.ino !== this.identity.inode) reject("directory changed");
      await handle.sync();
    } finally { await handle.close(); }
    await this.bound();
  }

  private async readFile(name: string): Promise<ResumeCheckpoint> {
    const handle = await open(join(this.directory, name), constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
    try {
      const before = await handle.stat({ bigint: true });
      if (!before.isFile() || before.nlink !== 1n || (Number(before.mode) & 0o777) !== 0o600 || Number(before.uid) !== process.getuid?.() || before.size > BigInt(MAX_CHECKPOINT_BYTES)) reject("unsafe checkpoint file");
      const bytes = Buffer.alloc(Number(before.size) + 1);
      let length = 0;
      while (length < bytes.length) {
        const result = await handle.read(bytes, length, bytes.length - length, length);
        if (result.bytesRead === 0) break;
        length += result.bytesRead;
      }
      const after = await handle.stat({ bigint: true });
      if (!sameFileSnapshot(before, after) || before.mode !== after.mode || after.nlink !== 1n || length !== Number(before.size)) reject("checkpoint changed while reading");
      const content = new TextDecoder("utf-8", { fatal: true }).decode(bytes.subarray(0, length));
      const cp = validateCheckpoint(JSON.parse(content));
      if (content !== `${JSON.stringify(cp)}\n`) reject("noncanonical checkpoint encoding");
      return cp;
    } finally { await handle.close(); }
  }

  private async history(): Promise<ResumeCheckpoint[]> {
    await this.bound();
    const names = (await readdir(this.directory)).filter(name => !/^\.stage-[0-9a-f-]{36}$/.test(name));
    if (names.some(name => !/^[1-9][0-9]*\.json$/.test(name))) reject("unknown checkpoint directory entry");
    names.sort((a, b) => Number(a.slice(0, -5)) - Number(b.slice(0, -5)));
    if (names.some((name, i) => name !== `${i + 1}.json`)) reject("generation gap");
    const history: ResumeCheckpoint[] = [];
    const events = new Set<string>();
    for (const [index, name] of names.entries()) {
      const cp = await this.readFile(name);
      if (cp.generation !== index + 1 || cp.previousCheckpoint !== (history.at(-1)?.fingerprint ?? null) || events.has(cp.eventId)) reject("generation chain or event mismatch");
      validateTransition(history.at(-1) ?? null, cp);
      history.push(cp); events.add(cp.eventId);
    }
    await this.bound();
    return history;
  }

  /** Structural/integrity resolution only. Freshness and authority revalidation remain mandatory. */
  async read(expected?: CheckpointIdentity): Promise<ResumeCheckpoint | null> {
    const identity = expected === undefined ? undefined : snapshotIdentity(expected);
    const current = (await this.history()).at(-1) ?? null;
    if (identity !== undefined && !matches(current, identity)) reject("stale checkpoint identity");
    return current;
  }

  private async confirm(expected: CheckpointIdentity): Promise<ResumeCheckpoint> {
    await this.sync();
    const confirmed = await this.read(expected);
    if (confirmed === null) reject("checkpoint missing");
    return confirmed;
  }

  async materialize(request: MaterializationRequest, observer?: PersistenceObserver): Promise<ResumeCheckpoint | null> {
    return this.publish(request, false, observer);
  }

  private async publish(request: MaterializationRequest, effectReadback: boolean, observer?: PersistenceObserver): Promise<ResumeCheckpoint | null> {
    if (request.trigger === "message") return this.read();
    const event = trigger(request.trigger);
    const eventId = text(request.eventId);
    const state = validateState(request.state);
    const expected = request.expected === null ? null : snapshotIdentity(request.expected);
    const history = await this.history();
    const current = history.at(-1) ?? null;
    const repeated = history.find(cp => cp.eventId === eventId);
    if (repeated !== undefined) {
      const previous = history.at(-2) ?? null;
      if (repeated === current && matches(previous, expected) && repeated.trigger === event && JSON.stringify(repeated.state) === JSON.stringify(state)) return this.confirm(repeated);
      reject("stale or conflicting event");
    }
    if (!matches(current, expected)) reject("stale writer generation");
    if (current !== null && JSON.stringify(current.state) === JSON.stringify(state)) return this.confirm(current);
    const cp = createCheckpoint((current?.generation ?? 0) + 1, current?.fingerprint ?? null, eventId, event, state);
    validateTransition(current, cp);
    if (!effectReadback && cp.state.externalEffects.some(effect => ["COMMITTED", "NOT_APPLIED"].includes(effect.state) && JSON.stringify(effect) !== JSON.stringify(current?.state.externalEffects.find(old => old.operationId === effect.operationId)))) reject("effect requires source-of-truth readback");
    await observer?.("beforeStage"); await this.bound();
    const name = `.stage-${randomUUID()}`;
    await secureCreateNoReplace({ directory: this.directory, name, directoryIdentity: this.identity }, Buffer.from(`${JSON.stringify(cp)}\n`));
    await observer?.("afterStage");
    if ((await this.readFile(name)).fingerprint !== cp.fingerprint) reject("staging readback");
    await observer?.("beforePublish"); await this.bound();
    await secureRenameNoReplace({ sourceDirectory: this.directory, sourceName: name, sourceDirectoryIdentity: this.identity, destinationDirectory: this.directory, destinationName: `${cp.generation}.json`, destinationDirectoryIdentity: this.identity });
    await observer?.("afterPublish");
    await this.sync(); await observer?.("afterSync");
    const confirmed = await this.read(cp);
    return confirmed;
  }

  /** Optional lifecycle adapter surface; event-driven materialization remains primary. */
  async flush(): Promise<ResumeCheckpoint | null> { await this.sync(); return this.read(); }

  /** Resolve persisted bytes -> validate full checkpoint -> derive the existing projection -> encode. */
  async toToon(expected: CheckpointIdentity): Promise<string> {
    const cp = await this.read(expected);
    if (cp === null) reject("checkpoint missing");
    return encodeResumeProjection({ ...cp.state.projection, checkpointFingerprint: cp.fingerprint });
  }

  async validateToon(input: string, expected: CheckpointIdentity): Promise<ResumeProjection> {
    const projection = decodeResumeProjection(input, { expectedCheckpoint: expected.fingerprint });
    if (encodeResumeProjection(projection) !== await this.toToon(expected)) reject("projection content differs from checkpoint");
    return projection;
  }

  /** Resolve one needed artifact at its authority; never infer validity from its mere existence. */
  async evidenceReference(expected: CheckpointIdentity, id: string, exists: (reference: string) => Promise<boolean>): Promise<string> {
    const identity = snapshotIdentity(expected);
    const cp = await this.read(identity);
    const ref = cp?.state.evidenceReferences.find(item => item.id === id);
    if (ref === undefined || await exists(ref.reference) !== true) reject("missing evidence artifact");
    await this.read(identity);
    return ref.reference;
  }

  private async operation(expected: CheckpointIdentity, operationId: string): Promise<{ cp: ResumeCheckpoint; effect: ExternalEffect }> {
    const cp = await this.read(expected);
    if (cp === null) reject("checkpoint missing");
    const effect = cp.state.externalEffects.find(item => item.operationId === operationId);
    if (effect === undefined) reject("effect was not prepared");
    return { cp, effect };
  }

  /** The callback is already authorized by the caller; this guard cannot grant permission. */
  async executeEffect(expected: CheckpointIdentity, operationId: string, execute: () => Promise<void>, readback: ReadEffect): Promise<ResumeCheckpoint> {
    const { cp, effect } = await this.operation(expected, operationId);
    if (effect.state === "COMMITTED") return this.confirm(cp);
    if (effect.state !== "PREPARED") reject("effect requires readback and explicit preparation before execution");
    // A unique event claims the operation. Reusing an idempotent event here could dispatch twice.
    const claimed = (await this.publish({ eventId: `dispatch-${randomUUID()}`, trigger: "effect_executed", expected: cp, state: { ...cp.state, externalEffects: cp.state.externalEffects.map(item => item.operationId === operationId ? { ...item, state: "UNKNOWN" } : item) } }, false))!;
    await execute();
    return this.recoverEffect(claimed, operationId, readback);
  }

  /** Read-only authority query. Inconclusive/active executions remain UNKNOWN; no effect callback. */
  async recoverEffect(expected: CheckpointIdentity, operationId: string, readback: ReadEffect): Promise<ResumeCheckpoint> {
    const { cp, effect } = await this.operation(expected, operationId);
    if (effect.state === "COMMITTED" || effect.state === "NOT_APPLIED") return this.confirm(cp);
    const raw = await readback(structuredClone(effect));
    const value = record(raw, ["operationId", "target", "action", "inputBindings", "outcome", "reference"]);
    if (effectBinding(raw as unknown as ExternalEffect) !== effectBinding(effect)) reject("readback operation binding mismatch");
    if (!["APPLIED", "NOT_APPLIED", "UNKNOWN"].includes(value.outcome as string)) reject("readback outcome");
    const status: ExternalEffect["state"] = value.outcome === "APPLIED" ? "COMMITTED" : value.outcome === "NOT_APPLIED" ? "NOT_APPLIED" : "UNKNOWN";
    const reference = status === "UNKNOWN" ? null : text(value.reference);
    if (status === "UNKNOWN" && value.reference !== null) reject("unknown readback must not claim evidence");
    return (await this.publish({ eventId: `readback-${randomUUID()}`, trigger: "effect_readback", expected: cp, state: { ...cp.state, externalEffects: cp.state.externalEffects.map(item => item.operationId === operationId ? { ...item, state: status, readbackReference: reference } : item) } }, true))!;
  }
}
