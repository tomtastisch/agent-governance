#!/usr/bin/env node
import { fileURLToPath, pathToFileURL } from "node:url";
import { COMMANDS, EXIT_CODES, exitCodeFor, type InstallerCommand, type InstallerRequest } from "./contracts.ts";
import { InstallerFailure, InterruptedFailure } from "./errors.ts";
import { InstallerTransaction } from "./transaction.ts";

type Writer = (value: string) => void;
const VALUE_OPTIONS = new Set(["--target-root", "--entry-file", "--scope", "--installation-root", "--local-rules"]);
function parse(argv: readonly string[]): { command: InstallerCommand; request: InstallerRequest; json: boolean } {
  const command = argv[0]; if (command === undefined || !COMMANDS.includes(command as InstallerCommand)) throw new Error("unknown or missing command");
  const values = new Map<string, string>(); let json = false; let dryRun = false; let nonInteractive = false;
  for (let index = 1; index < argv.length; index += 1) { const option = argv[index]; if (option === "--json") { if (json) throw new Error("duplicate option --json"); json = true; continue; } if (option === "--dry-run") { if (dryRun) throw new Error("duplicate option --dry-run"); dryRun = true; continue; } if (option === "--non-interactive") { if (nonInteractive) throw new Error("duplicate option --non-interactive"); nonInteractive = true; continue; } if (option === undefined || !VALUE_OPTIONS.has(option)) throw new Error(`unknown option ${String(option)}`); if (values.has(option)) throw new Error(`duplicate option ${option}`); const value = argv[++index]; if (value === undefined || value.startsWith("--") || /[\0\r\n]/.test(value)) throw new Error(`missing or unsafe value for ${option}`); values.set(option, value); }
  for (const required of ["--target-root", "--entry-file", "--scope", "--installation-root"]) if (!values.has(required)) throw new Error(`missing required option ${required}`);
  if (values.get("--scope") !== "global") throw new Error("scope must be global");
  const releaseRoot = fileURLToPath(new URL("..", import.meta.url));
  return { command: command as InstallerCommand, json, request: { targetRoot: values.get("--target-root")!, entryFile: values.get("--entry-file")!, scope: "global", installationRoot: values.get("--installation-root")!, ...(values.has("--local-rules") ? { localRules: values.get("--local-rules")! } : {}), dryRun: dryRun || command === "plan", nonInteractive, releaseRoot } };
}

export async function runCli(argv: readonly string[], out: Writer = console.log, error: Writer = console.error): Promise<number> {
  let parsed: ReturnType<typeof parse>; try { parsed = parse(argv); } catch (cause) { error(JSON.stringify({ schemaVersion: 1, outcome: "INVALID_INVOCATION", error: (cause as Error).message })); return EXIT_CODES.INVALID_INVOCATION; }
  try { const transaction = new InstallerTransaction(parsed.request); const result = parsed.command === "inspect" ? await transaction.inspect() : parsed.command === "status" ? await transaction.status() : parsed.command === "plan" ? await transaction.plan() : parsed.command === "verify" ? await transaction.verify() : parsed.command === "install" ? await transaction.install() : parsed.command === "update" ? await transaction.update() : parsed.command === "uninstall" ? await transaction.uninstall() : await transaction.rollback(); out(parsed.json ? JSON.stringify(result) : `${result.outcome}: ${result.state} (${result.phase})`); return exitCodeFor(result.outcome); }
  catch (cause) { if (cause instanceof InterruptedFailure) { error(JSON.stringify({ schemaVersion: 1, outcome: cause.outcome, phase: cause.phase, resourceId: cause.resourceId, rollbackStatus: cause.rollbackStatus, code: cause.code, signal: cause.signal, error: cause.message })); return cause.exitCode; } if (cause instanceof InstallerFailure) { error(JSON.stringify({ schemaVersion: 1, outcome: cause.outcome, phase: cause.phase, resourceId: cause.resourceId, rollbackStatus: cause.rollbackStatus, code: cause.code, error: cause.message })); return exitCodeFor(cause.outcome); } error(JSON.stringify({ schemaVersion: 1, outcome: "UNSAFE_STATE", error: (cause as Error).message })); return EXIT_CODES.UNSAFE_STATE; }
}
if (process.argv[1] !== undefined && import.meta.url === pathToFileURL(process.argv[1]).href) process.exitCode = await runCli(process.argv.slice(2));
