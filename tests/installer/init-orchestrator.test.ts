import assert from "node:assert/strict";
import { access, mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import test from "node:test";

import { resolveBinding } from "../../src/init/bindings.ts";
import { runInit } from "../../src/init/orchestrator.ts";
import {
  INIT_CANCELLED,
  type InitBindingSelection,
  type InitDependencies,
  type InitOptions,
  type InitPrompt,
  type InitStep,
  type InitTransaction,
} from "../../src/init/types.ts";
import type { InstallResult, InstallerRequest } from "../../src/contracts.ts";
import type { Candidate } from "../../src/discovery/types.ts";
import { InstallerTransaction } from "../../src/transaction.ts";
import { createReleaseFixture } from "../fixtures/installer/release.ts";
import { createTestRoot } from "../fixtures/installer/workspace.ts";

function candidate(root: string, confidence: Candidate["confidence"] = "HIGH_CONFIDENCE"): Candidate {
  return {
    root,
    candidateClass: "DIRECTORY",
    status: "COMPLETE",
    confidence,
    score: 9,
    families: ["runtime", "state", "tooling"],
    independentSources: 3,
    evidence: [],
    fileCount: 3,
    evidenceDensity: 1,
    activityAt: null,
    evidenceDigest: "a".repeat(64),
  };
}

function transactionResult(
  command: InstallResult["command"],
  state: InstallResult["state"] = "FRESH",
): InstallResult {
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
  selections: readonly InitBindingSelection[] | typeof INIT_CANCELLED,
  events: string[],
  approved: boolean | typeof INIT_CANCELLED = true,
): InitPrompt {
  return {
    dispose(): void {},
    step(step: InitStep): void { events.push(`${step.position}/${step.total}:${step.title}`); },
    async selectTargets(): Promise<readonly InitBindingSelection[] | typeof INIT_CANCELLED> {
      events.push("select");
      return selections;
    },
    async confirm(plans): Promise<boolean | typeof INIT_CANCELLED> {
      events.push(`confirm:${plans.map(({ target }) => target.targetRoot).join(",")}`);
      return approved;
    },
  };
}

function fakeTransaction(events: string[], targetRoot: string, state: InstallResult["state"] = "FRESH"): InitTransaction {
  return {
    async status(): Promise<InstallResult> { events.push(`status:${targetRoot}`); return transactionResult("status", state); },
    async plan(command = "install"): Promise<InstallResult> { events.push(`plan:${targetRoot}`); return { ...transactionResult("plan", state), plan: { schemaVersion: 1, architecture: "GLOBAL_EXPLICIT_PATH_MANAGED_BLOCK", command, state, resources: [], harnessSpecificMutation: false, mcpMutation: false, hookMutation: false, approvalExpansion: false } }; },
    async install(): Promise<InstallResult> { events.push(`install:${targetRoot}`); return transactionResult("install", "CURRENT"); },
    async update(): Promise<InstallResult> { events.push(`update:${targetRoot}`); return transactionResult("update", "CURRENT"); },
    async verify(): Promise<InstallResult> { events.push(`verify:${targetRoot}`); return transactionResult("verify", "CURRENT"); },
  };
}

test("resolveBinding requires an explicit Markdown entry and never invents a harness preset", () => {
  const discovered = candidate("/synthetic/runtime-root");
  assert.deepEqual(resolveBinding(discovered, { entryFile: "nested/AGENTS.md" }), {
    targetRoot: "/synthetic/runtime-root",
    entryFile: "nested/AGENTS.md",
  });
  assert.deepEqual(resolveBinding(undefined, {
    targetRoot: "/synthetic/custom-root",
    entryFile: "CUSTOM.md",
  }), {
    targetRoot: "/synthetic/custom-root",
    entryFile: "CUSTOM.md",
  });
  assert.throws(() => resolveBinding(discovered, { entryFile: "" }), /entry/i);
  assert.throws(() => resolveBinding(discovered, { entryFile: "../AGENTS.md" }), /entry|traversal/i);
  assert.throws(() => resolveBinding(discovered, { entryFile: "config.json" }), /Markdown/i);
  assert.throws(() => resolveBinding(undefined, { entryFile: "AGENTS.md" }), /root/i);
});

test("runInit executes exactly three steps and plans all deterministic targets before one approval and mutation", async () => {
  const root = await createTestRoot("agent-governance-init-order-");
  const alpha = join(root, "alpha");
  const zeta = join(root, "zeta");
  await Promise.all([mkdir(alpha), mkdir(zeta)]);
  const events: string[] = [];
  const candidates = [candidate(zeta), candidate(alpha)];
  const selections: readonly InitBindingSelection[] = [
    { candidate: candidates[0]!, manualInput: { entryFile: "ZETA.md" } },
    { candidate: candidates[1]!, manualInput: { entryFile: "ALPHA.md" } },
  ];
  const deps: InitDependencies = {
    async discoverCandidates(): Promise<readonly Candidate[]> { events.push("discover"); return candidates; },
    prompt: prompt(selections, events),
    createTransaction(request): InitTransaction { events.push(`create:${request.targetRoot}`); return fakeTransaction(events, request.targetRoot); },
  };

  try {
    const result = await runInit(options(root), deps);
    assert.equal(result.outcome, "SUCCESS");
    assert.deepEqual(result.targets.map(({ target }) => target.targetRoot), [alpha, zeta]);
    assert.deepEqual(events, [
      "1/3:Umgebung prüfen",
      "discover",
      "2/3:AI-/LLM-Ziele auswählen",
      "select",
      "3/3:Prüfen und einrichten",
      `create:${alpha}`,
      `status:${alpha}`,
      `plan:${alpha}`,
      `create:${zeta}`,
      `status:${zeta}`,
      `plan:${zeta}`,
      `confirm:${alpha},${zeta}`,
      `install:${alpha}`,
      `verify:${alpha}`,
      `install:${zeta}`,
      `verify:${zeta}`,
    ]);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("runInit uses real InstallerTransaction plan install and verify for every selected target", async () => {
  const root = await createTestRoot("agent-governance-init-real-");
  const first = join(root, "a-target");
  const second = join(root, "b-target");
  const installationRoot = join(root, "installation");
  const releaseRoot = await createReleaseFixture(join(root, "release"));
  await Promise.all([mkdir(first), mkdir(second)]);
  const events: string[] = [];
  const candidates = [candidate(second), candidate(first)];
  const selections: readonly InitBindingSelection[] = [
    { candidate: candidates[0]!, manualInput: { entryFile: "SECOND.md" } },
    { candidate: candidates[1]!, manualInput: { entryFile: "FIRST.md" } },
  ];
  const deps: InitDependencies = {
    async discoverCandidates(): Promise<readonly Candidate[]> { return candidates; },
    prompt: prompt(selections, events),
    createTransaction(request): InitTransaction {
      const transaction = new InstallerTransaction(request);
      const id = request.targetRoot;
      return {
        status: async () => { events.push(`status:${id}`); return transaction.status(); },
        plan: async () => { events.push(`plan:${id}`); return transaction.plan(); },
        install: async () => { events.push(`install:${id}`); return transaction.install(); },
        update: async () => { events.push(`update:${id}`); return transaction.update(); },
        verify: async () => { events.push(`verify:${id}`); return transaction.verify(); },
      };
    },
  };

  try {
    const result = await runInit(options(root, releaseRoot, installationRoot), deps);
    assert.equal(result.outcome, "SUCCESS");
    assert.match(await readFile(join(first, "FIRST.md"), "utf8"), /AGENT_GOVERNANCE_MANAGED_V1/);
    assert.match(await readFile(join(second, "SECOND.md"), "utf8"), /AGENT_GOVERNANCE_MANAGED_V1/);
    assert.deepEqual(result.targets.map(({ state }) => state), ["CURRENT", "CURRENT"]);
    assert.equal(events.indexOf(`plan:${second}`) < events.indexOf("confirm:" + [first, second].join(",")), true);
    assert.equal(events.indexOf("confirm:" + [first, second].join(",")) < events.indexOf(`install:${first}`), true);
    assert.equal(events.indexOf(`install:${first}`) < events.indexOf(`verify:${first}`), true);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("runInit returns before discovery, prompt, transaction construction, or mutation without a TTY", async () => {
  const events: string[] = [];
  const deps: InitDependencies = {
    async discoverCandidates(): Promise<readonly Candidate[]> { events.push("discover"); return []; },
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

test("runInit cancellation in step two performs no plan or mutation", async () => {
  const events: string[] = [];
  const deps: InitDependencies = {
    async discoverCandidates(): Promise<readonly Candidate[]> { events.push("discover"); return [candidate("/synthetic/a")]; },
    prompt: prompt(INIT_CANCELLED, events),
    createTransaction(): InitTransaction { events.push("transaction"); return fakeTransaction(events, "unused"); },
  };
  const result = await runInit(options("/synthetic/home"), deps);
  assert.equal(result.outcome, "INTERRUPTED");
  assert.equal(result.reason, "CANCELLED");
  assert.deepEqual(events, ["1/3:Umgebung prüfen", "discover", "2/3:AI-/LLM-Ziele auswählen", "select"]);
});

test("runInit creates no filesystem mutation when aggregate approval is declined", async () => {
  const root = await createTestRoot("agent-governance-init-decline-");
  const targetRoot = join(root, "target");
  const installationRoot = join(root, "installation");
  const releaseRoot = await createReleaseFixture(join(root, "release"));
  await mkdir(targetRoot);
  const selected = candidate(targetRoot);
  const events: string[] = [];
  try {
    const result = await runInit(options(root, releaseRoot, installationRoot), {
      async discoverCandidates(): Promise<readonly Candidate[]> { return [selected]; },
      prompt: prompt([{ candidate: selected, manualInput: { entryFile: "AGENTS.md" } }], events, false),
      createTransaction: (request) => new InstallerTransaction(request),
    });
    assert.equal(result.outcome, "INTERRUPTED");
    await assert.rejects(access(join(targetRoot, "AGENTS.md")));
    await assert.rejects(access(installationRoot));
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("runInit exposes only target status and plan data at the approval boundary", async () => {
  const selected = candidate("/synthetic/approval-boundary");
  let approvalKeys: string[] = [];
  const events: string[] = [];
  await runInit(options("/synthetic/home"), {
    async discoverCandidates(): Promise<readonly Candidate[]> { return [selected]; },
    prompt: {
      ...prompt([{ candidate: selected, manualInput: { entryFile: "AGENTS.md" } }], events),
      confirm: async (plans): Promise<true> => {
        approvalKeys = Object.keys(plans[0]!).sort();
        return true;
      },
    },
    createTransaction: () => fakeTransaction(events, selected.root),
  });
  assert.deepEqual(approvalKeys, ["plan", "status", "target"]);
});

test("runInit preserves verify failure as the aggregate failure", async () => {
  const targetRoot = "/synthetic/verify-failure";
  const events: string[] = [];
  const selected = candidate(targetRoot);
  const transaction: InitTransaction = {
    ...fakeTransaction(events, targetRoot),
    verify: async (): Promise<InstallResult> => {
      events.push(`verify:${targetRoot}`);
      return { ...transactionResult("verify", "TAMPERED"), outcome: "UNSAFE_STATE" };
    },
  };
  await assert.rejects(
    runInit(options("/synthetic/home"), {
      async discoverCandidates(): Promise<readonly Candidate[]> { return [selected]; },
      prompt: prompt([{ candidate: selected, manualInput: { entryFile: "AGENTS.md" } }], events),
      createTransaction: () => transaction,
    }),
    /verification failed/i,
  );
  assert.equal(events.includes(`verify:${targetRoot}`), true);
});

test("runInit disposes prompt progress after discovery and planning failures", async () => {
  const selected = candidate("/synthetic/dispose-target");
  for (const failure of ["discovery", "planning"] as const) {
    const events: string[] = [];
    const basePrompt = prompt([{ candidate: selected, manualInput: { entryFile: "AGENTS.md" } }], events);
    const disposablePrompt: InitPrompt = {
      ...basePrompt,
      dispose: () => { events.push("dispose"); },
    };
    await assert.rejects(
      runInit(options("/synthetic/home"), {
        discoverCandidates: async () => {
          if (failure === "discovery") throw new Error("synthetic discovery failure");
          return [selected];
        },
        prompt: disposablePrompt,
        createTransaction: () => ({
          ...fakeTransaction(events, selected.root),
          status: async () => {
            throw new Error("synthetic planning failure");
          },
        }),
      }),
      new RegExp(failure),
    );
    assert.equal(events.at(-1), "dispose", failure);
    assert.equal(events.filter((event) => event === "dispose").length, 1, failure);
  }
});

test("runInit keeps CURRENT targets idempotent and uses the default or explicit installation root", async () => {
  const root = await createTestRoot("agent-governance-init-current-");
  const targetRoot = join(root, "target");
  const releaseRoot = await createReleaseFixture(join(root, "release"));
  const defaultInstallationRoot = join(root, ".agent-governance");
  await mkdir(targetRoot);
  const request: InstallerRequest = {
    targetRoot,
    entryFile: "AGENTS.md",
    scope: "global",
    installationRoot: defaultInstallationRoot,
    dryRun: false,
    nonInteractive: false,
    releaseRoot,
  };
  await new InstallerTransaction(request).install();
  const entryBefore = await readFile(join(targetRoot, "AGENTS.md"));
  const backupsBefore = await readdir(join(defaultInstallationRoot, "backups", (await readdir(join(defaultInstallationRoot, "backups")))[0]!));
  const selected = candidate(targetRoot);
  const seenRequests: InstallerRequest[] = [];
  let mutationCheckpoint = false;
  try {
    const result = await runInit(options(root, releaseRoot), {
      async discoverCandidates(): Promise<readonly Candidate[]> { return [selected]; },
      prompt: prompt([{ candidate: selected, manualInput: { entryFile: "AGENTS.md" } }], []),
      createTransaction: (createdRequest) => {
        seenRequests.push(createdRequest);
        return new InstallerTransaction({ ...createdRequest, onCheckpoint: () => { mutationCheckpoint = true; } });
      },
    });
    assert.equal(result.outcome, "SUCCESS");
    assert.equal(result.targets[0]?.previousState, "CURRENT");
    assert.equal(result.targets[0]?.state, "CURRENT");
    assert.equal(seenRequests[0]?.installationRoot, defaultInstallationRoot);
    assert.equal(mutationCheckpoint, false);
    assert.deepEqual(await readFile(join(targetRoot, "AGENTS.md")), entryBefore);
    const binding = (await readdir(join(defaultInstallationRoot, "backups")))[0]!;
    assert.deepEqual(await readdir(join(defaultInstallationRoot, "backups", binding)), backupsBefore);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});


test("runInit aktualisiert ein OUTDATED-Ziel nach dem genehmigten Updateplan und verifiziert es", async () => {
  const root = await createTestRoot("agent-governance-init-update-");
  try {
    const targetRoot = join(root, "target");
    await mkdir(targetRoot);
    const oldRelease = await createReleaseFixture(join(root, "old"), "1.0.1");
    const releaseRoot = await createReleaseFixture(join(root, "new"), "1.1.0");
    const installationRoot = join(root, "installation");
    const request: InstallerRequest = { targetRoot, entryFile: "AGENTS.md", scope: "global", installationRoot, releaseRoot: oldRelease, dryRun: false, nonInteractive: false };
    await new InstallerTransaction(request).install();
    const localRules = join(installationRoot, "releases/1.0.1/bundle/agent-governance/local/user-rules.md");
    await mkdir(join(localRules, ".."), { recursive: true });
    await writeFile(localRules, "Synthetic local rule\n");
    const selected = candidate(targetRoot);
    let verified = false;
    const result = await runInit(options(root, releaseRoot, installationRoot), {
      discoverCandidates: async () => [selected],
      prompt: {
        ...prompt([{ candidate: selected, manualInput: { entryFile: "AGENTS.md" } }], []),
        confirm: async (plans) => {
          assert.equal(plans[0]?.status.state, "OUTDATED");
          assert.equal(plans[0]?.plan.plan?.command, "update");
          assert.ok(plans[0]?.plan.plan?.resources.some((r) => r.id === "local-rules" && r.operation === "create"));
          assert.match(await readFile(join(targetRoot, "AGENTS.md"), "utf8"), /1\.0\.1/);
          return true;
        },
      },
      createTransaction: (input) => {
        const transaction = new InstallerTransaction(input);
        return {
          status: () => transaction.status(), plan: (command) => transaction.plan(command),
          install: () => transaction.install(), update: () => transaction.update(),
          verify: async () => { const result = await transaction.verify(); verified = true; return result; },
        };
      },
    });
    assert.equal(result.outcome, "SUCCESS");
    assert.equal(result.targets[0]?.previousState, "OUTDATED");
    assert.equal(verified, true);
    assert.match(await readFile(join(targetRoot, "AGENTS.md"), "utf8"), /1\.1\.0/);
    assert.equal(await readFile(join(installationRoot, "releases/1.1.0/bundle/agent-governance/local/user-rules.md"), "utf8"), "Synthetic local rule\n");
  } finally { await rm(root, { recursive: true, force: true }); }
});
