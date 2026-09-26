#!/usr/bin/env node
/**
 * Cross-Language-Conformance-Probe (Issue #90).
 *
 * Validiert einen übergebenen Manifest-Root (bundle/agent-governance) mit dem
 * produktiven TypeScript-Validator `validateGovernanceContract`. Der Probe baut
 * das Release-Inventar deterministisch aus den tatsächlichen Dateien auf und
 * antwortet ausschließlich über den Exit-Code:
 *
 *   0 — Valid (Contract akzeptiert das Bundle)
 *   1 — Invalid (Contract lehnt das Bundle ab)
 *   2 — Aufruffehler
 *
 * Der Probe ist keine fachliche Authority und trifft keine Autorisierungs- oder
 * Deliverable-Entscheidung; er dient dem Cross-Language-Conformance-Gate.
 */
import { createHash } from "node:crypto";
import { lstat, readFile, readdir } from "node:fs/promises";
import { join, relative, sep } from "node:path";
import { validateGovernanceContract } from "../../src/governance-contract.ts";

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

async function main(): Promise<number> {
  const manifestRoot = process.argv[2];
  if (!manifestRoot) {
    process.stderr.write("usage: conformance_probe <manifestRoot>\n");
    return 2;
  }
  try {
    const files = await walk(manifestRoot);
    const inventory = new Map<string, string>();
    for (const file of files) {
      const content = await readFile(file);
      const rel = relative(manifestRoot, file).split(sep).join("/");
      inventory.set(`bundle/agent-governance/${rel}`, createHash("sha256").update(content).digest("hex"));
    }
    const manifestText = await readFile(join(manifestRoot, "manifest.toml"), "utf8");
    await validateGovernanceContract(manifestRoot, manifestText, inventory);
    return 0;
  } catch (error) {
    process.stderr.write(error instanceof Error ? error.message : String(error));
    return 1;
  }
}

process.exitCode = await main();
