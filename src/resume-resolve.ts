import { captureIdentity } from "./filesystem.ts";
import { ResumeCheckpointStore, type ExternalEffect, type ResumeCheckpoint } from "./resume-checkpoint.ts";

/** Aktuelle Kontext-Bindungen. `repository` ist Pflicht; alle übrigen Felder werden nur verglichen, wenn gesetzt. */
export interface ResolveContext {
  readonly repository: string;
  readonly scope?: string;
  readonly taskId?: string;
  readonly workItem?: string;
  readonly worktree?: string;
  readonly branch?: string;
  readonly dirty?: string;
}

export type ResumeTaskStatus = "RUNNING" | "FAILED" | "INCOMPLETE" | "COMPLETED";

export interface ResumeResolution {
  readonly store: string;
  readonly generation: number;
  readonly fingerprint: string;
  readonly taskId: string;
  readonly objective: string;
  readonly scope: readonly string[];
  readonly exactHead: string;
  readonly taskStatus: ResumeTaskStatus;
  readonly nextAtomicAction: string;
  readonly workItem: string | null;
  readonly externalEffects: readonly ExternalEffect[];
}

export type ResolveOutcome =
  | ({ readonly outcome: "RESUME" } & ResumeResolution)
  | { readonly outcome: "NO_MATCH" }
  | { readonly outcome: "AMBIGUOUS"; readonly candidates: readonly string[] }
  | { readonly outcome: "INVALID"; readonly reason: "unsafe-or-invalid candidate directory" | "corrupted checkpoint history"; readonly store: string };

function bindingMatches(context: ResolveContext, cp: ResumeCheckpoint): boolean {
  const ids = cp.state.identities;
  const projection = cp.state.projection;
  if (ids.repository !== context.repository) return false;
  if (context.scope !== undefined && ids.scope !== context.scope) return false;
  if (context.worktree !== undefined && ids.worktree !== context.worktree) return false;
  if (context.branch !== undefined && ids.branch !== context.branch) return false;
  if (context.dirty !== undefined && ids.dirty !== context.dirty) return false;
  if (context.taskId !== undefined && projection.taskId !== context.taskId) return false;
  if (context.workItem !== undefined && cp.state.workItem !== context.workItem) return false;
  return true;
}

/** Read-/Resolve-Seite: öffnet eine begrenzte, vom Aufrufer bereitgestellte Candidate-Scope, validiert jeden Store ausschließlich über die bestehende Checkpoint-API und liefert ein deterministisches Ergebnis. Keine Dateisystemsuche, keine Effektausführung, kein zweiter Zustand. */
export async function resolveResumeCandidates(candidates: readonly string[], context: ResolveContext): Promise<ResolveOutcome> {
  const matches: ResumeResolution[] = [];
  const seen = new Set<string>();
  for (const path of candidates) {
    let store: ResumeCheckpointStore;
    try {
      store = await ResumeCheckpointStore.open(path);
      const identity = await captureIdentity(path);
      const key = `${identity.device}:${identity.inode}`;
      if (seen.has(key)) continue;
      seen.add(key);
    } catch {
      return { outcome: "INVALID", reason: "unsafe-or-invalid candidate directory", store: path };
    }
    let cp: ResumeCheckpoint | null;
    try {
      cp = await store.read();
    } catch {
      return { outcome: "INVALID", reason: "corrupted checkpoint history", store: path };
    }
    if (cp === null) continue;
    const unresolvedEffect = (effect: ExternalEffect): boolean => effect.state === "PREPARED" || effect.state === "UNKNOWN";
    if (cp.state.taskStatus === "COMPLETED" && !cp.state.externalEffects.some(unresolvedEffect)) continue;
    if (!bindingMatches(context, cp)) continue;
    matches.push({
      store: path,
      generation: cp.generation,
      fingerprint: cp.fingerprint,
      taskId: cp.state.projection.taskId,
      objective: cp.state.projection.objective,
      scope: cp.state.projection.scope,
      exactHead: cp.state.projection.exactHead,
      taskStatus: cp.state.taskStatus,
      nextAtomicAction: cp.state.projection.nextAtomicAction,
      workItem: cp.state.workItem,
      externalEffects: cp.state.externalEffects,
    });
  }
  if (matches.length === 0) return { outcome: "NO_MATCH" };
  if (matches.length > 1) return { outcome: "AMBIGUOUS", candidates: matches.map((match) => match.store) };
  return { outcome: "RESUME", ...matches[0]! };
}
