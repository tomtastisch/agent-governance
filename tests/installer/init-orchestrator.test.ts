import assert from "node:assert/strict";
import { access, mkdir, readFile, rm } from "node:fs/promises";
import { join } from "node:path";
import test from "node:test";

import { resolveManualTarget, resolveTarget } from "../../src/init/bindings.ts";
import { runInit } from "../../src/init/orchestrator.ts";
import {
  INIT_CANCELLED,
  type DiscoveredHarness,
  type InitDependencies,
  type InitOptions,
  type InitPrompt,
  type InitSelection,
  type InitStep,
  type InitTransaction,
} from "../../src/init/types.ts";
import type { InstallResult, InstallerRequest } from "../../src/contracts.ts";
import { InstallerTransaction } from "../../src/transaction.ts";
import { createReleaseFixture } from "../fixtures/installer/release.ts";
import { createTestRoot } from "../fixtures/installer/workspace.ts";

function transactionResult(command: InstallResult["command"], state: InstallResult["state"] = "FRESH"): InstallResult {
  return {
    schemaVersion: 1,
    architecture: "GLOBAL_EXPLICIT_PATH_MANAGED_BLOCK",
    command,
    outcome: "SUCCESS",
    state,
    phase: command === "plan" ? "plan" : command === "verify" ? "verify" : "inspect",
    rollbackStatus: state === "CURRENT" ? "AVAILABLE" : "NOT_REQUIRED",
    capabilities: [],
  };
}

function options(home: string, releaseRoot = join(home, "release"), installationRoot?: string): InitOptions {
  return {
    isTTY: true,
    environment: { home, platform: "linux" },
    releaseRoot,
    ...(installationRoot === undefined ? {} : { installationRoot }),
  };
}

function prompt(
  selections: readonly InitSelection[] | typeof INIT_CANCELLED,
  events: string[],
  approved: boolean | typeof INIT_CANCELLED = true,
): InitPrompt {
  return {
    dispose(): void {},
    step(step: InitStep): void { events.push(`${step.position}/${step.total}:${step.title}`); },
    async selectTargets(): Promise<readonly InitSelection[] | typeof INIT_CANCELLED> {
      events.push("select");
      return selections;
    },
    async confirm(plans): Promise<boolean | typeof INIT_CANCELLED> {
      events.push(`confirm:${plans.map(({ target }) => target.targetRoot).join(",")}`);
      return approved;
    },
  };
}

function fakeTransaction(
  events: string[],
  targetRoot: string,
  state: InstallResult["state"] = "FRESH",
  localVersion: string | undefined = undefined,
): InitTransaction {
  return {
    async status(): Promise<InstallResult> { events.push(`status:${targetRoot}`); return transactionResult("status", state); },
    async plan(command = "install"): Promise<InstallResult> {
      events.push(`plan:${targetRoot}`);
      return { ...transactionResult("plan", state), plan: { schemaVersion: 1, architecture: "GLOBAL_EXPLICIT_PATH_MANAGED_BLOCK", command, state, resources: [], harnessSpecificMutation: false, mcpMutation: false, hookMutation: false, approvalExpansion: false } };
    },
    async install(): Promise<InstallResult> { events.push(`install:${targetRoot}`); return transactionResult("install", "CURRENT"); },
    async update(): Promise<InstallResult> { events.push(`update:${targetRoot}`); return transactionResult("update", "CURRENT"); },
    async verify(): Promise<InstallResult> { events.push(`verify:${targetRoot}`); return transactionResult("verify", "CURRENT"); },
    async localVersion(): Promise<string | undefined> { events.push(`localVersion:${targetRoot}`); return localVersion; },
  };
}

test("resolveManualTarget requires a canonical Markdown entry and never invents a harness preset", () => {
  assert.deepEqual(resolveManualTarget({ targetRoot: "/synthetic/custom-root", entryFile: "CUSTOM.md" }), {
    targetRoot: "/synthetic/custom-root",
    entryFile: "CUSTOM.md",
  });
  assert.throws(() => resolveManualTarget({ entryFile: "AGENTS.md" }), /root/i);
  assert.throws(() => resolveManualTarget({ targetRoot: "/x", entryFile: "../AGENTS.md" }), /traversal/i);
  assert.throws(() => resolveManualTarget({ targetRoot: "/x", entryFile: "config.json" }), /Markdown/i);
});

test("resolveTarget binds a supported harness from the SSOT and rejects unsupported ids", () => {
  const environment = { home: "/home/user", platform: "linux" as const };
  assert.deepEqual(resolveTarget({ harness: { id: "claude", displayName: "Anthropic Claude Code" } }, environment), {
    targetRoot: "/home/user/.claude",
    entryFile: "CLAUDE.md",
  });
  assert.throws(() => resolveTarget({ harness: { id: "pi", displayName: "Pi Coding Agent" } }, environment), /not supported/i);
});

test("runInit discovers harnesses, resolves support and latest, and plans only supported targets", async () => {
  const events: string[] = [];
  const home = "/synthetic/home";
  const claude: DiscoveredHarness = { id: "claude", displayName: "Anthropic Claude Code" };
  const pi: DiscoveredHarness = { id: "pi", displayName: "Pi Coding Agent" };
  const selections: readonly InitSelection[] = [{ harness: claude }];
  const deps: InitDependencies = {
    async discoverHarnesses() { events.push("discover"); return [claude, pi]; },
    async resolveLatestRelease() { events.push("latest"); return "1.4.5"; },
    prompt: prompt(selections, events),
    createTransaction(request): InitTransaction {
      events.push(`create:${request.targetRoot}`);
      return fakeTransaction(events, request.targetRoot, "FRESH");
    },
  };
  const result = await runInit(options(home), deps);
  assert.equal(result.outcome, "SUCCESS");
  assert.deepEqual(result.targets.map(({ target }) => target.targetRoot), ["/synthetic/home/.claude"]);
  assert.equal(events.includes("create:/synthetic/home/.claude"), true);
  assert.equal(events.some((event) => event.includes("pi")), false, "unsupported harness must not be planned");
  assert.ok(events.indexOf("discover") < events.indexOf("select"));
});

test("runInit returns before discovery, prompt, transaction, or mutation without a TTY", async () => {
  const events: string[] = [];
  const deps: InitDependencies = {
    async discoverHarnesses() { events.push("discover"); return []; },
    async resolveLatestRelease() { events.push("latest"); return undefined; },
    prompt: prompt([], events),
    createTransaction(): InitTransaction { events.push("transaction"); return fakeTransaction(events, "unused"); },
  };
  const result = await runInit({ ...options("/synthetic/home"), isTTY: false }, deps);
  assert.deepEqual(result, {
    schemaVersion: 1,
    command: "init",
    outcome: "INVALID_INVOCATION",
    reason: "NON_TTY",
    guidance: "Use an explicit transaction command with --non-interactive.",
    targets: [],
  });
  assert.deepEqual(events, []);
});

test("runInit cancellation in step two performs no mutation", async () => {
  const events: string[] = [];
  const deps: InitDependencies = {
    async discoverHarnesses() { events.push("discover"); return [{ id: "claude", displayName: "Anthropic Claude Code" }]; },
    async resolveLatestRelease() { events.push("latest"); return undefined; },
    prompt: prompt(INIT_CANCELLED, events),
    createTransaction(request): InitTransaction { events.push(`create:${request.targetRoot}`); return fakeTransaction(events, request.targetRoot, "FRESH"); },
  };
  const result = await runInit(options("/synthetic/home"), deps);
  assert.equal(result.outcome, "INTERRUPTED");
  assert.equal(result.reason, "CANCELLED");
  assert.equal(events.includes("install:/synthetic/home/.claude"), false);
});

test("runInit creates no filesystem mutation when aggregate approval is declined", async () => {
  const root = await createTestRoot("agent-governance-init-decline-");
  const installationRoot = join(root, "installation");
  const releaseRoot = await createReleaseFixture(join(root, "release"));
  await mkdir(join(root, ".claude"), { recursive: true });
  try {
    const result = await runInit(options(root, releaseRoot, installationRoot), {
      async discoverHarnesses() { return [{ id: "claude", displayName: "Anthropic Claude Code" }]; },
      async resolveLatestRelease() { return undefined; },
      prompt: prompt([{ harness: { id: "claude", displayName: "Anthropic Claude Code" } }], [], false),
      createTransaction: (request) => new InstallerTransaction(request),
    });
    assert.equal(result.outcome, "INTERRUPTED");
    await assert.rejects(access(join(root, ".claude", "CLAUDE.md")));
    await assert.rejects(access(installationRoot));
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("runInit installs and verifies a supported harness with the real transaction", async () => {
  const root = await createTestRoot("agent-governance-init-real-");
  const installationRoot = join(root, "installation");
  const releaseRoot = await createReleaseFixture(join(root, "release"));
  await mkdir(join(root, ".claude"), { recursive: true });
  try {
    const result = await runInit(options(root, releaseRoot, installationRoot), {
      async discoverHarnesses() { return [{ id: "claude", displayName: "Anthropic Claude Code" }]; },
      async resolveLatestRelease() { return undefined; },
      prompt: prompt([{ harness: { id: "claude", displayName: "Anthropic Claude Code" } }], []),
      createTransaction: (request) => new InstallerTransaction(request),
    });
    assert.equal(result.outcome, "SUCCESS");
    assert.match(await readFile(join(root, ".claude", "CLAUDE.md"), "utf8"), /AGENT_GOVERNANCE_MANAGED_V1/);
    assert.deepEqual(result.targets.map(({ state }) => state), ["CURRENT"]);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("runInit treats a throwing harness discovery as unavailable and never falls back to a heuristic", async () => {
  const events: string[] = [];
  const deps: InitDependencies = {
    async discoverHarnesses(): Promise<DiscoveredHarness[]> { events.push("discover"); throw new Error("dependency failure"); },
    async resolveLatestRelease() { events.push("latest"); return undefined; },
    prompt: {
      ...prompt([], events),
      dispose: () => { events.push("dispose"); },
    },
    createTransaction(): InitTransaction { events.push("transaction"); return fakeTransaction(events, "unused"); },
  };
  await assert.rejects(runInit(options("/synthetic/home"), deps), /dependency failure/);
  assert.equal(events.at(-1), "dispose");
  assert.equal(events.includes("transaction"), false);
});

test("runInit keeps an OUTDATED binding on the update path and verifies it", async () => {
  const root = await createTestRoot("agent-governance-init-update-");
  try {
    const targetRoot = join(root, ".claude");
    await mkdir(targetRoot, { recursive: true });
    const oldRelease = await createReleaseFixture(join(root, "old"), "1.0.1");
    const releaseRoot = await createReleaseFixture(join(root, "new"), "1.1.0");
    const installationRoot = join(root, "installation");
    const request: InstallerRequest = { targetRoot, entryFile: "CLAUDE.md", scope: "global", installationRoot, releaseRoot: oldRelease, dryRun: false, nonInteractive: false };
    await new InstallerTransaction(request).install();
    const result = await runInit(options(root, releaseRoot, installationRoot), {
      async discoverHarnesses() { return [{ id: "claude", displayName: "Anthropic Claude Code" }]; },
      async resolveLatestRelease() { return "1.1.0"; },
      prompt: prompt([{ harness: { id: "claude", displayName: "Anthropic Claude Code" } }], []),
      createTransaction: (input) => new InstallerTransaction(input),
    });
    assert.equal(result.outcome, "SUCCESS");
    assert.equal(result.targets[0]?.previousState, "OUTDATED");
    assert.match(await readFile(join(targetRoot, "CLAUDE.md"), "utf8"), /1\.1\.0/);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
