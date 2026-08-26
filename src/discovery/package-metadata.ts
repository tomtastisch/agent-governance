import type { DiscoveryLimits, EvidenceRecord } from "./types.ts";
import {
  collectStructureKeys,
  evidenceForStructure,
  readBoundedTextFile,
} from "./structured.ts";

const PACKAGE_STRUCTURE_KEYS = new Set(["bin", "engines", "dependencies", "exports", "scripts", "workspaces"]);

export async function analyzePackageMetadata(
  path: string,
  limits: DiscoveryLimits,
): Promise<readonly EvidenceRecord[]> {
  const source = await readBoundedTextFile(path, limits);
  let parsed: unknown;
  try {
    parsed = JSON.parse(source.text);
  } catch {
    throw new Error("package metadata is malformed JSON");
  }
  const collected = collectStructureKeys(parsed, limits);
  const packageKeys = collected.keys.filter((key) => PACKAGE_STRUCTURE_KEYS.has(key.toLowerCase()));
  const records = evidenceForStructure(
    source.path,
    "package_metadata",
    packageKeys,
    packageKeys,
    collected.status,
    limits,
  );
  return Object.freeze(records.filter(({ family, strength }) => family === "package_metadata" && strength === "weak"));
}
