import assert from "node:assert/strict";
import fsPromises from "node:fs/promises";
import { syncBuiltinESMExports } from "node:module";
import { link, mkdir, mkdtemp, readFile, realpath, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { loadDiscoveryCatalog } from "../../src/discovery/catalog.ts";
import { classifyEvidence } from "../../src/discovery/classifier.ts";
import { resolveCandidateIdentity } from "../../src/discovery/identity.ts";
import { discoverCandidates } from "../../src/discovery/index.ts";
import { enumerateCandidates } from "../../src/discovery/filesystem.ts";
import type { CandidateClass, EvidenceFamily, EvidenceRecord, EvidenceStrength } from "../../src/discovery/types.ts";
import { createReleaseFixture } from "../fixtures/installer/release.ts";

const catalog = loadDiscoveryCatalog();

for (const phase of ["enumeration", "analysis"] as const) {
  test(`later zones retain time after slow early ${phase}`, async () => {
    const fixture = await realpath(await mkdtemp(join(tmpdir(), "agent-governance-discovery-time-fairness-")));
    const home = join(fixture, "home");
    const config = join(fixture, "config");
    const noise = join(home, "noise");
    const candidate = join(config, "runtime-profile");
    let elapsed = 0;
    const originalLstat = fsPromises.lstat;
    const originalOpen = fsPromises.open;
    try {
      await mkdir(noise, { recursive: true });
      await mkdir(candidate, { recursive: true });
      for (let index = 0; index < 80; index += 1) await writeFile(join(noise, `${index}.json`), "{}");
      await writeFile(join(candidate, "runtime.json"), '{"transport":"local","command":"passive"}');
      await writeFile(join(candidate, "state.json"), '{"sessions":[]}');
      await writeFile(join(candidate, "tools.json"), '{"tools":[]}');
      fsPromises.lstat = (async (...args: Parameters<typeof originalLstat>) => {
        if (phase === "enumeration" && String(args[0]).startsWith(`${noise}/`)) elapsed += 5;
        return originalLstat(...args);
      }) as typeof originalLstat;
      fsPromises.open = (async (...args: Parameters<typeof originalOpen>) => {
        const handle = await originalOpen(...args);
        if (phase === "analysis" && String(args[0]).startsWith(`${noise}/`)) {
          const read = handle.read.bind(handle);
          handle.read = ((...readArgs: Parameters<typeof read>) => {
            elapsed += 10;
            return read(...readArgs);
          }) as typeof handle.read;
        }
        return handle;
      }) as typeof originalOpen;
      syncBuiltinESMExports();
      if (phase === "enumeration") {
        const enumerated = await enumerateCandidates([
          { id: "home", root: home, candidateClass: "DIRECTORY" },
          { id: "xdg_config", root: config, candidateClass: "DIRECTORY" },
        ], catalog.limits, () => elapsed);
        assert.equal(enumerated.some(({ root, files }) => root === candidate && files.length === 3), true);
        elapsed = 0;
      }
      const discovered = await discoverCandidates({
        environment: { home, xdgConfigHome: config, platform: "linux" },
        clock: () => elapsed,
      });
      assert.equal(discovered.find(({ root }) => root === candidate)?.confidence, "HIGH_CONFIDENCE");
      assert.equal(elapsed < catalog.limits.maxDurationMs, true);
    } finally {
      fsPromises.lstat = originalLstat;
      fsPromises.open = originalOpen;
      syncBuiltinESMExports();
      await rm(fixture, { recursive: true, force: true });
    }
  });
}

test("hard-linked evidence cannot impersonate independent physical sources", async () => {
  const fixture = await realpath(await mkdtemp(join(tmpdir(), "agent-governance-discovery-hardlinks-")));
  const home = join(fixture, "home");
  const candidate = join(home, "runtime-profile");
  const content = JSON.stringify({ transport: "local", command: "passive", sessions: [], tools: [] });
  try {
    await mkdir(candidate, { recursive: true });
    await writeFile(join(candidate, "runtime.json"), content);
    await link(join(candidate, "runtime.json"), join(candidate, "state.json"));
    await link(join(candidate, "runtime.json"), join(candidate, "tools.json"));
    const options = { environment: { home, platform: "linux" as const }, clock: () => 0 };
    assert.deepEqual(await discoverCandidates(options), []);
    await rm(join(candidate, "state.json"));
    await rm(join(candidate, "tools.json"));
    await writeFile(join(candidate, "state.json"), content);
    await writeFile(join(candidate, "tools.json"), content);
    const independent = await discoverCandidates(options);
    assert.equal(independent[0]?.confidence, "HIGH_CONFIDENCE");
    assert.equal(independent[0]?.independentSources, 3);
  } finally {
    await rm(fixture, { recursive: true, force: true });
  }
});

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
    sourceIdentity: `${root}/${name}`,
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

test("a large early candidate cannot hide a real candidate in a later discovery zone", async () => {
  const fixture = await realpath(await mkdtemp(join(tmpdir(), "agent-governance-discovery-fairness-")));
  const home = join(fixture, "home");
  const config = join(fixture, "config");
  const largeCandidate = join(home, "wide-container");
  const realCandidate = join(config, "runtime-profile");
  const releaseRoot = await createReleaseFixture(join(fixture, "release"));
  const catalogPath = join(releaseRoot, "bundle", "agent-governance", "ssot", "discovery", "discovery-signals.toml");
  try {
    await Promise.all([
      mkdir(largeCandidate, { recursive: true }),
      mkdir(realCandidate, { recursive: true }),
    ]);
    const source = await readFile(catalogPath, "utf8");
    const constrainedCatalog = source.replace("max_files = 256", "max_files = 6");
    assert.notEqual(constrainedCatalog, source);
    await writeFile(catalogPath, constrainedCatalog);
    await Promise.all([
      ...Array.from({ length: 7 }, (_, index) =>
        writeFile(join(largeCandidate, `noise-${index}.json`), "{}")),
      writeFile(join(realCandidate, "runtime.json"), JSON.stringify({ transport: "local", command: "passive" })),
      writeFile(join(realCandidate, "state.json"), JSON.stringify({ sessions: [] })),
      writeFile(join(realCandidate, "tools.json"), JSON.stringify({ tools: [] })),
    ]);

    const discovered = await discoverCandidates({
      environment: { home, xdgConfigHome: config, platform: "linux" },
      releaseRoot,
      clock: () => 0,
    });

    assert.deepEqual(discovered.map(({ root }) => root), [realCandidate]);
    assert.equal(discovered[0]?.confidence, "HIGH_CONFIDENCE");
  } finally {
    await rm(fixture, { recursive: true, force: true });
  }
});

test("multiple broad candidates share their early zone budget so a later real candidate is surfaced", async () => {
  const fixture = await realpath(await mkdtemp(join(tmpdir(), "agent-governance-discovery-zone-fairness-")));
  const home = join(fixture, "home");
  const config = join(fixture, "config");
  const broadCandidates = [join(home, "wide-a"), join(home, "wide-b")];
  const realCandidate = join(config, "runtime-profile");
  const releaseRoot = await createReleaseFixture(join(fixture, "release"));
  const catalogPath = join(releaseRoot, "bundle", "agent-governance", "ssot", "discovery", "discovery-signals.toml");
  try {
    await Promise.all([
      ...broadCandidates.map((candidate) => mkdir(candidate, { recursive: true })),
      mkdir(realCandidate, { recursive: true }),
    ]);
    const source = await readFile(catalogPath, "utf8");
    const constrainedCatalog = source.replace("max_files = 256", "max_files = 6");
    assert.notEqual(constrainedCatalog, source);
    await writeFile(catalogPath, constrainedCatalog);
    await Promise.all([
      ...broadCandidates.flatMap((candidate) =>
        Array.from({ length: 7 }, (_, index) =>
          writeFile(join(candidate, `noise-${index}.json`), "{}"))),
      writeFile(join(realCandidate, "runtime.json"), JSON.stringify({ transport: "local", command: "passive" })),
      writeFile(join(realCandidate, "state.json"), JSON.stringify({ sessions: [] })),
      writeFile(join(realCandidate, "tools.json"), JSON.stringify({ tools: [] })),
    ]);

    const discovered = await discoverCandidates({
      environment: { home, xdgConfigHome: config, platform: "linux" },
      releaseRoot,
      clock: () => 0,
    });

    assert.deepEqual(discovered.map(({ root }) => root), [realCandidate]);
    assert.equal(discovered[0]?.confidence, "HIGH_CONFIDENCE");
  } finally {
    await rm(fixture, { recursive: true, force: true });
  }
});

test("an exhausted early zone preserves the entry budget for a later real candidate", async () => {
  const fixture = await realpath(await mkdtemp(join(tmpdir(), "agent-governance-discovery-entry-fairness-")));
  const home = join(fixture, "home");
  const config = join(fixture, "config");
  const broadCandidates = Array.from({ length: 4 }, (_, index) => join(home, `wide-${index}`));
  const realCandidate = join(config, "runtime-profile");
  const releaseRoot = await createReleaseFixture(join(fixture, "release"));
  const catalogPath = join(releaseRoot, "bundle", "agent-governance", "ssot", "discovery", "discovery-signals.toml");
  try {
    await Promise.all([
      ...broadCandidates.map((candidate) => mkdir(candidate, { recursive: true })),
      mkdir(realCandidate, { recursive: true }),
    ]);
    const source = await readFile(catalogPath, "utf8");
    const constrainedCatalog = source
      .replace("max_files = 256", "max_files = 6")
      .replace("max_entries = 4096", "max_entries = 10");
    assert.notEqual(constrainedCatalog, source);
    await writeFile(catalogPath, constrainedCatalog);
    await Promise.all([
      ...broadCandidates.flatMap((candidate) =>
        Array.from({ length: 4 }, (_, index) =>
          writeFile(join(candidate, `noise-${index}.json`), "{}"))),
      writeFile(join(realCandidate, "runtime.json"), JSON.stringify({ transport: "local", command: "passive" })),
      writeFile(join(realCandidate, "state.json"), JSON.stringify({ sessions: [] })),
      writeFile(join(realCandidate, "tools.json"), JSON.stringify({ tools: [] })),
    ]);

    const discovered = await discoverCandidates({
      environment: { home, xdgConfigHome: config, platform: "linux" },
      releaseRoot,
      clock: () => 0,
    });

    assert.deepEqual(discovered.map(({ root }) => root), [realCandidate]);
    assert.equal(discovered[0]?.confidence, "HIGH_CONFIDENCE");
  } finally {
    await rm(fixture, { recursive: true, force: true });
  }
});

test("empty directories in an early zone cannot hide a later real candidate", async () => {
  const fixture = await realpath(await mkdtemp(join(tmpdir(), "agent-governance-discovery-empty-entry-fairness-")));
  const home = join(fixture, "home");
  const config = join(fixture, "config");
  const noise = join(home, "wide-empty-container");
  const realCandidate = join(config, "runtime-profile");
  const releaseRoot = await createReleaseFixture(join(fixture, "release"));
  const catalogPath = join(releaseRoot, "bundle", "agent-governance", "ssot", "discovery", "discovery-signals.toml");
  try {
    await Promise.all([mkdir(noise, { recursive: true }), mkdir(realCandidate, { recursive: true })]);
    for (let index = 0; index < 12; index += 1) {
      await mkdir(join(noise, `empty-${String(index).padStart(2, "0")}`));
    }
    const source = await readFile(catalogPath, "utf8");
    const constrainedCatalog = source.replace("max_entries = 4096", "max_entries = 10");
    assert.notEqual(constrainedCatalog, source);
    await writeFile(catalogPath, constrainedCatalog);
    await Promise.all([
      writeFile(join(realCandidate, "runtime.json"), JSON.stringify({ transport: "local", command: "passive" })),
      writeFile(join(realCandidate, "state.json"), JSON.stringify({ sessions: [] })),
      writeFile(join(realCandidate, "tools.json"), JSON.stringify({ tools: [] })),
    ]);

    const discovered = await discoverCandidates({
      environment: { home, xdgConfigHome: config, platform: "linux" },
      releaseRoot,
      clock: () => 0,
    });

    assert.deepEqual(discovered.map(({ root }) => root), [realCandidate]);
    assert.equal(discovered[0]?.confidence, "HIGH_CONFIDENCE");
  } finally {
    await rm(fixture, { recursive: true, force: true });
  }
});

test("discoverCandidates applies one injected-clock deadline to enumeration and evidence analysis", async () => {
  const fixture = await realpath(await mkdtemp(join(tmpdir(), "agent-governance-discovery-deadline-")));
  const home = join(fixture, "home");
  const config = join(fixture, "config");
  const candidate = join(config, "runtime-profile");
  let elapsed = 0;
  const originalOpen = fsPromises.open;
  try {
    await Promise.all([mkdir(home), mkdir(candidate, { recursive: true })]);
    await Promise.all([
      writeFile(join(candidate, "runtime.json"), JSON.stringify({ transport: "local", command: "passive" })),
      writeFile(join(candidate, "state.json"), JSON.stringify({ sessions: [] })),
      writeFile(join(candidate, "tools.json"), JSON.stringify({ tools: [] })),
    ]);

    fsPromises.open = (async (...args: Parameters<typeof originalOpen>) => {
      const handle = await originalOpen(...args);
      if (String(args[0]) === join(candidate, "state.json")) elapsed = catalog.limits.maxDurationMs;
      return handle;
    }) as typeof originalOpen;
    syncBuiltinESMExports();
    const discovered = await discoverCandidates({
      environment: { home, xdgConfigHome: config, platform: "linux" },
      clock: () => elapsed,
    });

    assert.equal(discovered.length, 1);
    assert.equal(discovered[0]?.status, "INCOMPLETE");
    assert.equal(discovered[0]?.confidence, "UNCERTAIN");
    assert.deepEqual(
      [...new Set(discovered[0]?.evidence.map(({ sourcePath }) => sourcePath))].map((path) => path.split("/").at(-1)),
      ["runtime.json", "state.json"],
    );
  } finally {
    fsPromises.open = originalOpen;
    syncBuiltinESMExports();
    await rm(fixture, { recursive: true, force: true });
  }
});

test("discoverCandidates uses the selected release catalog for evidence extraction", async () => {
  const fixture = await realpath(await mkdtemp(join(tmpdir(), "agent-governance-discovery-release-catalog-")));
  const home = join(fixture, "home");
  const config = join(fixture, "config");
  const candidate = join(config, "runtime-profile");
  const releaseRoot = await createReleaseFixture(join(fixture, "release"));
  const catalogPath = join(releaseRoot, "bundle", "agent-governance", "ssot", "discovery", "discovery-signals.toml");
  try {
    await Promise.all([mkdir(home), mkdir(candidate, { recursive: true })]);
    const source = await readFile(catalogPath, "utf8");
    const selectedCatalog = source
      .replace('keys = ["transport", "command", "arguments"]', 'keys = ["nebula_transport", "nebula_command"]')
      .replace('keys = ["sessions", "history", "state", "events"]', 'keys = ["nebula_sessions"]')
      .replace('keys = ["tools", "servers", "capabilities"]', 'keys = ["nebula_tools"]');
    assert.notEqual(selectedCatalog, source);
    await writeFile(catalogPath, selectedCatalog);
    await Promise.all([
      writeFile(join(candidate, "runtime.json"), JSON.stringify({ nebula_transport: "local", nebula_command: "passive" })),
      writeFile(join(candidate, "state.json"), JSON.stringify({ nebula_sessions: [] })),
      writeFile(join(candidate, "tools.json"), JSON.stringify({ nebula_tools: [] })),
    ]);

    const discovered = await discoverCandidates({
      environment: { home, xdgConfigHome: config, platform: "linux" },
      releaseRoot,
      clock: () => 0,
    });

    assert.deepEqual(discovered.map(({ root }) => root), [candidate]);
    assert.equal(discovered[0]?.confidence, "HIGH_CONFIDENCE");
  } finally {
    await rm(fixture, { recursive: true, force: true });
  }
});
