import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { access, mkdtemp, mkdir, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { InstallerTransaction } from "../../src/transaction.ts";

async function fixture(): Promise<{ allowed: string; home: string; release: string; install: string }> {
  const allowed = await mkdtemp(join(tmpdir(), "agent-governance-transaction-"));
  const home = join(allowed, "codex");
  const release = join(allowed, "release");
  const install = join(home, "governance");
  await mkdir(join(release, "bundle", "agent-governance"), { recursive: true });
  await mkdir(home);
  const files: Record<string, string> = {
    VERSION: "0.6.0\n",
    "bundle/GOVERNANCE.md": "canonical governance\n",
    "bundle/agent-governance/manifest.toml": 'schema_version = 2\nlocal_rules = "local/user-rules.md"\n',
  };
  for (const [path, content] of Object.entries(files)) await writeFile(join(release, path), content);
  const inventory = Object.entries(files)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([path, content]) => `${createHash("sha256").update(content).digest("hex")}  ${path}`)
    .join("\n");
  await writeFile(join(release, "release.files.sha256"), `${inventory}\n`);
  return { allowed, home, release, install };
}

test("fresh transaction backs up absences, stages, activates, and verifies", async () => {
  const f = await fixture();
  const transaction = new InstallerTransaction({
    harness: "codex",
    home: f.home,
    allowedRoot: f.allowed,
    releaseRoot: f.release,
    installRoot: f.install,
    dryRun: false,
  });
  const result = await transaction.install();
  assert.equal(result.outcome, "SUCCESS");
  assert.equal(result.state, "FRESH");
  assert.equal(await readFile(join(f.home, "AGENTS.md"), "utf8"), "canonical governance\n");
  assert.match(await readFile(join(f.home, "hooks.json"), "utf8"), /agent_governance__execute/);
  await access(join(f.install, "bundle", "agent-governance", "manifest.toml"));
});

test("dry run returns plan without productive side effects", async () => {
  const f = await fixture();
  const transaction = new InstallerTransaction({
    harness: "codex", home: f.home, allowedRoot: f.allowed, releaseRoot: f.release,
    installRoot: f.install, dryRun: true,
  });
  const result = await transaction.install();
  assert.equal(result.outcome, "SUCCESS");
  await assert.rejects(access(join(f.home, "AGENTS.md")));
  await assert.rejects(access(f.install));
});

test("verification fault rolls back all previously absent targets", async () => {
  const f = await fixture();
  const transaction = new InstallerTransaction({
    harness: "codex", home: f.home, allowedRoot: f.allowed, releaseRoot: f.release,
    installRoot: f.install, dryRun: false, faultAfter: "activate",
  });
  await assert.rejects(transaction.install(), /injected failure/);
  await assert.rejects(access(join(f.home, "AGENTS.md")));
  await assert.rejects(access(join(f.home, "hooks.json")));
  await assert.rejects(access(f.install));
});

test("second unchanged install is idempotent", async () => {
  const f = await fixture();
  const request = { harness: "codex" as const, home: f.home, allowedRoot: f.allowed,
    releaseRoot: f.release, installRoot: f.install, dryRun: false };
  await new InstallerTransaction(request).install();
  const before = await readFile(join(f.home, "hooks.json"), "utf8");
  const second = await new InstallerTransaction(request).install();
  assert.equal(second.state, "CURRENT");
  assert.equal(await readFile(join(f.home, "hooks.json"), "utf8"), before);
});

test("legacy migration preserves personal rules at manifest path", async () => {
  const f = await fixture();
  const personal = "Always preserve this personal rule.\n";
  await writeFile(
    join(f.home, "AGENTS.md"),
    `@~/agent-governance/adapters/AGENTS.md\n${personal}`,
  );
  const result = await new InstallerTransaction({
    harness: "codex", home: f.home, allowedRoot: f.allowed, releaseRoot: f.release,
    installRoot: f.install, dryRun: false,
  }).install();
  assert.equal(result.state, "LEGACY");
  assert.equal(
    await readFile(join(f.install, "bundle", "agent-governance", "local", "user-rules.md"), "utf8"),
    personal,
  );
});

test("tampered current binding fails closed instead of reporting CURRENT", async () => {
  const f = await fixture();
  const request = { harness: "codex" as const, home: f.home, allowedRoot: f.allowed,
    releaseRoot: f.release, installRoot: f.install, dryRun: false };
  await new InstallerTransaction(request).install();
  await writeFile(join(f.home, "AGENTS.md"), "tampered\n");
  await assert.rejects(new InstallerTransaction(request).install(), /unsafe install state/);
});
