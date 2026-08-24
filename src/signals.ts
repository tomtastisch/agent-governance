import type { InstallPhase } from "./contracts.ts";

export type CatchableSignal = "SIGINT" | "SIGTERM";

export interface SignalSource {
  on(signal: CatchableSignal, listener: () => void): void;
  off(signal: CatchableSignal, listener: () => void): void;
}

export class SignalInterruption extends Error {
  readonly signal: CatchableSignal;
  readonly phase: InstallPhase;

  constructor(signal: CatchableSignal, phase: InstallPhase) {
    super(`installation interrupted by ${signal}`);
    this.name = "SignalInterruption";
    this.signal = signal;
    this.phase = phase;
  }
}

export class SignalCoordinator {
  private readonly source: SignalSource;
  private readonly listeners: Readonly<Record<CatchableSignal, () => void>>;
  private interruptedBy: CatchableSignal | undefined;
  private started = false;

  constructor(source: SignalSource = process) {
    this.source = source;
    this.listeners = {
      SIGINT: () => this.latch("SIGINT"),
      SIGTERM: () => this.latch("SIGTERM"),
    };
  }

  start(): void {
    if (this.started) return;
    this.started = true;
    this.source.on("SIGINT", this.listeners.SIGINT);
    this.source.on("SIGTERM", this.listeners.SIGTERM);
  }

  checkpoint(phase: InstallPhase): void {
    if (this.interruptedBy !== undefined) {
      throw new SignalInterruption(this.interruptedBy, phase);
    }
  }

  dispose(): void {
    if (!this.started) return;
    this.started = false;
    this.source.off("SIGINT", this.listeners.SIGINT);
    this.source.off("SIGTERM", this.listeners.SIGTERM);
  }

  private latch(signal: CatchableSignal): void {
    this.interruptedBy ??= signal;
  }
}
