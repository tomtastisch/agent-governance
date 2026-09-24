import assert from "node:assert/strict";
import { chmod, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { createAgntnHarnessesAdapter } from "../../src/init/harnesses.ts";

test("the adapter reports installed harnesses by id and display name without executing their CLI", async () => {
  const root = await mkdtemp(join(tmpdir(), "agent-governance-harness-"));
  const bin = join(root, "bin");
  const executed = join(root, "executed.log");
  await mkdir(bin);
  const fake = join(bin, "gemini");
  await writeFile(fake, `#!/bin/sh\necho executed >> '${executed}'\nexit 1\n`, "utf8");
  await chmod(fake, 0o755);
  const previousPath = process.env.PATH;
  process.env.PATH = `${bin}:${previousPath}`;
  try {
    const harnesses = await createAgntnHarnessesAdapter().discover();
    const gemini = harnesses.find((harness) => harness.id === "gemini");
    assert.ok(gemini, "the fake gemini binary must be detected via PATH");
    assert.equal(gemini.displayName, "Google Gemini CLI");
    for (const harness of harnesses) {
      assert.equal(typeof harness.id, "string");
      assert.equal(typeof harness.displayName, "string");
    }
    await assert.rejects(readFile(executed), /ENOENT/);
  } finally {
    process.env.PATH = previousPath;
    await rm(root, { recursive: true, force: true });
  }
});
