import type { InstallPhase, TerminalOutcome } from "./contracts.ts";

export class InstallerFailure extends Error {
  readonly code: string;
  readonly phase: InstallPhase;
  readonly resourceId: string;
  readonly outcome: Exclude<TerminalOutcome, "SUCCESS">;
  readonly rollbackStatus: "NOT_REQUIRED" | "SUCCEEDED" | "FAILED";

  constructor(
    code: string,
    phase: InstallPhase,
    resourceId: string,
    outcome: Exclude<TerminalOutcome, "SUCCESS">,
    message: string,
    rollbackStatus: "NOT_REQUIRED" | "SUCCEEDED" | "FAILED" = "NOT_REQUIRED",
  ) {
    super(message);
    this.name = "InstallerFailure";
    this.code = code;
    this.phase = phase;
    this.resourceId = resourceId;
    this.outcome = outcome;
    this.rollbackStatus = rollbackStatus;
  }
}
