import assert from "node:assert/strict";
import test from "node:test";
import { createGhPreparationModule, type GhPreparationDependencies } from "../../src/init/tool-preparation/gh.ts";
import type { ToolPreparationResult } from "../../src/init/tool-preparation/types.ts";

function createMockDeps(overrides: Partial<GhPreparationDependencies> = {}): GhPreparationDependencies {
  return {
    platform: () => "linux",
    effectiveUserId: () => 0,
    write: () => {},
    runCommand: async () => { throw new Error("unexpected external process"); },
    checkGhExists: async () => ({ exists: false, version: undefined }),
    checkGhAuth: async () => ({ authenticated: false, user: undefined }),
    runGhAuthLogin: async () => true,
    runAptUpdate: async () => true,
    runAptInstall: async () => true,
    runBrewInstall: async () => true,
    checkAptAvailable: async () => true,
    checkBrewAvailable: async () => true,
    checkAptPrivileges: async () => true,
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
  const currentPlatform = "linux";

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
    runBrewInstall: async () => false,
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

test("gh module: successful login must be called and verified freshly", async () => {
  let authenticated = false;
  let checks = 0;
  let logins = 0;
  const module = createGhPreparationModule(createMockDeps({
    checkGhExists: async () => ({ exists: true, version: "2.40.0" }),
    checkGhAuth: async () => { checks++; return { authenticated, user: undefined }; },
    runGhAuthLogin: async () => { logins++; authenticated = true; return true; },
  }));
  assert.equal((await module.prepare({ authorizeInstall: false, authorizeLogin: true })).status, "READY");
  assert.equal(logins, 1);
  assert.equal(checks, 2);
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

test("default gh operations honor the injected runner, host and stderr boundary", async () => {
  const calls: { command: string; args: readonly string[]; options: unknown }[] = [];
  let authenticated = false;
  const module = createGhPreparationModule({
    runCommand: async (command, args, options) => {
      calls.push({ command, args, options });
      if (args[0] === "--version") return { exitCode: 0, stdout: "gh version 2.40.0", stderr: "" };
      if (args[1] === "login") authenticated = true;
      return { exitCode: authenticated ? 0 : 1, stdout: "", stderr: "" };
    },
  });
  assert.equal((await module.prepare({ authorizeInstall: false, authorizeLogin: true })).status, "READY");
  const login = calls.find(call => call.args[1] === "login");
  assert.ok(login, "injected runner must handle the actual login");
  assert.deepEqual(login.args, ["auth", "login", "--web", "--hostname", "github.com"]);
  assert.deepEqual(login.options, { stdio: ["inherit", 2, 2] });
  assert.ok(calls.filter(call => call.args[1] === "status").length >= 2);
  for (const call of calls.filter(call => call.args[1] === "status")) {
    assert.deepEqual(call.args, ["auth", "status", "--active", "--hostname", "github.com"]);
  }
});

test("Linux prerequisites are read-only and unprivileged installation gives manual guidance", async () => {
  const calls: string[] = [];
  const module = createGhPreparationModule({
    platform: () => "linux", effectiveUserId: () => 1000, write: () => {},
    checkGhExists: async () => ({ exists: false, version: undefined }),
    runCommand: async (command, args) => { calls.push([command, ...args].join(" ")); return { exitCode: 0, stdout: "", stderr: "" }; },
  });
  const result = await module.prepare({ authorizeInstall: true, authorizeLogin: false });
  assert.equal(result.status, "UNAVAILABLE");
  assert.match(result.message!, /sudo apt/);
  assert.match(result.message!, /without elevating/);
  assert.deepEqual(calls, ["which apt"]);
});

test("root Linux update and install run once as separate argv and require fresh gh", async () => {
  const calls: string[] = [];
  let exists = false;
  const module = createGhPreparationModule({
    platform: () => "linux", effectiveUserId: () => 0, write: () => {},
    checkGhExists: async () => { calls.push("inspect gh"); return { exists, version: undefined }; },
    checkGhAuth: async () => ({ authenticated: true, user: undefined }),
    runCommand: async (command, args) => {
      calls.push([command, ...args].join(" "));
      if (args[0] === "install") exists = true;
      return { exitCode: 0, stdout: "", stderr: "" };
    },
  });
  assert.equal((await module.prepare({ authorizeInstall: true, authorizeLogin: false })).status, "READY");
  assert.deepEqual(calls, ["inspect gh", "which apt", "apt update", "apt install -y gh", "inspect gh", "inspect gh"]);
});

test("macOS installation uses only brew and read-back rejects a missing executable", async () => {
  const calls: string[] = [];
  const module = createGhPreparationModule({
    platform: () => "darwin", write: () => {},
    checkGhExists: async () => ({ exists: false, version: undefined }),
    checkGhAuth: async () => { throw new Error("missing gh must not authenticate"); },
    runCommand: async (command, args) => { calls.push([command, ...args].join(" ")); return { exitCode: 0, stdout: "", stderr: "" }; },
  });
  assert.equal((await module.prepare({ authorizeInstall: true, authorizeLogin: false })).status, "UNAVAILABLE");
  assert.deepEqual(calls, ["which brew", "brew install gh"]);
});

test("provider exit success without authentication read-back cannot report READY", async () => {
  const module = createGhPreparationModule(createMockDeps({
    checkGhExists: async () => ({ exists: true, version: "2.40.0" }),
    checkGhAuth: async () => ({ authenticated: false, user: undefined }),
    runGhAuthLogin: async () => true,
  }));
  assert.equal((await module.prepare({ authorizeInstall: false, authorizeLogin: true })).status, "UNAVAILABLE");
});

test("unsupported platforms never attempt a package manager", async () => {
  const module = createGhPreparationModule({
    platform: () => "win32", write: () => {},
    checkGhExists: async () => ({ exists: false, version: undefined }),
    runCommand: async () => { throw new Error("unsupported platform must not spawn"); },
  });
  const result = await module.prepare({ authorizeInstall: true, authorizeLogin: true });
  assert.equal(result.status, "UNAVAILABLE");
  assert.match(result.message!, /cli.github.com/);
});

test("authorized login fails when gh disappears after inspection without installing", async () => {
  let exists = true;
  const module = createGhPreparationModule(createMockDeps({
    checkGhExists: async () => ({ exists, version: exists ? "2.40.0" : undefined }),
    checkGhAuth: async () => ({ authenticated: false, user: undefined }),
    runGhAuthLogin: async () => { throw new Error("missing gh must not launch login"); },
    runAptUpdate: async () => { throw new Error("login consent cannot authorize installation"); },
    runBrewInstall: async () => { throw new Error("login consent cannot authorize installation"); },
  }));
  assert.equal((await module.inspect()).status, "AUTH_REQUIRED");
  exists = false;
  assert.equal((await module.prepare({ authorizeInstall: false, authorizeLogin: true })).status, "UNAVAILABLE");
});

test("legacy gh authenticates the active github.com account without exposing API output", async () => {
  for (const exitCode of [0, 1]) {
    const calls: string[] = [];
    const module = createGhPreparationModule({
      runCommand: async (command, args) => {
        calls.push([command, ...args].join(" "));
        if (args[0] === "--version") return { exitCode: 0, stdout: "gh version 2.45.0", stderr: "" };
        if (args[0] === "auth") return { exitCode: 1, stdout: "", stderr: "unknown flag: --active\n\nUsage: gh auth status [flags]\n" };
        assert.deepEqual(args, ["api", "user", "--hostname", "github.com", "--silent"]);
        return { exitCode, stdout: "SYNTHETIC_PRIVATE_API_OUTPUT", stderr: "SYNTHETIC_PRIVATE_API_ERROR" };
      },
    });
    const result = await module.inspect();
    assert.equal(result.status, exitCode === 0 ? "READY" : "AUTH_REQUIRED");
    assert.equal(calls.filter(call => call.startsWith("gh api ")).length, 1);
    assert.doesNotMatch(JSON.stringify(result), /SYNTHETIC_PRIVATE_API/);
  }
});

test("ordinary auth failures never activate the legacy compatibility path", async () => {
  for (const stderr of ["authentication failed", "network timeout", "unknown flag: --hostname", "remote message: unknown flag: --active"]) {
    const module = createGhPreparationModule({
      runCommand: async (_command, args) => {
        if (args[0] === "--version") return { exitCode: 0, stdout: "gh version 2.57.0", stderr: "" };
        assert.equal(args[0], "auth", "a genuine auth failure must not fall back to another probe");
        return { exitCode: 1, stdout: "", stderr };
      },
    });
    assert.equal((await module.inspect()).status, "AUTH_REQUIRED");
  }
});

test("apt-installed legacy gh reaches READY only after separately authorized login and fresh API read-back", async () => {
  const { createToolPreparationOrchestrator } = await import("../../src/init/tool-preparation/index.ts");
  for (const loginPersists of [false, true]) {
    let installed = false; let authenticated = false;
    const events: string[] = [];
    const module = createGhPreparationModule({
      platform: () => "linux", effectiveUserId: () => 0, write: () => {},
      runCommand: async (command, args) => {
        events.push([command, ...args].join(" "));
        if (command === "which" || command === "apt") {
          if (command === "apt" && args[0] === "install") installed = true;
          return { exitCode: 0, stdout: "", stderr: "" };
        }
        if (args[0] === "--version") return { exitCode: installed ? 0 : 127, stdout: installed ? "gh version 2.45.0" : "", stderr: "" };
        if (args[0] === "auth" && args[1] === "status") return { exitCode: 1, stdout: "", stderr: "unknown flag: --active\n" };
        if (args[0] === "auth" && args[1] === "login") {
          authenticated = loginPersists;
          return { exitCode: 0, stdout: "", stderr: "" };
        }
        assert.deepEqual(args, ["api", "user", "--hostname", "github.com", "--silent"]);
        return { exitCode: authenticated ? 0 : 1, stdout: "", stderr: "" };
      },
    });
    const runner = createToolPreparationOrchestrator({ modules: [module], authorize: async () => { events.push("consent"); return true; } });
    const result = await runner.run({ skipTools: false });
    assert.equal(result[0]!.status, loginPersists ? "READY" : "UNAVAILABLE");
    const install = events.indexOf("apt install -y gh");
    const login = events.indexOf("gh auth login --web --hostname github.com");
    assert.equal(events.filter(event => event === "consent").length, 2);
    assert.ok(install > events.indexOf("consent"));
    assert.ok(login > events.lastIndexOf("consent") && events.lastIndexOf("consent") > install);
    assert.equal(events.at(-1), "gh api user --hostname github.com --silent");
  }
});
