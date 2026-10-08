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

test("alle Upstream-Harnesses und alternativen Binärnamen bleiben rein passiv erkennbar", async () => {
  const { HARNESS_DISCOVERY } = await import("../../src/init/harness-discovery.generated.ts");
  const { execFileSync } = await import("node:child_process");
  const { symlink } = await import("node:fs/promises");
  const which = execFileSync("which", ["which"], { encoding: "utf8" }).trim();
  const root = await mkdtemp(join(tmpdir(), "governance-all-harnesses-"));
  const executed = join(root, "executed");
  const previousPath = process.env.PATH;
  try {
    for (const alternative of [false, true]) {
      const bin = join(root, alternative ? "alternatives" : "primary");
      await mkdir(bin);
      await symlink(which, join(bin, "which"));
      process.env.PATH = bin;
      assert.deepEqual(await createAgntnHarnessesAdapter().discover(), []);
      for (const harness of HARNESS_DISCOVERY) {
        const binary = alternative ? harness.binaries.at(-1)! : harness.binaries[0];
        const path = join(bin, binary);
        await writeFile(path, `#!/bin/sh\necho executed >> '${executed}'\nexit 1\n`, { mode: 0o755 });
      }
      assert.deepEqual(await createAgntnHarnessesAdapter().discover(), HARNESS_DISCOVERY.map(({ id, displayName }) => ({ id, displayName })));
      await assert.rejects(readFile(executed), /ENOENT/u);
    }
  } finally {
    if (previousPath === undefined) delete process.env.PATH;
    else process.env.PATH = previousPath;
    await rm(root, { recursive: true, force: true });
  }
});
