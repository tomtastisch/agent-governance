import assert from "node:assert/strict";
import test from "node:test";
import { refineCandidateRoots } from "../../src/discovery/boundary.ts";
import { loadDiscoveryCatalog } from "../../src/discovery/catalog.ts";
import { classifyEvidence } from "../../src/discovery/classifier.ts";
import type { EvidenceFamily, EvidenceRecord, EvidenceStrength } from "../../src/discovery/types.ts";

const catalog = loadDiscoveryCatalog();

function cluster(root: string): readonly EvidenceRecord[] {
  const definitions: ReadonlyArray<[string, EvidenceFamily, string, EvidenceStrength]> = [
    ["runtime.json", "runtime", "runtime_endpoint", "strong"],
    ["state.json", "state", "state_continuity", "strong"],
    ["tools.json", "tooling", "tool_registry", "corroborating"],
  ];
  return definitions.map(([name, family, signalId, strength]) => Object.freeze({
    family,
    sourceKind: "json" as const,
    sourcePath: `${root}/${name}`,
    signalId,
    strength,
    status: "COMPLETE" as const,
    metadata: Object.freeze([signalId]),
  }));
}

function broadCandidate(root: string, records: readonly EvidenceRecord[]) {
  return classifyEvidence(records, catalog, {
    root,
    candidateClass: "DIRECTORY",
    status: "COMPLETE",
    fileCount: records.length,
    activityAt: 100,
  });
}

test("a broad container with one coherent child is replaced by the child root", () => {
  const container = "/synthetic/container";
  const child = `${container}/profile-a`;
  const refined = refineCandidateRoots([broadCandidate(container, cluster(child))]);

  assert.deepEqual(refined.map(({ root }) => root), [child]);
  assert.equal(refined[0]?.confidence, "HIGH_CONFIDENCE");
});

test("a broad container with multiple coherent child clusters becomes the smallest child roots", () => {
  const container = "/synthetic/container";
  const first = `${container}/profile-a`;
  const second = `${container}/profile-b`;
  const refined = refineCandidateRoots([
    broadCandidate(container, [...cluster(first), ...cluster(second)]),
  ]);

  assert.deepEqual(refined.map(({ root }) => root), [first, second]);
  assert.equal(refined.every(({ confidence }) => confidence === "HIGH_CONFIDENCE"), true);
});

test("an explicit coherent descendant eliminates its broad ancestor", () => {
  const container = "/synthetic/container";
  const child = `${container}/profile-a`;
  const records = cluster(child);
  const refined = refineCandidateRoots([
    broadCandidate(container, records),
    broadCandidate(child, records),
  ]);

  assert.deepEqual(refined.map(({ root }) => root), [child]);
});

test("boundary refinement retains the classifier catalog thresholds", () => {
  const container = "/synthetic/container";
  const child = `${container}/profile-a`;
  const strictCatalog = {
    ...catalog,
    confidence: { ...catalog.confidence, highMinimumScore: 12 },
  };
  const records = cluster(child);
  const candidate = classifyEvidence(records, strictCatalog, {
    root: container,
    candidateClass: "DIRECTORY",
    status: "COMPLETE",
    fileCount: records.length,
    activityAt: 100,
  });
  const refined = refineCandidateRoots([candidate], strictCatalog);

  assert.deepEqual(refined.map(({ root }) => root), [child]);
  assert.equal(refined[0]?.confidence, "UNCERTAIN");
});
