import assert from "node:assert/strict";
import { chmod, mkdir, mkdtemp, realpath, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { enumerateCandidates } from "../../src/discovery/filesystem.ts";
import { discoverZones } from "../../src/discovery/zones.ts";
import type { DiscoveryLimits, DiscoveryZone } from "../../src/discovery/types.ts";

const LIMITS: DiscoveryLimits = Object.freeze({
  maxDepth: 4,
  maxFiles: 64,
  maxEntries: 256,
  maxFileBytes: 1024,
  maxSqliteObjects: 16,
  maxSqliteColumns: 32,
  maxDurationMs: 1_000,
  maxMetadataLength: 80,
});

async function syntheticEnvironment(): Promise<{
  root: string;
  home: string;
  xdgConfig: string;
  xdgData: string;
  systemApplications: string;
}> {
  const root = await realpath(await mkdtemp(join(tmpdir(), "agent-governance-discovery-zones-")));
  const home = join(root, "home");
  const xdgConfig = join(root, "xdg-config");
  const xdgData = join(root, "xdg-data");
  const systemApplications = join(root, "system-applications");
  await Promise.all([
    mkdir(home, { recursive: true }),
    mkdir(xdgConfig, { recursive: true }),
    mkdir(xdgData, { recursive: true }),
    mkdir(join(home, "Library", "Application Support"), { recursive: true }),
    mkdir(join(home, "Applications"), { recursive: true }),
    mkdir(systemApplications, { recursive: true }),
  ]);
  return { root, home, xdgConfig, xdgData, systemApplications };
}

test("discoverZones uses only direct synthetic HOME, XDG, and macOS application zones", async () => {
  const fixture = await syntheticEnvironment();
  try {
    const zones = discoverZones({
      home: fixture.home,
      xdgConfigHome: fixture.xdgConfig,
      xdgDataHome: fixture.xdgData,
      platform: "darwin",
      macosSystemApplications: fixture.systemApplications,
    });
    assert.deepEqual(zones.map(({ id }) => id), [
      "home",
      "xdg_config",
      "xdg_data",
      "macos_application_support",
      "macos_user_applications",
      "macos_system_applications",
    ]);
    assert.equal(zones.every(({ root }) => root.startsWith(fixture.root)), true);
    assert.deepEqual(zones.slice(-2).map(({ candidateClass }) => candidateClass), [
      "APP_BUNDLE",
      "APP_BUNDLE",
    ]);
  } finally {
    await rm(fixture.root, { recursive: true, force: true });
  }
});

test("discoverZones rejects a symlinked supplied zone instead of following it", async () => {
  const fixture = await syntheticEnvironment();
  const link = join(fixture.root, "linked-config");
  try {
    await symlink(fixture.xdgConfig, link, "dir");
    assert.throws(
      () => discoverZones({ home: fixture.home, xdgConfigHome: link, platform: "linux" }),
      /symlink|canonical/i,
    );
  } finally {
    await rm(fixture.root, { recursive: true, force: true });
  }
});

test("discoverZones ignores absent optional XDG zones without widening beyond HOME", async () => {
  const fixture = await syntheticEnvironment();
  try {
    const zones = discoverZones({
      home: fixture.home,
      xdgConfigHome: join(fixture.root, "absent-config"),
      xdgDataHome: join(fixture.root, "absent-data"),
      platform: "linux",
    });
    assert.deepEqual(zones, [{ id: "home", root: fixture.home, candidateClass: "DIRECTORY" }]);
  } finally {
    await rm(fixture.root, { recursive: true, force: true });
  }
});

test("enumeration finds generic directory and app-bundle candidates without following symlinks", async () => {
  const fixture = await syntheticEnvironment();
  const configCandidate = join(fixture.xdgConfig, "runtime-a");
  const appCandidate = join(fixture.systemApplications, "runtime-b.app");
  const outside = join(fixture.root, "outside");
  try {
    await Promise.all([
      mkdir(configCandidate),
      mkdir(join(appCandidate, "Contents"), { recursive: true }),
      mkdir(outside),
    ]);
    await Promise.all([
      writeFile(join(configCandidate, "state.json"), "{}"),
      writeFile(join(appCandidate, "Contents", "Info.plist"), "<plist><dict></dict></plist>"),
      writeFile(join(outside, "private.json"), '{"secret":"must-not-be-seen"}'),
      symlink(outside, join(configCandidate, "linked"), "dir"),
    ]);

    const zones: readonly DiscoveryZone[] = [
      { id: "config", root: fixture.xdgConfig, candidateClass: "DIRECTORY" },
      { id: "apps", root: fixture.systemApplications, candidateClass: "APP_BUNDLE" },
    ];
    const candidates = await enumerateCandidates(zones, LIMITS, () => 0);

    assert.deepEqual(candidates.map(({ root }) => root), [configCandidate, appCandidate]);
    assert.deepEqual(candidates.map(({ candidateClass }) => candidateClass), ["DIRECTORY", "APP_BUNDLE"]);
    assert.equal(candidates.flatMap(({ files }) => files).some((path) => path.includes("private.json")), false);
    assert.equal(candidates[0]?.issues.includes("SYMLINK_SKIPPED"), true);
    assert.equal(candidates[0]?.status, "INCOMPLETE");
  } finally {
    await rm(fixture.root, { recursive: true, force: true });
  }
});

test("enumeration marks candidates incomplete at permission and file-size boundaries", async () => {
  const fixture = await syntheticEnvironment();
  const candidate = join(fixture.xdgConfig, "runtime-a");
  const denied = join(candidate, "denied");
  try {
    await mkdir(denied, { recursive: true });
    await writeFile(join(candidate, "oversized.json"), "x".repeat(LIMITS.maxFileBytes + 1));
    await writeFile(join(denied, "hidden.json"), "{}");
    await chmod(denied, 0o000);

    const candidates = await enumerateCandidates(
      [{ id: "config", root: fixture.xdgConfig, candidateClass: "DIRECTORY" }],
      LIMITS,
      () => 0,
    );
    assert.equal(candidates.length, 1);
    assert.equal(candidates[0]?.status, "INCOMPLETE");
    assert.equal(candidates[0]?.issues.includes("FILE_SIZE_LIMIT"), true);
    assert.equal(candidates[0]?.issues.includes("PERMISSION_DENIED"), true);
    assert.deepEqual(candidates[0]?.files, []);
  } finally {
    await chmod(denied, 0o700).catch(() => undefined);
    await rm(fixture.root, { recursive: true, force: true });
  }
});

test("enumeration enforces file, depth, entry, and deadline budgets", async () => {
  const scenarios: ReadonlyArray<{
    name: string;
    limits: DiscoveryLimits;
    expectedIssue: "FILE_LIMIT" | "DEPTH_LIMIT" | "ENTRY_LIMIT" | "TIME_LIMIT";
    clock?: () => number;
  }> = [
    { name: "file", limits: { ...LIMITS, maxFiles: 1 }, expectedIssue: "FILE_LIMIT" },
    { name: "depth", limits: { ...LIMITS, maxDepth: 1 }, expectedIssue: "DEPTH_LIMIT" },
    { name: "entry", limits: { ...LIMITS, maxEntries: 3 }, expectedIssue: "ENTRY_LIMIT" },
    {
      name: "time",
      limits: { ...LIMITS, maxDurationMs: 2 },
      expectedIssue: "TIME_LIMIT",
      clock: (() => {
        let tick = 0;
        return () => tick++;
      })(),
    },
  ];

  for (const scenario of scenarios) {
    const fixture = await syntheticEnvironment();
    const candidate = join(fixture.xdgConfig, `runtime-${scenario.name}`);
    try {
      await mkdir(join(candidate, "nested", "deeper"), { recursive: true });
      await Promise.all([
        writeFile(join(candidate, "one.json"), "{}"),
        writeFile(join(candidate, "two.json"), "{}"),
        writeFile(join(candidate, "nested", "three.json"), "{}"),
        writeFile(join(candidate, "nested", "deeper", "four.json"), "{}"),
      ]);
      const candidates = await enumerateCandidates(
        [{ id: "config", root: fixture.xdgConfig, candidateClass: "DIRECTORY" }],
        scenario.limits,
        scenario.clock ?? (() => 0),
      );
      assert.equal(candidates[0]?.status, "INCOMPLETE", scenario.name);
      assert.equal(candidates[0]?.issues.includes(scenario.expectedIssue), true, scenario.name);
      assert.equal(candidates[0]!.files.length <= scenario.limits.maxFiles, true, scenario.name);
      assert.equal(candidates[0]!.entriesVisited <= scenario.limits.maxEntries, true, scenario.name);
    } finally {
      await rm(fixture.root, { recursive: true, force: true });
    }
  }
});
