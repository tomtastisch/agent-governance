import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { join } from "node:path";
import test from "node:test";

import type { Candidate } from "../../src/discovery/types.ts";
import { createClackPrompt, type ClackPromptOperations } from "../../src/init/prompt.ts";
import { INIT_CANCELLED } from "../../src/init/types.ts";

function candidate(root: string, confidence: Candidate["confidence"]): Candidate {
  return {
    root,
    candidateClass: "DIRECTORY",
    status: "COMPLETE",
    confidence,
    score: confidence === "HIGH_CONFIDENCE" ? 9 : 3,
    families: ["runtime", "state", "tooling"],
    independentSources: 3,
    evidence: [],
    fileCount: 3,
    evidenceDensity: 1,
    activityAt: null,
    evidenceDigest: "b".repeat(64),
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

test("selectTargets preselects only high-confidence candidates and keeps the custom option last", async () => {
  const high = candidate("/synthetic/High", "HIGH_CONFIDENCE");
  const uncertain = candidate(`/synthetic/${"Uncertain-local-candidate-".repeat(4)}`, "UNCERTAIN");
  const fake = harness([[high.root, "__custom__"], "HIGH.md", "/synthetic/Manual", "MANUAL.md"]);
  const prompt = createClackPrompt({ prompts: fake.operations, columns: 60, environment: { NO_COLOR: "1" } });

  const selected = await prompt.selectTargets([uncertain, high]);

  assert.deepEqual(selected, [
    { candidate: high, manualInput: { entryFile: "HIGH.md" } },
    { manualInput: { targetRoot: "/synthetic/Manual", entryFile: "MANUAL.md" } },
  ]);
  const multiselect = fake.calls.find(({ kind }) => kind === "autocompleteMultiselect")?.options as {
    initialValues: string[];
    options: Array<{ value: string; label: string; hint?: string }>;
    message: string;
  };
  assert.deepEqual(multiselect?.initialValues, [high.root]);
  const options = multiselect.options;
  assert.deepEqual(options.map(({ value }) => value), [uncertain.root, high.root, "__custom__"]);
  assert.equal(options.at(-1)?.label, "AI/LLM nicht dabei?");
  assert.ok(options.every(({ hint }) => hint === "[fokus]"));
  assert.match(String(multiselect?.message), /\[hoch\].*\[unsicher\]/su);
  assert.match(String(multiselect?.message), /↑\/↓.*Leertaste.*Enter.*Ctrl\+C/su);
  assert.ok(options.every(({ label }) => label.split("\n").every((line) => line.length <= 56)));
});

test("selectTargets maps Ctrl+C cancellation to the orchestration sentinel", async () => {
  const fake = harness([CANCEL]);
  const prompt = createClackPrompt({ prompts: fake.operations, columns: 80, environment: {} });

  assert.equal(await prompt.selectTargets([candidate("/synthetic/High", "HIGH_CONFIDENCE")]), INIT_CANCELLED);
  assert.equal(fake.calls.filter(({ kind }) => kind === "cancel").length, 1);
});

test("path cancellation is clean and does not continue to later fields", async () => {
  const selected = candidate("/synthetic/Target", "HIGH_CONFIDENCE");
  const fake = harness([[selected.root], CANCEL, "must-not-be-read.md"]);
  const prompt = createClackPrompt({ prompts: fake.operations, columns: 80, environment: {} });

  assert.equal(await prompt.selectTargets([selected]), INIT_CANCELLED);
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
  assert.equal(fake.calls.filter(({ kind }) => kind === "cancel").length, 1);
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
  assert.match(result.stdout, /\u001b\[(?:32|33|36)m/u);
  assert.match(result.stdout, /"outcome":"INTERRUPTED"/u);
});

test("the real monochrome prompt keeps confidence, focus, and toggled selection semantically separate", () => {
  const result = spawnSync(process.execPath, [
    join(import.meta.dirname, "../e2e/run_init_pty.mjs"),
    "--columns=80",
    "--no-color",
    "--markers",
  ], { encoding: "utf8", timeout: 15_000 });
  const visible = result.stdout.replace(/\u001b\[[0-?]*[ -/]*[@-~]/gu, "");

  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
  assert.match(visible, /◼ \[hoch\] High[\s\S]*?\/synthetic\/High \(\[fokus\]\)/u);
  assert.match(visible, /◻ \[unsicher\] Uncertain[\s\S]*?\/synthetic\/Uncertain \(\[fokus\]\)/u);
  assert.match(visible, /◼ \[unsicher\] Uncertain[\s\S]*?\/synthetic\/Uncertain \(\[fokus\]\)/u);
  assert.match(visible, /\[hoch\].*\[unsicher\].*\[fokus\].*◼ Auswahl/su);
});
