import assert from "node:assert/strict";
import { cp, mkdir, readFile, readdir, rename, rm, symlink, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import test, { type TestContext } from "node:test";
import { createTestRoot } from "../fixtures/installer/workspace.ts";
import { createReleaseFixture, writeInventory } from "../fixtures/installer/release.ts";

// Positive payload data comes from the existing release fixture and package contract.
// Individual mutations below remain independent behavioral expectations.
async function allowlistedFixture(t: TestContext): Promise<{ root: string; paths: string[] }> {
  const root = await createTestRoot("agent-governance-pack-report-");
  t.after(() => rm(root, { recursive: true, force: true }));
  await createReleaseFixture(root);
  const repository = join(import.meta.dirname, "../..");
  const metadata = JSON.parse(await readFile(join(repository, "package.json"), "utf8"));
  await writeFile(join(root, "package.json"), JSON.stringify(metadata));
  for (const path of metadata.files as string[]) {
    if (["bundle", "dist", "prebuilds", "VERSION", "release.files.sha256"].includes(path)) continue;
    await mkdir(join(root, path, ".."), { recursive: true });
    await cp(join(repository, path), join(root, path), { recursive: true });
  }
  async function targets(value: unknown): Promise<void> {
    if (typeof value === "string") {
      await mkdir(join(root, value, ".."), { recursive: true });
      await writeFile(join(root, value), "fixture\n");
    } else if (typeof value === "object" && value !== null) {
      for (const child of Object.values(value)) await targets(child);
    }
  }
  await targets(metadata.bin);
  await targets(metadata.exports);
  await targets("dist/resume-checkpoint-schema.js");
  await targets(`prebuilds/${process.platform}-${process.arch}/agent_governance_fs.node`);
  const paths = await readdir(root, { recursive: true, withFileTypes: true });
  return { root, paths: paths.filter(entry => entry.isFile()).map(entry => join(entry.parentPath, entry.name).slice(root.length + 1)) };
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

test("pack verifier requires exactly the terminal branding asset path", async (t) => {
  const { root, paths } = await allowlistedFixture(t);
  const report = (entries: string[]) => [{ name: "@tomtastisch/agent-governance", files: entries.map((path) => ({ path })) }];
  const accepted = verify(root, report(paths));
  assert.equal(accepted.status, 0, accepted.stderr);

  const missing = verify(root, report(paths.filter((path) => path !== "assets/branding/agent-governance-terminal.png")));
  assert.notEqual(missing.status, 0);
  assert.match(missing.stderr, /missing tarball path: assets\/branding\/agent-governance-terminal\.png/u);
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

test("alle verifizierten Release-Payload-Dateien sind im Paket erforderlich", async (t) => {
  const { root, paths } = await allowlistedFixture(t);
  const missing = "bundle/agent-governance/modules/evidence.md";
  assert.ok(paths.includes(missing));
  const result = verify(root, report(paths.filter(path => path !== missing)));
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /missing tarball path/);
});

function report(paths: string[]) {
  return [{ name: "@tomtastisch/agent-governance", files: paths.map(path => ({ path })) }];
}

for (const field of ["bin", "exports"] as const) {
  test(`neue deklarierte ${field}-Ziele werden ohne manuelle Inventarliste geprüft`, async (t) => {
    const { root, paths } = await allowlistedFixture(t);
    const metadata = JSON.parse(await readFile(join(root, "package.json"), "utf8"));
    const target = "dist/declared-target.js";
    if (field === "bin") metadata.bin.extra = target;
    else metadata.exports["./extra"] = { default: `./${target}` };
    await writeFile(join(root, "package.json"), JSON.stringify(metadata));
    await addFixturePath(root, paths, target);
    assert.equal(verify(root, report(paths)).status, 0);
    const missing = verify(root, report(paths.filter(path => path !== target)));
    assert.notEqual(missing.status, 0);
    assert.match(missing.stderr, /missing tarball path/);
    await rm(join(root, target));
    assert.notEqual(verify(root, report(paths.filter(path => path !== target))).status, 0);
  });
}

for (const path of ["dist/internal-runtime.js", "dist/internal-runtime.d.ts", "contracts/extra-contract.json", "docs/extra-runtime.md"]) {
  test(`Package-Dateivertrag erfasst ${path}`, async (t) => {
    const { root, paths } = await allowlistedFixture(t);
    if (path.startsWith("docs/")) {
      const metadata = JSON.parse(await readFile(join(root, "package.json"), "utf8"));
      metadata.files.push(path);
      await writeFile(join(root, "package.json"), JSON.stringify(metadata));
    }
    await addFixturePath(root, paths, path);
    const accepted = verify(root, report(paths));
    assert.equal(accepted.status, 0, accepted.stderr);
    const missing = verify(root, report(paths.filter(value => value !== path)));
    assert.notEqual(missing.status, 0);
    assert.match(missing.stderr, /missing tarball path/);
  });
}

test("Release-Digests werden vor der Package-Aussage verifiziert", async (t) => {
  const { root, paths } = await allowlistedFixture(t);
  await writeFile(join(root, "bundle/GOVERNANCE.md"), "tampered\n");
  const result = verify(root, report(paths));
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /digest mismatch/);
});

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


test("verschobene Manifestreferenzen benötigen keine zweite Pfadliste", async (t) => {
  const { root, paths } = await allowlistedFixture(t);
  const before = "bundle/agent-governance/ssot/routing/tools.toml";
  const after = "bundle/agent-governance/ssot/routing/tool-profiles.toml";
  await rename(join(root, before), join(root, after));
  const index = join(root, "bundle/agent-governance/ssot/manifest.toml");
  await writeFile(index, (await readFile(index, "utf8")).replace('tools = "routing/tools.toml"', 'tools = "routing/tool-profiles.toml"'));
  await writeInventory(root);
  const updated = paths.map(path => path === before ? after : path);
  const accepted = verify(root, report(updated));
  assert.equal(accepted.status, 0, accepted.stderr);
  const missing = verify(root, report(updated.filter(path => path !== after)));
  assert.notEqual(missing.status, 0);
  assert.match(missing.stderr, /missing tarball path/);
});

test("jede Fixture-Datei muss im Report vorhanden sein", async (t) => {
  const { root, paths } = await allowlistedFixture(t);
  for (const path of paths) {
    const result = verify(root, report(paths.filter(value => value !== path)));
    assert.notEqual(result.status, 0, path);
    assert.match(result.stderr, /missing (?:native )?tarball path/, path);
  }
});

for (const path of ["../outside", "/outside", "dist/../outside", "dist//cli.js", "dist\\cli.js", "dist/cli.js\u0000", ".", "dist/*.js"]) {
  test(`nichtkanonischer Report-Pfad wird abgelehnt: ${JSON.stringify(path)}`, async (t) => {
    const { root, paths } = await allowlistedFixture(t);
    const result = verify(root, report([...paths, path]));
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /invalid package path/);
  });
}

test("doppelte und nicht textuelle Report-Pfade werden abgelehnt", async (t) => {
  const { root, paths } = await allowlistedFixture(t);
  const duplicate = verify(root, report([...paths, paths[0]!]));
  assert.notEqual(duplicate.status, 0);
  assert.match(duplicate.stderr, /duplicate tarball path/);
  const malformed = verify(root, [{ name: "@tomtastisch/agent-governance", files: [null] }]);
  assert.notEqual(malformed.status, 0);
  assert.match(malformed.stderr, /invalid package path/);
});

for (const field of ["files", "bin", "exports"] as const) {
  test(`unsichere deklarierte ${field}-Pfade werden abgelehnt`, async (t) => {
    const { root, paths } = await allowlistedFixture(t);
    const metadata = JSON.parse(await readFile(join(root, "package.json"), "utf8"));
    if (field === "files") metadata.files.push("../outside");
    else metadata[field].extra = "../outside";
    await writeFile(join(root, "package.json"), JSON.stringify(metadata));
    const result = verify(root, report(paths));
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /invalid package path/);
  });
}

for (const directory of [false, true]) {
  test(`Symlink als ${directory ? "Verzeichnis" : "Datei"} wird abgelehnt`, async (t) => {
    const { root, paths } = await allowlistedFixture(t);
    if (directory) {
      await rename(join(root, "dist"), join(root, "actual-dist"));
      await symlink(join(root, "actual-dist"), join(root, "dist"));
    } else {
      await rm(join(root, "dist/cli.js"));
      await symlink(join(root, "README.md"), join(root, "dist/cli.js"));
    }
    const result = verify(root, report(paths));
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /unsafe package entry/);
  });
}

for (const [content, diagnostic] of [
  ["-----BEGIN PRIVATE KEY-----", /potential secret material/],
  ["PreToolUse", /forbidden harness-specific runtime content/],
] as const) {
  test(`bestehender Inhaltsfilter bleibt wirksam: ${diagnostic.source}`, async (t) => {
    const { root, paths } = await allowlistedFixture(t);
    await writeFile(join(root, "dist/cli.js"), content);
    const result = verify(root, report(paths));
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, diagnostic);
  });
}

for (const path of ["tests/runtime.js", "tools/runtime.js", "integrations/runtime.js", "dist/hooks.js"]) {
  test(`Deklaration autorisiert keinen verbotenen Runtime-Pfad: ${path}`, async (t) => {
    const { root, paths } = await allowlistedFixture(t);
    const metadata = JSON.parse(await readFile(join(root, "package.json"), "utf8"));
    metadata.files.push(path);
    await writeFile(join(root, "package.json"), JSON.stringify(metadata));
    await addFixturePath(root, paths, path);
    const result = verify(root, report(paths));
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /forbidden runtime path/);
  });
}

test("die native Plattformmatrix bleibt verpflichtend", async (t) => {
  const { root, paths } = await allowlistedFixture(t);
  const run = () => spawnSync(process.execPath, [join(import.meta.dirname, "../../tools/verify-pack.mjs")], {
    cwd: root, input: JSON.stringify(report(paths)), encoding: "utf8",
    env: { ...process.env, REQUIRE_ALL_NATIVE_PREBUILDS: "1" },
  });
  const missing = run();
  assert.notEqual(missing.status, 0);
  assert.match(missing.stderr, /missing native tarball path/);
  for (const platform of ["darwin-arm64", "darwin-x64", "linux-arm64", "linux-x64"]) {
    const path = `prebuilds/${platform}/agent_governance_fs.node`;
    if (!paths.includes(path)) await addFixturePath(root, paths, path);
  }
  const accepted = run();
  assert.equal(accepted.status, 0, accepted.stderr);
  await addFixturePath(root, paths, "prebuilds/unsupported-x64/agent_governance_fs.node");
  const unsupported = run();
  assert.notEqual(unsupported.status, 0);
  assert.match(unsupported.stderr, /unexpected native tarball path/);
});

for (const field of ["bin", "exports"] as const) {
  test(`deklarierte ${field}-Ziele können private lokale Regeln nicht veröffentlichen`, async (t) => {
    const { root, paths } = await allowlistedFixture(t);
    const privatePath = "bundle/agent-governance/local/user-rules.md";
    await addFixturePath(root, paths, privatePath);
    const metadata = JSON.parse(await readFile(join(root, "package.json"), "utf8"));
    metadata[field].extra = `./${privatePath}`;
    await writeFile(join(root, "package.json"), JSON.stringify(metadata));
    const result = verify(root, report(paths));
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /unlisted bundle target/);
  });
}
