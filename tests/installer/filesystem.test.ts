import assert from "node:assert/strict";
import { mkdir, realpath, symlink, writeFile } from "node:fs/promises";
import { join } from "node:path";
import test from "node:test";

import { validateAllowedPath } from "../../src/filesystem.ts";
import { createTestRoot } from "../fixtures/installer/workspace.ts";

async function root(): Promise<string> {
  return createTestRoot("agent-governance-fs-");
}

test("installer test roots are canonical before production path validation", async () => {
  const fixtureRoot = await root();
  assert.equal(fixtureRoot, await realpath(fixtureRoot));
});

test("filesystem rejects relative paths and root escape", async () => {
  const allowed = await root();
  await assert.rejects(validateAllowedPath("relative", allowed, "missing"), /absolute/);
  await assert.rejects(
    validateAllowedPath(join(allowed, "..", "outside"), allowed, "missing"),
    /outside allowed root/,
  );
});

test("filesystem rejects symlink target and intermediate component", async () => {
  const allowed = await root();
  const outside = await root();
  await writeFile(join(outside, "file"), "outside");
  await symlink(join(outside, "file"), join(allowed, "target"));
  await assert.rejects(validateAllowedPath(join(allowed, "target"), allowed, "file"), /symlink/);

  await symlink(outside, join(allowed, "middle"));
  await assert.rejects(
    validateAllowedPath(join(allowed, "middle", "new"), allowed, "missing"),
    /symlink/,
  );
});

test("filesystem rejects unexpected existing type", async () => {
  const allowed = await root();
  await mkdir(join(allowed, "directory"));
  await assert.rejects(validateAllowedPath(join(allowed, "directory"), allowed, "file"), /regular file/);
});
