import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { basename, dirname, join } from "node:path";
import { spawnSync } from "node:child_process";
import test, { type TestContext } from "node:test";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";

import { BRANDING_ASSET_PATH, renderBranding } from "../../src/init/branding.ts";

test("terminal branding is a bounded PNG derived for runtime packaging", async () => {
  const bytes = await readFile(BRANDING_ASSET_PATH);
  assert.deepEqual([...bytes.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10]);
  assert.ok(bytes.readUInt32BE(16) <= 64);
  assert.ok(bytes.readUInt32BE(20) <= 64);
  assert.equal(basename(BRANDING_ASSET_PATH), "agent-governance-terminal.png");
});

test("branding uses a deterministic semantic text fallback", async () => {
  const output: string[] = [];
  await renderBranding({
    write: (value) => output.push(value),
    columns: 60,
    environment: { NO_COLOR: "1" },
  });
  assert.deepEqual(output, ["[AG] Agent Governance\n"]);
});

test("decorative renderer failure remains fail-open and continues with text", async () => {
  const output: string[] = [];
  await renderBranding({
    write: (value) => output.push(value),
    columns: 60,
    environment: {},
    renderImage: async () => { throw new Error("unsupported terminal protocol"); },
  });
  assert.deepEqual(output, ["[AG] Agent Governance\n"]);
});

test("an empty decorative render falls back to the semantic text brand", async () => {
  const output: string[] = [];
  await renderBranding({
    write: (value) => output.push(value),
    columns: 60,
    environment: { NO_COLOR: "1" },
    renderImage: async () => "",
  });
  assert.deepEqual(output, ["[AG] Agent Governance\n"]);
});

async function packageFixture(t: TestContext): Promise<{ root: string; paths: string[] }> {
  const root = await mkdtemp(join(tmpdir(), "agent-governance-brand-pack-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const paths = [
    "CHANGELOG.md", "LICENSE", "README.md", "VERSION", "package.json", "release.files.sha256",
    "bundle/GOVERNANCE.md", "bundle/agent-governance/manifest.toml", "docs/installer-cli-reference.md",
    "dist/cli.js", `prebuilds/${process.platform}-${process.arch}/agent_governance_fs.node`,
    "assets/branding/agent-governance-terminal.png",
  ];
  for (const path of paths) {
    await mkdir(dirname(join(root, path)), { recursive: true });
    await writeFile(join(root, path), path === "package.json" ? "{}\n" : "fixture\n");
  }
  return { root, paths };
}

function verifyPack(root: string, paths: readonly string[]) {
  return spawnSync(process.execPath, [join(import.meta.dirname, "../../tools/verify-pack.mjs")], {
    cwd: root,
    input: JSON.stringify([{ name: "@tomtastisch/agent-governance", files: paths.map((path) => ({ path })) }]),
    encoding: "utf8",
  });
}

test("pack verifier requires exactly the terminal branding asset path", async (t) => {
  const { root, paths } = await packageFixture(t);
  const accepted = verifyPack(root, paths);
  assert.equal(accepted.status, 0, accepted.stderr);

  const missing = verifyPack(root, paths.filter((path) => path !== "assets/branding/agent-governance-terminal.png"));
  assert.notEqual(missing.status, 0);
  assert.match(missing.stderr, /missing tarball path: assets\/branding\/agent-governance-terminal\.png/u);
});
