import assert from "node:assert/strict";
import { chmod, mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { fileURLToPath } from "node:url";

const testDirectory = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(testDirectory, "..", "..");
const hook = path.join(root, "integrations", "openhands", "bridge", "hook.mjs");

async function fixture() {
  const dir = await mkdtemp(path.join(os.tmpdir(), "ag-openhands-hook-"));
  const target = path.join(dir, "agents");
  const install = path.join(dir, "install");
  const state = path.join(dir, "state");
  const bundle = path.join(install, "releases", "1.9.4", "bundle");
  await mkdir(path.join(bundle, "agent-governance"), { recursive: true });
  await mkdir(target, { recursive: true });
  await mkdir(state, { recursive: true });
  await writeFile(path.join(bundle, "GOVERNANCE.md"), "# Agent Governance\n", "utf8");
  await writeFile(path.join(bundle, "agent-governance", "manifest.toml"), "schema_version = 4\n", "utf8");
  await writeFile(path.join(target, "AGENTS.md"), [
    "<!-- BEGIN AGENT_GOVERNANCE_MANAGED_V1 -->",
    `Normative governance entry: ${path.join(bundle, "GOVERNANCE.md")}`,
    `Normative manifest: ${path.join(bundle, "agent-governance", "manifest.toml")}`,
    "<!-- END AGENT_GOVERNANCE_MANAGED_V1 -->",
    "",
  ].join("\n"), "utf8");
  const cli = path.join(dir, "agent-governance");
  await writeFile(cli, `#!/bin/sh\nprintf '%s\\n' '{"schemaVersion":1,"outcome":"SUCCESS","state":"CURRENT"}'\n`, "utf8");
  await chmod(cli, 0o700);
  const work = path.join(dir, "work");
  await mkdir(work);
  return { dir, target, install, state, cli, work };
}

function event(type, overrides = {}) {
  return {
    event_type: type,
    session_id: "session-test-001",
    working_dir: overrides.working_dir,
    tool_name: overrides.tool_name ?? null,
    tool_input: overrides.tool_input ?? null,
    tool_response: overrides.tool_response ?? null,
    message: overrides.message ?? null,
    metadata: overrides.metadata ?? {},
  };
}

function runHook(fx, payload) {
  const result = spawnSync(process.execPath, [hook], {
    input: JSON.stringify(payload), encoding: "utf8", cwd: fx.work,
    env: {
      ...process.env,
      AGENT_GOVERNANCE_CLI: fx.cli,
      AGENT_GOVERNANCE_TARGET_ROOT: fx.target,
      AGENT_GOVERNANCE_ENTRY_FILE: "AGENTS.md",
      AGENT_GOVERNANCE_INSTALLATION_ROOT: fx.install,
      AGENT_GOVERNANCE_OPENHANDS_STATE_DIR: fx.state,
    },
  });
  let body = {};
  if (result.stdout.trim()) body = JSON.parse(result.stdout);
  return { ...result, body };
}

const activePlan = [
  { title: "Inspect", notes: "", status: "in_progress" },
  { title: "Implement", notes: "", status: "todo" },
];

async function ok(fx, payload) {
  const result = runHook(fx, payload);
  assert.equal(result.status, 0, result.stderr);
  return result;
}

async function savePlan(fx, tasks) {
  await ok(fx, event("PreToolUse", { working_dir: fx.work, tool_name: "task_tracker", tool_input: { command: "plan", task_list: tasks } }));
  await ok(fx, event("PostToolUse", { working_dir: fx.work, tool_name: "task_tracker", tool_input: { command: "plan", task_list: tasks }, tool_response: { is_error: false, command: "plan", task_list: tasks } }));
}

test("substantive actions require an active task plan", async () => {
  const fx = await fixture();
  try {
    await ok(fx, event("UserPromptSubmit", { working_dir: fx.work, message: "Implement feature" }));
    const blocked = runHook(fx, event("PreToolUse", { working_dir: fx.work, tool_name: "file_editor", tool_input: { command: "str_replace", path: path.join(fx.work, "a.js") } }));
    assert.equal(blocked.status, 2);
    assert.equal(blocked.body.decision, "deny");
    assert.match(blocked.body.reason, /task_tracker/i);
  } finally { await rm(fx.dir, { recursive: true, force: true }); }
});

test("task plan permits at most one in_progress item", async () => {
  const fx = await fixture();
  try {
    await ok(fx, event("UserPromptSubmit", { working_dir: fx.work, message: "Implement feature" }));
    const blocked = runHook(fx, event("PreToolUse", { working_dir: fx.work, tool_name: "task_tracker", tool_input: { command: "plan", task_list: [
      { title: "A", status: "in_progress" }, { title: "B", status: "in_progress" },
    ] } }));
    assert.equal(blocked.status, 2);
    assert.match(blocked.body.reason, /höchstens|at most|in_progress/i);
  } finally { await rm(fx.dir, { recursive: true, force: true }); }
});

test("iterative plan update plus verification allows stop", async () => {
  const fx = await fixture();
  try {
    await ok(fx, event("UserPromptSubmit", { working_dir: fx.work, message: "Implement feature" }));
    await savePlan(fx, activePlan);
    await ok(fx, event("PreToolUse", { working_dir: fx.work, tool_name: "file_editor", tool_input: { command: "view", path: path.join(fx.work, "a.js") } }));
    await ok(fx, event("PostToolUse", { working_dir: fx.work, tool_name: "file_editor", tool_input: { command: "view", path: path.join(fx.work, "a.js") }, tool_response: { is_error: false } }));
    const second = [
      { title: "Inspect", notes: "verified", status: "done" },
      { title: "Implement", notes: "", status: "in_progress" },
    ];
    await savePlan(fx, second);
    await ok(fx, event("PreToolUse", { working_dir: fx.work, tool_name: "file_editor", tool_input: { command: "str_replace", path: path.join(fx.work, "a.js") } }));
    await ok(fx, event("PostToolUse", { working_dir: fx.work, tool_name: "file_editor", tool_input: { command: "str_replace", path: path.join(fx.work, "a.js") }, tool_response: { is_error: false } }));
    await ok(fx, event("PreToolUse", { working_dir: fx.work, tool_name: "terminal", tool_input: { command: "npm test" } }));
    await ok(fx, event("PostToolUse", { working_dir: fx.work, tool_name: "terminal", tool_input: { command: "npm test" }, tool_response: { is_error: false, exit_code: 0 } }));
    const done = second.map((item) => ({ ...item, status: "done" }));
    await savePlan(fx, done);
    const stopped = runHook(fx, event("Stop", { working_dir: fx.work, metadata: { reason: "finish" } }));
    assert.equal(stopped.status, 0, stopped.stderr);
    assert.equal(stopped.body.decision, "allow");
  } finally { await rm(fx.dir, { recursive: true, force: true }); }
});

test("stop blocks unfinished plans", async () => {
  const fx = await fixture();
  try {
    await ok(fx, event("UserPromptSubmit", { working_dir: fx.work, message: "Implement feature" }));
    await savePlan(fx, activePlan);
    const blocked = runHook(fx, event("Stop", { working_dir: fx.work }));
    assert.equal(blocked.status, 2);
    assert.match(blocked.body.reason, /offen|unfinished|in_progress|todo/i);
  } finally { await rm(fx.dir, { recursive: true, force: true }); }
});

test("stop blocks a final change without later verification and plan refresh", async () => {
  const fx = await fixture();
  try {
    await ok(fx, event("UserPromptSubmit", { working_dir: fx.work, message: "Implement feature" }));
    await savePlan(fx, [{ title: "Implement", status: "in_progress", notes: "" }]);
    await ok(fx, event("PreToolUse", { working_dir: fx.work, tool_name: "file_editor", tool_input: { command: "str_replace", path: path.join(fx.work, "a.js") } }));
    await ok(fx, event("PostToolUse", { working_dir: fx.work, tool_name: "file_editor", tool_input: { command: "str_replace", path: path.join(fx.work, "a.js") }, tool_response: { is_error: false } }));
    const blockedPlan = runHook(fx, event("PreToolUse", { working_dir: fx.work, tool_name: "task_tracker", tool_input: { command: "plan", task_list: [{ title: "Implement", status: "done", notes: "" }] } }));
    assert.equal(blockedPlan.status, 2);
    assert.match(blockedPlan.body.reason, /verify|verifiz/i);
    const blockedStop = runHook(fx, event("Stop", { working_dir: fx.work }));
    assert.equal(blockedStop.status, 2);
    assert.match(blockedStop.body.reason, /unfinished|in_progress/i);
  } finally { await rm(fx.dir, { recursive: true, force: true }); }
});


test("finish bypasses PreToolUse task activity and is governed by Stop", async () => {
  const fx = await fixture();
  try {
    await ok(fx, event("UserPromptSubmit", { working_dir: fx.work, message: "Implement feature" }));
    await savePlan(fx, [{ title: "Implement", status: "in_progress", notes: "" }]);
    await ok(fx, event("PreToolUse", { working_dir: fx.work, tool_name: "terminal", tool_input: { command: "npm test" } }));
    await ok(fx, event("PostToolUse", { working_dir: fx.work, tool_name: "terminal", tool_input: { command: "npm test" }, tool_response: { is_error: false, exit_code: 0 } }));
    await savePlan(fx, [{ title: "Implement", status: "done", notes: "verified" }]);
    const preFinish = runHook(fx, event("PreToolUse", { working_dir: fx.work, tool_name: "finish", tool_input: { message: "done" } }));
    assert.equal(preFinish.status, 0, preFinish.stderr);
    assert.equal(preFinish.body.decision, "allow");
  } finally { await rm(fx.dir, { recursive: true, force: true }); }
});


test("stderr redirection to devnull remains read-only", async () => {
  const fx = await fixture();
  try {
    await ok(fx, event("UserPromptSubmit", { working_dir: fx.work, message: "Review" }));
    await savePlan(fx, [{ title: "Inspect", status: "in_progress", notes: "" }, { title: "Report", status: "todo", notes: "" }]);
    const action = { command: "find . -type f 2>/dev/null" };
    await ok(fx, event("PreToolUse", { working_dir: fx.work, tool_name: "terminal", tool_input: action }));
    await ok(fx, event("PostToolUse", { working_dir: fx.work, tool_name: "terminal", tool_input: action, tool_response: { is_error: false, exit_code: 0 } }));
    await savePlan(fx, [{ title: "Inspect", status: "done", notes: "reviewed" }, { title: "Report", status: "in_progress", notes: "" }]);
  } finally { await rm(fx.dir, { recursive: true, force: true }); }
});

test("file redirection remains a write effect", async () => {
  const fx = await fixture();
  try {
    await ok(fx, event("UserPromptSubmit", { working_dir: fx.work, message: "Generate" }));
    await savePlan(fx, [{ title: "Generate", status: "in_progress", notes: "" }, { title: "Report", status: "todo", notes: "" }]);
    const action = { command: "find . -type f > files.txt" };
    await ok(fx, event("PreToolUse", { working_dir: fx.work, tool_name: "terminal", tool_input: action }));
    await ok(fx, event("PostToolUse", { working_dir: fx.work, tool_name: "terminal", tool_input: action, tool_response: { is_error: false, exit_code: 0 } }));
    const blocked = runHook(fx, event("PreToolUse", { working_dir: fx.work, tool_name: "task_tracker", tool_input: { command: "plan", task_list: [{ title: "Generate", status: "done", notes: "" }, { title: "Report", status: "in_progress", notes: "" }] } }));
    assert.equal(blocked.status, 2);
    assert.match(blocked.body.reason, /verify/i);
  } finally { await rm(fx.dir, { recursive: true, force: true }); }
});


test("read-only session may finish without creating a task plan", async () => {
  const fx = await fixture();
  try {
    await ok(fx, event("UserPromptSubmit", { working_dir: fx.work, message: "Review" }));
    await ok(fx, event("PreToolUse", { working_dir: fx.work, tool_name: "file_editor", tool_input: { command: "view", path: path.join(fx.work, "a.js") } }));
    await ok(fx, event("PostToolUse", { working_dir: fx.work, tool_name: "file_editor", tool_input: { command: "view", path: path.join(fx.work, "a.js") }, tool_response: { is_error: false } }));
    await ok(fx, event("PreToolUse", { working_dir: fx.work, tool_name: "finish", tool_input: { message: "review complete" } }));
    await ok(fx, event("PostToolUse", { working_dir: fx.work, tool_name: "finish", tool_input: { message: "review complete" }, tool_response: { is_error: false } }));
    const stopped = runHook(fx, event("Stop", { working_dir: fx.work }));
    assert.equal(stopped.status, 0, stopped.stderr);
    assert.equal(stopped.body.decision, "allow");
  } finally { await rm(fx.dir, { recursive: true, force: true }); }
});


test("verification evidence requires an actual verification command", async () => {
  const fx = await fixture();
  try {
    await ok(fx, event("UserPromptSubmit", { working_dir: fx.work, message: "Implement" }));
    await savePlan(fx, [{ title: "Implement", status: "in_progress", notes: "" }]);
    await ok(fx, event("PreToolUse", { working_dir: fx.work, tool_name: "file_editor", tool_input: { command: "str_replace", path: path.join(fx.work, "a.js") } }));
    await ok(fx, event("PostToolUse", { working_dir: fx.work, tool_name: "file_editor", tool_input: { command: "str_replace", path: path.join(fx.work, "a.js") }, tool_response: { is_error: false } }));
    const fakeVerify = { command: 'echo "npm test"' };
    await ok(fx, event("PreToolUse", { working_dir: fx.work, tool_name: "terminal", tool_input: fakeVerify }));
    await ok(fx, event("PostToolUse", { working_dir: fx.work, tool_name: "terminal", tool_input: fakeVerify, tool_response: { is_error: false, exit_code: 0 } }));
    const blocked = runHook(fx, event("PreToolUse", { working_dir: fx.work, tool_name: "task_tracker", tool_input: { command: "plan", task_list: [{ title: "Implement", status: "done", notes: "" }] } }));
    assert.equal(blocked.status, 2);
    assert.match(blocked.body.reason, /verify/i);
  } finally { await rm(fx.dir, { recursive: true, force: true }); }
});
