import type { InstallPhase, TerminalOutcome } from "./contracts.js";

export class InstallerFailure extends Error {
  constructor(
    readonly code: string,
    readonly phase: InstallPhase,
    readonly resourceId: string,
    readonly outcome: Exclude<TerminalOutcome, "SUCCESS">,
    message: string,
    readonly rollbackStatus: "NOT_REQUIRED" | "SUCCEEDED" | "FAILED" = "NOT_REQUIRED",
  ) {
    super(message);
    this.name = "InstallerFailure";
  }
}
