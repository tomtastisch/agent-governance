import assert from "node:assert/strict";
import test from "node:test";
import { runToolPreparation, createToolPreparationOrchestrator } from "../../src/init/tool-preparation/index.ts";
import { createGhPreparationModule } from "../../src/init/tool-preparation/gh.ts";
import type { ToolPreparationResult } from "../../src/init/tool-preparation/types.ts";

test("runToolPreparation with skipTools returns empty array", async () => {
  const results = await runToolPreparation(true);
  assert.deepEqual(results, []);
});

test("gh module inspection and declined preparation use isolated dependencies", async () => {
  const module = createGhPreparationModule({
    checkGhExists: async () => ({ exists: false, version: undefined }),
    runCommand: async () => { throw new Error("unexpected external process"); },
  });
  assert.equal((await module.inspect()).status, "MISSING");
  assert.equal((await module.prepare({ authorizeInstall: false, authorizeLogin: false })).status, "SKIPPED");
});

test("gh module decline login cannot install or authenticate", async () => {
  const module = createGhPreparationModule({
    checkGhExists: async () => ({ exists: true, version: "2.40.0" }),
    checkGhAuth: async () => ({ authenticated: false, user: undefined }),
    runCommand: async () => { throw new Error("unexpected external process"); },
  });
  assert.equal((await module.prepare({ authorizeInstall: true, authorizeLogin: false })).status, "SKIPPED");
});

test("tool preparation uses registered fake modules without host authentication", async () => {
  const runner = createToolPreparationOrchestrator({
    modules: [{ toolId: "github_cli", inspect: async () => ({ toolId: "github_cli", status: "READY" }), prepare: async () => { throw new Error("READY must not mutate"); } }],
    authorize: async () => { throw new Error("READY must not prompt"); },
  });
  assert.deepEqual(await runner.run({ skipTools: false }), [{ toolId: "github_cli", status: "READY" }]);
});

test("CLI parse rejects invalid combination: init tools --skip-tools", async () => {
  const { runCli } = await import("../../src/cli.ts");
  const exitCode = await runCli(["init", "tools", "--skip-tools"], () => {}, () => {});
  assert.equal(exitCode, 2);
});

test("CLI parse rejects invalid combination: init --skip-tools tools", async () => {
  const { runCli } = await import("../../src/cli.ts");
  const exitCode = await runCli(["init", "--skip-tools", "tools"], () => {}, () => {});
  assert.equal(exitCode, 2);
});

test("CLI parse accepts: init", async () => {
  const { runCli } = await import("../../src/cli.ts");
  const exitCode = await runCli(["init", "--help"], () => {}, () => {});
  assert.equal(exitCode, 0);
});

test("CLI parse accepts: init --skip-tools", async () => {
  const { runCli } = await import("../../src/cli.ts");
  const exitCode = await runCli(["init", "--skip-tools", "--help"], () => {}, () => {});
  assert.equal(exitCode, 0);
});

test("CLI parse accepts: init tools", async () => {
  const { runCli } = await import("../../src/cli.ts");
  const exitCode = await runCli(["init", "tools", "--help"], () => {}, () => {});
  assert.equal(exitCode, 0);
});

test("CLI parse rejects unknown subcommand for init", async () => {
  const { runCli } = await import("../../src/cli.ts");
  const exitCode = await runCli(["init", "unknown"], () => {}, () => {});
  assert.equal(exitCode, 2);
});

test("CLI parse rejects unknown flag for init", async () => {
  const { runCli } = await import("../../src/cli.ts");
  const exitCode = await runCli(["init", "--unknown-flag"], () => {}, () => {});
  assert.equal(exitCode, 2);
});

test("INIT_STEPS has 4 steps including Tools vorbereiten", async () => {
  const { INIT_STEPS } = await import("../../src/init/types.ts");
  assert.equal(INIT_STEPS.length, 4);
  assert.equal(INIT_STEPS[0]!.title, "Umgebung prüfen");
  assert.equal(INIT_STEPS[1]!.title, "Coding-Harnesses auswählen");
  assert.equal(INIT_STEPS[2]!.title, "Tools vorbereiten");
  assert.equal(INIT_STEPS[3]!.title, "Prüfen und einrichten");
});

test("INIT_STEPS_NO_TOOLS has 3 steps without Tools vorbereiten", async () => {
  const { INIT_STEPS_NO_TOOLS } = await import("../../src/init/types.ts");
  assert.equal(INIT_STEPS_NO_TOOLS.length, 3);
  assert.equal(INIT_STEPS_NO_TOOLS[0]!.title, "Umgebung prüfen");
  assert.equal(INIT_STEPS_NO_TOOLS[1]!.title, "Coding-Harnesses auswählen");
  assert.equal(INIT_STEPS_NO_TOOLS[2]!.title, "Prüfen und einrichten");
});
test("tools-only CLI runs just preparation with typed JSON, failures and cancellation", async () => {
  const { runCli } = await import("../../src/cli.ts");
  const { InterruptedFailure } = await import("../../src/errors.ts");
  for (const status of ["READY", "SKIPPED", "UNAVAILABLE", "AUTH_REQUIRED"] as const) {
    const output: string[] = [];
    let prepared = 0;
    const exit = await runCli(["init", "tools", "--json"], value => output.push(value), () => {}, {
      initOptions: { isTTY: true, environment: { home: "/synthetic/home", platform: "linux" }, releaseRoot: "/synthetic/release" },
      init: async () => { throw new Error("full init must not run"); },
      createTransaction: () => { throw new Error("transaction must not run"); },
      prepareTools: async () => { prepared++; return [{ toolId: "github_cli", status }]; },
    });
    assert.equal(prepared, 1);
    assert.equal(output.length, 1);
    const result = JSON.parse(output[0]!);
    assert.deepEqual(result.targets, []);
    assert.equal(result.outcome, status === "READY" || status === "SKIPPED" ? "SUCCESS" : "UNSAFE_STATE");
    assert.equal(exit, status === "READY" || status === "SKIPPED" ? 0 : 4);
    if (exit !== 0) { assert.equal(result.reason, "TOOL_PREPARATION_FAILED"); assert.match(result.guidance, /init tools/); }
  }
  const output: string[] = [];
  assert.equal(await runCli(["init", "tools", "--json"], value => output.push(value), () => {}, {
    initOptions: { isTTY: true, environment: { home: "/synthetic/home", platform: "linux" }, releaseRoot: "/synthetic/release" },
    prepareTools: async () => { throw new InterruptedFailure("SIGINT", "inspect", "NOT_REQUIRED"); },
  }), 130);
  assert.equal(JSON.parse(output[0]!).reason, "CANCELLED");
});

test("tools-only CLI refuses non-TTY before preparation", async () => {
  const { runCli } = await import("../../src/cli.ts");
  const output: string[] = [];
  assert.equal(await runCli(["init", "tools", "--json"], value => output.push(value), () => {}, {
    initOptions: { isTTY: false, environment: { home: "/synthetic/home", platform: "linux" }, releaseRoot: "/synthetic/release" },
    prepareTools: async () => { throw new Error("non-TTY must not prepare"); },
  }), 2);
  assert.equal(JSON.parse(output[0]!).reason, "NON_TTY");
});

test("init help validates duplicates and exposes the three supported variants", async () => {
  const { runCli } = await import("../../src/cli.ts");
  for (const args of [
    ["init", "--help", "-h"], ["init", "tools", "tools", "--help"],
    ["init", "--skip-tools", "tools", "--help"], ["init", "--unknown", "--help"],
  ]) assert.equal(await runCli(args, () => {}, () => {}), 2, args.join(" "));
  const output: string[] = [];
  assert.equal(await runCli(["init", "--help"], value => output.push(value)), 0);
  assert.match(output[0]!, /agent-governance init \[--json\]/);
  assert.match(output[0]!, /agent-governance init --skip-tools \[--json\]/);
  assert.match(output[0]!, /agent-governance init tools \[--json\]/);
});
