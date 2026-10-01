import assert from "node:assert/strict";
import test from "node:test";
import { runToolPreparation } from "../../src/init/tool-preparation/index.ts";
import { ghPreparationModule } from "../../src/init/tool-preparation/gh.ts";
import type { ToolPreparationResult } from "../../src/init/tool-preparation/types.ts";

test("runToolPreparation with skipTools returns empty array", async () => {
  const results = await runToolPreparation(true);
  assert.deepEqual(results, []);
});

test("ghPreparationModule inspect returns structured result", async () => {
  const result = await ghPreparationModule.inspect();
  assert.equal(typeof result.toolId, "string");
  assert.equal(result.toolId, "github_cli");
  assert.ok(["READY", "MISSING", "AUTH_REQUIRED", "SKIPPED", "UNAVAILABLE"].includes(result.status));
  assert.ok(result.message === undefined || typeof result.message === "string");
});

test("ghPreparationModule prepare with userAuthorized=false returns SKIPPED", async () => {
  const result = await ghPreparationModule.prepare({ userAuthorized: false });
  assert.equal(result.toolId, "github_cli");
  assert.equal(result.status, "SKIPPED");
  assert.equal(result.message, "User declined preparation.");
});

test("runToolPreparation without skipTools returns results array", async () => {
  const results = await runToolPreparation(false);
  assert.ok(Array.isArray(results));
  assert.ok(results.length > 0);
  for (const result of results) {
    assert.ok(typeof result.toolId === "string");
    assert.ok(["READY", "MISSING", "AUTH_REQUIRED", "SKIPPED", "UNAVAILABLE"].includes(result.status));
  }
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