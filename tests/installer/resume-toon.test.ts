import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import {
  decodeResumeProjection,
  encodeResumeProjection,
  ResumeProjectionError,
  validateResumeProjection,
  type ResumeProjection,
} from "../../src/resume-toon.ts";

function sampleState(): ResumeProjection {
  return {
    taskId: "task-1",
    objective: "Resume Fast-Path verifizieren",
    scope: ["bundle", "tests"],
    exactHead: "a".repeat(40),
    checkpointFingerprint: "cp-1",
    evidence: [
      { id: "qa", bindings: ["b".repeat(40)], status: "REUSE" },
      { id: "sec", bindings: ["c".repeat(40)], status: "INVALIDATE" },
    ],
    incompleteEvidence: ["review-sec"],
    openFindings: [],
    nextAtomicAction: "unabhängige SEC-Prüfung ausführen",
  };
}

test("identical resume state encodes byte-identically", () => {
  const state = sampleState();
  assert.equal(encodeResumeProjection(state), encodeResumeProjection(structuredClone(state)));
});

test("reordered keys still encode byte-identically", () => {
  const state = sampleState();
  const reordered: ResumeProjection = {
    nextAtomicAction: state.nextAtomicAction,
    openFindings: state.openFindings,
    incompleteEvidence: state.incompleteEvidence,
    evidence: state.evidence,
    checkpointFingerprint: state.checkpointFingerprint,
    exactHead: state.exactHead,
    scope: state.scope,
    objective: state.objective,
    taskId: state.taskId,
  };
  assert.deepEqual(reordered, state);
  assert.equal(encodeResumeProjection(state), encodeResumeProjection(reordered));
});

test("encode then decode round-trips to a semantically identical state", () => {
  const state = sampleState();
  const decoded = decodeResumeProjection(encodeResumeProjection(state));
  assert.deepEqual(decoded, state);
});

test("a real .toon file can be written and read back", async () => {
  const dir = await mkdtemp(join(tmpdir(), "resume-toon-"));
  try {
    const state = sampleState();
    const path = join(dir, "resume.toon");
    await writeFile(path, encodeResumeProjection(state), "utf8");
    const fromDisk = await readFile(path, "utf8");
    assert.deepEqual(decodeResumeProjection(fromDisk), state);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

test("UTF-8 content survives the round-trip", () => {
  const state: ResumeProjection = {
    ...sampleState(),
    objective: "Prüfung — übergreifende „Änderung“ 中文 ✓",
    scope: ["bundle/agent-governance"],
    nextAtomicAction: "grenzüberschreitend fortfahren – nächste Aktion",
  };
  assert.deepEqual(decodeResumeProjection(encodeResumeProjection(state)), state);
});

test("corrupted syntax is rejected fail-closed", () => {
  const encoded = encodeResumeProjection(sampleState());
  const corrupted = `${encoded}\nbroken[unclosed: \x00`;
  assert.throws(() => decodeResumeProjection(corrupted));
});

test("unknown and disallowed fields are rejected fail-closed", () => {
  const state = sampleState();
  assert.throws(
    () => validateResumeProjection({ ...state, extraTruth: "nope" }),
    ResumeProjectionError,
  );
  assert.throws(
    () => validateResumeProjection({ ...state, evidence: [{ ...state.evidence[0], owner: "x" }] }),
    ResumeProjectionError,
  );
});

test("tampered checkpoint binding is rejected", () => {
  const state = sampleState();
  const decoded = decodeResumeProjection(encodeResumeProjection(state));
  const tampered = encodeResumeProjection({ ...decoded, checkpointFingerprint: "cp-tampered" });
  assert.throws(() => decodeResumeProjection(tampered, { expectedCheckpoint: "cp-1" }), ResumeProjectionError);
});

test("a stale projection (mismatched expected checkpoint) is rejected", () => {
  const stale = encodeResumeProjection(sampleState());
  assert.throws(
    () => decodeResumeProjection(stale, { expectedCheckpoint: "cp-newer" }),
    ResumeProjectionError,
  );
});

test("an incomplete projection is rejected", () => {
  const state = sampleState() as unknown as Record<string, unknown>;
  const { nextAtomicAction: _dropped, ...incomplete } = state;
  assert.throws(() => validateResumeProjection(incomplete), ResumeProjectionError);
});

test("secret or private raw data is never accepted", () => {
  const state = sampleState();
  assert.throws(
    () => validateResumeProjection({ ...state, secret: "hunter2" }),
    ResumeProjectionError,
  );
  assert.throws(
    () =>
      validateResumeProjection({
        ...state,
        evidence: [{ id: "e", bindings: [], status: "REUSE", apiKey: "sk-123" }],
      }),
    ResumeProjectionError,
  );
});

test("the .toon projection carries no independent truth beyond the schema", () => {
  const state = sampleState();
  const encoded = encodeResumeProjection(state);
  const decoded = decodeResumeProjection(encoded);
  assert.deepEqual(Object.keys(decoded).sort(), Object.keys(state).sort());
  assert.deepEqual(decoded, state);
  assert.doesNotThrow(() => validateResumeProjection(decoded));
});
