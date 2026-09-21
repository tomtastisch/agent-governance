import assert from "node:assert/strict";
import { cp, mkdtemp, readFile, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { loadCommandCatalog } from "../../src/command-catalog.ts";
import { COMMANDS } from "../../src/contracts.ts";
import {
  PUBLIC_COMMAND_HANDLERS,
  renderCommandHelp,
  renderGlobalHelp,
} from "../../src/public-commands.ts";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const EXPECTED = {
  inspect: { path: ["inspect"], capability: "transaction", effect: "read", orchestrates: false, interactive: false },
  plan: { path: ["plan"], capability: "transaction", effect: "read", orchestrates: false, interactive: false },
  install: { path: ["install"], capability: "transaction", effect: "write", orchestrates: false, interactive: false },
  verify: { path: ["verify"], capability: "transaction", effect: "read", orchestrates: false, interactive: false },
  status: { path: ["status"], capability: "transaction", effect: "read", orchestrates: false, interactive: false },
  update: { path: ["update"], capability: "transaction", effect: "write", orchestrates: false, interactive: false },
  uninstall: { path: ["uninstall"], capability: "transaction", effect: "write", orchestrates: false, interactive: false },
  rollback: { path: ["rollback"], capability: "transaction", effect: "write", orchestrates: false, interactive: false },
  init: { path: ["init"], capability: "orchestration", effect: "write", orchestrates: true, interactive: true },
} as const;

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

test("command catalog exposes exactly the nine public IDs, paths, and semantics", () => {
  const commands = loadCommandCatalog();
  assert.deepEqual(
    Object.fromEntries(commands.map(({ id, description: _description, ...definition }) => [id, definition])),
    EXPECTED,
  );
  assert.equal(commands.every(({ description }) => description.trim().length > 0), true);
  assert.deepEqual(COMMANDS, ["inspect", "plan", "install", "verify", "status", "update", "uninstall", "rollback"]);
  assert.equal(COMMANDS.includes("init" as never), false);
});

test("command catalog rejects unknown fields, wrong types, duplicate paths, and invalid semantics", async () => {
  const mutations: ReadonlyArray<[string, (manifest: string, catalog: string) => [string, string], RegExp]> = [
    ["unknown field", (manifest, catalog) => [manifest, catalog.replace("interactive = false", "interactive = false\nextra = true")], /unknown field/i],
    ["wrong type", (manifest, catalog) => [manifest, catalog.replace("interactive = false", 'interactive = "false"')], /interactive/i],
    ["duplicate path", (manifest, catalog) => [manifest, catalog.replace('path = ["plan"]', 'path = ["inspect"]')], /duplicate path/i],
    ["invalid effect", (manifest, catalog) => [manifest, catalog.replace('effect = "read"', 'effect = "write"')], /semantics/i],
    ["invalid init capability", (manifest, catalog) => [manifest, catalog.replace('capability = "orchestration"', 'capability = "transaction"')], /semantics/i],
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

test("public handler registry and help are derived from the command SSOT", () => {
  const commands = loadCommandCatalog();
  assert.deepEqual(Object.keys(PUBLIC_COMMAND_HANDLERS), commands.map(({ id }) => id));
  const globalHelp = renderGlobalHelp();
  for (const command of commands) {
    assert.match(globalHelp, new RegExp(`\\b${command.id}\\b`));
    assert.equal(globalHelp.includes(command.description), true, command.id);
    const commandHelp = renderCommandHelp(command.id);
    assert.equal(commandHelp.includes(command.description), true, command.id);
    assert.equal(commandHelp.includes(`agent-governance ${command.path.join(" ")}`), true, command.id);
  }
});

test("CLI reference options match rendered command help", async () => {
  const optionPattern = /(?:^|[^\w-])(--[a-z][a-z0-9-]*|-[A-Za-z0-9]+)(?![\w-])/g;
  const extractOptions = (text: string): string[] => [
    ...new Set([...text.matchAll(optionPattern)].map((match) => match[1]!)),
  ].sort();
  const renderedOptions = (id: Parameters<typeof renderCommandHelp>[0]): string[] => {
    const options = renderCommandHelp(id).split("\nOptions:\n", 2)[1];
    assert.notEqual(options, undefined, id);
    return extractOptions(options!);
  };

  const reference = await readFile(join(ROOT, "docs", "installer-cli-reference.md"), "utf8");
  const optionSection = reference.split("## Options- und Keyword-Referenz", 2)[1]?.split("\n## Exitverhalten", 1)[0];
  assert.notEqual(optionSection, undefined);
  const optionHeadings = [...optionSection!.matchAll(/^### (.+)$/gm)].map((match) => match[1]!);
  const documentedTransactionOptions = extractOptions(optionHeadings.join("\n"));

  const initSection = reference.split("### `init`", 2)[1]?.split("\n### `", 1)[0];
  assert.notEqual(initSection, undefined);
  assert.deepEqual(extractOptions(initSection!), renderedOptions("init"));

  const transactionCommands = loadCommandCatalog().filter(({ capability }) => capability === "transaction");
  assert.notEqual(transactionCommands.length, 0);
  for (const command of transactionCommands) {
    assert.deepEqual(renderedOptions(command.id), documentedTransactionOptions, command.id);
  }
});
