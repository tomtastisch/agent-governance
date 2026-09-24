import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative, resolve, sep } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const srcRoot = join(repositoryRoot, "src");

function moduleKey(absolute: string): string {
  return relative(srcRoot, absolute).split(sep).join("/").replace(/\.ts$/, "");
}

function listTsFiles(directory: string): string[] {
  const result: string[] = [];
  for (const entry of readdirSync(directory)) {
    const absolute = join(directory, entry);
    if (statSync(absolute).isDirectory()) result.push(...listTsFiles(absolute));
    else if (absolute.endsWith(".ts")) result.push(absolute);
  }
  return result;
}

const IMPORT_RE = /from\s+["'](\.\.?\/[^"']+)["']/g;

function directImports(absolute: string): Set<string> {
  const source = readFileSync(absolute, "utf8");
  const imports = new Set<string>();
  for (const match of source.matchAll(IMPORT_RE)) {
    const specifier = match[1]!;
    imports.add(moduleKey(resolve(dirname(absolute), specifier)));
  }
  return imports;
}

function buildGraph(): Map<string, Set<string>> {
  const files = listTsFiles(srcRoot);
  const graph = new Map<string, Set<string>>();
  for (const file of files) graph.set(moduleKey(file), directImports(file));
  return graph;
}

function isInstallerModule(key: string): boolean {
  return key === "transaction" || key.startsWith("installer/");
}

const INSTALLER_FILES = listTsFiles(srcRoot).filter((file) => isInstallerModule(moduleKey(file)));

test("the installer transaction domain declares a single orchestrating entry point", () => {
  const transactionSources = INSTALLER_FILES.filter((file) => {
    const source = readFileSync(file, "utf8");
    return /export\s+(?:default\s+)?class\s+InstallerTransaction\b/.test(source);
  });
  assert.deepEqual(transactionSources.map((file) => moduleKey(file)), ["transaction"]);
});

test("the installer domain keeps its dependency graph free of cycles", () => {
  const graph = buildGraph();
  const nodes = new Set(INSTALLER_FILES.map((file) => moduleKey(file)));
  const visiting = new Set<string>();
  const visited = new Set<string>();
  const stack: string[] = [];
  const visit = (key: string): void => {
    if (visited.has(key)) return;
    assert.ok(!visiting.has(key), `import cycle: ${[...stack, key].join(" -> ")}`);
    visiting.add(key);
    stack.push(key);
    for (const target of graph.get(key) ?? []) {
      if (nodes.has(target)) visit(target);
    }
    stack.pop();
    visiting.delete(key);
    visited.add(key);
  };
  for (const node of nodes) visit(node);
});

test("no generic utility bucket exists inside the installer domain", () => {
  const forbidden = ["utils", "helpers", "common", "misc", "shared", "transaction-utils"];
  const offenders = INSTALLER_FILES
    .map((file) => moduleKey(file))
    .filter((key) => forbidden.includes(key.split("/").at(-1) ?? ""));
  assert.deepEqual(offenders, []);
});

test("lower-level primitives never import the installer transaction domain", () => {
  const primitives = new Set([
    "contracts",
    "errors",
    "filesystem",
    "native-filesystem",
    "managed-block",
    "release",
    "signals",
    "planner",
    "target",
    "closed-toml",
    "governance-contract",
  ]);
  const graph = buildGraph();
  const offenders: string[] = [];
  for (const [source, targets] of graph) {
    if (!primitives.has(source)) continue;
    for (const target of targets) {
      if (isInstallerModule(target)) offenders.push(`${source} -> ${target}`);
    }
  }
  assert.deepEqual(offenders.sort(), []);
});

test("installer components never import the CLI or the orchestrating transaction", () => {
  const graph = buildGraph();
  const offenders: string[] = [];
  for (const [source, targets] of graph) {
    if (!source.startsWith("installer/")) continue;
    for (const target of targets) {
      if (target === "transaction" || target === "cli" || target === "public-commands") {
        offenders.push(`${source} -> ${target}`);
      }
    }
  }
  assert.deepEqual(offenders.sort(), []);
});

test("the orchestrating transaction never imports the CLI layer", () => {
  const graph = buildGraph();
  const targets = graph.get("transaction") ?? new Set<string>();
  for (const forbidden of ["cli", "public-commands", "command-catalog"]) {
    assert.ok(!targets.has(forbidden), `transaction imports ${forbidden}`);
  }
});
