import assert from "node:assert/strict";
import { test } from "node:test";
import { chmod, mkdtemp, readdir, realpath, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { ResumeCheckpointStore, type ResumeState } from "../../src/resume-checkpoint.ts";
import { resolveResumeCandidates, type ResolveContext } from "../../src/resume-resolve.ts";

interface Overrides {
  taskId?: string;
  repository?: string;
  scope?: string;
  worktree?: string;
  branch?: string;
  dirty?: string;
  workItem?: string | null;
  taskStatus?: ResumeState["taskStatus"];
  exactHead?: string;
  nextAtomicAction?: string;
  externalEffects?: ResumeState["externalEffects"];
}

function makeState(overrides: Overrides = {}): ResumeState {
  return {
    projection: {
      taskId: overrides.taskId ?? "issue-95",
      objective: "Resume-Kandidaten deterministisch auflösen",
      scope: ["resume"],
      exactHead: overrides.exactHead ?? "a".repeat(40),
      evidence: [],
      incompleteEvidence: [],
      openFindings: [],
      nextAtomicAction: overrides.nextAtomicAction ?? "gezielte-tests",
    },
    identities: {
      scope: overrides.scope ?? "resume-scope",
      repository: overrides.repository ?? "repo-a",
      worktree: overrides.worktree ?? "worktree-a",
      branch: overrides.branch ?? "feat/issue-95/resume-candidate-resolution",
      dirty: overrides.dirty ?? "clean",
      dependencies: "lock-a",
      configuration: "config-a",
      governance: "gov-a",
      environment: "env-a",
    },
    authorities: ["git:repo-a"],
    activeTask: "resolve",
    taskStatus: overrides.taskStatus ?? "RUNNING",
    decisions: [],
    evidenceReferences: [],
    workItem: overrides.workItem === undefined ? null : overrides.workItem,
    externalEffects: overrides.externalEffects ?? [],
  };
}

interface Store {
  directory: string;
  store: ResumeCheckpointStore;
}

async function makeStore(t: { after(fn: () => Promise<void>): void }, state: ResumeState): Promise<Store> {
  const directory = await realpath(await mkdtemp(join(tmpdir(), "resolve-")));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const store = await ResumeCheckpointStore.open(directory);
  await store.materialize({ eventId: "event-1", trigger: "task_identified", expected: null, state });
  return { directory, store };
}

const context = (overrides: Partial<ResolveContext> = {}): ResolveContext => ({
  repository: "repo-a",
  scope: "resume-scope",
  worktree: "worktree-a",
  branch: "feat/issue-95/resume-candidate-resolution",
  dirty: "clean",
  ...overrides,
});

test("genau ein gültiger Candidate ergibt RESUME mit Identität und nächster Aktion", async (t) => {
  const { directory, store } = await makeStore(t, makeState());
  const expected = await store.read();
  const result = await resolveResumeCandidates([directory], context());
  assert.equal(result.outcome, "RESUME");
  if (result.outcome !== "RESUME") return;
  assert.equal(result.store, directory);
  assert.equal(result.generation, expected!.generation);
  assert.equal(result.fingerprint, expected!.fingerprint);
  assert.equal(result.taskId, "issue-95");
  assert.equal(result.nextAtomicAction, "gezielte-tests");
  assert.equal(result.taskStatus, "RUNNING");
});

test("leere Candidate-Scope ergibt NO_MATCH", async () => {
  const result = await resolveResumeCandidates([], context());
  assert.equal(result.outcome, "NO_MATCH");
});

test("Candidate eines anderen Repository wird deterministisch ausgeschlossen", async (t) => {
  const { directory } = await makeStore(t, makeState({ repository: "repo-other" }));
  const result = await resolveResumeCandidates([directory], context());
  assert.equal(result.outcome, "NO_MATCH");
});

test("Candidate eines anderen Scope wird deterministisch ausgeschlossen", async (t) => {
  const { directory } = await makeStore(t, makeState({ scope: "other-scope" }));
  const result = await resolveResumeCandidates([directory], context());
  assert.equal(result.outcome, "NO_MATCH");
});

test("abweichende taskId bei gesetzter Kontext-taskId wird ausgeschlossen", async (t) => {
  const { directory } = await makeStore(t, makeState({ taskId: "issue-87" }));
  const result = await resolveResumeCandidates([directory], context({ taskId: "issue-95" }));
  assert.equal(result.outcome, "NO_MATCH");
});

test("übereinstimmendes workItem bei gesetzter Kontext-workItem bleibt RESUME", async (t) => {
  const { directory } = await makeStore(t, makeState({ workItem: "github:issue-95" }));
  const result = await resolveResumeCandidates([directory], context({ workItem: "github:issue-95" }));
  assert.equal(result.outcome, "RESUME");
});

test("abweichendes workItem bei gesetzter Kontext-workItem wird ausgeschlossen", async (t) => {
  const { directory } = await makeStore(t, makeState({ workItem: "github:issue-95" }));
  const result = await resolveResumeCandidates([directory], context({ workItem: "github:issue-87" }));
  assert.equal(result.outcome, "NO_MATCH");
});

test("gesetztes Kontext-workItem schließt einen Checkpoint ohne workItem aus", async (t) => {
  const { directory } = await makeStore(t, makeState({ workItem: null }));
  const result = await resolveResumeCandidates([directory], context({ workItem: "github:issue-95" }));
  assert.equal(result.outcome, "NO_MATCH");
});

test("abweichende branch-Bindung wird ausgeschlossen", async (t) => {
  const { directory } = await makeStore(t, makeState({ branch: "feat/other" }));
  const result = await resolveResumeCandidates([directory], context());
  assert.equal(result.outcome, "NO_MATCH");
});

test("abweichende worktree-Bindung wird ausgeschlossen", async (t) => {
  const { directory } = await makeStore(t, makeState({ worktree: "worktree-other" }));
  const result = await resolveResumeCandidates([directory], context());
  assert.equal(result.outcome, "NO_MATCH");
});

test("abgeschlossener Auftrag wird nicht allein wegen des Checkpoints reaktiviert", async (t) => {
  const { directory } = await makeStore(t, makeState({ taskStatus: "COMPLETED" }));
  const result = await resolveResumeCandidates([directory], context());
  assert.equal(result.outcome, "NO_MATCH");
});

test("COMPLETED mit unresolved Effect wird nicht verworfen und bleibt RESUME", async (t) => {
  const effect = { operationId: "op-1", target: "github:pr-1", action: "create", inputBindings: ["head-a"], state: "PREPARED" as const, readbackReference: null };
  const { directory, store } = await makeStore(t, makeState());
  const first = await store.read();
  const prepared = await store.materialize({ eventId: "prepare", trigger: "effect_prepared", expected: first, state: { ...makeState(), externalEffects: [effect] } });
  await store.materialize({ eventId: "complete", trigger: "task_completed", expected: prepared, state: { ...makeState(), taskStatus: "COMPLETED", externalEffects: [effect] } });
  const result = await resolveResumeCandidates([directory], context());
  assert.equal(result.outcome, "RESUME");
  if (result.outcome === "RESUME") {
    assert.equal(result.taskStatus, "COMPLETED");
    assert.equal(result.externalEffects[0]!.state, "PREPARED");
  }
});

test("mehrere ununterscheidbare gültige Stores ergeben AMBIGUOUS", async (t) => {
  const a = await makeStore(t, makeState());
  const b = await makeStore(t, makeState());
  const result = await resolveResumeCandidates([a.directory, b.directory], context());
  assert.equal(result.outcome, "AMBIGUOUS");
  if (result.outcome === "AMBIGUOUS") assert.equal(result.candidates.length, 2);
});

test("zwei Locator-Einträge auf denselben kanonischen Store ergeben keine Mehrdeutigkeit", async (t) => {
  const { directory } = await makeStore(t, makeState());
  const result = await resolveResumeCandidates([directory, directory], context());
  assert.equal(result.outcome, "RESUME");
});

test("mehrere Generationen eines Stores ergeben maximal einen aktuellen Candidate", async (t) => {
  const { directory, store } = await makeStore(t, makeState());
  const first = await store.read();
  await store.materialize({ eventId: "event-2", trigger: "next_action_changed", expected: first, state: makeState({ nextAtomicAction: "review" }) });
  await store.materialize({ eventId: "event-3", trigger: "next_action_changed", expected: await store.read(), state: makeState({ nextAtomicAction: "final" }) });
  const result = await resolveResumeCandidates([directory], context());
  assert.equal(result.outcome, "RESUME");
  if (result.outcome === "RESUME") {
    assert.equal(result.generation, 3);
    assert.equal(result.nextAtomicAction, "final");
  }
});

test("beschädigte Generation ergibt INVALID und wird nicht still verworfen", async (t) => {
  const { directory } = await makeStore(t, makeState());
  const forged = join(directory, "2.json");
  await writeFile(forged, `${JSON.stringify({ schemaVersion: 1, generation: 2, previousCheckpoint: "b".repeat(64), eventId: "bad", trigger: "task_started", state: {}, fingerprint: "c".repeat(64) })}\n`);
  await chmod(forged, 0o600);
  const result = await resolveResumeCandidates([directory], context());
  assert.equal(result.outcome, "INVALID");
});

test("Generation Gap ergibt INVALID", async (t) => {
  const directory = await realpath(await mkdtemp(join(tmpdir(), "resolve-gap-")));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const gap = join(directory, "2.json");
  await writeFile(gap, `${JSON.stringify({ schemaVersion: 1, generation: 2, previousCheckpoint: null, eventId: "gap", trigger: "task_started", state: makeState(), fingerprint: "c".repeat(64) })}\n`);
  await chmod(gap, 0o600);
  const result = await resolveResumeCandidates([directory], context());
  assert.equal(result.outcome, "INVALID");
});

test("symlinked Candidate-Pfad ergibt INVALID", async (t) => {
  const { directory } = await makeStore(t, makeState());
  const parent = await realpath(await mkdtemp(join(tmpdir(), "resolve-link-")));
  t.after(() => rm(parent, { recursive: true, force: true }));
  const link = join(parent, "candidate");
  await symlink(directory, link);
  const result = await resolveResumeCandidates([link], context());
  assert.equal(result.outcome, "INVALID");
});

test("nicht-privater Candidate-Ordner ergibt INVALID", async (t) => {
  const { directory } = await makeStore(t, makeState());
  await chmod(directory, 0o755);
  const result = await resolveResumeCandidates([directory], context());
  assert.equal(result.outcome, "INVALID");
});

test("gleicher Task mit neuem HEAD bleibt RESUME (exactHead ist keine Identität)", async (t) => {
  const { directory } = await makeStore(t, makeState({ exactHead: "b".repeat(40) }));
  const result = await resolveResumeCandidates([directory], context());
  assert.equal(result.outcome, "RESUME");
});

test("abweichender Dirty State wird bei gesetzter dirty-Bindung nicht durch gleichen HEAD verdeckt", async (t) => {
  const { directory } = await makeStore(t, makeState({ dirty: "clean", exactHead: "a".repeat(40) }));
  const result = await resolveResumeCandidates([directory], context({ dirty: "dirty-now" }));
  assert.equal(result.outcome, "NO_MATCH");
});

test("Fresh-Chat ohne taskId löst einen eindeutigen Candidate auf und entdeckt die taskId", async (t) => {
  const { directory } = await makeStore(t, makeState());
  const result = await resolveResumeCandidates([directory], { repository: "repo-a", scope: "resume-scope", worktree: "worktree-a", branch: "feat/issue-95/resume-candidate-resolution" });
  assert.equal(result.outcome, "RESUME");
  if (result.outcome === "RESUME") assert.equal(result.taskId, "issue-95");
});

test("PREPARED External Effect wird nie ausgeführt und bleibt referenziert", async (t) => {
  const effect = { operationId: "op-1", target: "github:pr-1", action: "create", inputBindings: ["head-a"], state: "PREPARED" as const, readbackReference: null };
  const { directory, store } = await makeStore(t, makeState());
  const first = await store.read();
  await store.materialize({ eventId: "prepare", trigger: "effect_prepared", expected: first, state: { ...makeState(), externalEffects: [effect] } });
  const result = await resolveResumeCandidates([directory], context());
  assert.equal(result.outcome, "RESUME");
  if (result.outcome === "RESUME") assert.deepEqual(result.externalEffects, [effect]);
  assert.equal((await store.read())!.state.externalEffects[0]!.state, "PREPARED");
});

test("UNKNOWN External Effect wird nie ausgeführt", async (t) => {
  const effect = { operationId: "op-1", target: "github:pr-1", action: "create", inputBindings: ["head-a"], state: "PREPARED" as const, readbackReference: null };
  const { directory, store } = await makeStore(t, makeState());
  const first = await store.read();
  const prepared = await store.materialize({ eventId: "prepare", trigger: "effect_prepared", expected: first, state: { ...makeState(), externalEffects: [effect] } });
  await store.materialize({ eventId: "dispatch", trigger: "effect_executed", expected: prepared, state: { ...makeState(), externalEffects: [{ ...effect, state: "UNKNOWN" }] } });
  const result = await resolveResumeCandidates([directory], context());
  assert.equal(result.outcome, "RESUME");
  assert.equal((await store.read())!.state.externalEffects[0]!.state, "UNKNOWN");
});

test("Resolver ist rein lesend und materialisiert keine neue Generation", async (t) => {
  const { directory, store } = await makeStore(t, makeState());
  await resolveResumeCandidates([directory], context());
  assert.deepEqual(await readdir(directory), ["1.json"]);
  assert.equal((await store.read())!.generation, 1);
});

test("ein INVALID-Kandidat dominiert über einen gültigen passenden Kandidaten", async (t) => {
  const valid = await makeStore(t, makeState());
  const corrupted = await realpath(await mkdtemp(join(tmpdir(), "resolve-bad-")));
  t.after(() => rm(corrupted, { recursive: true, force: true }));
  await chmod(corrupted, 0o755);
  const result = await resolveResumeCandidates([valid.directory, corrupted], context());
  assert.equal(result.outcome, "INVALID");
});
