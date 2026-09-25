import type { ResumeState } from "../../../src/resume-checkpoint.ts";

export function state(): ResumeState {
  return {
    projection: { taskId: "issue-87", objective: "Resume sicher materialisieren", scope: ["resume"], exactHead: "a".repeat(40), evidence: [{ id: "test-1", bindings: ["content-a"], status: "REUSE" }], incompleteEvidence: [], openFindings: [], nextAtomicAction: "gezielte-tests" },
    identities: { scope: "scope-a", repository: "repo-a", worktree: "worktree-a", branch: "feat/issue-87/resume", dirty: "clean", dependencies: "lock-a", configuration: "config-a", governance: "governance-a", environment: "env-a" },
    authorities: ["git:repo-a", "github:issue-87"], activeTask: "persist", taskStatus: "RUNNING",
    decisions: ["decision:reuse-native"], evidenceReferences: [{ id: "test-1", reference: "artifact:test-1" }],
    workItem: "github:issue-87", externalEffects: [],
  };
}
