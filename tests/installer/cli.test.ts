import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { runCli } from "../../src/cli.ts";

async function roots(): Promise<{ allowed: string; home: string; release: string; install: string }> {
  const allowed = await mkdtemp(join(tmpdir(), "agent-governance-cli-"));
  const home = join(allowed, "Codex Home With Spaces");
  const release = join(allowed, "release");
  const install = join(home, "governance");
  await mkdir(home);
  await mkdir(join(release, "bundle", "agent-governance"), { recursive: true });
  const files: Record<string, string> = {
    VERSION: "0.6.0\n",
    "bundle/GOVERNANCE.md": "governance\n",
    "bundle/agent-governance/manifest.toml": 'schema_version = 2\nlocal_rules = "local/user-rules.md"\n',
  };
  for (const [path, value] of Object.entries(files)) await writeFile(join(release, path), value);
  await writeFile(join(release, "release.files.sha256"), `${Object.entries(files).sort(([a],[b]) => a.localeCompare(b)).map(
    ([path, value]) => `${createHash("sha256").update(value).digest("hex")}  ${path}`,
  ).join("\n")}\n`);
  return { allowed, home, release, install };
}

function args(command: string, r: Awaited<ReturnType<typeof roots>>): string[] {
  return [command, "--harness", "codex", "--home", r.home, "--allowed-root", r.allowed,
    "--release-root", r.release, "--install-root", r.install, "--json"];
}

test("CLI inspect and plan emit deterministic JSON without mutation", async () => {
  const r = await roots();
  const output: string[] = [];
  assert.equal(await runCli(args("inspect", r), (value) => output.push(value)), 0);
  assert.equal(JSON.parse(output.at(-1)!).state, "FRESH");
  assert.equal(await runCli(args("plan", r), (value) => output.push(value)), 0);
  const plan = JSON.parse(output.at(-1)!);
  assert.equal(plan.plan.mcpMutation, false);
  assert.equal(plan.plan.approvalExpansion, false);
});

test("CLI install, verify, status, and rollback operate in isolated home", async () => {
  const r = await roots();
  const output: string[] = [];
  for (const command of ["install", "verify", "status", "rollback"]) {
    assert.equal(await runCli(args(command, r), (value) => output.push(value)), 0, command);
  }
  assert.equal(JSON.parse(output.at(-1)!).rollbackStatus, "SUCCEEDED");
  assert.equal(await runCli(args("rollback", r), (value) => output.push(value)), 0);
});

test("CLI rejects unsupported harness and incomplete invocation", async () => {
  const r = await roots();
  const errors: string[] = [];
  const unsupported = args("inspect", r);
  unsupported[unsupported.indexOf("codex")] = "opencode";
  assert.equal(await runCli(unsupported, () => {}, (value) => errors.push(value)), 3);
  assert.equal(await runCli(["install", "--json"], () => {}, (value) => errors.push(value)), 2);
  assert.equal(errors.some((value) => value.includes("token")), false);
});
