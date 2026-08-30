import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { loadDiscoveryCatalog } from "../../src/discovery/catalog.ts";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));

async function catalogFixture(
  mutate: (manifest: string, catalog: string) => [string, string],
): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "agent-governance-discovery-catalog-"));
  const manifestPath = join(root, "bundle", "agent-governance", "manifest.toml");
  const catalogPath = join(
    root,
    "bundle",
    "agent-governance",
    "catalogs",
    "discovery-signals.toml",
  );
  await mkdir(dirname(catalogPath), { recursive: true });
  const sourceManifest = await readFile(
    join(ROOT, "bundle", "agent-governance", "manifest.toml"),
    "utf8",
  );
  const sourceCatalog = await readFile(
    join(ROOT, "bundle", "agent-governance", "catalogs", "discovery-signals.toml"),
    "utf8",
  );
  const [manifest, catalog] = mutate(sourceManifest, sourceCatalog);
  await writeFile(manifestPath, manifest);
  await writeFile(catalogPath, catalog);
  return root;
}

test("discovery catalog exposes generic families, classes, confidence gates, and positive limits", () => {
  const catalog = loadDiscoveryCatalog();

  assert.deepEqual(Object.keys(catalog.candidateClasses).sort(), ["app_bundle", "directory"]);
  assert.deepEqual(Object.keys(catalog.evidenceFamilies).sort(), [
    "ai_metadata",
    "document",
    "package_metadata",
    "runtime",
    "state",
    "tooling",
  ]);
  assert.equal(catalog.confidence.highRequiresRuntime, true);
  assert.equal(catalog.confidence.highMinimumFamilies >= 2, true);
  assert.equal(catalog.confidence.highMinimumIndependentSources >= 2, true);
  assert.equal(catalog.confidence.uncertainMinimumScore < catalog.confidence.highMinimumScore, true);
  assert.equal(Object.values(catalog.limits).every((limit) => Number.isInteger(limit) && limit > 0), true);
  assert.equal(catalog.signals.length > 0, true);
  assert.equal(new Set(catalog.signals.map(({ id }) => id)).size, catalog.signals.length);

  const serialized = JSON.stringify(catalog).toLowerCase();
  for (const forbidden of ["anthropic", "claude", "codex", "copilot", "cursor", "gemini", "ollama", "openai"]) {
    assert.equal(serialized.includes(forbidden), false, forbidden);
  }
});

test("discovery catalog rejects unknown fields, invalid limits, duplicate IDs, and unknown references", async () => {
  const mutations: ReadonlyArray<[
    string,
    (manifest: string, catalog: string) => [string, string],
    RegExp,
  ]> = [
    [
      "unknown field",
      (manifest, catalog) => [manifest, catalog.replace("max_depth = 4", "max_depth = 4\nunexpected = true")],
      /unknown field/i,
    ],
    [
      "zero limit",
      (manifest, catalog) => [manifest, catalog.replace("max_files = 256", "max_files = 0")],
      /max_files|positive/i,
    ],
    [
      "unknown family",
      (manifest, catalog) => [manifest, catalog.replace('family = "runtime"', 'family = "unknown"')],
      /family/i,
    ],
    [
      "duplicate signal ID",
      (manifest, catalog) => [manifest, catalog.replace('id = "state_continuity"', 'id = "runtime_endpoint"')],
      /duplicate/i,
    ],
    [
      "unknown source kind",
      (manifest, catalog) => [manifest, catalog.replace('source_kinds = ["json", "toml", "plist"]', 'source_kinds = ["network"]')],
      /source/i,
    ],
    [
      "manifest traversal",
      (manifest, catalog) => [
        manifest.replace(
          'discovery_signals = "catalogs/discovery-signals.toml"',
          'discovery_signals = "../discovery-signals.toml"',
        ),
        catalog,
      ],
      /path|traversal/i,
    ],
  ];

  for (const [name, mutate, pattern] of mutations) {
    const root = await catalogFixture(mutate);
    try {
      assert.throws(() => loadDiscoveryCatalog(root), pattern, name);
    } finally {
      await rm(root, { recursive: true, force: true });
    }
  }
});
