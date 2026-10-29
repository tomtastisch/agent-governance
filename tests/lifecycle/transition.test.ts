import test from "node:test";
import assert from "node:assert/strict";
import {
  validateStart,
  validateBlock,
  validateResume,
  validateComplete,
  processEvent,
  checkDependencies,
  isSliceActive,
} from "../../src/lifecycle/transition.ts";
import type {
  Evidence,
  WorkItemId,
  WorkItemState,
} from "../../src/lifecycle/state.ts";

const WORK_ITEM_ID: WorkItemId = { value: "wi-123" };
const EVIDENCE: Evidence = {
  references: ["ev-1", "ev-2"],
  secureReference: "ev-1",
};

test("validateStart approves when all preconditions met", () => {
  const dec = validateStart(WORK_ITEM_ID, "work.ready" as WorkItemState, EVIDENCE, "evt-1", {
    authorized: true,
    currentStateResolved: true,
    uniqueIdentity: true,
    scopeConfirmed: true,
    startPreconditionsMet: true,
  });
  assert.strictEqual(dec.decision, "approve");
  assert.strictEqual(dec.sourceState, "work.ready");
  assert.strictEqual(dec.targetState, "work.in_progress");
  assert.strictEqual(dec.projection.labelAssignment, "in-progress");
  assert.strictEqual(dec.projection.target.value, "wi-123");
});

test("validateStart rejects when not authorized", () => {
  const dec = validateStart(WORK_ITEM_ID, "work.ready" as WorkItemState, EVIDENCE, "evt-1", {
    authorized: false,
    currentStateResolved: true,
    uniqueIdentity: true,
    scopeConfirmed: true,
    startPreconditionsMet: true,
  });
  assert.strictEqual(dec.decision, "reject");
  assert.strictEqual(dec.reason.includes("authorized start"), true);
});

test("validateStart rejects when currentStateResolution missing", () => {
  const dec = validateStart(WORK_ITEM_ID, "work.ready" as WorkItemState, EVIDENCE, "evt-1", {
    authorized: true,
    currentStateResolved: false,
    uniqueIdentity: true,
    scopeConfirmed: true,
    startPreconditionsMet: true,
  });
  assert.strictEqual(dec.decision, "reject");
  assert.strictEqual(dec.reason.includes("Current-State Resolution"), true);
});

test("validateStart rejects when uniqueIdentity missing", () => {
  const dec = validateStart(WORK_ITEM_ID, "work.ready" as WorkItemState, EVIDENCE, "evt-1", {
    authorized: true,
    currentStateResolved: true,
    uniqueIdentity: false,
    scopeConfirmed: true,
    startPreconditionsMet: true,
  });
  assert.strictEqual(dec.decision, "reject");
  assert.strictEqual(dec.reason.includes("unique identity"), true);
});

test("validateStart rejects when scope not confirmed", () => {
  const dec = validateStart(WORK_ITEM_ID, "work.ready" as WorkItemState, EVIDENCE, "evt-1", {
    authorized: true,
    currentStateResolved: true,
    uniqueIdentity: true,
    scopeConfirmed: false,
    startPreconditionsMet: true,
  });
  assert.strictEqual(dec.decision, "reject");
  assert.strictEqual(dec.reason.includes("scope confirmation"), true);
});

test("validateStart rejects when start preconditions not met", () => {
  const dec = validateStart(WORK_ITEM_ID, "work.ready" as WorkItemState, EVIDENCE, "evt-1", {
    authorized: true,
    currentStateResolved: true,
    uniqueIdentity: true,
    scopeConfirmed: true,
    startPreconditionsMet: false,
  });
  assert.strictEqual(dec.decision, "reject");
  assert.strictEqual(dec.reason.includes("start preconditions"), true);
});

test("validateBlock approves with complete blocker", () => {
  const dec = validateBlock(WORK_ITEM_ID, "work.in_progress", {
    scope: "task-456",
    cause: "External dependency unavailable",
    evidence: ["ev-1"],
    resolution: "Wait for dependency",
  }, "evt-2");
  assert.strictEqual(dec.decision, "approve");
  assert.strictEqual(dec.sourceState, "work.in_progress");
  assert.strictEqual(dec.targetState, "work.blocked");
});

test("validateBlock rejects with incomplete blocker", () => {
  const dec = validateBlock(WORK_ITEM_ID, "work.in_progress", {
    scope: "",
    cause: "External dependency unavailable",
    evidence: [],
    resolution: "",
  }, "evt-2");
  assert.strictEqual(dec.decision, "reject");
  assert.strictEqual(dec.reason.includes("blocker scope"), true);
  assert.strictEqual(dec.reason.includes("blocker evidence"), true);
  assert.strictEqual(dec.reason.includes("blocker resolution"), true);
});

test("validateResume approves with evidenced resolution", () => {
  const dec = validateResume(WORK_ITEM_ID, "work.blocked", ["ev-1", "ev-2"], "evt-3");
  assert.strictEqual(dec.decision, "approve");
  assert.strictEqual(dec.sourceState, "work.blocked");
  assert.strictEqual(dec.targetState, "work.in_progress");
  assert.strictEqual(dec.projection.labelAssignment, "in-progress");
});

test("validateResume rejects with empty resolution evidence", () => {
  const dec = validateResume(WORK_ITEM_ID, "work.blocked", [], "evt-3");
  assert.strictEqual(dec.decision, "reject");
  assert.strictEqual(dec.reason.includes("resolutionEvidence"), true);
});

test("validateComplete approves when all preconditions met", () => {
  const dec = validateComplete(WORK_ITEM_ID, "work.in_progress", {
    outcomeMet: true,
    reviewsPassed: true,
    blockingFindings: 0,
    effectsVerified: true,
  }, "evt-4");
  assert.strictEqual(dec.decision, "approve");
  assert.strictEqual(dec.sourceState, "work.in_progress");
  assert.strictEqual(dec.targetState, "work.completed");
  assert.strictEqual(dec.projection.labelAssignment, "remove");
});

test("validateComplete rejects with blocking findings", () => {
  const dec = validateComplete(WORK_ITEM_ID, "work.in_progress", {
    outcomeMet: true,
    reviewsPassed: true,
    blockingFindings: 2,
    effectsVerified: true,
  }, "evt-4");
  assert.strictEqual(dec.decision, "reject");
  assert.strictEqual(dec.reason.includes("no blocking-valid findings"), true);
});

test("validateComplete rejects when effects not verified", () => {
  const dec = validateComplete(WORK_ITEM_ID, "work.in_progress", {
    outcomeMet: true,
    reviewsPassed: true,
    blockingFindings: 0,
    effectsVerified: false,
  }, "evt-4");
  assert.strictEqual(dec.decision, "reject");
  assert.strictEqual(dec.reason.includes("effects verified"), true);
});

test("processEvent is idempotent for duplicate eventId", () => {
  const input = {
    workItemId: WORK_ITEM_ID,
    event: "work_started" as const,
    currentState: "work.ready" as WorkItemState,
    evidence: EVIDENCE,
    eventId: "evt-dup",
    appliedEvents: ["evt-dup"],
  };
  const dec = processEvent(input);
  assert.strictEqual(dec.decision, "reject");
  assert.strictEqual(dec.reason.includes("already applied"), true);
  assert.strictEqual(dec.reason.includes("idempotent"), true);
});

test("processEvent rejects mismatched source state", () => {
  const input = {
    workItemId: WORK_ITEM_ID,
    event: "work_started" as const,
    currentState: "work.in_progress" as WorkItemState,
    evidence: EVIDENCE,
    eventId: "evt-mismatch",
    appliedEvents: [],
  };
  const dec = processEvent(input);
  assert.strictEqual(dec.decision, "reject");
  assert.strictEqual(dec.reason.includes("Invalid transition"), true);
});

test("processEvent rejects missing evidence", () => {
  const input = {
    workItemId: WORK_ITEM_ID,
    event: "work_started" as const,
    currentState: "work.ready" as WorkItemState,
    evidence: { references: [], secureReference: "" },
    eventId: "evt-noev",
    appliedEvents: [],
  };
  const dec = processEvent(input);
  assert.strictEqual(dec.decision, "reject");
  assert.strictEqual(dec.reason.includes("Missing required evidence"), true);
});

test("processEvent approves valid work_started", () => {
  const input = {
    workItemId: WORK_ITEM_ID,
    event: "work_started" as const,
    currentState: "work.ready" as WorkItemState,
    evidence: EVIDENCE,
    eventId: "evt-ok",
    appliedEvents: [],
  };
  const dec = processEvent(input);
  assert.strictEqual(dec.decision, "approve");
  assert.strictEqual(dec.targetState, "work.in_progress");
  assert.strictEqual(dec.projection.labelAssignment, "in-progress");
});

test("processEvent approves valid work_completed", () => {
  const input = {
    workItemId: WORK_ITEM_ID,
    event: "work_completed" as const,
    currentState: "work.in_progress" as WorkItemState,
    evidence: EVIDENCE,
    eventId: "evt-complete",
    appliedEvents: [],
  };
  const dec = processEvent(input);
  assert.strictEqual(dec.decision, "approve");
  assert.strictEqual(dec.targetState, "work.completed");
  assert.strictEqual(dec.projection.labelAssignment, "remove");
});

test("checkDependencies blocks only dependent gates when github missing", () => {
  const res = checkDependencies({ github: false, tools: true, auth: true });
  assert.ok(res.blocked.includes("label-projection"));
  assert.ok(res.allowed.includes("lifecycle-decision"));
  assert.ok(res.allowed.includes("tool-dependent-gate"));
  assert.ok(res.allowed.includes("auth-dependent-gate"));
});

test("checkDependencies allows all when all available", () => {
  const res = checkDependencies({ github: true, tools: true, auth: true });
  assert.strictEqual(res.blocked.length, 0);
  assert.strictEqual(res.allowed.length, 4);
});

test("isSliceActive: active child does not affect parent", () => {
  const res = isSliceActive(
    { value: "child-1" },
    { value: "parent-1" },
    true,
    false
  );
  assert.strictEqual(res.sliceActive, true);
  assert.strictEqual(res.parentAffected, false);
});

test("isSliceActive: inactive child is not active", () => {
  const res = isSliceActive(
    { value: "child-1" },
    { value: "parent-1" },
    false,
    false
  );
  assert.strictEqual(res.sliceActive, false);
  assert.strictEqual(res.parentAffected, false);
});
