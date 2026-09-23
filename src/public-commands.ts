import { loadCommandCatalog } from "./command-catalog.ts";
import type { InstallResult, PublicCommandDefinition, PublicCommandId } from "./contracts.ts";
import type { InitResult } from "./init/types.ts";
import { createTerminalTheme, type TerminalTheme } from "./terminal/theme.ts";
import type { InstallerTransaction } from "./transaction.ts";

export interface PublicCommandExecution {
  readonly transaction: () => InstallerTransaction;
  readonly init: () => Promise<InitResult>;
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
  init: async ({ init }): Promise<InitResult> => init(),
});

const COMMAND_OPTIONS: readonly { name: string; description: string }[] = [
  { name: "--target-root <path>", description: "Explicit target root." },
  { name: "--entry-file <path>", description: "Relative Markdown entry file." },
  { name: "--scope global", description: "Required global scope." },
  { name: "--installation-root <path>", description: "Explicit installation root." },
  { name: "--local-rules <path>", description: "Optional local rules file." },
  { name: "--dry-run", description: "Do not mutate the target." },
  { name: "--non-interactive", description: "Disable interactive behavior." },
  { name: "--json", description: "Emit structured JSON." },
  { name: "-h, --help", description: "Show this help." },
];

function resolveTheme(theme: TerminalTheme | undefined): TerminalTheme {
  return theme ?? createTerminalTheme({ color: false });
}

export function renderGlobalHelp(commands: readonly PublicCommandDefinition[] = loadCommandCatalog(), theme?: TerminalTheme): string {
  const t = resolveTheme(theme);
  const width = Math.max(...commands.map(({ path }) => path.join(" ").length));
  const lines = commands.map(({ path, description }) => `  ${t.cyan(path.join(" ").padEnd(width))}  ${t.dim(description)}`);
  return [
    `${t.cyan("Usage:")} agent-governance ${t.cyan("<command>")} ${t.dim("[options]")}`,
    "",
    t.cyan("Commands:"),
    ...lines,
    "",
    t.dim("Run agent-governance <command> --help for command-specific help."),
  ].join("\n");
}

export function renderCommandHelp(id: PublicCommandId, commands: readonly PublicCommandDefinition[] = loadCommandCatalog(), theme?: TerminalTheme): string {
  const t = resolveTheme(theme);
  const command = commands.find((candidate) => candidate.id === id);
  if (command === undefined) throw new Error(`unknown public command ${id}`);
  const isOrchestration = command.capability === "orchestration";
  const path = command.path.join(" ");
  const usageArgs = isOrchestration
    ? ""
    : " --target-root <absolute-path> --entry-file <relative.md> --scope global --installation-root <absolute-path> [options]";
  const usage = `${t.cyan("Usage:")} agent-governance ${t.cyan(path)}${usageArgs === "" ? "" : t.dim(usageArgs)}`;
  const options = isOrchestration
    ? [{ name: "-h, --help", description: "Show this help." }]
    : COMMAND_OPTIONS;
  const width = Math.max(...options.map(({ name }) => name.length));
  const optionLines = options.map(({ name, description }) => `  ${t.cyan(name.padEnd(width))}  ${t.dim(description)}`);
  return [
    usage,
    "",
    t.dim(command.description),
    "",
    t.cyan("Options:"),
    ...optionLines,
  ].join("\n");
}
