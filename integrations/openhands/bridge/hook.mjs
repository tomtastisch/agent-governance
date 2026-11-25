import { constants as C } from "node:fs";
import { lstat, mkdir, open, rename } from "node:fs/promises";
import { execFile } from "node:child_process";
import { homedir } from "node:os";
import path from "node:path";
import { promisify } from "node:util";

const exec = promisify(execFile);
const SID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$/;
const STATUSES = new Set(["todo", "in_progress", "done"]);
const WRITE_COMMANDS = new Set(["create", "str_replace", "insert", "write", "replace", "delete"]);
const VERIFY = /^(?:npm (?:test|run (?:test|lint|build|check|typecheck|verify))|pnpm (?:test|lint|build|check|typecheck)|yarn (?:test|lint|build|check)|python3? -m (?:unittest|pytest)|pytest|cargo test|go test|mvn (?:test|verify)|gradle (?:test|check)|\.\/gradlew (?:test|check)|make (?:test|check)|agent-governance verify)(?:\s|$)/;
const TWRITE = /(?:^|[;&| ]+)(?:rm|mv|cp|mkdir|touch|chmod|chown|git (?:add|commit|push|merge|rebase|checkout|switch|reset|clean)|npm (?:install|i|add|uninstall|remove)|pnpm (?:add|install|remove)|yarn (?:add|install|remove)|sed -i|perl -pi)(?: |$)/;
const TRO = /^\s*(?:pwd|ls(?: |$)|git (?:status|log|show|diff|branch|rev-parse|remote)(?: |$)|cat |grep |rg |find |head |tail |wc |stat |sed -n |node --version|npm --version|python3? --version)/;

const plain = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
const stateDir = () => process.env.AGENT_GOVERNANCE_OPENHANDS_STATE_DIR
  ?? path.join(homedir(), ".openhands", "governance-enforcement");

async function readInput() {
  process.stdin.setEncoding("utf8");
  let raw = "";
  for await (const chunk of process.stdin) {
    raw += chunk;
    if (Buffer.byteLength(raw) > 1048576) throw new Error("input_too_large");
  }
  const value = JSON.parse(raw || "{}");
  if (!plain(value)) throw new Error("input_not_object");
  return value;
}
function respond(decision, reason, additionalContext) {
  const body = { decision };
  if (reason) body.reason = reason;
  if (additionalContext) body.additionalContext = additionalContext;
  process.stdout.write(JSON.stringify(body));
  process.exit(decision === "deny" ? 2 : 0);
}
const allow = (context) => respond("allow", null, context);
const deny = (reason) => respond("deny", reason);
const fresh = (i) => ({
  schemaVersion: 1, sessionId: i.session_id, workingDir: i.working_dir ?? process.cwd(),
  plan: null, planRevision: 0, sequence: 0, substantiveActions: 0,
  lastChange: 0, lastVerify: 0, lastPlan: 0
});

async function ensureStateDir() {
  const dir = stateDir();
  await mkdir(dir, { recursive: true, mode: 0o700 });
  const s = await lstat(dir);
  if (!s.isDirectory() || s.isSymbolicLink() || (s.mode & 0o077) !== 0) {
    throw new Error("unsafe_state_directory");
  }
}
function stateFile(sessionId) {
  if (!SID.test(sessionId ?? "")) throw new Error("invalid_session_id");
  return path.join(stateDir(), `${sessionId}.json`);
}
async function loadState(input) {
  await ensureStateDir();
  const file = stateFile(input.session_id);
  try {
    const s = await lstat(file);
    if (!s.isFile() || s.isSymbolicLink() || s.size > 262144 || (s.mode & 0o077) !== 0) {
      throw new Error("unsafe_state_file");
    }
    const h = await open(file, C.O_RDONLY | (C.O_NOFOLLOW ?? 0));
    try { return JSON.parse(await h.readFile("utf8")); }
    finally { await h.close(); }
  } catch (error) {
    if (error?.code === "ENOENT") return fresh(input);
    throw error;
  }
}
async function saveState(state) {
  await ensureStateDir();
  const file = stateFile(state.sessionId);
  const temp = `${file}.tmp.${process.pid}`;
  const h = await open(temp, C.O_CREAT | C.O_EXCL | C.O_WRONLY, 0o600);
  try {
    await h.writeFile(`${JSON.stringify(state, null, 2)}\n`, "utf8");
    await h.sync();
  } finally { await h.close(); }
  await rename(temp, file);
  const s = await lstat(file);
  if (!s.isFile() || s.isSymbolicLink() || (s.mode & 0o077) !== 0) {
    throw new Error("state_write_failed");
  }
}

async function verifyGovernance() {
  const cli = process.env.AGENT_GOVERNANCE_CLI ?? "agent-governance";
  const targetRoot = process.env.AGENT_GOVERNANCE_TARGET_ROOT ?? path.join(homedir(), ".agents");
  const entryFile = process.env.AGENT_GOVERNANCE_ENTRY_FILE ?? "AGENTS.md";
  const installationRoot = process.env.AGENT_GOVERNANCE_INSTALLATION_ROOT
    ?? path.join(homedir(), ".agent-governance");
  const { stdout } = await exec(cli, [
    "verify", "--target-root", targetRoot, "--entry-file", entryFile,
    "--scope", "global", "--installation-root", installationRoot,
    "--json", "--non-interactive"
  ], { timeout: 15000, maxBuffer: 262144, encoding: "utf8" });
  const result = JSON.parse(stdout.trim());
  if (result?.outcome !== "SUCCESS" || result?.state !== "CURRENT") {
    throw new Error(`governance_not_current:${result?.state ?? "unknown"}`);
  }
}

function validatePlan(tasks) {
  if (!Array.isArray(tasks) || tasks.length < 1 || tasks.length > 100) {
    return "task_tracker requires 1..100 tasks";
  }
  let active = 0;
  const titles = new Set();
  for (const task of tasks) {
    if (!plain(task) || typeof task.title !== "string" || task.title.trim().length < 1 || task.title.length > 500) {
      return "task_tracker task title is invalid";
    }
    if (!STATUSES.has(task.status)) return `task_tracker status is invalid for ${task.title}`;
    if (titles.has(task.title)) return `task_tracker contains duplicate task: ${task.title}`;
    titles.add(task.title);
    if (task.status === "in_progress") active += 1;
  }
  const unfinished = tasks.some((task) => task.status !== "done");
  if (active > 1) return "task_tracker permits at most one in_progress task";
  if (unfinished && active !== 1) return "task_tracker requires exactly one in_progress task while work remains";
  return null;
}
const currentTask = (plan) => Array.isArray(plan)
  ? plan.find((task) => task.status === "in_progress") ?? null
  : null;

function transitionError(state, next) {
  const previous = Array.isArray(state.plan) ? state.plan : [];
  if (previous.length === 0) return null;
  const nextByTitle = new Map(next.map((task) => [task.title, task]));
  for (const old of previous) {
    if (old.status !== "done" && !nextByTitle.has(old.title)) {
      return `open task may not be silently removed: ${old.title}`;
    }
    if (old.status === "done" && nextByTitle.get(old.title)?.status !== "done") {
      return `completed task may not be reopened: ${old.title}`;
    }
  }
  const oldActive = currentTask(previous);
  const newActive = currentTask(next);
  if (oldActive && newActive?.title !== oldActive.title) {
    if (nextByTitle.get(oldActive.title)?.status !== "done") {
      return `active task must be completed before advancing: ${oldActive.title}`;
    }
    if (state.lastChange > state.lastVerify) {
      return `verify changes for ${oldActive.title} before advancing the task plan`;
    }
  }
  if (oldActive && nextByTitle.get(oldActive.title)?.status === "done"
      && state.lastChange > state.lastVerify) {
    return `verify changes for ${oldActive.title} before marking it done`;
  }
  return null;
}

const command = (input) => typeof input?.command === "string" ? input.command : "";
function hasWriteRedirect(value) {
  const sanitized = value
    .replace(/(?:^|\s)\d*>>?\s*\/dev\/null(?=\s|$)/g, " ")
    .replace(/(?:^|\s)\d*>>?\s*&\d+(?=\s|$)/g, " ");
  return /(?:^|\s)\d*>>?\s*[^&\s]+/.test(sanitized);
}
function isReadOnly(tool, input) {
  if (tool === "file_editor") return input?.command === "view";
  if (tool === "terminal") return TRO.test(command(input)) && !TWRITE.test(command(input)) && !hasWriteRedirect(command(input));
  if (tool === "task_tracker") return false;
  return /(?:read|get|list|search|find|view|status|diff|log)/i.test(tool ?? "");
}
function isChange(tool, input) {
  if (tool === "file_editor") return WRITE_COMMANDS.has(input?.command);
  if (["apply_patch", "write_file", "edit_file"].includes(tool)) return true;
  if (tool === "terminal") return TWRITE.test(command(input)) || hasWriteRedirect(command(input));
  return /(?:create|update|delete|write|edit|merge|push|publish|upload|move|rename)/i.test(tool ?? "");
}
function isVerification(tool, input) {
  if (tool !== "terminal") return false;
  return command(input).split(/&&|;|\|\|/).some((part) => VERIFY.test(part.trim()));
}
function succeeded(response) {
  if (!plain(response)) return true;
  if (response.is_error === true) return false;
  if (Number.isInteger(response.exit_code) && response.exit_code !== 0) return false;
  return true;
}

async function onPrompt(input) {
  const state = await loadState(input);
  state.workingDir = input.working_dir ?? state.workingDir;
  await saveState(state);
  allow("Agent Governance is immutable and verified. For substantive multi-step work use the native task_tracker iteratively: keep exactly one subtask in_progress, execute it, verify relevant effects, update its status immediately, then advance to the next subtask.");
}
async function onPreTool(input) {
  const state = await loadState(input);
  const tool = input.tool_name;
  const toolInput = plain(input.tool_input) ? input.tool_input : {};
  if (tool === "finish") allow();
  if (tool === "task_tracker") {
    const next = toolInput.task_list;
    const invalid = validatePlan(next);
    if (invalid) deny(invalid);
    const transition = transitionError(state, next);
    if (transition) deny(transition);
    allow();
  }
  if (!isReadOnly(tool, toolInput) && !currentTask(state.plan)) {
    deny("Substantive action blocked: create or update the native task_tracker first and keep exactly one subtask in_progress.");
  }
  allow();
}
async function onPostTool(input) {
  const state = await loadState(input);
  if (!succeeded(input.tool_response)) allow();
  const tool = input.tool_name;
  if (tool === "finish") allow();
  state.sequence += 1;
  const toolInput = plain(input.tool_input) ? input.tool_input : {};
  if (tool === "task_tracker") {
    const plan = input.tool_response?.task_list ?? toolInput.task_list;
    const invalid = validatePlan(plan);
    if (invalid) throw new Error(`invalid_persisted_plan:${invalid}`);
    state.plan = plan;
    state.planRevision += 1;
    state.lastPlan = state.sequence;
  } else {
    if (!isReadOnly(tool, toolInput)) state.substantiveActions += 1;
    if (isChange(tool, toolInput)) state.lastChange = state.sequence;
    if (isVerification(tool, toolInput)) state.lastVerify = state.sequence;
  }
  await saveState(state);
  allow();
}
async function onStop(input) {
  const state = await loadState(input);
  if (state.substantiveActions === 0 && !state.plan) allow();
  const invalid = validatePlan(state.plan);
  if (invalid) deny(`Completion blocked: ${invalid}`);
  const openTasks = state.plan.filter((task) => task.status !== "done");
  if (openTasks.length) {
    deny(`Completion blocked: unfinished tasks remain (${openTasks.map((task) => task.title).join(", ")}).`);
  }
  if (state.lastChange > state.lastVerify) {
    deny("Completion blocked: the latest change has no successful verification or test evidence.");
  }
  if (state.lastChange > 0 && state.lastPlan <= state.lastVerify) {
    deny("Completion blocked: update task_tracker after the final successful verification before finishing.");
  }
  allow();
}
async function main() {
  try {
    const event = await readInput();
    if (!SID.test(event.session_id ?? "")) deny("Agent Governance enforcement blocked: invalid OpenHands session identity.");
    await verifyGovernance();
    if (event.event_type === "UserPromptSubmit") return onPrompt(event);
    if (event.event_type === "PreToolUse") return onPreTool(event);
    if (event.event_type === "PostToolUse") return onPostTool(event);
    if (event.event_type === "Stop") return onStop(event);
    allow();
  } catch (error) {
    deny(`Agent Governance enforcement blocked fail-closed: ${String(error?.message ?? error).slice(0, 500)}`);
  }
}
await main();
