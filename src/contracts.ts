export const COMMANDS = ["inspect", "plan", "install", "verify", "status", "update", "uninstall", "rollback"] as const;
export type InstallerCommand = (typeof COMMANDS)[number];
export const INSTALL_STATES = ["FRESH", "CURRENT", "OUTDATED", "DOWNGRADE_BLOCKED", "ABSENT", "TAMPERED", "RECOVERY_REQUIRED"] as const;
export type InstallState = (typeof INSTALL_STATES)[number];
export const INSTALL_PHASES = ["inspect", "plan", "backup", "stage", "activate", "verify", "rollback"] as const;
export type InstallPhase = (typeof INSTALL_PHASES)[number];
export const TERMINAL_OUTCOMES = ["SUCCESS", "INVALID_INVOCATION", "UNSAFE_STATE", "VERIFICATION_ROLLED_BACK", "ROLLBACK_FAILED", "INTERRUPTED"] as const;
export type TerminalOutcome = (typeof TERMINAL_OUTCOMES)[number];
export const EXIT_CODES = Object.freeze({ SUCCESS: 0, INVALID_INVOCATION: 2, UNSAFE_STATE: 4, VERIFICATION_ROLLED_BACK: 5, ROLLBACK_FAILED: 6, INTERRUPTED: 130 });
export function exitCodeFor(outcome: TerminalOutcome): number { return EXIT_CODES[outcome]; }
export interface InstallerRequest { readonly targetRoot: string; readonly entryFile: string; readonly scope: "global"; readonly installationRoot: string; readonly localRules?: string; readonly dryRun: boolean; readonly nonInteractive: boolean; readonly releaseRoot: string; }
export interface PlannedResource { readonly id: "release" | "current-metadata" | "entry-file" | "backup" | "receipt" | "local-rules"; readonly target: string; readonly operation: "create" | "replace" | "remove" | "preserve" | "verify"; }
export interface InstallPlan { readonly schemaVersion: 1; readonly architecture: "GLOBAL_EXPLICIT_PATH_MANAGED_BLOCK"; readonly command: InstallerCommand; readonly state: InstallState; readonly resources: readonly PlannedResource[]; readonly harnessSpecificMutation: false; readonly mcpMutation: false; readonly hookMutation: false; readonly approvalExpansion: false; }
export interface InstallResult { readonly schemaVersion: 1; readonly architecture: "GLOBAL_EXPLICIT_PATH_MANAGED_BLOCK"; readonly command: InstallerCommand; readonly outcome: TerminalOutcome; readonly state: InstallState; readonly phase: InstallPhase; readonly rollbackStatus: "NOT_REQUIRED" | "AVAILABLE" | "SUCCEEDED" | "FAILED"; readonly capabilities: readonly ("FILESYSTEM_INSTALLED" | "BINDING_MATERIALIZED" | "DIGEST_VERIFIED" | "ROLLBACK_AVAILABLE")[]; readonly plan?: InstallPlan; }
