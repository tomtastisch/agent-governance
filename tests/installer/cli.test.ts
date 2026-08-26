import assert from "node:assert/strict";
import { join } from "node:path";
import test from "node:test";
import { runCli } from "../../src/cli.ts";
import { InstallerFailure, InterruptedFailure } from "../../src/errors.ts";
import { InstallerTransaction } from "../../src/transaction.ts";
import { COMMANDS, type InstallResult } from "../../src/contracts.ts";
import { createTestRoot } from "../fixtures/installer/workspace.ts";

async function args(command: string): Promise<string[]> { const target = await createTestRoot("agent-governance-cli-"); return [command, "--scope", "global", "--target-root", target, "--entry-file", "AGENTS.md", "--installation-root", join(target, ".agent-governance"), "--non-interactive", "--json"]; }
function result(command: InstallResult["command"]): InstallResult { return { schemaVersion: 1, architecture: "GLOBAL_EXPLICIT_PATH_MANAGED_BLOCK", command, outcome: "SUCCESS", state: "FRESH", phase: "inspect", rollbackStatus: "NOT_REQUIRED", capabilities: [] }; }

test("CLI inspect and plan emit deterministic versioned JSON without mutation", async () => { const output: string[] = []; assert.equal(await runCli(await args("inspect"), (value) => output.push(value)), 0); assert.equal(JSON.parse(output.at(-1)!).schemaVersion, 1); assert.equal(await runCli(await args("plan"), (value) => output.push(value)), 0); const plan = JSON.parse(output.at(-1)!).plan; assert.equal(plan.harnessSpecificMutation, false); assert.equal(plan.hookMutation, false); });
test("CLI exposes all generic commands through one explicit path contract", async () => { const originals = new Map<string, unknown>(); for (const command of ["install", "verify", "status", "update", "uninstall", "rollback"] as const) { originals.set(command, InstallerTransaction.prototype[command]); InstallerTransaction.prototype[command] = async () => result(command) as never; } try { for (const command of originals.keys()) assert.equal(await runCli(await args(command), () => {}), 0, command); } finally { for (const [command, original] of originals) Object.assign(InstallerTransaction.prototype, { [command]: original }); } });
test("CLI renders global and command help before required options or transaction access", async () => {
  const originals = new Map<string, unknown>();
  let transactionCalls = 0;
  for (const command of COMMANDS) {
    originals.set(command, InstallerTransaction.prototype[command]);
    InstallerTransaction.prototype[command] = (async () => { transactionCalls += 1; throw new Error("transaction must not run for help"); }) as never;
  }
  try {
    for (const argv of [["--help"], ["-h"], ["init", "--help"], ["install", "--help"], ["install", "-h"]]) {
      const output: string[] = [];
      const errors: string[] = [];
      assert.equal(await runCli(argv, (value) => output.push(value), (value) => errors.push(value)), 0, argv.join(" "));
      assert.equal(output.length, 1, argv.join(" "));
      assert.equal(errors.length, 0, argv.join(" "));
    }
    assert.equal(transactionCalls, 0);
  } finally {
    for (const [command, original] of originals) Object.assign(InstallerTransaction.prototype, { [command]: original });
  }
});
test("CLI rejects implicit, duplicate, unknown, non-global, and harness-specific arguments", async () => { for (const argv of [[], ["install", "--json"], [...await args("install"), "--target-root", "/duplicate"], [...await args("install"), "--scope", "project"], [...await args("install"), "--harness", "codex"]]) assert.equal(await runCli(argv, () => {}, () => {}), 2); });
test("CLI rejects unknown commands with exit 2 even when help is requested", async () => { assert.equal(await runCli(["unknown", "--help"], () => {}, () => {}), 2); });
test("CLI maps structured failures and catchable signals without secret content", async () => { const original = InstallerTransaction.prototype.install; try { InstallerTransaction.prototype.install = async () => { throw new InstallerFailure("VERIFY", "verify", "entry-file", "VERIFICATION_ROLLED_BACK", "failed", "SUCCEEDED"); }; const errors: string[] = []; assert.equal(await runCli(await args("install"), () => {}, (value) => errors.push(value)), 5); assert.equal(JSON.parse(errors.at(-1)!).outcome, "VERIFICATION_ROLLED_BACK"); for (const [signal, code] of [["SIGINT", 130], ["SIGTERM", 143]] as const) { InstallerTransaction.prototype.install = async () => { throw new InterruptedFailure(signal, "activate", "SUCCEEDED"); }; assert.equal(await runCli(await args("install"), () => {}, (value) => errors.push(value)), code); assert.equal(JSON.parse(errors.at(-1)!).signal, signal); } assert.equal(errors.some((value) => /token|secret/i.test(value)), false); } finally { InstallerTransaction.prototype.install = original; } });
