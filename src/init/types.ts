import type { InstallResult, InstallerCommand, InstallerRequest, InstallState } from "../contracts.ts";

export interface InitEnvironment {
  readonly home: string;
  readonly xdgConfigHome?: string;
  readonly xdgDataHome?: string;
  readonly platform: NodeJS.Platform;
}

export interface DiscoveredHarness {
  readonly id: string;
  readonly displayName: string;
}

export interface InitTarget {
  readonly targetRoot: string;
  readonly entryFile: string;
}

export interface InitManualInput {
  readonly targetRoot?: string;
  readonly entryFile: string;
}

export type InitSelection =
  | { readonly harness: DiscoveredHarness }
  | { readonly manualInput: InitManualInput };

export interface HarnessRow {
  readonly id: string;
  readonly displayName: string;
  readonly supported: boolean;
  readonly targetRoot?: string;
  readonly entryFile?: string;
  readonly state?: InstallState;
  readonly localVersion?: string;
  readonly latestVersion?: string;
}

export interface InitStep {
  readonly position: 1 | 2 | 3;
  readonly total: 3;
  readonly title: "Umgebung prüfen" | "Coding-Harnesses auswählen" | "Prüfen und einrichten";
}

export const INIT_STEPS: readonly InitStep[] = Object.freeze([
  Object.freeze({ position: 1, total: 3, title: "Umgebung prüfen" }),
  Object.freeze({ position: 2, total: 3, title: "Coding-Harnesses auswählen" }),
  Object.freeze({ position: 3, total: 3, title: "Prüfen und einrichten" }),
]);

export const INIT_CANCELLED: unique symbol = Symbol("INIT_CANCELLED");

export interface InitTransaction {
  readonly status: () => Promise<InstallResult>;
  readonly plan: (command?: InstallerCommand) => Promise<InstallResult>;
  readonly install: () => Promise<InstallResult>;
  readonly update: () => Promise<InstallResult>;
  readonly verify: () => Promise<InstallResult>;
  readonly localVersion: () => Promise<string | undefined>;
}

export interface InitPlannedTarget {
  readonly target: InitTarget;
  readonly status: InstallResult;
  readonly plan: InstallResult;
  readonly displayName: string;
}

export interface InitPrompt {
  readonly step: (step: InitStep) => void;
  readonly dispose: () => void;
  readonly selectTargets: (
    rows: readonly HarnessRow[],
  ) => Promise<readonly InitSelection[] | typeof INIT_CANCELLED>;
  readonly confirm: (
    plans: readonly InitPlannedTarget[],
  ) => Promise<boolean | typeof INIT_CANCELLED>;
}

export interface InitDependencies {
  readonly discoverHarnesses: (
    options: { readonly environment: InitEnvironment },
  ) => Promise<readonly DiscoveredHarness[]>;
  readonly resolveLatestRelease: () => Promise<string | undefined>;
  readonly prompt: InitPrompt;
  readonly createTransaction: (request: InstallerRequest) => InitTransaction;
}

export interface InitOptions {
  readonly isTTY: boolean;
  readonly environment: InitEnvironment;
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
