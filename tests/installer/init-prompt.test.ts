import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { join } from "node:path";
import test from "node:test";

import { createClackPrompt, type ClackPromptOperations } from "../../src/init/prompt.ts";
import { INIT_CANCELLED, type HarnessRow, type InitPlannedTarget } from "../../src/init/types.ts";

function row(id: string, displayName: string, overrides: Partial<HarnessRow> = {}): HarnessRow {
  return {
    id,
    displayName,
    supported: true,
    targetRoot: `/synthetic/${id}`,
    entryFile: "AGENTS.md",
    state: "CURRENT",
    localVersion: "1.4.5",
    latestVersion: "1.4.5",
    ...overrides,
  };
}

interface Harness {
  readonly operations: ClackPromptOperations;
  readonly calls: Array<{ readonly kind: string; readonly options?: unknown }>;
}

function harness(responses: readonly unknown[]): Harness {
  const calls: Array<{ kind: string; options?: unknown }> = [];
  const pending = [...responses];
  return {
    calls,
    operations: {
      autocompleteMultiselect: async (options) => {
        calls.push({ kind: "autocompleteMultiselect", options });
        return pending.shift();
      },
      path: async (options) => { calls.push({ kind: "path", options }); return pending.shift(); },
      text: async (options) => { calls.push({ kind: "text", options }); return pending.shift(); },
      confirm: async (options) => { calls.push({ kind: "confirm", options }); return pending.shift(); },
      spinner: () => ({
        start(message): void { calls.push({ kind: "spinner:start", options: { message } }); },
        stop(message): void { calls.push({ kind: "spinner:stop", options: { message } }); },
      }),
      cancel(message): void { calls.push({ kind: "cancel", options: { message } }); },
      isCancel: (value): boolean => value === CANCEL,
    },
  };
}

const CANCEL = Symbol("cancel");

test("selectTargets preselects supported harnesses, disables unsupported ones, and keeps the manual action first", async () => {
  const claude = row("claude", "Anthropic Claude Code");
  const pi: HarnessRow = { id: "pi", displayName: "Pi Coding Agent", supported: false };
  const fake = harness([["claude", "__custom__"], "/synthetic/Manual", "MANUAL.md"]);
  const prompt = createClackPrompt({ prompts: fake.operations, columns: 60, environment: { NO_COLOR: "1" } });

  const selected = await prompt.selectTargets([pi, claude]);

  assert.deepEqual(selected, [
    { harness: { id: "claude", displayName: "Anthropic Claude Code" } },
    { manualInput: { targetRoot: "/synthetic/Manual", entryFile: "MANUAL.md" } },
  ]);
  const multiselect = fake.calls.find(({ kind }) => kind === "autocompleteMultiselect")?.options as {
    initialValues: string[];
    options: Array<{ value: string; label: string; hint?: string; disabled?: boolean }>;
    message: string;
    filter: (search: string, option: { value: string; label: string; hint?: string; disabled?: boolean }) => boolean;
  };
  assert.deepEqual(multiselect?.initialValues, ["claude"]);
  const options = multiselect.options;
  assert.deepEqual(options.map(({ value }) => value), ["__custom__", "pi", "claude"]);
  assert.equal(options[0]?.label, "Coding-Harness nicht dabei?");
  assert.equal(options[1]?.disabled, true, "unsupported harness must be disabled");
  assert.equal(options[2]?.disabled, undefined, "supported harness must be selectable");
  assert.ok(options.every(({ hint }) => hint === "[fokus]"));
  assert.match(String(multiselect?.message), /Coding-Harness nicht dabei\?.*\? tippen.*Tab/su);
  assert.match(String(multiselect?.message), /✓.*⚠.*nicht init/su);
  assert.equal(fake.calls.filter(({ kind }) => kind === "text").length, 1);
  assert.equal(fake.calls.filter(({ kind }) => kind === "path").length, 1);
});

test("selectTargets maps Ctrl+C cancellation to the orchestration sentinel", async () => {
  const fake = harness([CANCEL]);
  const prompt = createClackPrompt({ prompts: fake.operations, columns: 80, environment: {} });

  assert.equal(await prompt.selectTargets([row("claude", "Anthropic Claude Code")]), INIT_CANCELLED);
  assert.equal(fake.calls.filter(({ kind }) => kind === "cancel").length, 1);
});

test("manual entry cancellation is clean and does not continue to later fields", async () => {
  const fake = harness([["__custom__"], CANCEL, "must-not-be-read.md"]);
  const prompt = createClackPrompt({ prompts: fake.operations, columns: 80, environment: {} });

  assert.equal(await prompt.selectTargets([row("claude", "Anthropic Claude Code")]), INIT_CANCELLED);
  assert.equal(fake.calls.filter(({ kind }) => kind === "path").length, 1);
  assert.equal(fake.calls.filter(({ kind }) => kind === "cancel").length, 1);
});

test("step uses a spinner and confirm preserves false and cancellation semantics", async () => {
  const fake = harness([false, CANCEL]);
  const prompt = createClackPrompt({ prompts: fake.operations, columns: 80, environment: {} });
  prompt.step({ position: 1, total: 3, title: "Umgebung prüfen" });

  assert.equal(await prompt.confirm([]), false);
  assert.equal(await prompt.confirm([]), INIT_CANCELLED);
  assert.deepEqual(fake.calls.slice(0, 2).map(({ kind }) => kind), ["spinner:start", "spinner:stop"]);
  assert.equal(fake.calls[1]?.options && (fake.calls[1].options as { message?: string }).message, "[1/3] Umgebung prüfen");
  assert.equal(fake.calls.filter(({ kind }) => kind === "cancel").length, 1);
});

test("dispose stops active progress exactly once", () => {
  const fake = harness([]);
  const prompt = createClackPrompt({ prompts: fake.operations, columns: 80, environment: {} });
  prompt.step({ position: 1, total: 3, title: "Umgebung prüfen" });

  prompt.dispose();
  prompt.dispose();

  assert.deepEqual(fake.calls.map(({ kind }) => kind), ["spinner:start", "spinner:stop"]);
});

test("confirm shows each target's harness, state, mutation, and resource operations before approval", async () => {
  const fake = harness([true]);
  const prompt = createClackPrompt({ prompts: fake.operations, columns: 80, environment: { NO_COLOR: "1" } });
  const plans: readonly InitPlannedTarget[] = [{
    target: { targetRoot: "/synthetic/Target", entryFile: "nested/AGENTS.md" },
    displayName: "Anthropic Claude Code",
    status: {
      schemaVersion: 1,
      architecture: "GLOBAL_EXPLICIT_PATH_MANAGED_BLOCK",
      command: "status",
      outcome: "SUCCESS",
      state: "OUTDATED",
      phase: "inspect",
      rollbackStatus: "AVAILABLE",
      capabilities: [],
    },
    plan: {
      schemaVersion: 1,
      architecture: "GLOBAL_EXPLICIT_PATH_MANAGED_BLOCK",
      command: "plan",
      outcome: "SUCCESS",
      state: "OUTDATED",
      phase: "plan",
      rollbackStatus: "AVAILABLE",
      capabilities: [],
      plan: {
        schemaVersion: 1,
        architecture: "GLOBAL_EXPLICIT_PATH_MANAGED_BLOCK",
        command: "update",
        state: "OUTDATED",
        resources: [
          { id: "release", target: "/installation/releases/1.1.0", operation: "create" },
          { id: "entry-file", target: "/synthetic/Target/nested/AGENTS.md", operation: "replace" },
        ],
        harnessSpecificMutation: false,
        mcpMutation: false,
        hookMutation: false,
        approvalExpansion: false,
      },
    },
  }];

  assert.equal(await prompt.confirm(plans), true);
  const confirmation = fake.calls.find(({ kind }) => kind === "confirm")?.options as { message: string };
  assert.match(confirmation.message, /Harness:\s*Anthropic Claude Code/u);
  assert.match(confirmation.message, /Target Root:\s*\/synthetic\/Target/u);
  assert.match(confirmation.message, /Entry File:\s*nested\/AGENTS\.md/u);
  assert.match(confirmation.message, /Aktueller Zustand:\s*OUTDATED/u);
  assert.match(confirmation.message, /Mutation:\s*update/u);
  assert.match(confirmation.message, /release:\s*create.*\/installation\/releases\/1\.1\.0/u);
  assert.match(confirmation.message, /jetzt einrichten und anschließend verifizieren\?$/u);
});

test("the real CLI uses the Clack prompt and handles Ctrl+C in a synthetic PTY", () => {
  const result = spawnSync(process.execPath, [
    join(import.meta.dirname, "../e2e/run_init_pty.mjs"),
    "--columns=60",
    "--no-color",
    "--cancel",
  ], { encoding: "utf8", timeout: 15_000 });

  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
  assert.doesNotMatch(result.stdout, /interactive init prompt is unavailable/u);
  assert.match(result.stdout, /Einrichtung abgebrochen|INTERRUPTED/u);
});

test("the colored PTY path recognizes the fully rendered prompt before Ctrl+C", () => {
  const result = spawnSync(process.execPath, [
    join(import.meta.dirname, "../e2e/run_init_pty.mjs"),
    "--columns=80",
    "--cancel",
  ], { encoding: "utf8", timeout: 15_000 });

  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
  assert.match(result.stdout, /\u001b\[(?:31|32|33|36)m/u);
});

test("the real monochrome prompt keeps status, focus, and selection semantically separate", () => {
  const result = spawnSync(process.execPath, [
    join(import.meta.dirname, "../e2e/run_init_pty.mjs"),
    "--columns=80",
    "--no-color",
    "--markers",
  ], { encoding: "utf8", timeout: 15_000 });

  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
  assert.match(result.stdout, /Governance v1\.4\.4 → v1\.4\.5 verfügbar/u);
  assert.match(result.stdout, /erkannt · nicht unterstützt/u);
  assert.match(result.stdout, /MARKER_SELECTION_RENDERED/u);
});

test("the real 60-column prompt keeps the manual fallback actionable with overflowing multiline options", () => {
  const result = spawnSync(process.execPath, [
    join(import.meta.dirname, "../e2e/run_init_pty.mjs"),
    "--columns=60",
    "--no-color",
    "--fallback",
  ], { encoding: "utf8", timeout: 15_000 });

  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
  assert.match(result.stdout, /Harness 19/u);
  assert.match(result.stdout, /FALLBACK_SEARCH_ACTION_VISIBLE/u);
  assert.match(result.stdout, /FALLBACK_PROMPT_CANCELLED/u);
});
