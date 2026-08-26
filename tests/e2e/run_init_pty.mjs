#!/usr/bin/env node
import { spawn } from "node:child_process";
import { mkdir, mkdtemp, realpath, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");

async function runChild() {
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
  const columnsArgument = process.argv.find((value) => value.startsWith("--columns="));
  const columns = columnsArgument?.slice("--columns=".length) ?? "80";
  if (!/^(?:60|80|120)$/u.test(columns)) throw new Error("columns must be 60, 80, or 120");
  const syntheticRoot = await realpath(await mkdtemp(join(tmpdir(), "agent-governance-init-pty-")));
  const home = join(syntheticRoot, "home");
  const xdgConfigHome = join(syntheticRoot, "xdg-config");
  const xdgDataHome = join(syntheticRoot, "xdg-data");
  const xdgCacheHome = join(syntheticRoot, "xdg-cache");
  const systemApplications = join(syntheticRoot, "system-applications");
  await Promise.all([home, xdgConfigHome, xdgDataHome, xdgCacheHome, systemApplications].map((path) => mkdir(path)));

  const childArguments = [process.execPath, "--experimental-strip-types", fileURLToPath(import.meta.url), "--child"];
  const expectDriver = [
    "set timeout 10",
    "set columns $env(AGENT_GOVERNANCE_TEST_COLUMNS)",
    "set executable $env(AGENT_GOVERNANCE_TEST_NODE)",
    "set entry $env(AGENT_GOVERNANCE_TEST_ENTRY)",
    "set stty_init \"rows 24 columns $columns\"",
    "spawn -noecho $executable --experimental-strip-types $entry --child",
    "expect {",
    "  -re {AI/LLM nicht dabei} { send \\003; exp_continue }",
    "  eof {}",
    "  timeout { exit 124 }",
    "}",
    "set result [wait]",
    "exit [lindex $result 3]",
  ].join("\n");
  const output = [];
  try {
    const child = spawn("expect", ["-c", expectDriver], {
      cwd: repositoryRoot,
      env: {
        PATH: process.env.PATH,
        HOME: home,
        XDG_CONFIG_HOME: xdgConfigHome,
        XDG_DATA_HOME: xdgDataHome,
        XDG_CACHE_HOME: xdgCacheHome,
        AGENT_GOVERNANCE_TEST_SYSTEM_APPLICATIONS: systemApplications,
        AGENT_GOVERNANCE_TEST_COLUMNS: columns,
        AGENT_GOVERNANCE_TEST_NODE: childArguments[0],
        AGENT_GOVERNANCE_TEST_ENTRY: childArguments[2],
        COLUMNS: columns,
        TERM: process.argv.includes("--no-color") ? "dumb" : "xterm-256color",
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
    else if (process.argv.includes("--cancel") && !/Einrichtung abgebrochen|INTERRUPTED/u.test(rendered)) process.exitCode = 1;
    else process.exitCode = exitCode === 0 || exitCode === 130 ? 0 : exitCode;
  } finally {
    await rm(syntheticRoot, { recursive: true, force: true });
  }
}

if (process.argv.includes("--child")) await runChild();
else await runParent();
