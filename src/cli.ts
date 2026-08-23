#!/usr/bin/env node
import { pathToFileURL } from "node:url";

import { EXIT_CODES, exitCodeFor, type InstallerRequest } from "./contracts.ts";
import { InstallerFailure } from "./errors.ts";
import { InstallerTransaction } from "./transaction.ts";

type Writer = (value: string) => void;
const COMMANDS = new Set(["inspect", "plan", "install", "verify", "rollback", "status"]);
const VALUE_OPTIONS = new Set(["--harness", "--home", "--allowed-root", "--release-root", "--install-root"]);

function parse(argv: readonly string[]): { command: string; request: InstallerRequest; json: boolean } {
  const command = argv[0];
  if (command === undefined || !COMMANDS.has(command)) throw new Error("unknown or missing command");
  const values = new Map<string, string>();
  let json = false;
  let dryRun = false;
  for (let index = 1; index < argv.length; index += 1) {
    const option = argv[index];
    if (option === "--json") { json = true; continue; }
    if (option === "--dry-run") { dryRun = true; continue; }
    if (option === undefined || !option.startsWith("--")) throw new Error("invalid argument");
    if (!VALUE_OPTIONS.has(option)) throw new Error(`unknown option ${option}`);
    if (values.has(option)) throw new Error(`duplicate option ${option}`);
    const value = argv[index + 1];
    if (value === undefined || value.startsWith("--")) throw new Error(`missing value for ${option}`);
    values.set(option, value);
    index += 1;
  }
  const required = ["--harness", "--home", "--allowed-root", "--release-root", "--install-root"];
  for (const key of required) if (!values.has(key)) throw new Error(`missing required option ${key}`);
  return {
    command,
    json,
    request: {
      harness: values.get("--harness")!, home: values.get("--home")!,
      allowedRoot: values.get("--allowed-root")!, releaseRoot: values.get("--release-root")!,
      installRoot: values.get("--install-root")!, dryRun: dryRun || command === "plan",
    },
  };
}

export async function runCli(argv: readonly string[], out: Writer = console.log, error: Writer = console.error): Promise<number> {
  let parsed: ReturnType<typeof parse>;
  try { parsed = parse(argv); } catch (cause) {
    error(JSON.stringify({ outcome: "INVALID_INVOCATION", error: (cause as Error).message }));
    return EXIT_CODES.INVALID_INVOCATION;
  }
  if (parsed.request.harness !== "codex") {
    error(JSON.stringify({ outcome: "UNSUPPORTED_HARNESS", harness: parsed.request.harness }));
    return EXIT_CODES.UNSUPPORTED_HARNESS;
  }
  try {
    const transaction = new InstallerTransaction(parsed.request);
    const result = parsed.command === "inspect" ? await transaction.inspect()
      : parsed.command === "plan" ? await transaction.plan()
      : parsed.command === "install" ? await transaction.install()
      : parsed.command === "verify" ? await transaction.verify()
      : parsed.command === "rollback" ? await transaction.rollback()
      : await transaction.status();
    out(parsed.json ? JSON.stringify(result) : `${result.outcome}: ${result.state} (${result.phase})`);
    return exitCodeFor(result.outcome);
  } catch (cause) {
    if (cause instanceof InstallerFailure) {
      error(JSON.stringify({
        outcome: cause.outcome,
        phase: cause.phase,
        resourceId: cause.resourceId,
        rollbackStatus: cause.rollbackStatus,
        code: cause.code,
        error: cause.message,
      }));
      return exitCodeFor(cause.outcome);
    }
    error(JSON.stringify({ outcome: "UNSAFE_STATE", error: (cause as Error).message }));
    return EXIT_CODES.UNSAFE_STATE;
  }
}

if (process.argv[1] !== undefined && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exitCode = await runCli(process.argv.slice(2));
}
