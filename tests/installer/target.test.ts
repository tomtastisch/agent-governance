import assert from "node:assert/strict";
import { mkdir, symlink, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import test from "node:test";

import { inspectTarget } from "../../src/target.ts";
import { createTestRoot } from "../fixtures/installer/workspace.ts";

test("target inspection accepts only explicit canonical roots and relative Markdown entries", async () => {
  const root = await createTestRoot("agent-governance-target-");
  const installation = join(root, "installation");
  await mkdir(join(root, "nested"));
  const result = await inspectTarget(root, "nested/AGENTS.md", installation);
  assert.equal(result.entryPath, join(root, "nested", "AGENTS.md"));
  assert.equal(result.entryExists, false);
  assert.equal(result.installationRoot, installation);
});

test("target inspection rejects relative roots, traversal, absolute entries, and non-Markdown files", async () => {
  const root = await createTestRoot("agent-governance-target-");
  for (const [target, entry, installation, pattern] of [
    ["relative", "AGENTS.md", join(root, "install"), /absolute/],
    [root, "../AGENTS.md", join(root, "install"), /relative|escape|traversal/],
    [root, join(root, "AGENTS.md"), join(root, "install"), /relative/],
    [root, "AGENTS.txt", join(root, "install"), /Markdown/],
    [root, "AGENTS.md", "relative", /absolute/],
  ] as const) await assert.rejects(inspectTarget(target, entry, installation), pattern);
});

test("target inspection rejects symlink roots, parents, entries, and unexpected entry types", async () => {
  const root = await createTestRoot("agent-governance-target-");
  const outside = await createTestRoot("agent-governance-outside-");
  const linkedRoot = join(dirname(root), `${root.split("/").at(-1)}-link`);
  await symlink(root, linkedRoot);
  await assert.rejects(inspectTarget(linkedRoot, "AGENTS.md", join(root, "install")), /symlink|canonical/);
  await symlink(outside, join(root, "linked"));
  await assert.rejects(inspectTarget(root, "linked/AGENTS.md", join(root, "install")), /symlink/);
  await symlink(join(outside, "AGENTS.md"), join(root, "ENTRY.md"));
  await assert.rejects(inspectTarget(root, "ENTRY.md", join(root, "install")), /symlink/);
  await mkdir(join(root, "DIRECTORY.md"));
  await assert.rejects(inspectTarget(root, "DIRECTORY.md", join(root, "install")), /regular file/);
  await writeFile(join(root, "SAFE.md"), "user\n");
  assert.equal((await inspectTarget(root, "SAFE.md", join(root, "install"))).entryExists, true);
});

test("target inspection rejects missing target roots and symlinked installation ancestors", async () => {
  const root = await createTestRoot("agent-governance-target-");
  const outside = await createTestRoot("agent-governance-outside-");
  await assert.rejects(inspectTarget(join(root, "missing"), "AGENTS.md", join(root, "install")), /missing/);
  await assert.rejects(inspectTarget(root, "missing/AGENTS.md", join(root, "install")), /parent|missing/);
  await symlink(outside, join(root, "install-link"));
  await assert.rejects(inspectTarget(root, "AGENTS.md", join(root, "install-link", "governance")), /symlink/);
});
