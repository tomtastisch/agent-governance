import assert from "node:assert/strict";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";

test("pack verifier accepts the npm 12 package-keyed JSON report", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "agent-governance-pack-report-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const paths = [
    "CHANGELOG.md",
    "INSTALL.md",
    "LICENSE",
    "README.md",
    "VERSION",
    "package.json",
    "release.files.sha256",
    "bundle/GOVERNANCE.md",
    "bundle/agent-governance/manifest.toml",
    "dist/cli.js",
    `prebuilds/${process.platform}-${process.arch}/agent_governance_fs.node`,
  ];
  for (const path of paths) {
    await mkdir(join(root, path, ".."), { recursive: true });
    await writeFile(join(root, path), path === "package.json" ? "{}\n" : "fixture\n");
  }
  const report = { "@tomtastisch/agent-governance": { name: "@tomtastisch/agent-governance", files: paths.map((path) => ({ path })) } };
  const result = spawnSync(process.execPath, [join(import.meta.dirname, "../../tools/verify-pack.mjs")], {
    cwd: root,
    input: JSON.stringify(report),
    encoding: "utf8",
  });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /11 tarball entries are generic and allowlisted/);
});

test("pack verifier rejects a package-key mismatch", () => {
  const report = { "@foreign/package": { name: "@tomtastisch/agent-governance", files: [] } };
  const result = spawnSync(process.execPath, [join(import.meta.dirname, "../../tools/verify-pack.mjs")], {
    input: JSON.stringify(report),
    encoding: "utf8",
  });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /unexpected schema/);
});
