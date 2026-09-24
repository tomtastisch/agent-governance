import assert from "node:assert/strict";
import test from "node:test";

import { resolveSupport } from "../../src/init/support.ts";
import type { InitEnvironment } from "../../src/init/types.ts";

const env: InitEnvironment = { home: "/home/user", platform: "linux" };

test("claude binds to ~/.claude with the native CLAUDE.md entry", () => {
  assert.deepEqual(resolveSupport("claude", env), {
    supported: true,
    targetRoot: "/home/user/.claude",
    entryFile: "CLAUDE.md",
  });
});

test("codex binds to ~/.codex with the native AGENTS.md entry", () => {
  assert.deepEqual(resolveSupport("codex", env), {
    supported: true,
    targetRoot: "/home/user/.codex",
    entryFile: "AGENTS.md",
  });
});

test("opencode resolves XDG_CONFIG_HOME first and falls back to ~/.config", () => {
  assert.deepEqual(resolveSupport("opencode", { ...env, xdgConfigHome: "/custom/xdg" }), {
    supported: true,
    targetRoot: "/custom/xdg/opencode",
    entryFile: "AGENTS.md",
  });
  assert.deepEqual(resolveSupport("opencode", env), {
    supported: true,
    targetRoot: "/home/user/.config/opencode",
    entryFile: "AGENTS.md",
  });
});

test("detected harnesses outside the support SSOT stay unsupported", () => {
  for (const id of ["github-copilot", "pi", "gemini", "cursor", "unknown"]) {
    assert.deepEqual(resolveSupport(id, env), { supported: false }, id);
  }
});
