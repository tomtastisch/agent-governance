/**
 * Work-Item Lifecycle State Types (Issue #54)
 *
 * Canonical, platform-neutral lifecycle semantics for Agent Governance work items.
 * States: work.ready, work.in_progress, work.blocked, work.completed.
 * Events: work_started, work_blocked, work_resumed, work_completed.
 *
 * Lifecycle State != GitHub Label.
 * Lifecycle Event != Chatphrase.
 */

/** Canonical lifecycle states. */
export type WorkItemState =
  | "work.ready"
  | "work.in_progress"
  | "work.blocked"
  | "work.completed";

/** Canonical lifecycle events. */
export type LifecycleEvent =
  | "work_started"
  | "work_blocked"
  | "work_resumed"
  | "work_completed";

/** Evidence references supporting a transition. */
export interface Evidence {
  /** Reference identifiers to supporting evidence artifacts. */
  readonly references: readonly string[];
  /** Secure, non-secret reference to evidence (no secrets, no PII fingerprints). */
  readonly secureReference: string;
}

/** Deterministic projection produced by a valid transition decision. */
export interface ProjectionPlan {
  /** Managed in-progress label assignment. */
  readonly labelAssignment: "in-progress" | "remove" | "none";
  /** Target work item for the projection. */
  readonly target: WorkItemId;
}

/** Result of a lifecycle transition decision. */
export interface TransitionDecision {
  /** Unique work item identifier. */
  readonly workItemId: WorkItemId;
  /** Event that triggered the transition. */
  readonly event: LifecycleEvent;
  /** Source (current) state. */
  readonly sourceState: WorkItemState;
  /** Target state after transition. */
  readonly targetState: WorkItemState;
  /** Approve or reject decision. */
  readonly decision: "approve" | "reject";
  /** Present and missing evidence references. */
  readonly evidence: {
    readonly present: readonly string[];
    readonly missing: readonly string[];
  };
  /** Human-readable reason for the decision. */
  readonly reason: string;
  /** Projection plan for downstream consumer (Issue #79 Apply). */
  readonly projection: ProjectionPlan;
}

/** Unique work item identifier. */
export interface WorkItemId {
  readonly value: string;
}
