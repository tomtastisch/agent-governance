import type { InstallPhase, TerminalOutcome } from "./contracts.ts";
import type { CatchableSignal } from "./signals.ts";

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

export class InterruptedFailure extends InstallerFailure {
  readonly signal: CatchableSignal;
  readonly exitCode: 130 | 143;

  constructor(
    signal: CatchableSignal,
    phase: InstallPhase,
    rollbackStatus: "NOT_REQUIRED" | "SUCCEEDED" | "FAILED",
  ) {
    super("INTERRUPTED", phase, "installation", "INTERRUPTED", `installation interrupted by ${signal}`, rollbackStatus);
    this.name = "InterruptedFailure";
    this.signal = signal;
    this.exitCode = signal === "SIGINT" ? 130 : 143;
  }
}
