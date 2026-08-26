import assert from "node:assert/strict";
import test from "node:test";
import { loadDiscoveryCatalog } from "../../src/discovery/catalog.ts";
import { classifyEvidence } from "../../src/discovery/classifier.ts";
import { resolveDuplicateCandidates } from "../../src/discovery/duplicates.ts";
import type { EvidenceFamily, EvidenceRecord, EvidenceStrength } from "../../src/discovery/types.ts";

const catalog = loadDiscoveryCatalog();

function records(root: string, extra = false): readonly EvidenceRecord[] {
  const definitions: Array<[string, EvidenceFamily, string, EvidenceStrength]> = [
    ["runtime.json", "runtime", "runtime_endpoint", "strong"],
    ["state.json", "state", "state_continuity", "strong"],
    ["tools.json", "tooling", "tool_registry", "corroborating"],
  ];
  if (extra) definitions.push(["models.json", "ai_metadata", "model_configuration", "corroborating"]);
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

function candidate(root: string, activityAt: number, extra = false) {
  const evidence = records(root, extra);
  return classifyEvidence(evidence, catalog, {
    root,
    candidateClass: "DIRECTORY",
    status: "COMPLETE",
    fileCount: evidence.length,
    activityAt,
  });
}

test("an active candidate wins over a structurally near-identical copy", () => {
  const active = candidate("/synthetic/runtime-profile", 200, true);
  const copy = candidate("/synthetic/runtime-profile-copy", 100);
  const resolved = resolveDuplicateCandidates([copy, active]);

  assert.deepEqual(resolved.map(({ root }) => root), [active.root]);
  assert.equal(resolved[0]?.confidence, "HIGH_CONFIDENCE");
});

test("indistinguishable copies are both retained and demoted to uncertain", () => {
  const first = candidate("/synthetic/runtime-profile", 100);
  const second = candidate("/synthetic/runtime-profile-snapshot", 100);
  const resolved = resolveDuplicateCandidates([first, second]);

  assert.deepEqual(resolved.map(({ root }) => root), [first.root, second.root]);
  assert.equal(resolved.every(({ confidence }) => confidence === "UNCERTAIN"), true);
});

test("mtime is only a secondary tie-breaker after generic identity and structural similarity", () => {
  const first = candidate("/synthetic/profile-a", 100);
  const unrelatedNewer = candidate("/synthetic/profile-b", 10_000);
  const resolved = resolveDuplicateCandidates([first, unrelatedNewer]);

  assert.deepEqual(resolved.map(({ root }) => root), [first.root, unrelatedNewer.root]);
  assert.equal(resolved.every(({ confidence }) => confidence === "HIGH_CONFIDENCE"), true);
});
