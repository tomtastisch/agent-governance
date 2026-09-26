import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { cp, lstat, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, relative, sep } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { validateGovernanceContract } from "../../src/governance-contract.ts";

/**
 * TypeScript-Seite des Cross-Language-Conformance-Gates (Issue #90).
 *
 * Der produktive Validator `validateGovernanceContract` muss das reale Bundle
 * akzeptieren und jede Mutation der gemeinsam mit der Python-Testreferenz geteilten
 * Mutation-Batterie (`tests/contracts/conformance-mutations.json`) ablehnen. Die
 * Python-Seite prüft dieselben Fixtures in `tests/test_conformance.py`.
 */

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const GOVERNANCE_ROOT = join(ROOT, "bundle", "agent-governance");
const MUTATIONS_FILE = join(ROOT, "tests", "contracts", "conformance-mutations.json");

interface Mutation {
  readonly id: string;
  readonly file: string;
  readonly find: string;
  readonly replace: string;
}

function loadMutations(): Mutation[] {
  const parsed: unknown = JSON.parse(readFileSync(MUTATIONS_FILE, "utf8"));
  if (typeof parsed !== "object" || parsed === null || !Array.isArray((parsed as { mutations?: unknown }).mutations)) {
    throw new Error("conformance mutation battery has an unexpected schema");
  }
  return (parsed as { mutations: Mutation[] }).mutations;
}

async function walk(directory: string): Promise<string[]> {
  const result: string[] = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const absolute = join(directory, entry.name);
    if (entry.isSymbolicLink()) throw new Error(`symlink is not allowed: ${absolute}`);
    if (entry.isDirectory()) result.push(...(await walk(absolute)));
    else if (entry.isFile()) result.push(absolute);
  }
  return result;
}

async function buildInventory(manifestRoot: string): Promise<Map<string, string>> {
  const inventory = new Map<string, string>();
  for (const file of await walk(manifestRoot)) {
    const content = await readFile(file);
    const rel = relative(manifestRoot, file).split(sep).join("/");
    inventory.set(`bundle/agent-governance/${rel}`, createHash("sha256").update(content).digest("hex"));
  }
  return inventory;
}

async function validateRoot(manifestRoot: string): Promise<void> {
  const inventory = await buildInventory(manifestRoot);
  const manifestText = await readFile(join(manifestRoot, "manifest.toml"), "utf8");
  await validateGovernanceContract(manifestRoot, manifestText, inventory);
}

test("the TypeScript validator accepts the real bundle", async () => {
  await validateRoot(GOVERNANCE_ROOT);
});

test("the TypeScript validator rejects every shared mutation", async (t) => {
  for (const mutation of loadMutations()) {
    await t.test(mutation.id, async () => {
      const temp = await mkdtemp(join(tmpdir(), "agent-governance-ts-conformance-"));
      try {
        const manifestRoot = join(temp, "agent-governance");
        await cp(GOVERNANCE_ROOT, manifestRoot, { recursive: true });
        const target = join(manifestRoot, mutation.file);
        const original = await readFile(target, "utf8");
        if (!original.includes(mutation.find)) throw new Error(`mutation anchor missing: ${mutation.file}: ${mutation.find}`);
        await writeFile(target, original.replace(mutation.find, mutation.replace), "utf8");
        await assert.rejects(() => validateRoot(manifestRoot), Error, mutation.id);
      } finally {
        await rm(temp, { recursive: true, force: true });
      }
    });
  }
});

test("the shared mutation battery is non-empty and has unique ids", () => {
  const mutations = loadMutations();
  assert.ok(mutations.length > 0);
  assert.equal(new Set(mutations.map((mutation) => mutation.id)).size, mutations.length);
});
