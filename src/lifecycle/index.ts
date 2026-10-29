/**
 * Lifecycle module public API (Issue #54).
 *
 * Re-exports all lifecycle types. The lifecycle engine is free of GitHub
 * write effects — it decides, the consumer (Issue #79) applies.
 */

export type {
  WorkItemId,
  WorkItemState,
  LifecycleEvent,
  Evidence,
  ProjectionPlan,
  TransitionDecision,
} from "./state.js";
