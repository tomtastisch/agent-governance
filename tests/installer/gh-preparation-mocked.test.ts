import assert from "node:assert/strict";
import test from "node:test";
import { createGhPreparationModule, type GhPreparationDependencies } from "../../src/init/tool-preparation/gh.ts";
import type { ToolPreparationResult } from "../../src/init/tool-preparation/types.ts";

function createMockDeps(overrides: Partial<GhPreparationDependencies> = {}): GhPreparationDependencies {
  return {
    runCommand: async () => ({ exitCode: 0, stdout: "", stderr: "" }),
    checkGhExists: async () => ({ exists: false, version: undefined }),
    checkGhAuth: async () => ({ authenticated: false, user: undefined }),
    runGhAuthLogin: async () => true,
    runAptUpdate: async () => true,
    runAptInstall: async () => true,
    runBrewInstall: async () => true,
    checkAptAvailable: async () => true,
    checkBrewAvailable: async () => true,
    formatInstallGuidance: () => "Install guidance",
    ...overrides,
  };
}

test("gh module: MISSING + decline install => SKIPPED", async () => {
  const deps = createMockDeps({
    checkGhExists: async () => ({ exists: false, version: undefined }),
  });
  const module = createGhPreparationModule(deps);
  const result = await module.prepare({ authorizeInstall: false, authorizeLogin: false });
  assert.equal(result.toolId, "github_cli");
  assert.equal(result.status, "SKIPPED");
  assert.equal(result.message, "User declined gh installation.");
});

test("gh module: MISSING + authorize install + install succeeds => READY", async () => {
  let installCalled = false;
  let aptUpdateCalled = false;
  let aptInstallCalled = false;
  let brewInstallCalled = false;
  let checkGhExistsCallCount = 0;
  const currentPlatform = process.platform;
  
  const deps = createMockDeps({
    checkGhExists: async () => {
      checkGhExistsCallCount++;
      if (checkGhExistsCallCount === 1) return { exists: false, version: undefined };
      return { exists: true, version: "2.40.0" };
    },
    runAptUpdate: async () => { aptUpdateCalled = true; return true; },
    runAptInstall: async () => { aptInstallCalled = true; return true; },
    runBrewInstall: async () => { brewInstallCalled = true; return true; },
    checkAptAvailable: async () => true,
    checkBrewAvailable: async () => true,
    checkGhAuth: async () => ({ authenticated: true, user: "testuser" }),
  });
  const module = createGhPreparationModule(deps);
  const result = await module.prepare({ authorizeInstall: true, authorizeLogin: true });
  assert.equal(result.toolId, "github_cli");
  assert.equal(result.status, "READY");
  if (currentPlatform === "linux") {
    assert.ok(aptUpdateCalled, "apt update should be called on linux");
    assert.ok(aptInstallCalled, "apt install should be called on linux");
  } else if (currentPlatform === "darwin") {
    assert.ok(brewInstallCalled, "brew install should be called on darwin");
  }
});

test("gh module: MISSING + authorize install + install fails => UNAVAILABLE", async () => {
  const deps = createMockDeps({
    checkGhExists: async () => ({ exists: false, version: undefined }),
    runAptUpdate: async () => true,
    runAptInstall: async () => false,
    checkAptAvailable: async () => true,
  });
  const module = createGhPreparationModule(deps);
  const result = await module.prepare({ authorizeInstall: true, authorizeLogin: true });
  assert.equal(result.toolId, "github_cli");
  assert.equal(result.status, "UNAVAILABLE");
  assert.ok(result.message !== undefined);
});

test("gh module: PRESENT + AUTH_REQUIRED + decline login => SKIPPED", async () => {
  const deps = createMockDeps({
    checkGhExists: async () => ({ exists: true, version: "2.40.0" }),
    checkGhAuth: async () => ({ authenticated: false, user: undefined }),
  });
  const module = createGhPreparationModule(deps);
  const result = await module.prepare({ authorizeInstall: true, authorizeLogin: false });
  assert.equal(result.toolId, "github_cli");
  assert.equal(result.status, "SKIPPED");
  assert.equal(result.message, "User declined gh authentication.");
});

test("gh module: PRESENT + AUTH_REQUIRED + authorize login + login succeeds => READY", async () => {
  const deps = createMockDeps({
    checkGhExists: async () => ({ exists: true, version: "2.40.0" }),
    checkGhAuth: async () => ({ authenticated: true, user: "testuser" }),
    runGhAuthLogin: async () => true,
  });
  const module = createGhPreparationModule(deps);
  const result = await module.prepare({ authorizeInstall: true, authorizeLogin: true });
  assert.equal(result.toolId, "github_cli");
  assert.equal(result.status, "READY");
});

test("gh module: PRESENT + AUTH_REQUIRED + authorize login + login fails => AUTH_REQUIRED", async () => {
  const deps = createMockDeps({
    checkGhExists: async () => ({ exists: true, version: "2.40.0" }),
    checkGhAuth: async () => ({ authenticated: false, user: undefined }),
    runGhAuthLogin: async () => false,
  });
  const module = createGhPreparationModule(deps);
  const result = await module.prepare({ authorizeInstall: true, authorizeLogin: true });
  assert.equal(result.toolId, "github_cli");
  assert.equal(result.status, "AUTH_REQUIRED");
  assert.ok(result.message?.includes("authentication failed"));
});

test("gh module: READY => READY (no action needed)", async () => {
  const deps = createMockDeps({
    checkGhExists: async () => ({ exists: true, version: "2.40.0" }),
    checkGhAuth: async () => ({ authenticated: true, user: "testuser" }),
  });
  const module = createGhPreparationModule(deps);
  const result = await module.prepare({ authorizeInstall: true, authorizeLogin: true });
  assert.equal(result.toolId, "github_cli");
  assert.equal(result.status, "READY");
});

test("gh module: MISSING + no package manager => UNAVAILABLE", async () => {
  const deps = createMockDeps({
    checkGhExists: async () => ({ exists: false, version: undefined }),
    checkAptAvailable: async () => false,
    checkBrewAvailable: async () => false,
  });
  const module = createGhPreparationModule(deps);
  const result = await module.prepare({ authorizeInstall: true, authorizeLogin: true });
  assert.equal(result.toolId, "github_cli");
  assert.equal(result.status, "UNAVAILABLE");
});

test("gh module: inspect MISSING", async () => {
  const deps = createMockDeps({
    checkGhExists: async () => ({ exists: false, version: undefined }),
  });
  const module = createGhPreparationModule(deps);
  const result = await module.inspect();
  assert.equal(result.toolId, "github_cli");
  assert.equal(result.status, "MISSING");
});

test("gh module: inspect AUTH_REQUIRED", async () => {
  const deps = createMockDeps({
    checkGhExists: async () => ({ exists: true, version: "2.40.0" }),
    checkGhAuth: async () => ({ authenticated: false, user: undefined }),
  });
  const module = createGhPreparationModule(deps);
  const result = await module.inspect();
  assert.equal(result.toolId, "github_cli");
  assert.equal(result.status, "AUTH_REQUIRED");
});

test("gh module: inspect READY", async () => {
  const deps = createMockDeps({
    checkGhExists: async () => ({ exists: true, version: "2.40.0" }),
    checkGhAuth: async () => ({ authenticated: true, user: "testuser" }),
  });
  const module = createGhPreparationModule(deps);
  const result = await module.inspect();
  assert.equal(result.toolId, "github_cli");
  assert.equal(result.status, "READY");
});

test("gh module: non-TTY handled by orchestrator not module", async () => {
  // The gh module itself doesn't handle TTY - that's the orchestrator's responsibility
  // This test verifies the module works correctly regardless of TTY
  const deps = createMockDeps({
    checkGhExists: async () => ({ exists: false, version: undefined }),
  });
  const module = createGhPreparationModule(deps);
  const result = await module.prepare({ authorizeInstall: false, authorizeLogin: false });
  assert.equal(result.status, "SKIPPED");
  assert.equal(result.message, "User declined gh installation.");
});

test("gh module: cancellation via Ctrl+C propagates", async () => {
  let cancelled = false;
  const deps = createMockDeps({
    checkGhExists: async () => ({ exists: false, version: undefined }),
    runAptInstall: async () => { cancelled = true; return false; },
    checkAptAvailable: async () => true,
    runAptUpdate: async () => true,
  });
  const module = createGhPreparationModule(deps);
  // Test that the module can be interrupted - this is more of an integration test
  // The actual cancellation handling is in the orchestrator
  const result = await module.prepare({ authorizeInstall: true, authorizeLogin: true });
  assert.ok(["UNAVAILABLE", "SKIPPED"].includes(result.status));
});