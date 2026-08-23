import { join } from "node:path";

import { INSTALL_PHASES, type InstallPlan } from "./contracts.ts";

export interface CodexPlanInput {
  readonly harness: "codex";
  readonly state: "FRESH" | "CURRENT" | "LEGACY" | "UNKNOWN";
  readonly home: string;
  readonly installRoot: string;
}

export function planCodex(input: CodexPlanInput): InstallPlan {
  if (input.state === "UNKNOWN") throw new Error("cannot plan unknown Codex state");
  const operation = input.state === "FRESH" ? "create" : input.state === "CURRENT" ? "preserve" : "replace";
  return {
    schemaVersion: 1,
    harness: "codex",
    state: input.state,
    phases: INSTALL_PHASES,
    resources: [
      { id: "codex-global-instructions", target: join(input.home, "AGENTS.md"), operation },
      { id: "codex-hooks", target: join(input.home, "hooks.json"), operation },
      { id: "governance-installation", target: input.installRoot, operation },
    ],
    mcpMutation: false,
    approvalExpansion: false,
  };
}
