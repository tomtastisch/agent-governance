export type ToolPreparationStatus = "READY" | "MISSING" | "AUTH_REQUIRED" | "SKIPPED" | "UNAVAILABLE";

export interface ToolPreparationResult {
  readonly toolId: string;
  readonly status: ToolPreparationStatus;
  readonly message?: string;
}

export interface ToolPreparationModule {
  readonly toolId: string;
  readonly inspect: () => Promise<ToolPreparationResult>;
  readonly prepare: (options: { readonly userAuthorized: boolean }) => Promise<ToolPreparationResult>;
}

export interface ToolPreparationOrchestrator {
  readonly run: (options: { readonly skipTools: boolean }) => Promise<readonly ToolPreparationResult[]>;
}