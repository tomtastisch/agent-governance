import type { InstallResult, InstallerRequest, InstallState } from "../contracts.ts";
import type { Candidate, DiscoverCandidatesOptions } from "../discovery/types.ts";

export interface InitTarget {
  readonly targetRoot: string;
  readonly entryFile: string;
}

export interface InitManualInput {
  readonly targetRoot?: string;
  readonly entryFile: string;
}

export interface InitBindingSelection {
  readonly candidate?: Candidate;
  readonly manualInput: InitManualInput;
}

export interface InitStep {
  readonly position: 1 | 2 | 3;
  readonly total: 3;
  readonly title: "Umgebung prüfen" | "AI-/LLM-Ziele auswählen" | "Prüfen und einrichten";
}

export const INIT_STEPS: readonly InitStep[] = Object.freeze([
  Object.freeze({ position: 1, total: 3, title: "Umgebung prüfen" }),
  Object.freeze({ position: 2, total: 3, title: "AI-/LLM-Ziele auswählen" }),
  Object.freeze({ position: 3, total: 3, title: "Prüfen und einrichten" }),
]);

export const INIT_CANCELLED: unique symbol = Symbol("INIT_CANCELLED");

export interface InitTransaction {
  readonly status: () => Promise<InstallResult>;
  readonly plan: () => Promise<InstallResult>;
  readonly install: () => Promise<InstallResult>;
  readonly verify: () => Promise<InstallResult>;
}

export interface InitPlannedTarget {
  readonly target: InitTarget;
  readonly status: InstallResult;
  readonly plan: InstallResult;
}

export interface InitPrompt {
  readonly step: (step: InitStep) => void;
  readonly selectTargets: (
    candidates: readonly Candidate[],
  ) => Promise<readonly InitBindingSelection[] | typeof INIT_CANCELLED>;
  readonly confirm: (
    plans: readonly InitPlannedTarget[],
  ) => Promise<boolean | typeof INIT_CANCELLED>;
}

export interface InitDependencies {
  readonly discoverCandidates: (
    options: DiscoverCandidatesOptions,
  ) => Promise<readonly Candidate[]>;
  readonly prompt: InitPrompt;
  readonly createTransaction: (request: InstallerRequest) => InitTransaction;
}

export interface InitOptions {
  readonly isTTY: boolean;
  readonly environment: DiscoverCandidatesOptions["environment"];
  readonly releaseRoot: string;
  readonly installationRoot?: string;
}

export interface InitTargetResult {
  readonly target: InitTarget;
  readonly previousState: InstallState;
  readonly state: "CURRENT";
}

export type InitResult =
  | {
      readonly schemaVersion: 1;
      readonly command: "init";
      readonly outcome: "SUCCESS";
      readonly targets: readonly InitTargetResult[];
    }
  | {
      readonly schemaVersion: 1;
      readonly command: "init";
      readonly outcome: "INVALID_INVOCATION";
      readonly reason: "NON_TTY";
      readonly guidance: "Use an explicit transaction command with --non-interactive.";
      readonly targets: readonly [];
    }
  | {
      readonly schemaVersion: 1;
      readonly command: "init";
      readonly outcome: "INTERRUPTED";
      readonly reason: "CANCELLED";
      readonly targets: readonly [];
    };
