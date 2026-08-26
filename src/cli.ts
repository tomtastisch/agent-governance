#!/usr/bin/env node
import { fileURLToPath } from "node:url";
import { realpathSync } from "node:fs";
import { homedir } from "node:os";
import { dirname } from "node:path";
import { EXIT_CODES, exitCodeFor, type InstallerCommand, type InstallerRequest, type PublicCommandDefinition, type PublicCommandId, type TerminalOutcome } from "./contracts.ts";
import { discoverCandidates } from "./discovery/index.ts";
import { InstallerFailure, InterruptedFailure } from "./errors.ts";
import { runInit } from "./init/orchestrator.ts";
import type { InitOptions, InitPrompt, InitResult } from "./init/types.ts";
import { InstallerTransaction } from "./transaction.ts";
import { loadCommandCatalog } from "./command-catalog.ts";
import { PUBLIC_COMMAND_HANDLERS, renderCommandHelp, renderGlobalHelp } from "./public-commands.ts";

type Writer = (value: string) => void;
export interface CliDependencies {
  readonly createTransaction?: (request: InstallerRequest) => InstallerTransaction;
  readonly init?: () => Promise<InitResult>;
  readonly initOptions?: InitOptions;
  readonly initPrompt?: InitPrompt;
}
const VALUE_OPTIONS = new Set(["--target-root", "--entry-file", "--scope", "--installation-root", "--local-rules"]);
function parse(argv: readonly string[], publicCommands: readonly PublicCommandId[]): { command: PublicCommandId; request?: InstallerRequest; json: boolean } {
  const command = argv[0]; if (command === undefined || !publicCommands.includes(command as PublicCommandId)) throw new Error("unknown or missing command");
  if (command === "init") {
    if (argv.length !== 1) throw new Error(`unknown option ${String(argv[1])}`);
    return { command, json: false };
  }
  const values = new Map<string, string>(); let json = false; let dryRun = false; let nonInteractive = false;
  for (let index = 1; index < argv.length; index += 1) { const option = argv[index]; if (option === "--json") { if (json) throw new Error("duplicate option --json"); json = true; continue; } if (option === "--dry-run") { if (dryRun) throw new Error("duplicate option --dry-run"); dryRun = true; continue; } if (option === "--non-interactive") { if (nonInteractive) throw new Error("duplicate option --non-interactive"); nonInteractive = true; continue; } if (option === undefined || !VALUE_OPTIONS.has(option)) throw new Error(`unknown option ${String(option)}`); if (values.has(option)) throw new Error(`duplicate option ${option}`); const value = argv[++index]; if (value === undefined || value.startsWith("--") || /[\0\r\n]/.test(value)) throw new Error(`missing or unsafe value for ${option}`); values.set(option, value); }
  for (const required of ["--target-root", "--entry-file", "--scope", "--installation-root"]) if (!values.has(required)) throw new Error(`missing required option ${required}`);
  if (values.get("--scope") !== "global") throw new Error("scope must be global");
  const releaseRoot = dirname(dirname(fileURLToPath(import.meta.url)));
  return { command: command as InstallerCommand, json, request: { targetRoot: values.get("--target-root")!, entryFile: values.get("--entry-file")!, scope: "global", installationRoot: values.get("--installation-root")!, ...(values.has("--local-rules") ? { localRules: values.get("--local-rules")! } : {}), dryRun: dryRun || command === "plan", nonInteractive, releaseRoot } };
}

function isHelp(value: string | undefined): boolean { return value === "--help" || value === "-h"; }
function isOutcome(value: unknown): value is TerminalOutcome { return typeof value === "string" && ["SUCCESS", "INVALID_INVOCATION", "UNSAFE_STATE", "VERIFICATION_ROLLED_BACK", "ROLLBACK_FAILED", "INTERRUPTED"].includes(value); }

const unavailablePrompt: InitPrompt = Object.freeze({
  step: () => undefined,
  selectTargets: async () => { throw new Error("interactive init prompt is unavailable"); },
  confirm: async () => { throw new Error("interactive init prompt is unavailable"); },
});

function defaultInitOptions(): InitOptions {
  const home = realpathSync(homedir());
  const releaseRoot = dirname(dirname(fileURLToPath(import.meta.url)));
  const xdgConfigHome = process.env.XDG_CONFIG_HOME;
  const xdgDataHome = process.env.XDG_DATA_HOME;
  return {
    isTTY: Boolean(process.stdin.isTTY && process.stdout.isTTY),
    environment: {
      home,
      platform: process.platform,
      ...(xdgConfigHome === undefined || xdgConfigHome === "" ? {} : { xdgConfigHome }),
      ...(xdgDataHome === undefined || xdgDataHome === "" ? {} : { xdgDataHome }),
    },
    releaseRoot,
  };
}

export async function runCli(argv: readonly string[], out: Writer = console.log, error: Writer = console.error, dependencies: CliDependencies = {}): Promise<number> {
  let definitions: readonly PublicCommandDefinition[];
  try { definitions = loadCommandCatalog(); }
  catch (cause) { error(JSON.stringify({ schemaVersion: 1, outcome: "UNSAFE_STATE", error: (cause as Error).message })); return EXIT_CODES.UNSAFE_STATE; }
  const publicCommands = definitions.map(({ id }) => id);
  if (argv.length === 1 && isHelp(argv[0])) { out(renderGlobalHelp(definitions)); return EXIT_CODES.SUCCESS; }
  if (argv.length === 2 && publicCommands.includes(argv[0] as PublicCommandId) && isHelp(argv[1])) { out(renderCommandHelp(argv[0] as PublicCommandId, definitions)); return EXIT_CODES.SUCCESS; }
  let parsed: ReturnType<typeof parse>; try { parsed = parse(argv, publicCommands); } catch (cause) { error(JSON.stringify({ schemaVersion: 1, outcome: "INVALID_INVOCATION", error: (cause as Error).message })); return EXIT_CODES.INVALID_INVOCATION; }
  try {
    let transaction: InstallerTransaction | undefined;
    const result = await PUBLIC_COMMAND_HANDLERS[parsed.command]({
      transaction: () => {
        if (parsed.request === undefined) throw new Error("transaction request is unavailable");
        transaction ??= (dependencies.createTransaction ?? ((request) => new InstallerTransaction(request)))(parsed.request);
        return transaction;
      },
      init: dependencies.init ?? (() => runInit(
        dependencies.initOptions ?? defaultInitOptions(),
        {
          discoverCandidates,
          prompt: dependencies.initPrompt ?? unavailablePrompt,
          createTransaction: dependencies.createTransaction ?? ((request) => new InstallerTransaction(request)),
        },
      )),
    });
    const structured = typeof result === "object" && result !== null ? result as Record<string, unknown> : undefined;
    out(parsed.json ? JSON.stringify(result) : structured !== undefined && typeof structured.outcome === "string" && typeof structured.state === "string" && typeof structured.phase === "string" ? `${structured.outcome}: ${structured.state} (${structured.phase})` : JSON.stringify(result));
    return isOutcome(structured?.outcome) ? exitCodeFor(structured.outcome) : EXIT_CODES.SUCCESS;
  }
  catch (cause) { if (cause instanceof InterruptedFailure) { error(JSON.stringify({ schemaVersion: 1, outcome: cause.outcome, phase: cause.phase, resourceId: cause.resourceId, rollbackStatus: cause.rollbackStatus, code: cause.code, signal: cause.signal, error: cause.message })); return cause.exitCode; } if (cause instanceof InstallerFailure) { error(JSON.stringify({ schemaVersion: 1, outcome: cause.outcome, phase: cause.phase, resourceId: cause.resourceId, rollbackStatus: cause.rollbackStatus, code: cause.code, error: cause.message })); return exitCodeFor(cause.outcome); } error(JSON.stringify({ schemaVersion: 1, outcome: "UNSAFE_STATE", error: (cause as Error).message })); return EXIT_CODES.UNSAFE_STATE; }
}
if (process.argv[1] !== undefined && fileURLToPath(import.meta.url) === realpathSync(process.argv[1])) process.exitCode = await runCli(process.argv.slice(2));
