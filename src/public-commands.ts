import { loadCommandCatalog } from "./command-catalog.ts";
import type { InstallResult, PublicCommandDefinition, PublicCommandId } from "./contracts.ts";
import type { InstallerTransaction } from "./transaction.ts";

export interface PublicCommandExecution {
  readonly transaction: () => InstallerTransaction;
  readonly init: () => Promise<unknown>;
}

export type PublicCommandHandler = (execution: PublicCommandExecution) => Promise<unknown>;

export const PUBLIC_COMMAND_HANDLERS: Readonly<Record<PublicCommandId, PublicCommandHandler>> = Object.freeze({
  inspect: async ({ transaction }): Promise<InstallResult> => transaction().inspect(),
  plan: async ({ transaction }): Promise<InstallResult> => transaction().plan(),
  install: async ({ transaction }): Promise<InstallResult> => transaction().install(),
  verify: async ({ transaction }): Promise<InstallResult> => transaction().verify(),
  status: async ({ transaction }): Promise<InstallResult> => transaction().status(),
  update: async ({ transaction }): Promise<InstallResult> => transaction().update(),
  uninstall: async ({ transaction }): Promise<InstallResult> => transaction().uninstall(),
  rollback: async ({ transaction }): Promise<InstallResult> => transaction().rollback(),
  init: async ({ init }): Promise<unknown> => init(),
});

export function renderGlobalHelp(commands: readonly PublicCommandDefinition[] = loadCommandCatalog()): string {
  const width = Math.max(...commands.map(({ path }) => path.join(" ").length));
  const lines = commands.map(({ path, description }) => `  ${path.join(" ").padEnd(width)}  ${description}`);
  return [
    "Usage: agent-governance <command> [options]",
    "",
    "Commands:",
    ...lines,
    "",
    "Run agent-governance <command> --help for command-specific help.",
  ].join("\n");
}

export function renderCommandHelp(id: PublicCommandId, commands: readonly PublicCommandDefinition[] = loadCommandCatalog()): string {
  const command = commands.find((candidate) => candidate.id === id);
  if (command === undefined) throw new Error(`unknown public command ${id}`);
  const invocation = command.capability === "orchestration"
    ? `agent-governance ${command.path.join(" ")}`
    : `agent-governance ${command.path.join(" ")} --target-root <absolute-path> --entry-file <relative.md> --scope global --installation-root <absolute-path> [options]`;
  const options = command.capability === "orchestration"
    ? ["  -h, --help  Show this help."]
    : [
        "  --target-root <path>       Explicit target root.",
        "  --entry-file <path>        Relative Markdown entry file.",
        "  --scope global             Required global scope.",
        "  --installation-root <path> Explicit installation root.",
        "  --local-rules <path>       Optional local rules file.",
        "  --dry-run                  Do not mutate the target.",
        "  --non-interactive          Disable interactive behavior.",
        "  --json                     Emit structured JSON.",
        "  -h, --help                 Show this help.",
      ];
  return [`Usage: ${invocation}`, "", command.description, "", "Options:", ...options].join("\n");
}
