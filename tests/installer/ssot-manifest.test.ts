import assert from "node:assert/strict";
import { cp, mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { loadSsotIndex, parseSsotManifestText, SSOT_DOMAIN_IDS } from "../../src/ssot-manifest.ts";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const GOVERNANCE_ROOT = join(ROOT, "bundle", "agent-governance");

const VALID = `schema_version = 1

[domains.routing]
triggers = "routing/triggers.toml"
policy_tags = "routing/policy-tags.toml"
scopes = "routing/scopes.toml"
tools = "routing/tools.toml"

[domains.commands]
commands = "commands/commands.toml"

[domains.discovery]
discovery_signals = "discovery/discovery-signals.toml"
`;

test("ssot manifest accepts exactly the three registered domains", () => {
  const index = parseSsotManifestText(VALID);
  assert.equal(index.schemaVersion, 1);
  assert.deepEqual(Object.keys(index.domains).sort(), ["commands", "discovery", "routing"]);
  assert.equal(index.domains.routing.triggers, "routing/triggers.toml");
  assert.equal(index.domains.commands.commands, "commands/commands.toml");
  assert.equal(index.domains.discovery.discovery_signals, "discovery/discovery-signals.toml");
});

const rejections: ReadonlyArray<[string, string, RegExp]> = [
  ["an unknown domain", VALID.replace('[domains.commands]\ncommands = "commands/commands.toml"\n', '[domains.future]\nplaceholder = "future/placeholder.toml"\n'), /domains|unknown/i],
  ["a missing domain", VALID.replace('[domains.commands]\ncommands = "commands/commands.toml"\n', ""), /domains|missing|unknown/i],
  ["an unknown top-level field", VALID.replace("schema_version = 1\n", 'schema_version = 1\nunexpected = "shadow"\n'), /missing or unknown fields/i],
  ["a wrong schema version", VALID.replace("schema_version = 1", "schema_version = 2"), /schema is invalid/i],
  ["a duplicate catalog ID across domains", VALID.replace('discovery_signals = "discovery/discovery-signals.toml"', 'commands = "discovery/discovery-signals.toml"'), /duplicate catalog ID/i],
  ["a duplicate authority path", VALID.replace('discovery_signals = "discovery/discovery-signals.toml"', 'discovery_signals = "routing/triggers.toml"'), /duplicate authority path/i],
  ["a traversal path", VALID.replace('triggers = "routing/triggers.toml"', 'triggers = "../triggers.toml"'), /invalid manifest path/i],
  ["an absolute path", VALID.replace('triggers = "routing/triggers.toml"', 'triggers = "/abs/triggers.toml"'), /invalid manifest path/i],
  ["a non-toml file type", VALID.replace('triggers = "routing/triggers.toml"', 'triggers = "routing/triggers.txt"'), /invalid format/i],
  ["an invalid catalog ID", VALID.replace('tools = "routing/tools.toml"', 'Invalid-ID = "routing/tools.toml"'), /unsupported TOML syntax|invalid catalog ID/i],
  ["an empty domain", VALID.replace('commands = "commands/commands.toml"', ""), /empty/i],
];

for (const [label, text, pattern] of rejections) {
  test(`ssot manifest fails closed on ${label}`, () => {
    assert.throws(() => parseSsotManifestText(text), pattern);
  });
}

test("ssot resolution is deterministic and independent of directory enumeration", () => {
  const first = loadSsotIndex();
  const second = loadSsotIndex();
  assert.deepEqual(first.index, second.index);
  for (const domain of SSOT_DOMAIN_IDS) {
    for (const catalogId of Object.keys(first.index.domains[domain])) {
      assert.equal(first.catalogFile(domain, catalogId), second.catalogFile(domain, catalogId));
    }
  }
});

test("the canonical ssot tree registers only the real domains with no legacy or future placeholders", async () => {
  const ssotRoot = join(GOVERNANCE_ROOT, "ssot");
  const entries = (await readdir(ssotRoot, { withFileTypes: true })).map((entry) => entry.name).sort();
  assert.deepEqual(entries, ["commands", "discovery", "manifest.toml", "routing"]);
  const legacyCatalogRoot = join(GOVERNANCE_ROOT, "catalogs");
  await assert.rejects(readdir(legacyCatalogRoot), /ENOENT/);
  const rootManifest = await readFile(join(GOVERNANCE_ROOT, "manifest.toml"), "utf8");
  assert.doesNotMatch(rootManifest, /\[catalogs\]/);
  assert.match(rootManifest, /ssot = "ssot\/manifest\.toml"/);
});

test("runtime ssot resolution rejects a non-canonical ssot manifest path", async () => {
  const root = await mkdtemp(join(tmpdir(), "agent-governance-ssot-canonical-"));
  try {
    const bundleRoot = join(root, "bundle", "agent-governance");
    await cp(GOVERNANCE_ROOT, bundleRoot, { recursive: true });
    const manifestPath = join(bundleRoot, "manifest.toml");
    await writeFile(manifestPath, (await readFile(manifestPath, "utf8")).replace('ssot = "ssot/manifest.toml"', 'ssot = "elsewhere/manifest.toml"'));
    assert.throws(() => loadSsotIndex(root), /canonical/i);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
