import { join } from "node:path";
import type { InitEnvironment } from "./types.ts";

export interface SupportedBinding {
  readonly supported: true;
  readonly targetRoot: string;
  readonly entryFile: string;
}

export type SupportDecision = SupportedBinding | { readonly supported: false };

interface BindingRule {
  readonly targetRoot: (environment: InitEnvironment) => string;
  readonly entryFile: string;
}

const SUPPORTED_BINDINGS: Readonly<Record<string, BindingRule>> = {
  claude: {
    targetRoot: (environment: InitEnvironment) => join(environment.home, ".claude"),
    entryFile: "CLAUDE.md",
  },
  codex: {
    targetRoot: (environment: InitEnvironment) => join(environment.home, ".codex"),
    entryFile: "AGENTS.md",
  },
  opencode: {
    targetRoot: (environment: InitEnvironment) => join(environment.xdgConfigHome ?? join(environment.home, ".config"), "opencode"),
    entryFile: "AGENTS.md",
  },
};

export function resolveSupport(harnessId: string, environment: InitEnvironment): SupportDecision {
  const rule = SUPPORTED_BINDINGS[harnessId];
  if (rule === undefined) return { supported: false };
  return {
    supported: true,
    targetRoot: rule.targetRoot(environment),
    entryFile: rule.entryFile,
  };
}
