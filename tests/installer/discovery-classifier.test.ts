import assert from "node:assert/strict";
import test from "node:test";
import { loadDiscoveryCatalog } from "../../src/discovery/catalog.ts";
import { classifyEvidence } from "../../src/discovery/classifier.ts";
import type {
  CandidateClass,
  EvidenceFamily,
  EvidenceRecord,
  EvidenceSourceKind,
  EvidenceStrength,
} from "../../src/discovery/types.ts";

const catalog = loadDiscoveryCatalog();

function evidence(
  root: string,
  name: string,
  family: EvidenceFamily,
  signalId: string,
  strength: EvidenceStrength,
  sourceKind: EvidenceSourceKind = "json",
): EvidenceRecord {
  return Object.freeze({
    family,
    sourceKind,
    sourcePath: `${root}/${name}`,
    signalId,
    strength,
    status: "COMPLETE",
    metadata: Object.freeze([signalId]),
  });
}

function classify(
  records: readonly EvidenceRecord[],
  root = "/synthetic/runtime-profile",
  candidateClass: CandidateClass = "DIRECTORY",
) {
  return classifyEvidence(records, catalog, {
    root,
    candidateClass,
    status: "COMPLETE",
    fileCount: new Set(records.map(({ sourcePath }) => sourcePath)).size,
    activityAt: 100,
  });
}

test("independent Runtime, State, Tooling, and AI metadata sources qualify as high confidence", () => {
  const root = "/synthetic/runtime-profile";
  const candidate = classify([
    evidence(root, "runtime.json", "runtime", "runtime_endpoint", "strong"),
    evidence(root, "state.sqlite", "state", "state_continuity", "strong", "sqlite_schema"),
    evidence(root, "tools.toml", "tooling", "tool_registry", "corroborating", "toml"),
    evidence(root, "models.plist", "ai_metadata", "model_configuration", "corroborating", "plist"),
  ]);

  assert.equal(candidate.confidence, "HIGH_CONFIDENCE");
  assert.equal(candidate.score, 11);
  assert.deepEqual(candidate.families, ["ai_metadata", "runtime", "state", "tooling"]);
  assert.equal(candidate.independentSources, 4);
});

test("package-only, App-bundle, and plausible incomplete evidence remain uncertain", () => {
  const root = "/synthetic/runtime-profile";
  const packageOnly = classify([
    evidence(root, "package.json", "package_metadata", "package_surface", "weak", "package_metadata"),
  ]);
  assert.equal(packageOnly.confidence, "UNCERTAIN");

  const appBundle = classify([
    evidence(root, "runtime.json", "runtime", "runtime_endpoint", "strong"),
    evidence(root, "state.json", "state", "state_continuity", "strong"),
    evidence(root, "tools.json", "tooling", "tool_registry", "corroborating"),
  ], "/synthetic/runtime-profile.app", "APP_BUNDLE");
  assert.equal(appBundle.confidence, "UNCERTAIN");

  const plausible = classify([
    evidence(root, "runtime.json", "runtime", "runtime_endpoint", "strong"),
    evidence(root, "state.json", "state", "state_continuity", "strong"),
  ]);
  assert.equal(plausible.confidence, "UNCERTAIN");
});

test("overlays, one broad document, message-like metadata, and an AI-agent phrase are rejected", () => {
  const root = "/synthetic/overlay";
  const cases: readonly (readonly EvidenceRecord[])[] = [
    [
      evidence(root, "tools.json", "tooling", "tool_registry", "corroborating"),
      evidence(root, "prompts.toml", "ai_metadata", "model_configuration", "corroborating", "toml"),
      evidence(root, "rules.plist", "document", "structured_document", "weak", "plist"),
    ],
    [
      evidence(root, "everything.json", "runtime", "runtime_endpoint", "strong"),
      evidence(root, "everything.json", "state", "state_continuity", "strong"),
      evidence(root, "everything.json", "tooling", "tool_registry", "corroborating"),
      evidence(root, "everything.json", "ai_metadata", "model_configuration", "corroborating"),
    ],
    [evidence(root, "message.json", "document", "structured_document", "weak")],
    [{ ...evidence(root, "note.json", "document", "structured_document", "weak"), metadata: ["AI agent"] }],
  ];

  for (const records of cases) {
    assert.equal(classify(records, root).confidence, "REJECTED");
  }
});

test("duplicate signals from one source cannot inflate source, family, or score gates", () => {
  const root = "/synthetic/runtime-profile";
  const repeated = Array.from({ length: 12 }, () =>
    evidence(root, "runtime.json", "runtime", "runtime_endpoint", "strong"));
  const candidate = classify(repeated);

  assert.equal(candidate.confidence, "REJECTED");
  assert.equal(candidate.score, 4);
  assert.equal(candidate.independentSources, 1);
  assert.deepEqual(candidate.families, ["runtime"]);
});
