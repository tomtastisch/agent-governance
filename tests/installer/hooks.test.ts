import assert from "node:assert/strict";
import test from "node:test";

import { mergeGovernanceHook } from "../../src/hooks.ts";

test("hook merge preserves unrelated configuration and adds no approvals", () => {
  const existing = JSON.stringify({ description: "keep", hooks: { Stop: [{ hooks: [] }] } });
  const result = JSON.parse(mergeGovernanceHook(existing, "/safe/codex-hook.mjs")) as Record<string, unknown>;
  assert.equal(result.description, "keep");
  assert.deepEqual((result.hooks as Record<string, unknown>).Stop, [{ hooks: [] }]);
  assert.equal(JSON.stringify(result).includes("approval"), false);
  assert.equal(JSON.stringify(result).includes("agent_governance__execute"), true);
});

test("hook merge rejects malformed and duplicate governance configuration", () => {
  assert.throws(() => mergeGovernanceHook("{", "/safe/hook.mjs"), /valid JSON/);
  const duplicate = JSON.stringify({
    hooks: {
      PreToolUse: [
        { matcher: "agent_governance__execute", hooks: [] },
        { matcher: "agent_governance__execute", hooks: [] },
      ],
    },
  });
  assert.throws(() => mergeGovernanceHook(duplicate, "/safe/hook.mjs"), /ambiguous/);
});
