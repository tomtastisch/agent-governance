import assert from "node:assert/strict";
import test from "node:test";
import { PassThrough } from "node:stream";
import * as preparation from "../../src/init/tool-preparation/index.ts";
import { InterruptedFailure } from "../../src/errors.ts";
import type { ToolPreparationModule } from "../../src/init/tool-preparation/types.ts";

// External tools and raw terminal input are replaced; the orchestration stays real.
test("fresh install requests login afterwards and returns one final result", async () => {
  const events: string[] = [];
  let installed = false;
  let authenticated = false;
  const module: ToolPreparationModule = {
    toolId: "github_cli",
    inspect: async () => ({ toolId: "github_cli", status: !installed ? "MISSING" : authenticated ? "READY" : "AUTH_REQUIRED" }),
    prepare: async ({ authorizeInstall, authorizeLogin }) => {
      if (authorizeInstall) { events.push("install"); installed = true; }
      if (authorizeLogin) { events.push("login"); authenticated = true; }
      return { toolId: "github_cli", status: authenticated ? "READY" : "SKIPPED" };
    },
  };
  const runner = preparation.createToolPreparationOrchestrator({
    modules: [module],
    authorize: async (_module, message) => { events.push(message); return true; },
  });
  assert.deepEqual(await runner.run({ skipTools: false }), [{ toolId: "github_cli", status: "READY" }]);
  assert.match(events[0]!, /install/i);
  assert.equal(events[1], "install");
  assert.match(events[2]!, /login|auth/i);
  assert.equal(events[3], "login");
});

test("declined or failed installation never requests login", async () => {
  for (const allowed of [false, true]) {
    let prompts = 0;
    const module: ToolPreparationModule = {
      toolId: "github_cli",
      inspect: async () => ({ toolId: "github_cli", status: "MISSING" }),
      prepare: async () => ({ toolId: "github_cli", status: allowed ? "UNAVAILABLE" : "SKIPPED" }),
    };
    const runner = preparation.createToolPreparationOrchestrator({ modules: [module], authorize: async () => { prompts++; return allowed; } });
    assert.equal((await runner.run({ skipTools: false }))[0]!.status, allowed ? "UNAVAILABLE" : "SKIPPED");
    assert.equal(prompts, 1);
  }
});

test("raw Ctrl-C restores input and propagates interruption instead of declining", async () => {
  const input = Object.assign(new PassThrough(), { isTTY: true, isRaw: false, setRawMode(value: boolean) { this.isRaw = value; return this; } });
  const output: string[] = [];
  const pending = preparation.promptUserAuthorization({ toolId: "github_cli" } as ToolPreparationModule, "Install gh?", { stdin: input, write: value => output.push(value) });
  input.write(Buffer.from([3]));
  await assert.rejects(pending, (error: unknown) => error instanceof InterruptedFailure && error.exitCode === 130);
  assert.equal(input.isRaw, false);
  assert.equal(input.listenerCount("data"), 0);
  assert.match(output.join(""), /USER:/);
});

test("real child-process login sends provider output to stderr and propagates exit 130", async () => {
  const { spawnSync } = await import("node:child_process");
  const { mkdir, writeFile, rm } = await import("node:fs/promises");
  const { join } = await import("node:path");
  const { createTestRoot } = await import("../fixtures/installer/workspace.ts");
  const root = await createTestRoot("gh-preparation-process-");
  try {
    await mkdir(join(root, "bin"));
    await writeFile(join(root, "bin", "gh"), `#!/bin/sh
case "$1 $2" in
  "--version ") echo 'gh version 2.40.0'; exit 0 ;;
  "auth status") echo 'SYNTHETIC_PRIVATE_AUTH_OUTPUT' >&2; test -f "$GH_TEST_STATE"; exit $? ;;
  "auth login") echo 'SYNTHETIC_DEVICE_CODE'; echo 'SYNTHETIC_PROVIDER_GUIDANCE' >&2; if test "$GH_TEST_CANCEL" = 1; then exit 130; fi; : > "$GH_TEST_STATE"; exit 0 ;;
esac
exit 99
`, { mode: 0o755 });
    for (const cancel of [false, true]) {
      const child = spawnSync(process.execPath, ["--experimental-strip-types", "--input-type=module", "-e", `
        import { runCli } from './src/cli.ts';
        import { createToolPreparationOrchestrator } from './src/init/tool-preparation/index.ts';
        const runner = createToolPreparationOrchestrator({ authorize: async () => true });
        process.exitCode = await runCli(['init', 'tools', '--json'], console.log, console.error, {
          initOptions: { isTTY: true, environment: { home: '/synthetic/home', platform: 'linux' }, releaseRoot: '/synthetic/release' },
          prepareTools: skipTools => runner.run({ skipTools }),
        });
      `], {
        cwd: process.cwd(), encoding: "utf8", timeout: 5000,
        env: { PATH: join(root, "bin"), GH_TEST_STATE: join(root, cancel ? "cancel-state" : "ready-state"), GH_TEST_CANCEL: cancel ? "1" : "0" },
      });
      assert.equal(child.status, cancel ? 130 : 0, child.stderr);
      const result = JSON.parse(child.stdout);
      assert.equal(result.outcome, cancel ? "INTERRUPTED" : "SUCCESS");
      assert.deepEqual(result.targets, []);
      assert.match(child.stderr, /SYNTHETIC_DEVICE_CODE/);
      assert.match(child.stderr, /SYNTHETIC_PROVIDER_GUIDANCE/);
      assert.equal(child.stderr.includes("SYNTHETIC_PRIVATE_AUTH_OUTPUT"), false);
    }
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("authorization catchable signals restore raw mode and remove temporary handlers", async () => {
  const { EventEmitter } = await import("node:events");
  for (const [signal, code] of [["SIGTERM", 143], ["SIGINT", 130]] as const) {
    const signals = new EventEmitter();
    const input = Object.assign(new PassThrough(), { isTTY: true, isRaw: false, setRawMode(value: boolean) { this.isRaw = value; return this; } });
    const pending = preparation.promptUserAuthorization({ toolId: "github_cli" } as ToolPreparationModule, "Login?", { stdin: input, write: () => {}, signals });
    signals.emit(signal);
    // A normal input event must not be needed to restore the terminal.
    assert.equal(input.isRaw, false);
    input.end();
    await assert.rejects(pending, (error: unknown) => error instanceof InterruptedFailure && error.exitCode === code);
    assert.equal(input.listenerCount("data"), 0);
    assert.equal(signals.listenerCount("SIGINT"), 0);
    assert.equal(signals.listenerCount("SIGTERM"), 0);
  }
});

test("CLI JSON preparation accepts terminal stdin with redirected stdout", async () => {
  const { spawnSync } = await import("node:child_process");
  for (const inputTTY of [true, false]) {
    const child = spawnSync(process.execPath, ["--experimental-strip-types", "--input-type=module", "-e", `
      import { runCli } from './src/cli.ts';
      Object.defineProperty(process.stdin, 'isTTY', { value: ${inputTTY} });
      Object.defineProperty(process.stdout, 'isTTY', { value: false });
      process.exitCode = await runCli(['init','tools','--json'], console.log, console.error, {
        prepareTools: async () => [{ toolId: 'github_cli', status: 'READY' }],
        createTransaction: () => { throw new Error('tools-only cannot start target setup'); },
      });
    `], { encoding: "utf8", timeout: 5000 });
    assert.equal(child.status, inputTTY ? 0 : 2, child.stderr);
    const result = JSON.parse(child.stdout);
    assert.equal(result.outcome, inputTTY ? "SUCCESS" : "INVALID_INVOCATION");
    if (inputTTY) assert.deepEqual(result.toolPreparation, [{ toolId: "github_cli", status: "READY" }]);
    else assert.equal(result.reason, "NON_TTY");
  }
});
