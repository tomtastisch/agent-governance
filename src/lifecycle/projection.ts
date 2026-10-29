/**
 * Managed in-progress projection (Issue #54).
 *
 * Pure function: derives a ProjectionPlan from a TransitionDecision.
 * The engine produces the plan; the consumer (Issue #79 Apply contract)
 * applies it with read-back. No GitHub API calls inside this module.
 */

import type { ProjectionPlan, TransitionDecision, WorkItemId } from "./state.js";

/**
 * Derive the managed label projection from a transition decision.
 *
 * - work_started approved  → labelAssignment: "in-progress", target: workItemId
 * - work_completed approved → labelAssignment: "remove", target: workItemId
 * - all other decisions   → labelAssignment: "none"
 */
export function buildProjection(
  decision: TransitionDecision
): ProjectionPlan {
  if (decision.decision !== "approve") {
    return { labelAssignment: "none", target: decision.workItemId };
  }

  switch (decision.event) {
    case "work_started":
      return { labelAssignment: "in-progress", target: decision.workItemId };
    case "work_completed":
      return { labelAssignment: "remove", target: decision.workItemId };
    case "work_blocked":
    case "work_resumed":
      return { labelAssignment: "none", target: decision.workItemId };
  }
}

/**
 * Build a no-op projection (used when lifecycle decision is rejected
 * or dependencies are missing).
 */
export function noProjection(workItemId: WorkItemId): ProjectionPlan {
  return { labelAssignment: "none", target: workItemId };
}
