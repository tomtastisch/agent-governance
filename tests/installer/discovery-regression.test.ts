import assert from "node:assert/strict";
import { mkdir, mkdtemp, realpath, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { loadDiscoveryCatalog } from "../../src/discovery/catalog.ts";
import { classifyEvidence } from "../../src/discovery/classifier.ts";
import { resolveCandidateIdentity } from "../../src/discovery/identity.ts";
import { discoverCandidates } from "../../src/discovery/index.ts";
import { createClackPrompt, type ClackPromptOperations } from "../../src/init/prompt.ts";
import { INIT_CANCELLED } from "../../src/init/types.ts";
import type { CandidateClass, EvidenceFamily, EvidenceRecord, EvidenceStrength } from "../../src/discovery/types.ts";

const catalog = loadDiscoveryCatalog();

function fixtureRecords(root: string, shape: "high" | "package" | "app" | "overlay"): readonly EvidenceRecord[] {
  const rows: Array<[string, EvidenceFamily, string, EvidenceStrength, EvidenceRecord["sourceKind"]]> =
    shape === "package"
      ? [["package.json", "package_metadata", "package_surface", "weak", "package_metadata"]]
      : shape === "overlay"
        ? [
          ["tools.json", "tooling", "tool_registry", "corroborating", "json"],
          ["prompts.toml", "ai_metadata", "model_configuration", "corroborating", "toml"],
          ["rules.plist", "document", "structured_document", "weak", "plist"],
        ]
        : [
          ["runtime.json", "runtime", "runtime_endpoint", "strong", "json"],
          ["state.json", "state", "state_continuity", "strong", "json"],
          ["tools.json", "tooling", "tool_registry", "corroborating", "json"],
        ];
  return rows.map(([name, family, signalId, strength, sourceKind]) => Object.freeze({
    family,
    sourceKind,
    sourcePath: `${root}/${name}`,
    signalId,
    strength,
    status: "COMPLETE" as const,
    metadata: Object.freeze([signalId]),
  }));
}

test("the synthetic seven-label fixture conservatively recognizes six without label-driven rules", () => {
  const fixtures: ReadonlyArray<{ label: string; shape: "high" | "package" | "app" | "overlay"; class: CandidateClass }> = [
    { label: "Known target 1", shape: "high", class: "DIRECTORY" },
    { label: "Known target 2", shape: "high", class: "DIRECTORY" },
    { label: "Known target 3", shape: "high", class: "DIRECTORY" },
    { label: "Known target 4", shape: "high", class: "DIRECTORY" },
    { label: "Known target 5", shape: "package", class: "DIRECTORY" },
    { label: "Known target 6", shape: "app", class: "APP_BUNDLE" },
    { label: "Unrelated overlay", shape: "overlay", class: "DIRECTORY" },
  ];

  const results = fixtures.map((fixture, index) => {
    const root = `/synthetic/candidate-${index}${fixture.class === "APP_BUNDLE" ? ".app" : ""}`;
    const evidence = fixtureRecords(root, fixture.shape);
    return {
      label: fixture.label,
      candidate: classifyEvidence(evidence, catalog, {
        root,
        candidateClass: fixture.class,
        status: "COMPLETE",
        fileCount: evidence.length,
        activityAt: 100,
      }),
    };
  });

  assert.equal(results.filter(({ candidate }) => candidate.confidence !== "REJECTED").length, 6);
  assert.equal(results.filter(({ candidate }) => candidate.confidence === "HIGH_CONFIDENCE").length, 4);
  assert.equal(results.at(-1)?.candidate.confidence, "REJECTED");
});

test("display identity is available only after positive classification and sanitizes local labels", () => {
  const positiveRoot = "/synthetic/runtime\u001b-profile";
  const positiveEvidence = fixtureRecords(positiveRoot, "high");
  const positive = classifyEvidence(positiveEvidence, catalog, {
    root: positiveRoot,
    candidateClass: "DIRECTORY",
    status: "COMPLETE",
    fileCount: positiveEvidence.length,
  });
  const rejectedRoot = "/synthetic/overlay";
  const rejectedEvidence = fixtureRecords(rejectedRoot, "overlay");
  const rejected = classifyEvidence(rejectedEvidence, catalog, {
    root: rejectedRoot,
    candidateClass: "DIRECTORY",
    status: "COMPLETE",
    fileCount: rejectedEvidence.length,
  });

  assert.equal(resolveCandidateIdentity(positive).label, "runtime?-profile");
  assert.throws(() => resolveCandidateIdentity(rejected), /positive classification/i);
});

test("discoverCandidates classifies only passive generic structure from a synthetic environment", async () => {
  const fixture = await realpath(await mkdtemp(join(tmpdir(), "agent-governance-discovery-index-")));
  const home = join(fixture, "home");
  const config = join(fixture, "config");
  const candidate = join(config, "runtime-profile");
  try {
    await Promise.all([mkdir(home), mkdir(candidate, { recursive: true })]);
    await Promise.all([
      writeFile(join(candidate, "runtime.json"), JSON.stringify({ transport: "local", command: "passive" })),
      writeFile(join(candidate, "state.json"), JSON.stringify({ sessions: [] })),
      writeFile(join(candidate, "tools.json"), JSON.stringify({ tools: [] })),
    ]);

    const discovered = await discoverCandidates({
      environment: { home, xdgConfigHome: config, platform: "linux" },
      clock: () => 0,
    });

    assert.deepEqual(discovered.map(({ root }) => root), [candidate]);
    assert.equal(discovered[0]?.confidence, "HIGH_CONFIDENCE");
  } finally {
    await rm(fixture, { recursive: true, force: true });
  }
});

test("a completely unknown governance-capable AI environment is discovered and offered in step two", async () => {
  const fixture = await realpath(await mkdtemp(join(tmpdir(), "agent-governance-unknown-environment-")));
  const home = join(fixture, "home");
  const config = join(fixture, "config");
  const candidate = join(config, "AsterveilAI");
  const cancel = Symbol("cancel");
  let offeredValues: readonly string[] = [];
  const operations: ClackPromptOperations = {
    autocompleteMultiselect: async ({ options }) => {
      offeredValues = options.map(({ value }) => value);
      return cancel;
    },
    path: async () => { throw new Error("unexpected path prompt"); },
    confirm: async () => { throw new Error("unexpected confirm prompt"); },
    spinner: () => ({ start() {}, stop() {} }),
    cancel() {},
    isCancel: (value) => value === cancel,
  };
  try {
    await Promise.all([mkdir(home), mkdir(candidate, { recursive: true })]);
    await Promise.all([
      writeFile(join(candidate, "runtime.toml"), 'transport = "local"\ncommand = "serve"\n'),
      writeFile(join(candidate, "sessions.json"), JSON.stringify({ sessions: [] })),
      writeFile(join(candidate, "capabilities.json"), JSON.stringify({ capabilities: [] })),
      writeFile(join(candidate, "bindings.json"), JSON.stringify({ instructions: [], rules: [] })),
    ]);

    const discovered = await discoverCandidates({
      environment: { home, xdgConfigHome: config, platform: "linux" },
      clock: () => 0,
    });
    const selection = await createClackPrompt({
      prompts: operations,
      columns: 60,
      environment: { NO_COLOR: "1" },
    }).selectTargets(discovered);

    assert.equal(selection, INIT_CANCELLED);
    assert.deepEqual(discovered.map(({ root }) => root), [candidate]);
    assert.equal(discovered[0]?.confidence, "HIGH_CONFIDENCE");
    assert.deepEqual(discovered[0]?.families, ["document", "runtime", "state", "tooling"]);
    assert.equal(offeredValues.includes(candidate), true);
  } finally {
    await rm(fixture, { recursive: true, force: true });
  }
});

test("a standalone model cache is not offered as a governance target", async () => {
  const fixture = await realpath(await mkdtemp(join(tmpdir(), "agent-governance-model-cache-")));
  const home = join(fixture, "home");
  const data = join(fixture, "data");
  const modelCache = join(data, "AsterveilModelCache");
  try {
    await Promise.all([mkdir(home), mkdir(modelCache, { recursive: true })]);
    await Promise.all([
      writeFile(join(modelCache, "models.json"), JSON.stringify({ models: [], providers: [] })),
      writeFile(join(modelCache, "weights.gguf"), "synthetic-model-artifact"),
    ]);

    const discovered = await discoverCandidates({
      environment: { home, xdgDataHome: data, platform: "linux" },
      clock: () => 0,
    });

    assert.deepEqual(discovered, []);
  } finally {
    await rm(fixture, { recursive: true, force: true });
  }
});
