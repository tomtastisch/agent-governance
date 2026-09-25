import assert from "node:assert/strict";
import { test } from "node:test";
import { chmod, link, mkdtemp, open, readFile, readdir, realpath, rm, symlink, writeFile, type FileHandle } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fork } from "node:child_process";
import { once } from "node:events";
import { ResumeCheckpointStore, MATERIALIZATION_TRIGGERS } from "../../src/resume-checkpoint.ts";
import { encodeResumeProjection } from "../../src/resume-toon.ts";
import { state } from "../fixtures/resume/state.ts";

async function fixture(t: { after(fn: () => Promise<void>): void }) {
  const directory = await realpath(await mkdtemp(join(tmpdir(), "resume-")));
  t.after(() => rm(directory, { recursive: true, force: true }));
  return { directory, store: await ResumeCheckpointStore.open(directory) };
}
const initial = (store: ResumeCheckpointStore) => store.materialize({ eventId: "event-1", trigger: "task_identified", expected: null, state: state() });
const operation = { operationId: "op-1", target: "github:pr-1", action: "create", inputBindings: ["head-a"], state: "PREPARED" as const, readbackReference: null };
async function prepared(store: ResumeCheckpointStore) {
  const first = await initial(store);
  return (await store.materialize({ eventId: "prepare", trigger: "effect_prepared", expected: first, state: { ...state(), externalEffects: [operation] } }))!;
}
const applied = async () => ({ operationId: "op-1", target: "github:pr-1", action: "create", inputBindings: ["head-a"], outcome: "APPLIED" as const, reference: "github:readback-1" });

test("Checkpoint bleibt nach Fresh-Chat, Modell- und Sessionwechsel auflösbar; TOON ist abgeleitet", async (t) => {
  const { directory, store } = await fixture(t);
  const first = await initial(store);
  assert.equal(first!.generation, 1);
  assert.match(first!.fingerprint, /^[a-f0-9]{64}$/);
  assert.deepEqual((await (await ResumeCheckpointStore.open(directory)).read())!.state, state());
  const toon = await store.toToon(first!);
  assert.equal((await store.validateToon(toon, first!)).checkpointFingerprint, first!.fingerprint);
  const forged = encodeResumeProjection({ ...state().projection, nextAtomicAction: "falsche-aktion", checkpointFingerprint: first!.fingerprint });
  await assert.rejects(store.validateToon(forged, first!), /projection/);
  const next = await store.materialize({ eventId: "event-2", trigger: "next_action_changed", expected: first, state: { ...state(), projection: { ...state().projection, nextAtomicAction: "review" } } });
  await assert.rejects(store.validateToon(toon, next!), /checkpoint|projection/);
  await assert.rejects(store.read(first!), /stale/);
});

test("Alle Mindest-Trigger sind geschlossen und irrelevante Nachrichten schreiben nichts", async (t) => {
  const { directory, store } = await fixture(t);
  assert.equal(await store.materialize({ eventId: "chat-1", trigger: "message", expected: null, state: state() }), null);
  assert.deepEqual(await readdir(directory), []);
  let current = await initial(store);
  for (const trigger of MATERIALIZATION_TRIGGERS) {
    current = await store.materialize({ eventId: trigger, trigger, expected: current, state: { ...state(), activeTask: trigger } });
  }
  assert.equal(current!.generation, MATERIALIZATION_TRIGGERS.length + 1);
  assert.deepEqual(await store.flush(), current);
  await assert.rejects(store.materialize({ eventId: "x", trigger: "invented", expected: current, state: state() }), /trigger/);
});

test("Generation, Event und Inhalt binden idempotente Wiederholung und stale Writer", async (t) => {
  const { store } = await fixture(t);
  const first = await initial(store);
  assert.deepEqual(await initial(store), first);
  await assert.rejects(store.materialize({ eventId: "event-1", trigger: "task_identified", expected: null, state: { ...state(), activeTask: "anderer-task" } }), /event|stale/);
  await assert.rejects(store.materialize({ eventId: "new", trigger: "task_started", expected: null, state: state() }), /stale/);
  await assert.rejects(store.materialize({ eventId: "new", trigger: "task_started", expected: { generation: 1, fingerprint: "b".repeat(64) }, state: state() }), /stale/);
  const changed = await store.materialize({ eventId: "dirty", trigger: "exact_state_changed", expected: first, state: { ...state(), identities: { ...state().identities, dirty: "diff-b" } } });
  assert.notEqual(changed!.fingerprint, first!.fingerprint);
  await assert.rejects(initial(store), /stale|event/);
});

test("Wiederholung nach fehlgeschlagenem Directory-Sync bestätigt erst nach erfolgreicher Persistenz", async (t) => {
  const { directory, store } = await fixture(t);
  const handle = await open(directory, "r");
  const prototype = Object.getPrototypeOf(handle) as FileHandle;
  const sync = prototype.sync;
  await handle.close();
  let failSync = true;
  t.mock.method(prototype, "sync", async function (this: FileHandle) {
    if ((await this.stat()).isDirectory() && failSync) throw Object.assign(new Error("directory sync failed"), { code: "EIO" });
    return sync.call(this);
  });
  await assert.rejects(initial(store), { code: "EIO" });
  const visible = (await store.read())!;
  assert.equal(visible.generation, 1);
  await assert.rejects(initial(store), { code: "EIO" });
  const unchanged = () => store.materialize({ eventId: "unchanged", trigger: "task_started", expected: visible, state: state() });
  await assert.rejects(unchanged(), { code: "EIO" });
  failSync = false;
  assert.deepEqual(await initial(store), visible);
  assert.deepEqual(await unchanged(), visible);
});

test("Aufrufermutation der erwarteten Identität kann stale Writer oder Reads nicht rebaselinen", async (t) => {
  const { store } = await fixture(t);
  const first = (await initial(store))!;
  const newer = (await store.materialize({ eventId: "finding", trigger: "finding_opened", expected: first, state: { ...state(), projection: { ...state().projection, openFindings: ["finding-1"] } } }))!;
  const expected = { generation: first.generation, fingerprint: first.fingerprint };
  const pending = store.materialize({ eventId: "stale", trigger: "task_started", expected, state: state() });
  Object.assign(expected, { generation: newer.generation, fingerprint: newer.fingerprint });
  await assert.rejects(pending, /stale/);
  assert.deepEqual((await store.read())!.state.projection.openFindings, ["finding-1"]);
  Object.assign(expected, { generation: first.generation, fingerprint: first.fingerprint });
  const read = store.read(expected);
  Object.assign(expected, { generation: newer.generation, fingerprint: newer.fingerprint });
  await assert.rejects(read, /stale/);
});

test("Evidence-Callback kann die erwartete Identität über einen Checkpoint-Wechsel nicht verändern", async (t) => {
  const { store } = await fixture(t);
  const first = (await initial(store))!;
  const expected = { generation: first.generation, fingerprint: first.fingerprint };
  await assert.rejects(store.evidenceReference(expected, "test-1", async () => {
    const newer = (await store.materialize({ eventId: "changed", trigger: "next_action_changed", expected: first, state: { ...state(), activeTask: "changed" } }))!;
    Object.assign(expected, { generation: newer.generation, fingerprint: newer.fingerprint });
    return true;
  }), /stale/);
});

test("Schema, unbekannte Felder, sensible Daten und fehlende Evidence-Referenzen scheitern vor Persistenz", async (t) => {
  const { directory, store } = await fixture(t);
  for (const invalid of [
    { ...state(), credentials: "redacted" },
    { ...state(), taskStatus: "PASS" },
    { ...state(), evidenceReferences: [] },
    { ...state(), decisions: ["password=synthetic-only"] },
    { ...state(), projection: { ...state().projection, objective: "x".repeat(8193) } },
    { ...state(), identities: { ...state().identities, dirty: "" } },
  ]) {
    await assert.rejects(store.materialize({ eventId: "bad", trigger: "task_identified", expected: null, state: invalid as never }));
    assert.deepEqual(await readdir(directory), []);
  }
});

test("Pfad-, Rechte-, Symlink- und Hardlink-Manipulation werden abgelehnt", async (t) => {
  const { directory, store } = await fixture(t);
  await assert.rejects(ResumeCheckpointStore.open("relative"));
  await assert.rejects(ResumeCheckpointStore.open(`${directory}/../${directory.split("/").at(-1)}`));
  await initial(store);
  const path = join(directory, "1.json");
  await link(path, join(directory, ".stage-00000000-0000-0000-0000-000000000000"));
  await assert.rejects(store.read(), /unsafe/);
  await rm(join(directory, ".stage-00000000-0000-0000-0000-000000000000"));
  await rm(path);
  await symlink("/etc/passwd", path);
  await assert.rejects(store.read(), /unsafe|symlink|ELOOP/);
  await chmod(directory, 0o755);
  await assert.rejects(ResumeCheckpointStore.open(directory), /private/);
});

test("Beschädigte, partielle, unsupported und lückenhafte publizierte Zustände werden niemals zurückgestuft", async (t) => {
  const { directory, store } = await fixture(t);
  const first = await initial(store);
  for (const content of ["{", JSON.stringify({ ...first, schemaVersion: 2 }), JSON.stringify({ ...first, state: { ...state(), activeTask: "tampered" } })]) {
    await writeFile(join(directory, "1.json"), content, { mode: 0o600 });
    await assert.rejects(store.read());
  }
  await writeFile(join(directory, "1.json"), JSON.stringify(first), { mode: 0o600 });
  await writeFile(join(directory, "3.json"), JSON.stringify(first), { mode: 0o600 });
  await assert.rejects(store.read(), /generation/);
});

test("Prozessabbruch an jeder Persistenzgrenze lässt nur vollständige Generationen sichtbar", { timeout: 30000 }, async (t) => {
  for (const stage of ["beforeStage", "afterStage", "beforePublish", "afterPublish", "afterSync"]) {
    const { directory, store } = await fixture(t);
    await initial(store);
    const child = fork(new URL("../fixtures/resume/writer.ts", import.meta.url), [directory, stage, "crash"], { stdio: ["ignore", "ignore", "pipe", "ipc"] });
    await once(child, "message");
    const done = once(child, "exit"); child.send("go");
    const [, signal] = await done;
    assert.equal(signal, "SIGKILL");
    const recovered = await (await ResumeCheckpointStore.open(directory)).read();
    assert.equal(recovered!.generation, ["afterPublish", "afterSync"].includes(stage) ? 2 : 1);
    assert.equal(recovered!.state.activeTask, recovered!.generation === 2 ? "crash" : "persist");
  }
});

test("Zwei echte Writer publizieren dieselbe Generation höchstens einmal", { timeout: 30000 }, async (t) => {
  const { directory, store } = await fixture(t);
  await initial(store);
  const children = ["writer-a", "writer-b"].map(id => fork(new URL("../fixtures/resume/writer.ts", import.meta.url), [directory, "none", id], { stdio: ["ignore", "ignore", "pipe", "ipc"] }));
  await Promise.all(children.map(child => once(child, "message")));
  const completed = children.map(child => once(child, "exit"));
  children.forEach(child => child.send("go"));
  assert.deepEqual((await Promise.all(completed)).map(([code]) => code).sort(), [0, 2]);
  assert.equal((await store.read())!.generation, 2);
  assert.equal(JSON.parse(await readFile(join(directory, "2.json"), "utf8")).generation, 2);
});

test("TOON liest persistierte Bytes erneut und verweigert einen nachträglich beschädigten Checkpoint", async (t) => {
  const { directory, store } = await fixture(t);
  const cp = await initial(store);
  const fresh = await ResumeCheckpointStore.open(directory);
  assert.match(await fresh.toToon(cp!), /Resume sicher materialisieren/);
  await writeFile(join(directory, "1.json"), "{broken");
  await assert.rejects(fresh.toToon(cp!));
});

test("Deterministische Identität hängt nicht von Objekt-Key-Reihenfolgen ab", async (t) => {
  const a = await fixture(t); const b = await fixture(t);
  const cp = await initial(a.store);
  const input = state();
  const reordered = { ...input, identities: Object.fromEntries(Object.entries(input.identities).reverse()), projection: Object.fromEntries(Object.entries(input.projection).reverse()) } as typeof input;
  const other = await b.store.materialize({ eventId: "event-1", trigger: "task_identified", expected: null, state: reordered });
  assert.equal(cp!.fingerprint, other!.fingerprint);
});

test("Write-ahead ist vor dem Effekt sichtbar; erst Readback erzeugt COMMITTED", async (t) => {
  const { directory, store } = await fixture(t);
  const cp = await prepared(store);
  let calls = 0;
  const committed = await store.executeEffect(cp, "op-1", async () => {
    calls++;
    const live = await (await ResumeCheckpointStore.open(directory)).read();
    assert.equal(live!.state.externalEffects[0]!.state, "UNKNOWN");
    assert.equal(JSON.parse(await readFile(join(directory, "2.json"), "utf8")).state.externalEffects[0].state, "PREPARED");
  }, applied);
  assert.equal(committed.state.externalEffects[0]!.state, "COMMITTED");
  await store.executeEffect(committed, "op-1", async () => { calls++; }, applied);
  assert.equal(calls, 1);
});

test("Unterbrochene Effekte werden read-only aufgelöst und niemals blind erneut ausgeführt", async (t) => {
  const { directory, store } = await fixture(t);
  const cp = await prepared(store);
  let calls = 0;
  await assert.rejects(store.executeEffect(cp, "op-1", async () => { calls++; throw new Error("abbruch"); }, applied));
  const fresh = await ResumeCheckpointStore.open(directory);
  const unknown = (await fresh.read())!;
  assert.equal(unknown.state.externalEffects[0]!.state, "UNKNOWN");
  await assert.rejects(fresh.executeEffect(unknown, "op-1", async () => { calls++; }, applied), /readback/);
  const recovered = await fresh.recoverEffect(unknown, "op-1", applied);
  assert.equal(recovered.state.externalEffects[0]!.state, "COMMITTED");
  assert.equal(calls, 1);
});

test("PREPARED ohne Wirkung und unklarer Readback erlauben ausschließlich kontrollierte Fortsetzung", async (t) => {
  const { store } = await fixture(t);
  const cp = await prepared(store);
  const unknown = await store.recoverEffect(cp, "op-1", async () => ({ ...await applied(), outcome: "UNKNOWN", reference: null }));
  assert.equal(unknown.state.externalEffects[0]!.state, "UNKNOWN");
  await assert.rejects(store.executeEffect(unknown, "op-1", async () => {}, applied), /readback/);
  const absent = await store.recoverEffect(unknown, "op-1", async () => ({ ...await applied(), outcome: "NOT_APPLIED" }));
  assert.equal(absent.state.externalEffects[0]!.state, "NOT_APPLIED");
  const retry = await store.materialize({ eventId: "explicit-retry", trigger: "effect_prepared", expected: absent, state: { ...absent.state, externalEffects: [operation] } });
  let calls = 0;
  await store.executeEffect(retry!, "op-1", async () => { calls++; }, applied);
  assert.equal(calls, 1);
});

test("Manipulierte Effect-Bindung, ungebundener Readback und Löschen offener Operationen scheitern", async (t) => {
  const { store } = await fixture(t);
  const cp = await prepared(store);
  for (const effects of [[], [{ ...operation, target: "github:other" }], [{ ...operation, state: "COMMITTED", readbackReference: "invented" }]]) {
    await assert.rejects(store.materialize({ eventId: "unsafe", trigger: "effect_readback", expected: cp, state: { ...cp.state, externalEffects: effects as never } }), /effect|readback/);
  }
  await assert.rejects(store.recoverEffect(cp, "op-1", async () => ({ ...await applied(), target: "github:other" })), /binding/);
  assert.equal((await store.read())!.generation, cp.generation);
});

test("Konkurrierende Effect-Ausführung beansprucht die Operation vor dem Callback exklusiv", async (t) => {
  const { store } = await fixture(t);
  const cp = await prepared(store);
  let calls = 0;
  const results = await Promise.allSettled([1, 2].map(() => store.executeEffect(cp, "op-1", async () => { calls++; }, applied)));
  assert.equal(results.filter(r => r.status === "fulfilled").length, 1);
  assert.equal(calls, 1);
});

test("Evidence-INCOMPLETE und Scope-/Dirty-Änderungen bleiben getrennt und werden nicht aufgewertet", async (t) => {
  const { store } = await fixture(t);
  const first = await initial(store);
  const input = { ...state(), projection: { ...state().projection, evidence: [], incompleteEvidence: ["test-1"] }, taskStatus: "INCOMPLETE" as const };
  const incomplete = await store.materialize({ eventId: "incomplete", trigger: "task_incomplete", expected: first, state: input });
  const changed = await store.materialize({ eventId: "scope", trigger: "scope_changed", expected: incomplete, state: { ...input, identities: { ...input.identities, scope: "scope-b", dirty: "diff-b" }, projection: { ...input.projection, scope: ["changed-scope"] } } });
  assert.deepEqual(changed!.state.projection.incompleteEvidence, ["test-1"]);
  assert.deepEqual(changed!.state.projection.evidence, []);
  await assert.rejects(store.read(incomplete!), /stale/);
  await assert.rejects(store.materialize({ eventId: "contradiction", trigger: "evidence_completed", expected: changed, state: { ...input, projection: { ...input.projection, evidence: state().projection.evidence } } }), /incomplete/);
});

test("Aufrufermutation während Persistenz kann keine ungeprüften Metadaten einschleusen", async (t) => {
  const { store } = await fixture(t);
  const input = state();
  const cp = await store.materialize({ eventId: "snapshot", trigger: "task_identified", expected: null, state: input }, point => {
    if (point === "beforeStage") (input.projection.scope as string[]).push("password=synthetic-only");
  });
  assert.deepEqual(cp!.state.projection.scope, ["resume"]);
});

test("Progressive Nachladung löst nur angefragte Evidence auf; fehlendes Artefakt scheitert", async (t) => {
  const { store } = await fixture(t);
  const cp = await initial(store);
  const seen: string[] = [];
  assert.equal(await store.evidenceReference(cp!, "test-1", async ref => { seen.push(ref); return true; }), "artifact:test-1");
  assert.deepEqual(seen, ["artifact:test-1"]);
  await assert.rejects(store.evidenceReference(cp!, "test-1", async () => false), /missing evidence/);
  await assert.rejects(store.evidenceReference(cp!, "unknown", async () => true), /missing evidence/);
});

test("SIGKILL vor/nach realer Wirkung und nach Readback erzeugt bei Recovery keinen zweiten Effekt", { timeout: 30000 }, async (t) => {
  for (const stage of ["beforeEffect", "afterEffect", "afterReadback"]) {
    const { directory, store } = await fixture(t);
    const target = `${directory}-effect`;
    t.after(() => rm(target, { force: true }));
    await prepared(store);
    const child = fork(new URL("../fixtures/resume/effect.ts", import.meta.url), [directory, target, stage], { stdio: ["ignore", "ignore", "pipe", "ipc"] });
    await once(child, "message");
    const done = once(child, "exit"); child.send("go");
    assert.equal((await done)[1], "SIGKILL");
    const fresh = await ResumeCheckpointStore.open(directory);
    const cp = (await fresh.read())!;
    assert.equal(cp.state.externalEffects[0]!.state, "UNKNOWN");
    const observed = await readFile(target, "utf8").catch(error => { if (error.code === "ENOENT") return ""; throw error; });
    const recovered = await fresh.recoverEffect(cp, "op-1", async () => ({ ...await applied(), outcome: observed ? "APPLIED" : "NOT_APPLIED" }));
    assert.equal(recovered.state.externalEffects[0]!.state, observed ? "COMMITTED" : "NOT_APPLIED");
    assert.equal(observed, stage === "beforeEffect" ? "" : "effect\n");
  }
});
