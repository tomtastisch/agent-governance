import test from "node:test";
import assert from "node:assert/strict";
import type {
  WorkItemState,
  LifecycleEvent,
  Evidence,
  ProjectionPlan,
  TransitionDecision,
} from "../../src/lifecycle/state.ts";

test("WorkItemState has exactly 4 literal values", () => {
  const states: WorkItemState[] = [
    "work.ready",
    "work.in_progress",
    "work.blocked",
    "work.completed",
  ];
  assert.strictEqual(states.length, 4);
  assert.ok(states.includes("work.ready"));
  assert.ok(states.includes("work.in_progress"));
  assert.ok(states.includes("work.blocked"));
  assert.ok(states.includes("work.completed"));
});

test("LifecycleEvent has exactly 4 literal values", () => {
  const events: LifecycleEvent[] = [
    "work_started",
    "work_blocked",
    "work_resumed",
    "work_completed",
  ];
  assert.strictEqual(events.length, 4);
});

test("Evidence interface has references and secureReference", () => {
  const ev: Evidence = {
    references: ["ref-1", "ref-2"],
    secureReference: "ref-1",
  };
  assert.strictEqual(ev.references.length, 2);
  assert.strictEqual(ev.secureReference, "ref-1");
});

test("ProjectionPlan interface has labelAssignment and target", () => {
  const proj: ProjectionPlan = {
    labelAssignment: "in-progress",
    target: { value: "wi-123" },
  };
  assert.strictEqual(proj.labelAssignment, "in-progress");
  assert.strictEqual(proj.target.value, "wi-123");
});

test("TransitionDecision interface has all required fields", () => {
  const dec: TransitionDecision = {
    workItemId: { value: "wi-123" },
    event: "work_started",
    sourceState: "work.ready",
    targetState: "work.in_progress",
    decision: "approve",
    evidence: { present: ["ref-1"], missing: [] },
    reason: "Test decision",
    projection: { labelAssignment: "in-progress", target: { value: "wi-123" } },
  };
  assert.strictEqual(dec.decision, "approve");
  assert.strictEqual(dec.sourceState, "work.ready");
  assert.strictEqual(dec.targetState, "work.in_progress");
  assert.strictEqual(dec.projection.labelAssignment, "in-progress");
});
