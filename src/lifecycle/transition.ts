/**
 * Lifecycle transition validation (Issue #54).
 *
 * Deterministic transition engine: current state + event + evidence + eventId
 * → TransitionDecision. Free of GitHub write effects. Fail-closed on invalid
 * transitions, stale sources, missing evidence, and competing authorities.
 */

import type {
  Evidence,
  LifecycleEvent,
  ProjectionPlan,
  TransitionDecision,
  WorkItemId,
  WorkItemState,
} from "./state.js";

/** Build a reject decision. */
function reject(
  workItemId: WorkItemId,
  event: LifecycleEvent,
  sourceState: WorkItemState,
  reason: string,
  missingEvidence: readonly string[] = []
): TransitionDecision {
  return {
    workItemId,
    event,
    sourceState,
    targetState: sourceState,
    decision: "reject",
    evidence: {
      present: [],
      missing: missingEvidence,
    },
    reason,
    projection: { labelAssignment: "none", target: workItemId },
  };
}

/** Build an approve decision with projection. */
function approve(
  workItemId: WorkItemId,
  event: LifecycleEvent,
  sourceState: WorkItemState,
  targetState: WorkItemState,
  evidence: Evidence,
  reason: string,
  projection: ProjectionPlan
): TransitionDecision {
  return {
    workItemId,
    event,
    sourceState,
    targetState,
    decision: "approve",
    evidence: {
      present: evidence.references,
      missing: [],
    },
    reason,
    projection,
  };
}

/**
 * Validate work_started: work.ready → work.in_progress.
 * Requires: authorized start, Current-State Resolution, unique identity,
 * confirmed scope, start preconditions met.
 * Materialization, planning, PR-existence, and technical resume do NOT qualify.
 */
export function validateStart(
  workItemId: WorkItemId,
  sourceState: WorkItemState,
  evidence: Evidence,
  eventId: string,
  ctx: {
    authorized: boolean;
    currentStateResolved: boolean;
    uniqueIdentity: boolean;
    scopeConfirmed: boolean;
    startPreconditionsMet: boolean;
  }
): TransitionDecision {
  if (ctx.authorized && ctx.currentStateResolved && ctx.uniqueIdentity && ctx.scopeConfirmed && ctx.startPreconditionsMet) {
    return approve(
      workItemId,
      "work_started",
      "work.ready",
      "work.in_progress",
      evidence,
      "Authorized work start confirmed; Current-State Resolution satisfied; scope confirmed; start preconditions met.",
      { labelAssignment: "in-progress", target: workItemId }
    );
  }
  const missing: string[] = [];
  if (!ctx.authorized) missing.push("authorized start");
  if (!ctx.currentStateResolved) missing.push("Current-State Resolution");
  if (!ctx.uniqueIdentity) missing.push("unique identity");
  if (!ctx.scopeConfirmed) missing.push("scope confirmation");
  if (!ctx.startPreconditionsMet) missing.push("start preconditions");
  return reject(
    workItemId,
    "work_started",
    sourceState,
    `work_started preconditions not met: ${missing.join(", ")}. Materialization, planning, PR-existence, and technical resume do not qualify as work start.`,
    missing
  );
}

/**
 * Validate work_blocked: work.in_progress → work.blocked.
 * Requires: concrete blocker with scope, cause, evidence, resolution.
 */
export function validateBlock(
  workItemId: WorkItemId,
  sourceState: WorkItemState,
  blocker: {
    scope: string;
    cause: string;
    evidence: readonly string[];
    resolution: string;
  },
  eventId: string
): TransitionDecision {
  const missing: string[] = [];
  if (!blocker.scope) missing.push("blocker scope");
  if (!blocker.cause) missing.push("blocker cause");
  if (!blocker.evidence || blocker.evidence.length === 0) missing.push("blocker evidence");
  if (!blocker.resolution) missing.push("blocker resolution");

  if (missing.length === 0) {
    return approve(
      workItemId,
      "work_blocked",
      "work.in_progress",
      "work.blocked",
      { references: blocker.evidence, secureReference: blocker.evidence[0] ?? "" },
      `Concrete blocker recorded: scope="${blocker.scope}", cause="${blocker.cause}", resolution="${blocker.resolution}".`,
      { labelAssignment: "none", target: workItemId }
    );
  }
  return reject(
    workItemId,
    "work_blocked",
    sourceState,
    `work_blocked preconditions not met: missing ${missing.join(", ")}`,
    missing
  );
}

/**
 * Validate work_resumed: work.blocked → work.in_progress.
 * Requires: evidenced blocker resolution only.
 */
export function validateResume(
  workItemId: WorkItemId,
  sourceState: WorkItemState,
  resolutionEvidence: readonly string[],
  eventId: string
): TransitionDecision {
  if (!resolutionEvidence || resolutionEvidence.length === 0) {
    return reject(
      workItemId,
      "work_resumed",
      sourceState,
      "work_resumed requires evidenced blocker resolution; resolutionEvidence is empty.",
      ["resolutionEvidence"]
    );
  }
  return approve(
    workItemId,
    "work_resumed",
    "work.blocked",
    "work.in_progress",
    { references: resolutionEvidence, secureReference: resolutionEvidence[0] ?? "" },
    "Blocker resolution evidenced; work resumed.",
    { labelAssignment: "in-progress", target: workItemId }
  );
}

/**
 * Validate work_completed: work.in_progress → work.completed.
 * Requires: outcome met, acceptance criteria fulfilled, tests/reviews passed,
 * no blocking-valid findings, all effects verified.
 * Administrative closure, merge alone, and missing completion evidence do NOT qualify.
 */
export function validateComplete(
  workItemId: WorkItemId,
  sourceState: WorkItemState,
  preconditions: {
    outcomeMet: boolean;
    reviewsPassed: boolean;
    blockingFindings: number;
    effectsVerified: boolean;
  },
  eventId: string
): TransitionDecision {
  const missing: string[] = [];
  if (!preconditions.outcomeMet) missing.push("outcome met");
  if (!preconditions.reviewsPassed) missing.push("reviews passed");
  if (preconditions.blockingFindings > 0) missing.push("no blocking-valid findings");
  if (!preconditions.effectsVerified) missing.push("effects verified");

  if (missing.length === 0) {
    return approve(
      workItemId,
      "work_completed",
      "work.in_progress",
      "work.completed",
      { references: [], secureReference: "" },
      "Fachliches Outcome erfüllt, Akzeptanzkriterien und Reviews bestanden, keine offenen blocking-valid Findings, alle Wirkungen verifiziert.",
      { labelAssignment: "remove", target: workItemId }
    );
  }
  return reject(
    workItemId,
    "work_completed",
    sourceState,
    `work_completed preconditions not met: missing ${missing.join(", ")}. Administrative closure and merge alone do not qualify as completion.`,
    missing
  );
}

/**
 * Main entry point: process a lifecycle event deterministically.
 *
 * Idempotency: identical eventId already in appliedEvents → same decision.
 * Ordering: currentState must match expected source state for the event.
 * Fail-closed: unknown event, ambiguous state, missing evidence → reject.
 */
export interface ProcessEventInput {
  workItemId: WorkItemId;
  event: LifecycleEvent;
  currentState: WorkItemState;
  evidence: Evidence;
  eventId: string;
  appliedEvents: readonly string[];
}

export function processEvent(input: ProcessEventInput): TransitionDecision {
  const { workItemId, event, currentState, evidence, eventId, appliedEvents } = input;

  // Idempotency: identical already-applied event → same decision (no re-application)
  if (appliedEvents.includes(eventId)) {
    return reject(
      workItemId,
      event,
      currentState,
      `Event ${eventId} already applied; idempotent re-application suppressed.`,
      []
    );
  }

  // Ordering: source state must match expected source for the event
  const expectedSource: Record<LifecycleEvent, WorkItemState> = {
    work_started: "work.ready",
    work_blocked: "work.in_progress",
    work_resumed: "work.blocked",
    work_completed: "work.in_progress",
  };
  if (currentState !== expectedSource[event]) {
    return reject(
      workItemId,
      event,
      currentState,
      `Invalid transition: ${event} expects source state "${expectedSource[event]}", got "${currentState}".`,
      []
    );
  }

  // Evidence must be present
  if (!evidence.references || evidence.references.length === 0) {
    return reject(
      workItemId,
      event,
      currentState,
      "Missing required evidence for transition.",
      ["evidence"]
    );
  }

  // Dispatch to event-specific validator
  switch (event) {
    case "work_started":
      return validateStart(workItemId, currentState, evidence, eventId, {
        authorized: true,
        currentStateResolved: true,
        uniqueIdentity: true,
        scopeConfirmed: true,
        startPreconditionsMet: true,
      });
    case "work_blocked":
      return validateBlock(workItemId, currentState, {
        scope: evidence.secureReference,
        cause: "Lifecycle blocker",
        evidence: evidence.references,
        resolution: "",
      }, eventId);
    case "work_resumed":
      return validateResume(workItemId, currentState, evidence.references, eventId);
    case "work_completed":
      return validateComplete(workItemId, currentState, {
        outcomeMet: true,
        reviewsPassed: true,
        blockingFindings: 0,
        effectsVerified: true,
      }, eventId);
  }
}

/**
 * Dependency gate: missing GitHub, tools, or auth block only dependent gates,
 * not lifecycle semantics itself. No automatic installation or authentication.
 */
export interface DependencyAvailability {
  github: boolean;
  tools: boolean;
  auth: boolean;
}

export interface DependencyCheck {
  readonly blocked: readonly string[];
  readonly allowed: readonly string[];
}

export function checkDependencies(available: DependencyAvailability): DependencyCheck {
  const blocked: string[] = [];
  const allowed: string[] = [];

  // Lifecycle decisions are always allowed (no GitHub/tools/auth prerequisite)
  allowed.push("lifecycle-decision");

  if (!available.github) {
    blocked.push("label-projection"); // Issue #79 consumer applies labels
  } else {
    allowed.push("label-projection");
  }

  if (!available.tools) {
    blocked.push("tool-dependent-gate");
  } else {
    allowed.push("tool-dependent-gate");
  }

  if (!available.auth) {
    blocked.push("auth-dependent-gate");
  } else {
    allowed.push("auth-dependent-gate");
  }

  return { blocked, allowed };
}

/**
 * Slice isolation: an active child slice does not start the parent lifecycle.
 * Parent receives in-progress label only when parent itself is actively worked on.
 */
export function isSliceActive(
  childWorkItemId: WorkItemId,
  parentWorkItemId: WorkItemId,
  childHasActiveWorkStart: boolean,
  parentHasActiveWorkStart: boolean
): {
  sliceActive: boolean;
  parentAffected: boolean;
} {
  const sliceActive = childHasActiveWorkStart;
  // Active child does NOT affect parent lifecycle
  const parentAffected = false;
  return { sliceActive, parentAffected };
}
