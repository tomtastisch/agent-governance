import test from "node:test";
import assert from "node:assert/strict";
import { buildProjection, noProjection } from "../../src/lifecycle/projection.ts";
import type {
  TransitionDecision,
  WorkItemId,
} from "../../src/lifecycle/state.ts";

const WORK_ITEM_ID: WorkItemId = { value: "wi-123" };

function approvedDecision(
  event: "work_started" | "work_completed",
  targetState: "work.in_progress" | "work.completed",
  labelAssignment: "in-progress" | "remove"
): TransitionDecision {
  return {
    workItemId: WORK_ITEM_ID,
    event,
    sourceState:
      event === "work_started" ? "work.ready" : "work.in_progress",
    targetState,
    decision: "approve",
    evidence: { present: ["ev-1"], missing: [] },
    reason: "Test approved decision",
    projection: { labelAssignment, target: WORK_ITEM_ID },
  };
}

function rejectedDecision(): TransitionDecision {
  return {
    workItemId: WORK_ITEM_ID,
    event: "work_started",
    sourceState: "work.ready",
    targetState: "work.ready",
    decision: "reject",
    evidence: { present: [], missing: ["evidence"] },
    reason: "Test rejected decision",
    projection: { labelAssignment: "none", target: WORK_ITEM_ID },
  };
}

test("buildProjection for approved work_started returns in-progress", () => {
  const proj = buildProjection(
    approvedDecision("work_started", "work.in_progress", "in-progress")
  );
  assert.strictEqual(proj.labelAssignment, "in-progress");
  assert.strictEqual(proj.target.value, "wi-123");
});

test("buildProjection for approved work_completed returns remove", () => {
  const proj = buildProjection(
    approvedDecision("work_completed", "work.completed", "remove")
  );
  assert.strictEqual(proj.labelAssignment, "remove");
  assert.strictEqual(proj.target.value, "wi-123");
});

test("buildProjection for rejected decision returns none", () => {
  const proj = buildProjection(rejectedDecision());
  assert.strictEqual(proj.labelAssignment, "none");
});

test("buildProjection for work_blocked returns none", () => {
  const dec: TransitionDecision = {
    workItemId: WORK_ITEM_ID,
    event: "work_blocked",
    sourceState: "work.in_progress",
    targetState: "work.blocked",
    decision: "approve",
    evidence: { present: ["ev-1"], missing: [] },
    reason: "Test blocked",
    projection: { labelAssignment: "none", target: WORK_ITEM_ID },
  };
  const proj = buildProjection(dec);
  assert.strictEqual(proj.labelAssignment, "none");
});

test("buildProjection for work_resumed returns none", () => {
  const dec: TransitionDecision = {
    workItemId: WORK_ITEM_ID,
    event: "work_resumed",
    sourceState: "work.blocked",
    targetState: "work.in_progress",
    decision: "approve",
    evidence: { present: ["ev-1"], missing: [] },
    reason: "Test resumed",
    projection: { labelAssignment: "none", target: WORK_ITEM_ID },
  };
  const proj = buildProjection(dec);
  assert.strictEqual(proj.labelAssignment, "none");
});

test("noProjection returns none", () => {
  const proj = noProjection(WORK_ITEM_ID);
  assert.strictEqual(proj.labelAssignment, "none");
  assert.strictEqual(proj.target.value, "wi-123");
});
