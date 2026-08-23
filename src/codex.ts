import { lstat, readFile } from "node:fs/promises";
import { join } from "node:path";

import type { InstallState } from "./contracts.ts";

const LEGACY_IMPORTS = [
  "@~/agent-governance/adapters/AGENTS.md",
  "@~/agent-governance/adapters/codex.md",
] as const;

export interface CodexInventory {
  readonly harness: "codex";
  readonly home: string;
  readonly installRoot: string;
  readonly agents?: string;
  readonly overridePresent: boolean;
  readonly hooksPresent: boolean;
  readonly configPresent: boolean;
  readonly manifestPresent: boolean;
  readonly legacyImport: boolean;
  readonly bindingCurrent: boolean;
  readonly hookCurrent: boolean;
}

async function optionalFile(path: string): Promise<string | undefined> {
  try {
    const stat = await lstat(path);
    if (stat.isSymbolicLink() || !stat.isFile()) throw new Error(`unsafe Codex file: ${path}`);
    if (stat.size > 1024 * 1024) throw new Error(`Codex file exceeds size limit: ${path}`);
    return await readFile(path, "utf8");
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return undefined;
    throw error;
  }
}

export async function inspectCodex(home: string, installRoot: string): Promise<CodexInventory> {
  const [agents, override, hooks, config, manifest, governance] = await Promise.all([
    optionalFile(join(home, "AGENTS.md")),
    optionalFile(join(home, "AGENTS.override.md")),
    optionalFile(join(home, "hooks.json")),
    optionalFile(join(home, "config.toml")),
    optionalFile(join(installRoot, "bundle", "agent-governance", "manifest.toml")),
    optionalFile(join(installRoot, "bundle", "GOVERNANCE.md")),
  ]);
  let hookCurrent = false;
  if (hooks !== undefined) {
    try {
      const parsed: unknown = JSON.parse(hooks);
      const groups = (parsed as { hooks?: { PreToolUse?: unknown } }).hooks?.PreToolUse;
      hookCurrent = Array.isArray(groups) && groups.filter(
        (group) => (group as { matcher?: unknown }).matcher === "agent_governance__execute",
      ).length === 1;
    } catch {
      hookCurrent = false;
    }
  }
  return {
    harness: "codex",
    home,
    installRoot,
    ...(agents === undefined ? {} : { agents }),
    overridePresent: override !== undefined,
    hooksPresent: hooks !== undefined,
    configPresent: config !== undefined,
    manifestPresent: manifest !== undefined,
    legacyImport: agents !== undefined && LEGACY_IMPORTS.some((item) => agents.includes(item)),
    bindingCurrent: agents !== undefined && governance !== undefined && agents === governance,
    hookCurrent,
  };
}

export function classifyCodex(inventory: CodexInventory | { readonly harness: string }): InstallState {
  if (inventory.harness !== "codex") throw new Error(`unsupported harness: ${inventory.harness}`);
  const codex = inventory as CodexInventory;
  if (codex.overridePresent) return "UNKNOWN";
  if (codex.legacyImport && codex.manifestPresent) return "UNKNOWN";
  if (codex.legacyImport) return "LEGACY";
  if (codex.manifestPresent && codex.bindingCurrent && codex.hookCurrent) return "CURRENT";
  if (codex.manifestPresent || codex.agents !== undefined || codex.hooksPresent || codex.configPresent) {
    return "UNKNOWN";
  }
  return "FRESH";
}
