export const INSTALL_STATES = [
  "FRESH",
  "CURRENT",
  "LEGACY",
  "UNKNOWN",
  "UNSUPPORTED",
] as const;

export type InstallState = (typeof INSTALL_STATES)[number];

export const INSTALL_PHASES = [
  "inspect",
  "classify",
  "plan",
  "backup",
  "stage",
  "activate",
  "verify",
  "rollback",
] as const;

export type InstallPhase = (typeof INSTALL_PHASES)[number];

export const TERMINAL_OUTCOMES = [
  "SUCCESS",
  "INVALID_INVOCATION",
  "UNSUPPORTED_HARNESS",
  "UNSAFE_STATE",
  "VERIFICATION_ROLLED_BACK",
  "ROLLBACK_FAILED",
] as const;

export type TerminalOutcome = (typeof TERMINAL_OUTCOMES)[number];

export const EXIT_CODES = Object.freeze({
  SUCCESS: 0,
  INVALID_INVOCATION: 2,
  UNSUPPORTED_HARNESS: 3,
  UNSAFE_STATE: 4,
  VERIFICATION_ROLLED_BACK: 5,
  ROLLBACK_FAILED: 6,
});

export function exitCodeFor(outcome: TerminalOutcome): number {
  return EXIT_CODES[outcome];
}

export interface InstallerRequest {
  readonly harness: string;
  readonly home: string;
  readonly allowedRoot: string;
  readonly releaseRoot: string;
  readonly installRoot: string;
  readonly dryRun: boolean;
}

export interface PlannedResource {
  readonly id: string;
  readonly target: string;
  readonly operation: "create" | "replace" | "remove" | "preserve";
}

export interface InstallPlan {
  readonly schemaVersion: 1;
  readonly harness: "codex";
  readonly state: Exclude<InstallState, "UNSUPPORTED">;
  readonly phases: readonly InstallPhase[];
  readonly resources: readonly PlannedResource[];
  readonly mcpMutation: false;
  readonly approvalExpansion: false;
}

export interface InstallResult {
  readonly outcome: TerminalOutcome;
  readonly state: InstallState;
  readonly phase: InstallPhase;
  readonly rollbackStatus: "NOT_REQUIRED" | "SUCCEEDED" | "FAILED";
  readonly plan?: InstallPlan;
}
