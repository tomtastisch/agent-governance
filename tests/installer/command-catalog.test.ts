import assert from "node:assert/strict";
import { cp, mkdtemp, readFile, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { loadCommandCatalog } from "../../src/command-catalog.ts";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));

async function catalogFixture(mutate?: (ssotManifest: string, catalog: string) => [string, string]): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "agent-governance-command-catalog-"));
  const bundleRoot = join(root, "bundle", "agent-governance");
  await cp(join(ROOT, "bundle", "agent-governance"), bundleRoot, { recursive: true });
  const ssotManifestPath = join(bundleRoot, "ssot", "manifest.toml");
  const catalogPath = join(bundleRoot, "ssot", "commands", "commands.toml");
  let ssotManifest = await readFile(ssotManifestPath, "utf8");
  let catalog = await readFile(catalogPath, "utf8");
  if (mutate !== undefined) [ssotManifest, catalog] = mutate(ssotManifest, catalog);
  await writeFile(ssotManifestPath, ssotManifest);
  await writeFile(catalogPath, catalog);
  return root;
}

test("command catalog loads the public commands from the SSOT with unique IDs", () => {
  const commands = loadCommandCatalog();
  assert.ok(commands.length > 0);
  assert.equal(new Set(commands.map(({ id }) => id)).size, commands.length);
});

test("command catalog rejects unknown fields, wrong types, duplicate paths, and invalid vocabulary", async () => {
  const mutations: ReadonlyArray<[string, (manifest: string, catalog: string) => [string, string], RegExp]> = [
    ["unknown field", (manifest, catalog) => [manifest, catalog.replace("interactive = false", "interactive = false\nextra = true")], /unknown field/i],
    ["wrong type", (manifest, catalog) => [manifest, catalog.replace("interactive = false", 'interactive = "false"')], /interactive/i],
    ["duplicate path", (manifest, catalog) => [manifest, catalog.replace('path = ["plan"]', 'path = ["inspect"]')], /duplicate path/i],
    ["invalid effect", (manifest, catalog) => [manifest, catalog.replace('effect = "read"', 'effect = "delete"')], /effect/i],
    ["invalid capability", (manifest, catalog) => [manifest, catalog.replace('capability = "orchestration"', 'capability = "execute"')], /capability/i],
    ["invalid id", (manifest, catalog) => [manifest, catalog.replace('id = "inspect"', 'id = "Inspect"')], /id is invalid/i],
    ["manifest traversal", (manifest, catalog) => [manifest.replace('commands = "commands/commands.toml"', 'commands = "../commands.toml"'), catalog], /path|traversal/i],
  ];
  for (const [name, mutate, pattern] of mutations) {
    const root = await catalogFixture(mutate);
    try {
      assert.throws(() => loadCommandCatalog(root), pattern, name);
    } finally {
      await rm(root, { recursive: true, force: true });
    }
  }
});

test("command manifest rejects symlinked intermediate path components", async () => {
  const external = await catalogFixture();
  const root = await mkdtemp(join(tmpdir(), "agent-governance-command-manifest-link-"));
  try {
    await symlink(join(external, "bundle"), join(root, "bundle"), "dir");
    assert.throws(() => loadCommandCatalog(root), /symlink/i);
  } finally {
    await rm(root, { recursive: true, force: true });
    await rm(external, { recursive: true, force: true });
  }
});
