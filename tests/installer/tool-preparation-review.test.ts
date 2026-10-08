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
      assert.equal(child.stdout.includes("effectContext"), false, "interner Effekttransport bleibt außerhalb des öffentlichen Ergebnisses");
      if (cancel) {
        assert.equal(result.phase, "activate");
        assert.equal(result.resourceId, "github_cli:login");
        assert.equal(result.externalEffect.state, "UNVERIFIED");
        assert.equal(result.externalEffect.rollback, "NOT_ATTEMPTED");
        assert.match(result.externalEffect.guidance, /provider|Provider/);
      }
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

test("signals sent only to the CLI reach preparation children and wait for child close", async () => {
  const { spawn } = await import("node:child_process");
  const { mkdir, writeFile, rm } = await import("node:fs/promises");
  const { join } = await import("node:path");
  const { createTestRoot } = await import("../fixtures/installer/workspace.ts");
  const root = await createTestRoot("gh-signal-forwarding-");
  try {
    await mkdir(join(root, "bin"));
    await writeFile(join(root, "bin", "gh"), `#!${process.execPath}\nprocess.on('SIGINT', finish); process.on('SIGTERM', finish);\nfunction finish() { process.stderr.write('CHILD_SIGNAL_RECEIVED\\n'); setTimeout(() => { process.stderr.write('CHILD_STOPPED\\n'); process.exit(0); }, 50); }\nprocess.stderr.write('CHILD_READY\\n'); setTimeout(() => process.exit(99), 2000);\n`, { mode: 0o755 });
    for (const signal of ["SIGINT", "SIGTERM"] as const) {
      const child = spawn(process.execPath, ["--experimental-strip-types", "--input-type=module", "-e", `
        import { createGhPreparationModule } from './src/init/tool-preparation/gh.ts';
        import { runCli } from './src/cli.ts';
        const module = createGhPreparationModule({ checkGhExists: async () => ({ exists: true, version: 'synthetic' }), checkGhAuth: async () => ({ authenticated: false, user: undefined }), write: () => {} });
        process.exitCode = await runCli(['init','tools','--json'], console.log, console.error, {
          initOptions: { isTTY: true, environment: { home: '/synthetic/home', platform: 'linux' }, releaseRoot: '/synthetic/release' },
          prepareTools: async () => [await module.prepare({ authorizeInstall: false, authorizeLogin: true })],
        });
      `], { env: { ...process.env, PATH: join(root, "bin") }, stdio: ["ignore", "pipe", "pipe"] });
      let output = ""; let errors = ""; let sent = false;
      const closed = new Promise<{ code: number | null; signal: NodeJS.Signals | null }>(resolve => child.on("close", (code, signal) => resolve({ code, signal })));
      const timer = setTimeout(() => child.kill("SIGKILL"), 5000);
      child.stdout.on("data", chunk => { output += chunk; });
      child.stderr.on("data", chunk => { errors += chunk; if (!sent && errors.includes("CHILD_READY")) { sent = true; child.kill(signal); } });
      const result = await closed; clearTimeout(timer);
      assert.equal(result.code, signal === "SIGINT" ? 130 : 143, errors);
      assert.match(errors, /CHILD_SIGNAL_RECEIVED/);
      assert.match(errors, /CHILD_STOPPED/);
      const value = JSON.parse(output);
      assert.equal(value.signal, signal);
      assert.equal(value.phase, "activate");
      assert.equal(value.resourceId, "github_cli:login");
      assert.equal(value.externalEffect.state, "UNVERIFIED");
      assert.equal(value.externalEffect.rollback, "NOT_ATTEMPTED");
    }
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("reale Signale nach Tool-Preparation erhalten JSON bei lesenden Prüfungen und echtem Confirm-Prompt", async () => {
  const { spawn } = await import("node:child_process");
  for (const operation of ["status", "plan", "verify", "confirm", "plan-error"] as const) {
    for (const signal of ["SIGINT", "SIGTERM"] as const) {
      const child = spawn(process.execPath, ["--experimental-strip-types", "--input-type=module", "-e", `
        import { runCli } from './src/cli.ts';
        import { runInit } from './src/init/orchestrator.ts';
        import { createClackPrompt } from './src/init/prompt.ts';
        const operation = ${JSON.stringify(operation)};
        const options = { isTTY: true, environment: { home: '/synthetic/home', platform: 'linux' }, releaseRoot: '/synthetic/release' };
        const realPrompt = createClackPrompt();
        const prompt = { step() {}, dispose() { realPrompt.dispose(); }, async selectTargets() { return [{ manualInput: { targetRoot: '/synthetic/target', entryFile: 'AGENTS.md' } }]; }, async confirm(plans, signal) { if (operation !== 'confirm') return true; const pending = realPrompt.confirm(plans, signal); process.stderr.write('READ_READY\\n'); return pending; } };
        const result = command => ({ schemaVersion: 1, command, outcome: 'SUCCESS', state: command === 'status' ? 'FRESH' : 'CURRENT', phase: command === 'plan' ? 'plan' : command === 'verify' ? 'verify' : 'inspect', rollbackStatus: 'NOT_REQUIRED', capabilities: [], plan: { command: 'install', resources: [] } });
        const read = async command => { if (operation === command || (operation === 'plan-error' && command === 'plan')) { process.stderr.write('READ_READY\\n'); await new Promise(resolve => setTimeout(resolve, 200)); if (operation === 'plan-error') throw new Error('synthetic read failure after signal'); } return result(command); };
        const transaction = { status: () => read('status'), plan: () => read('plan'), verify: () => read('verify'), localVersion: async () => undefined, install: async () => { process.stderr.write('TARGET_MUTATION\\n'); return result('install'); }, update: async () => result('update') };
        process.exitCode = await runCli(['init', '--json'], console.log, console.error, { initOptions: options, initPrompt: prompt,
          init: () => runInit(options, { discoverHarnesses: async () => [], resolveLatestRelease: async () => undefined, prompt, prepareTools: async () => [{ toolId: 'github_cli', status: 'READY', message: 'completed' }], createTransaction: () => transaction }) });
        process.stderr.write('LISTENERS=' + process.listenerCount('SIGINT') + ',' + process.listenerCount('SIGTERM') + '\\n');
      `], { stdio: ["pipe", "pipe", "pipe"] });
      let output = ""; let errors = ""; let sent = false;
      const closed = new Promise<{ code: number | null; signal: NodeJS.Signals | null }>((resolve, reject) => {
        child.once("error", reject);
        child.once("close", (code, signal) => resolve({ code, signal }));
      });
      const timer = setTimeout(() => child.kill("SIGKILL"), 5000);
      child.stdout.on("data", chunk => { output += chunk; });
      child.stderr.on("data", chunk => {
        errors += chunk;
        if (!sent && errors.includes("READ_READY")) { sent = true; child.kill(signal); }
      });
      let result;
      try { result = await closed; } finally { clearTimeout(timer); }
      assert.equal(sent, true);
      assert.equal(result.signal, null, `${signal}:${operation}: ${errors}`);
      assert.equal(result.code, signal === "SIGINT" ? 130 : 143, errors);
      const value = JSON.parse(output);
      assert.equal(value.outcome, "INTERRUPTED");
      assert.equal(value.signal, signal);
      assert.equal(value.phase, operation === "status" ? "inspect" : operation === "verify" ? "verify" : "plan");
      assert.equal(value.rollbackStatus, "NOT_REQUIRED");
      assert.deepEqual(value.toolPreparation, [{ toolId: "github_cli", status: "READY", message: "completed" }]);
      assert.match(errors, /LISTENERS=0,0/u);
      if (operation !== "verify") assert.doesNotMatch(errors, /TARGET_MUTATION/u);
    }
  }
});

test("Tool-Abbruch unterscheidet Inspektion, externe Mutation und deren unverifizierten Read-back", async () => {
  const { createGhPreparationModule } = await import("../../src/init/tool-preparation/gh.ts");
  for (const stage of ["inspect", "apt-update", "apt-install", "brew-install", "login", "install-readback", "login-readback"] as const) {
    for (const signal of ["SIGINT", "SIGTERM"] as const) {
      let versionReads = 0;
      let authReads = 0;
      let mutated = false;
      const commands: string[] = [];
      const login = stage === "login" || stage === "login-readback";
      const module = createGhPreparationModule({
        platform: () => stage.startsWith("apt") ? "linux" : "darwin",
        effectiveUserId: () => 0, write: () => {},
        runCommand: async (command, args) => {
          const invocation = `${command} ${args.join(" ")}`;
          commands.push(invocation);
          const interrupt = (): never => { throw new InterruptedFailure(signal, "inspect", "NOT_REQUIRED"); };
          if (invocation === "gh --version") {
            versionReads++;
            if (stage === "inspect" || (stage === "install-readback" && versionReads === 2)) interrupt();
            return { exitCode: login || mutated ? 0 : 1, stdout: "gh version 2.60.0", stderr: "" };
          }
          if (invocation.startsWith("gh auth status")) {
            authReads++;
            if (stage === "login-readback" && authReads === 2) interrupt();
            return { exitCode: 1, stdout: "", stderr: "" };
          }
          if (command === "which") return { exitCode: 0, stdout: "", stderr: "" };
          mutated = true;
          if ((stage === "apt-update" && invocation === "apt update") ||
              (stage === "apt-install" && invocation === "apt install -y gh") ||
              (stage === "brew-install" && invocation === "brew install gh") ||
              (stage === "login" && invocation.startsWith("gh auth login"))) interrupt();
          return { exitCode: 0, stdout: "", stderr: "" };
        },
      });
      await assert.rejects(stage === "inspect" ? module.inspect() : module.prepare({ authorizeInstall: !login, authorizeLogin: login }), (cause: unknown) => {
        assert.ok(cause instanceof InterruptedFailure);
        assert.equal(cause.signal, signal);
        assert.equal(cause.phase, stage === "inspect" ? "inspect" : stage.endsWith("readback") ? "verify" : "activate");
        assert.equal(cause.resourceId, `github_cli:${stage === "inspect" ? "inspect" : login ? "login" : "install"}`);
        assert.equal(cause.rollbackStatus, "NOT_REQUIRED");
        assert.equal(cause.externalEffect?.state, mutated ? "UNVERIFIED" : undefined);
        assert.equal(cause.externalEffect?.rollback, mutated ? "NOT_ATTEMPTED" : undefined);
        if (mutated) assert.match(cause.externalEffect!.guidance, /kein externer Rollback/);
        return true;
      });
      if (stage === "apt-update") assert.ok(!commands.some(command => command.startsWith("apt install")));
    }
  }
});

test("Installationseffekt bleibt zwischen Modul-Read-back und separater Loginfreigabe erhalten", async () => {
  const { createGhPreparationModule } = await import("../../src/init/tool-preparation/gh.ts");
  const { runCli } = await import("../../src/cli.ts");
  for (const stage of ["inspect-after-install", "login-approval", "login-precheck"] as const) {
    for (const signal of ["SIGINT", "SIGTERM"] as const) {
      let existsCalls = 0;
      let installed = false;
      let loginStarted = false;
      const module = createGhPreparationModule({
        platform: () => "darwin", write: () => {}, checkBrewAvailable: async () => true,
        checkGhExists: async () => {
          existsCalls++;
          if ((stage === "inspect-after-install" && existsCalls === 4) || (stage === "login-precheck" && existsCalls === 5)) throw new InterruptedFailure(signal, "inspect", "NOT_REQUIRED");
          return { exists: installed, version: "synthetic" };
        },
        runBrewInstall: async () => { installed = true; return true; },
        checkGhAuth: async () => ({ authenticated: false, user: undefined }),
        runGhAuthLogin: async () => { loginStarted = true; return true; },
      });
      let authorizations = 0;
      const runner = preparation.createToolPreparationOrchestrator({ modules: [module], authorize: async () => {
        authorizations++;
        if (authorizations === 2 && stage === "login-approval") throw new InterruptedFailure(signal, "inspect", "NOT_REQUIRED");
        return true;
      } });
      const output: string[] = [];
      const exit = await runCli(["init", "tools", "--json"], value => output.push(value), () => {}, {
        initOptions: { isTTY: true, environment: { home: "/synthetic/home", platform: "darwin" }, releaseRoot: "/synthetic/release" },
        prepareTools: skipTools => runner.run({ skipTools }),
      });
      assert.equal(exit, signal === "SIGINT" ? 130 : 143);
      assert.equal(installed, true);
      assert.equal(loginStarted, false);
      assert.equal(output.length, 1);
      const result = JSON.parse(output[0]!);
      assert.equal(result.resourceId, "github_cli:install");
      assert.equal(result.externalEffect.state, "UNVERIFIED");
      assert.equal(result.externalEffect.rollback, "NOT_ATTEMPTED");
      assert.equal(result.phase, stage === "login-approval" ? "plan" : "verify");
    }
  }
});

test("frühe Init-Schritte und alle Auswahlprompts behandeln echte OS-Signale strukturiert", async () => {
  const { spawn } = await import("node:child_process");
  const { mkdir, rm } = await import("node:fs/promises");
  const { join } = await import("node:path");
  const { createTestRoot } = await import("../fixtures/installer/workspace.ts");
  const root = await createTestRoot("init-early-signals-");
  await mkdir(join(root, ".claude"));
  try {
    for (const stage of ["discovery", "latest", "row-status", "row-version", "selection", "manual-root", "manual-entry"] as const) {
      for (const signal of ["SIGINT", "SIGTERM"] as const) {
        const child = spawn(process.execPath, ["--experimental-strip-types", "--input-type=module", "-e", `
          import * as clack from '@clack/prompts';
          import { runCli } from './src/cli.ts';
          import { runInit } from './src/init/orchestrator.ts';
          import { createClackPrompt } from './src/init/prompt.ts';
          import { INIT_CANCELLED } from './src/init/types.ts';
          const stage = ${JSON.stringify(stage)}; const home = ${JSON.stringify(root)};
          const ready = pending => { process.stderr.write('EARLY_READY\\n'); return pending; };
          const pause = async current => { if (stage === current) await ready(new Promise(resolve => setTimeout(resolve, 200))); };
          const real = createClackPrompt({ prompts: {
            autocompleteMultiselect: options => stage === 'selection' ? ready(clack.autocompleteMultiselect({ ...options, output: process.stderr })) : Promise.resolve(['__custom__']),
            path: options => stage === 'manual-root' ? ready(clack.path({ ...options, output: process.stderr })) : Promise.resolve(home),
            text: options => ready(clack.text({ ...options, output: process.stderr })),
            confirm: async () => { throw new Error('confirmation must not start'); },
            spinner: () => ({ start() {}, stop() {} }), cancel() {}, isCancel: clack.isCancel,
          } });
          const prompt = { ...real, selectTargets: (rows, signal) => ['selection','manual-root','manual-entry'].includes(stage) ? real.selectTargets(rows, signal) : Promise.resolve(INIT_CANCELLED) };
          const options = { isTTY: true, environment: { home, platform: 'linux' }, releaseRoot: home + '/release' };
          const transaction = { status: async () => { await pause('row-status'); return { state: 'FRESH' }; }, localVersion: async () => { await pause('row-version'); }, plan: async () => { throw new Error('plan must not start'); } };
          process.exitCode = await runCli(['init','--json'], console.log, console.error, { init: () => runInit(options, {
            discoverHarnesses: async () => { await pause('discovery'); return stage.startsWith('row-') ? [{ id: 'claude', displayName: 'Claude' }] : []; },
            resolveLatestRelease: async () => { await pause('latest'); }, prompt, createTransaction: () => transaction,
            prepareTools: async () => { throw new Error('tool mutation must not start'); },
          }) });
          process.stderr.write('LISTENERS=' + process.listenerCount('SIGINT') + ',' + process.listenerCount('SIGTERM') + '\\n');
        `], { stdio: ["pipe", "pipe", "pipe"] });
        let output = ""; let errors = ""; let sent = false;
        const closed = new Promise<{ code: number | null; signal: NodeJS.Signals | null }>((resolve, reject) => {
          child.once("error", reject); child.once("close", (code, signal) => resolve({ code, signal }));
        });
        const timer = setTimeout(() => child.kill("SIGKILL"), 5000);
        child.stdout.on("data", chunk => { output += chunk; });
        child.stderr.on("data", chunk => { errors += chunk; if (!sent && errors.includes("EARLY_READY")) { sent = true; child.kill(signal); } });
        let result;
        try { result = await closed; } finally { clearTimeout(timer); }
        assert.equal(sent, true);
        assert.equal(result.signal, null, `${stage}:${signal}: ${errors}`);
        assert.equal(result.code, signal === "SIGINT" ? 130 : 143, errors);
        const value = JSON.parse(output);
        assert.equal(value.outcome, "INTERRUPTED");
        assert.equal(value.signal, signal);
        assert.equal(value.phase, ["selection", "manual-root", "manual-entry"].includes(stage) ? "plan" : "inspect");
        assert.deepEqual(value.targets, []);
        assert.deepEqual(value.toolPreparation, []);
        assert.match(errors, /LISTENERS=0,0/);
      }
    }
  } finally { await rm(root, { recursive: true, force: true }); }
});
