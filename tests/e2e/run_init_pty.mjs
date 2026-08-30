#!/usr/bin/env node
import { spawn } from "node:child_process";
import { chmod, mkdir, mkdtemp, realpath, rm, writeFile } from "node:fs/promises";
import { createRequire, syncBuiltinESMExports } from "node:module";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const require = createRequire(import.meta.url);

function markerCandidate(root, confidence) {
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
    evidenceDigest: "c".repeat(64),
  };
}

async function runChild() {
  if (process.argv.includes("--markers-child") || process.argv.includes("--fallback-child") || process.argv.includes("--entry-child")) {
    const { createClackPrompt } = await import("../../src/init/prompt.ts");
    const { INIT_CANCELLED } = await import("../../src/init/types.ts");
    const columns = process.env.AGENT_GOVERNANCE_TEST_COLUMNS;
    if (!columns || !/^(?:60|80|120)$/u.test(columns)) throw new Error("synthetic PTY columns are invalid");
    const candidates = process.argv.includes("--entry-child")
      ? [markerCandidate(join(process.env.XDG_CONFIG_HOME, "runtime-profile"), "HIGH_CONFIDENCE")]
      : process.argv.includes("--fallback-child")
      ? Array.from({ length: 20 }, (_, index) => markerCandidate(
          `/synthetic/Candidate-${String(index + 1).padStart(2, "0")}-${"multiline-label-".repeat(4)}`,
          index === 0 ? "HIGH_CONFIDENCE" : "UNCERTAIN",
        ))
      : [
          markerCandidate("/synthetic/High", "HIGH_CONFIDENCE"),
          markerCandidate("/synthetic/Uncertain", "UNCERTAIN"),
        ];
    const result = await createClackPrompt({
      columns: Number.parseInt(columns, 10),
      environment: process.env,
    }).selectTargets(candidates);
    if (process.argv.includes("--entry-child")) {
      const entryFile = result === INIT_CANCELLED ? "CANCELLED" : result[0]?.manualInput.entryFile;
      process.stdout.write(`ENTRY_SELECTION_COMPLETED=${String(entryFile)}\n`);
      return;
    }
    const prefix = process.argv.includes("--fallback-child") ? "FALLBACK" : "MARKER";
    process.stdout.write(result === INIT_CANCELLED ? `${prefix}_PROMPT_CANCELLED\n` : `${prefix}_PROMPT_COMPLETED\n`);
    return;
  }
  if (process.argv.includes("--boundary-child")) {
    const childProcess = require("node:child_process");
    const intercepted = [];
    const methods = ["spawn", "spawnSync", "exec", "execSync", "execFile", "execFileSync", "fork"];
    for (const method of methods) {
      Object.defineProperty(childProcess, method, {
        configurable: true,
        value: (...args) => {
          intercepted.push(`${method}:${String(args[0])}`);
          throw new Error(`forbidden child process via ${method}`);
        },
        writable: true,
      });
    }
    syncBuiltinESMExports();
    const { runCli } = await import("../../src/cli.ts");
    const exitCode = await runCli(["init"], console.log, console.error);
    process.stdout.write(`INIT_BOUNDARY_EXIT=${exitCode}\n`);
    process.stdout.write(`INIT_BOUNDARY_SPAWN_LOG=${JSON.stringify(intercepted)}\n`);
    return;
  }
  const { runCli } = await import("../../src/cli.ts");
  const home = process.env.HOME;
  const xdgConfigHome = process.env.XDG_CONFIG_HOME;
  const xdgDataHome = process.env.XDG_DATA_HOME;
  const systemApplications = process.env.AGENT_GOVERNANCE_TEST_SYSTEM_APPLICATIONS;
  if (!home || !xdgConfigHome || !xdgDataHome || !systemApplications) {
    throw new Error("synthetic PTY environment is incomplete");
  }
  process.exitCode = await runCli(["init"], console.log, console.error, {
    initOptions: {
      isTTY: Boolean(process.stdin.isTTY && process.stdout.isTTY),
      environment: {
        home,
        xdgConfigHome,
        xdgDataHome,
        macosSystemApplications: systemApplications,
        platform: process.platform,
      },
      releaseRoot: repositoryRoot,
    },
  });
}

async function runParent() {
  const markers = process.argv.includes("--markers");
  const fallback = process.argv.includes("--fallback");
  const entryNewFile = process.argv.includes("--entry-new-file");
  const boundary = process.argv.includes("--boundary");
  const columnsArgument = process.argv.find((value) => value.startsWith("--columns="));
  const columns = columnsArgument?.slice("--columns=".length) ?? "80";
  if (!/^(?:60|80|120)$/u.test(columns)) throw new Error("columns must be 60, 80, or 120");
  const syntheticRoot = await realpath(await mkdtemp(join(tmpdir(), "agent-governance-init-pty-")));
  const home = join(syntheticRoot, "home");
  const xdgConfigHome = join(syntheticRoot, "xdg-config");
  const xdgDataHome = join(syntheticRoot, "xdg-data");
  const xdgCacheHome = join(syntheticRoot, "xdg-cache");
  const systemApplications = join(syntheticRoot, "system-applications");
  const managerShims = join(syntheticRoot, "manager-shims");
  await Promise.all([home, xdgConfigHome, xdgDataHome, xdgCacheHome, systemApplications, managerShims].map((path) => mkdir(path)));
  if (entryNewFile) await mkdir(join(xdgConfigHome, "runtime-profile"));
  if (boundary) {
    await Promise.all(["npm", "pnpm", "yarn", "bun"].map(async (manager) => {
      const shim = join(managerShims, manager);
      await writeFile(shim, "#!/bin/sh\nexit 73\n", "utf8");
      await chmod(shim, 0o755);
    }));
  }

  const childEntry = fileURLToPath(import.meta.url);
  const interaction = boundary
    ? [
        "expect -re {Search:}",
        "send \\033",
        "expect eof",
      ]
    : entryNewFile
    ? [
        "expect -re {Search:}",
        "send -- \"\\r\"",
        "expect -re {relative Markdown-Entry-Datei}",
        "send -- \"AGENTS.md\\r\"",
        "expect -re {ENTRY_SELECTION_COMPLETED=AGENTS.md}",
        "expect eof",
      ]
    : fallback
    ? [
        "expect -re {(?:◻|\\[\u2022\\]) AI/LLM nicht dabei\\?}",
        "send -- \"Candidate-19\"",
        "after 300",
        "expect -re {(?:◻|\\[\u2022\\]) AI/LLM nicht dabei\\?}",
        "send -- \"\\t\"",
        "after 200",
        "expect -re {(?:◼|\\[\\+\\]) AI/LLM nicht dabei\\?}",
        "puts \"FALLBACK_SEARCH_ACTION_VISIBLE\"",
        "send \\003",
        "expect eof",
      ]
    : markers
    ? [
        "expect -re {Search:}",
        "send -- \"Uncertain\"",
        "after 200",
        "send -- \"\\033\\[B\"",
        "after 200",
        "expect -re {Space/Tab:.*select}",
        "send -- \" \"",
        "expect -re {Uncertain}",
        "puts \"MARKER_SELECTION_RENDERED\"",
        "send \\003",
        "expect eof",
      ]
    : [
        "expect {",
        "  -re {Search:} { send \\003; exp_continue }",
        "  eof {}",
        "  timeout { exit 124 }",
        "}",
      ];
  const expectDriver = [
    "set timeout 10",
    "set columns $env(AGENT_GOVERNANCE_TEST_COLUMNS)",
    "set executable $env(AGENT_GOVERNANCE_TEST_NODE)",
    "set entry $env(AGENT_GOVERNANCE_TEST_ENTRY)",
    "set stty_init \"rows 24 columns $columns\"",
    `spawn -noecho $executable --experimental-strip-types $entry ${entryNewFile ? "--entry-child" : fallback ? "--fallback-child" : markers ? "--markers-child" : boundary ? "--boundary-child" : "--child"}`,
    ...interaction,
    "set result [wait]",
    "exit [lindex $result 3]",
  ].join("\n");
  const output = [];
  try {
    const child = spawn("expect", ["-c", expectDriver], {
      cwd: repositoryRoot,
      env: {
        PATH: boundary ? `${managerShims}:${process.env.PATH ?? ""}` : process.env.PATH,
        HOME: home,
        XDG_CONFIG_HOME: xdgConfigHome,
        XDG_DATA_HOME: xdgDataHome,
        XDG_CACHE_HOME: xdgCacheHome,
        AGENT_GOVERNANCE_TEST_SYSTEM_APPLICATIONS: systemApplications,
        AGENT_GOVERNANCE_TEST_COLUMNS: columns,
        AGENT_GOVERNANCE_TEST_NODE: process.execPath,
        AGENT_GOVERNANCE_TEST_ENTRY: childEntry,
        COLUMNS: columns,
        TERM: process.argv.includes("--term-linux") ? "linux" : "xterm-256color",
        ...(process.argv.includes("--no-color") ? { NO_COLOR: "1" } : {}),
      },
      stdio: ["pipe", "pipe", "pipe"],
    });
    child.stdout.on("data", (chunk) => output.push(chunk));
    child.stderr.on("data", (chunk) => output.push(chunk));
    const exitCode = await new Promise((accept, reject) => {
      const timeout = setTimeout(() => {
        child.kill("SIGTERM");
        reject(new Error(`PTY init smoke timed out after output: ${Buffer.concat(output).toString("utf8")}`));
      }, 10_000);
      child.once("error", reject);
      child.once("exit", (code) => {
        clearTimeout(timeout);
        accept(code ?? 1);
      });
    });
    const rendered = Buffer.concat(output).toString("utf8");
    process.stdout.write(rendered);
    if (/interactive init prompt is unavailable/u.test(rendered)) process.exitCode = 1;
    else if (entryNewFile && !/ENTRY_SELECTION_COMPLETED=AGENTS\.md/u.test(rendered)) process.exitCode = 1;
    else if (fallback && (!/FALLBACK_SEARCH_ACTION_VISIBLE/u.test(rendered) || !/FALLBACK_PROMPT_CANCELLED/u.test(rendered))) process.exitCode = 1;
    else if (markers && (!/MARKER_SELECTION_RENDERED/u.test(rendered) || !/MARKER_PROMPT_CANCELLED/u.test(rendered))) process.exitCode = 1;
    else if (process.argv.includes("--cancel") && !/Einrichtung abgebrochen|INTERRUPTED/u.test(rendered)) process.exitCode = 1;
    else process.exitCode = exitCode === 0 || exitCode === 130 ? 0 : exitCode;
  } finally {
    await rm(syntheticRoot, { recursive: true, force: true });
  }
}

if (process.argv.includes("--child") || process.argv.includes("--markers-child") || process.argv.includes("--fallback-child") || process.argv.includes("--entry-child") || process.argv.includes("--boundary-child")) await runChild();
else await runParent();
