import assert from "node:assert/strict";
import test from "node:test";

import { planCodex } from "../../src/planner.ts";

test("Codex plan is deterministic and never mutates MCP or approvals", () => {
  const input = {
    harness: "codex" as const,
    state: "FRESH" as const,
    home: "/allowed/codex",
    installRoot: "/allowed/codex/governance",
  };
  const first = planCodex(input);
  const second = planCodex(input);
  assert.deepEqual(first, second);
  assert.equal(first.mcpMutation, false);
  assert.equal(first.approvalExpansion, false);
  assert.deepEqual(first.resources.map((resource) => resource.id), [
    "codex-global-instructions",
    "codex-hooks",
    "governance-installation",
    "transaction-receipt",
  ]);
});
