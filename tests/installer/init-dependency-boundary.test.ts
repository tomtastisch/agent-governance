import assert from "node:assert/strict";
import { access, cp, mkdir, mkdtemp, readFile, rm, symlink, writeFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { createRequire, syncBuiltinESMExports } from "node:module";
import { dirname, join, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import type { InitPrompt } from "../../src/init/types.ts";
import { createTestRoot } from "../fixtures/installer/workspace.ts";

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const require = createRequire(import.meta.url);

test("the 1.1.0 real init path never starts a package manager or dependency repair process", async (t) => {
  const root = await createTestRoot("agent-governance-init-dependency-boundary-");
  const home = join(root, "home");
  const targetRoot = join(root, "target");
  const installationRoot = join(root, "installation");
  await Promise.all([mkdir(home), mkdir(targetRoot)]);
  t.after(() => rm(root, { recursive: true, force: true }));

  const childProcess = require("node:child_process") as typeof import("node:child_process");
  const intercepted: string[] = [];
  const methods = ["spawn", "spawnSync", "exec", "execSync", "execFile", "execFileSync", "fork"] as const;
  const originals = new Map<string, unknown>();
  for (const method of methods) {
    originals.set(method, childProcess[method]);
    Object.defineProperty(childProcess, method, {
      configurable: true,
      value: (...args: unknown[]) => {
        intercepted.push(`${method}:${String(args[0])}`);
        throw new Error(`init attempted forbidden child process via ${method}`);
      },
      writable: true,
    });
  }
  syncBuiltinESMExports();
  t.after(() => {
    for (const method of methods) {
      Object.defineProperty(childProcess, method, {
        configurable: true,
        value: originals.get(method),
        writable: true,
      });
    }
    syncBuiltinESMExports();
  });

  const prompt: InitPrompt = {
    step(): void {},
    async selectTargets() {
      return [{ manualInput: { targetRoot, entryFile: "AGENTS.md" } }];
    },
    async confirm() {
      return true;
    },
  };
  const output: string[] = [];
  const errors: string[] = [];
  const { runCli } = await import("../../src/cli.ts");

  const exitCode = await runCli(
    ["init"],
    (value) => output.push(value),
    (value) => errors.push(value),
    {
      initOptions: {
        isTTY: true,
        environment: { home, platform: process.platform },
        installationRoot,
        releaseRoot: repositoryRoot,
      },
      initPrompt: prompt,
    },
  );

  assert.equal(exitCode, 0, errors.join("\n"));
  assert.deepEqual(intercepted, []);
  assert.match(output.join("\n"), /"command":"init"/u);
  assert.match(await readFile(join(targetRoot, "AGENTS.md"), "utf8"), /AGENT_GOVERNANCE_MANAGED_V1/u);
  await access(join(installationRoot, "bindings"));
  assert.equal((await readFile(join(repositoryRoot, "VERSION"), "utf8")).trim(), "1.1.0");
});

test("the default init setup intercepts forbidden processes before CLI and prompt imports", () => {
  const result = spawnSync(process.execPath, [
    join(repositoryRoot, "tests/e2e/run_init_pty.mjs"),
    "--boundary",
    "--columns=60",
    "--no-color",
  ], { encoding: "utf8", timeout: 15_000 });

  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
  assert.match(result.stdout, /INIT_BOUNDARY_EXIT=130/u);
  assert.match(result.stdout, /INIT_BOUNDARY_SPAWN_LOG=\[\]/u);
  assert.doesNotMatch(result.stdout, /forbidden child process/u);
});

test("the boundary regression catches a package-manager spawn injected into defaultInitOptions", async (t) => {
  const mutationRoot = await mkdtemp(join(repositoryRoot, "tmp-init-boundary-mutation-"));
  await Promise.all([
    cp(join(repositoryRoot, "src"), join(mutationRoot, "src"), { recursive: true }),
    cp(join(repositoryRoot, "bundle"), join(mutationRoot, "bundle"), { recursive: true }),
    symlink(join(repositoryRoot, "node_modules"), join(mutationRoot, "node_modules"), "dir"),
  ]);
  t.after(() => rm(mutationRoot, { recursive: true, force: true }));

  const cliPath = join(mutationRoot, "src", "cli.ts");
  const mutated = (await readFile(cliPath, "utf8"))
    .replace(
      'import { fileURLToPath } from "node:url";',
      'import { fileURLToPath } from "node:url";\nimport { spawnSync } from "node:child_process";',
    )
    .replace(
      "  const home = realpathSync(homedir());",
      '  spawnSync("npm", ["--version"]);\n  const home = realpathSync(homedir());',
    );
  await writeFile(cliPath, mutated, "utf8");

  const childProcess = require("node:child_process") as typeof import("node:child_process");
  const intercepted: string[] = [];
  const original = childProcess.spawnSync;
  Object.defineProperty(childProcess, "spawnSync", {
    configurable: true,
    value: (...args: unknown[]) => {
      intercepted.push(`spawnSync:${String(args[0])}`);
      throw new Error("mutation attempted forbidden package-manager spawn");
    },
    writable: true,
  });
  syncBuiltinESMExports();
  t.after(() => {
    Object.defineProperty(childProcess, "spawnSync", { configurable: true, value: original, writable: true });
    syncBuiltinESMExports();
  });

  const { runCli } = await import(`${cliPath}?mutation=${Date.now()}`);
  const errors: string[] = [];
  const exitCode = await runCli(["init"], () => {}, (value: string) => errors.push(value), {
    initPrompt: {
      step(): void {},
      async selectTargets() { return []; },
      async confirm() { return false; },
    },
  });

  assert.equal(exitCode, 4, errors.join("\n"));
  assert.deepEqual(intercepted, ["spawnSync:npm"]);
  assert.match(errors.join("\n"), /UNSAFE_STATE/u);
});
