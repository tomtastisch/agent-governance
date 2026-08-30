import assert from "node:assert/strict";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import test, { type TestContext } from "node:test";

async function allowlistedFixture(t: TestContext): Promise<{ root: string; paths: string[] }> {
  const root = await mkdtemp(join(tmpdir(), "agent-governance-pack-report-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const paths = [
    "CHANGELOG.md",
    "LICENSE",
    "README.md",
    "VERSION",
    "package.json",
    "release.files.sha256",
    "bundle/GOVERNANCE.md",
    "bundle/agent-governance/manifest.toml",
    "bundle/agent-governance/catalogs/commands.toml",
    "bundle/agent-governance/catalogs/discovery-signals.toml",
    "assets/branding/agent-governance-terminal.png",
    "docs/installer-cli-reference.md",
    "dist/cli.js",
    `prebuilds/${process.platform}-${process.arch}/agent_governance_fs.node`,
  ];
  for (const path of paths) {
    await mkdir(join(root, path, ".."), { recursive: true });
    await writeFile(join(root, path), path === "package.json" ? '{"name":"@tomtastisch/agent-governance"}\n' : "fixture\n");
  }
  return { root, paths };
}

async function addFixturePath(root: string, paths: string[], path: string): Promise<void> {
  await mkdir(join(root, path, ".."), { recursive: true });
  await writeFile(join(root, path), "fixture\n");
  paths.push(path);
}

function verify(root: string, report: unknown) {
  return spawnSync(process.execPath, [join(import.meta.dirname, "../../tools/verify-pack.mjs")], {
    cwd: root,
    input: JSON.stringify(report),
    encoding: "utf8",
  });
}

test("pack verifier accepts the npm 12 package-keyed JSON report", async (t) => {
  const { root, paths } = await allowlistedFixture(t);
  const report = { "@tomtastisch/agent-governance": { name: "@tomtastisch/agent-governance", files: paths.map((path) => ({ path })) } };
  const result = verify(root, report);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /tarball entries are generic and allowlisted/);
});

for (const path of [
  "INSTALL.md",
  "assets/diagrams/governance-overview.png",
  "docs/harness-recipes.md",
  "docs/installer-architecture.md",
]) {
  test(`pack verifier rejects forbidden package path ${path}`, async (t) => {
    const { root, paths } = await allowlistedFixture(t);
    await addFixturePath(root, paths, path);
    const report = [{ name: "@tomtastisch/agent-governance", files: paths.map((fixturePath) => ({ path: fixturePath })) }];
    const result = verify(root, report);
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /forbidden|unexpected tarball path/);
  });
}

for (const required of [
  "README.md",
  "LICENSE",
  "CHANGELOG.md",
  "docs/installer-cli-reference.md",
  "assets/branding/agent-governance-terminal.png",
  "bundle/agent-governance/catalogs/commands.toml",
  "bundle/agent-governance/catalogs/discovery-signals.toml",
]) {
  test(`pack verifier requires package path ${required}`, async (t) => {
    const { root, paths } = await allowlistedFixture(t);
    const report = [{
      name: "@tomtastisch/agent-governance",
      files: paths.filter((path) => path !== required).map((path) => ({ path })),
    }];
    const result = verify(root, report);
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, new RegExp(`missing tarball path: ${required.replaceAll(".", "\\.")}`));
  });
}

test("pack verifier rejects foreign package identity in npm 12 reports", async (t) => {
  const { root, paths } = await allowlistedFixture(t);
  const report = { "@foreign/package": { name: "@foreign/package", files: paths.map((path) => ({ path })) } };
  const result = verify(root, report);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /unexpected schema/);
});

test("pack verifier rejects foreign package identity in npm 11 reports", async (t) => {
  const { root, paths } = await allowlistedFixture(t);
  const report = [{ name: "@foreign/package", files: paths.map((path) => ({ path })) }];
  const result = verify(root, report);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /unexpected schema/);
});

test("pack verifier rejects multiple npm 12 package keys", () => {
  const report = {
    "@tomtastisch/agent-governance": { name: "@tomtastisch/agent-governance", files: [] },
    "@foreign/package": { name: "@foreign/package", files: [] },
  };
  const result = verify(process.cwd(), report);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /unexpected schema/);
});
