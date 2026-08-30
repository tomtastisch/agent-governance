import { constants } from "node:fs";
import { lstat, open, realpath } from "node:fs/promises";
import { extname, isAbsolute, resolve } from "node:path";
import { parse } from "smol-toml";
import { loadDiscoveryCatalog } from "./catalog.ts";
import type {
  DiscoveryLimits,
  DiscoveryCatalog,
  DiscoveryStatus,
  EvidenceRecord,
  EvidenceSourceKind,
} from "./types.ts";

interface CollectedStructure {
  readonly keys: readonly string[];
  readonly status: DiscoveryStatus;
}

export function sanitizeDisplay(value: string, maximumLength: number): string {
  return value.replace(/[\u0000-\u001f\u007f-\u009f]/gu, "?").slice(0, maximumLength);
}

function validateLimits(limits: DiscoveryLimits): void {
  for (const [name, value] of Object.entries(limits)) {
    if (!Number.isSafeInteger(value) || value <= 0) throw new Error(`${name} must be a positive integer`);
  }
}

export async function readBoundedTextFile(path: string, limits: DiscoveryLimits): Promise<{
  readonly path: string;
  readonly text: string;
}> {
  validateLimits(limits);
  if (!isAbsolute(path)) throw new Error("structured file path must be absolute");
  const normalized = resolve(path);
  const pathMetadata = await lstat(normalized);
  if (pathMetadata.isSymbolicLink() || !pathMetadata.isFile()) {
    throw new Error("structured file must be a regular non-symlink file");
  }
  if ((await realpath(normalized)) !== normalized) {
    throw new Error("structured file path must be canonical and contain no symlinks");
  }
  if (pathMetadata.size > limits.maxFileBytes) throw new Error("structured file exceeds size limit");

  const handle = await open(normalized, constants.O_RDONLY | constants.O_NOFOLLOW);
  try {
    const openedMetadata = await handle.stat();
    if (
      !openedMetadata.isFile() ||
      openedMetadata.dev !== pathMetadata.dev ||
      openedMetadata.ino !== pathMetadata.ino ||
      openedMetadata.size > limits.maxFileBytes
    ) {
      throw new Error("structured file exceeds size limit or changed type");
    }
    const bytes = await handle.readFile();
    if (bytes.byteLength > limits.maxFileBytes) throw new Error("structured file exceeds size limit");
    let text: string;
    try {
      text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
    } catch {
      throw new Error("structured file is not valid UTF-8");
    }
    return { path: normalized, text };
  } finally {
    await handle.close();
  }
}

export function collectStructureKeys(value: unknown, limits: DiscoveryLimits): CollectedStructure {
  const keys: string[] = [];
  let entries = 0;
  let incomplete = false;

  const visit = (current: unknown, depth: number): void => {
    if (current === null || typeof current !== "object") return;
    if (depth > limits.maxDepth) {
      incomplete = true;
      return;
    }
    if (Array.isArray(current)) {
      for (const item of current) {
        if (entries >= limits.maxEntries) {
          incomplete = true;
          return;
        }
        entries += 1;
        visit(item, depth + 1);
      }
      return;
    }
    for (const [key, child] of Object.entries(current as Record<string, unknown>)) {
      if (entries >= limits.maxEntries) {
        incomplete = true;
        return;
      }
      entries += 1;
      keys.push(sanitizeDisplay(key, limits.maxMetadataLength));
      visit(child, depth + 1);
    }
  };

  visit(value, 0);
  return Object.freeze({
    keys: Object.freeze(keys),
    status: incomplete ? "INCOMPLETE" : "COMPLETE",
  });
}

function plistKeys(text: string, limits: DiscoveryLimits): CollectedStructure {
  if (/<!DOCTYPE/i.test(text)) throw new Error("structured plist is malformed");
  const tagNames = [...text.matchAll(/<\/?\s*([A-Za-z][A-Za-z0-9_-]*)\b[^>]*>/g)].map((match) => match[1]!.toLowerCase());
  const allowedTags = new Set(["plist", "dict", "array", "key", "string", "integer", "real", "true", "false", "date", "data"]);
  if (tagNames.some((tag) => !allowedTags.has(tag))) throw new Error("structured plist is malformed");
  if ((text.match(/<plist\b/gi)?.length ?? 0) !== 1 || (text.match(/<\/plist\s*>/gi)?.length ?? 0) !== 1) {
    throw new Error("structured plist is malformed");
  }
  if ((text.match(/<key\b[^>]*>/gi)?.length ?? 0) !== (text.match(/<\/key\s*>/gi)?.length ?? 0)) {
    throw new Error("structured plist is malformed");
  }

  const stack: string[] = [];
  let incomplete = false;
  for (const match of text.matchAll(/<(\/?)\s*(dict|array)\b[^>]*>/gi)) {
    const closing = match[1] === "/";
    const tag = match[2]!.toLowerCase();
    if (closing) {
      if (stack.pop() !== tag) throw new Error("structured plist is malformed");
    } else {
      stack.push(tag);
      if (stack.length > limits.maxDepth) incomplete = true;
    }
  }
  if (stack.length > 0) throw new Error("structured plist is malformed");

  const keys: string[] = [];
  for (const match of text.matchAll(/<key\b[^>]*>([^<]*)<\/key\s*>/gi)) {
    if (keys.length >= limits.maxEntries) {
      incomplete = true;
      break;
    }
    keys.push(sanitizeDisplay(match[1] ?? "", limits.maxMetadataLength));
  }
  return Object.freeze({
    keys: Object.freeze(keys),
    status: incomplete ? "INCOMPLETE" : "COMPLETE",
  });
}

function normalizedKey(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9_]/g, "");
}

export function evidenceForStructure(
  sourcePath: string,
  sourceKind: EvidenceSourceKind,
  matchKeys: readonly string[],
  metadata: readonly string[],
  status: DiscoveryStatus,
  limits: DiscoveryLimits,
  catalog: DiscoveryCatalog = loadDiscoveryCatalog(),
): readonly EvidenceRecord[] {
  const normalized = new Set(matchKeys.map(normalizedKey));
  const safeMetadata = Object.freeze(
    metadata.slice(0, limits.maxEntries).map((value) => sanitizeDisplay(value, limits.maxMetadataLength)),
  );
  const safePath = sanitizeDisplay(sourcePath, limits.maxMetadataLength);
  return Object.freeze(catalog.signals.flatMap((signal): EvidenceRecord[] => {
    if (!signal.sourceKinds.includes(sourceKind)) return [];
    const matches = signal.keys.filter((key) => normalized.has(key));
    if (matches.length < signal.minimumMatches) return [];
    return [Object.freeze({
      family: signal.family,
      sourceKind,
      sourcePath: safePath,
      signalId: signal.id,
      strength: signal.strength,
      status,
      metadata: safeMetadata,
    })];
  }));
}

export async function analyzeStructuredFile(
  path: string,
  limits: DiscoveryLimits,
  catalog?: DiscoveryCatalog,
): Promise<readonly EvidenceRecord[]> {
  const source = await readBoundedTextFile(path, limits);
  const extension = extname(source.path).toLowerCase();
  let sourceKind: EvidenceSourceKind;
  let collected: CollectedStructure;
  try {
    if (extension === ".json") {
      sourceKind = "json";
      collected = collectStructureKeys(JSON.parse(source.text), limits);
    } else if (extension === ".toml") {
      sourceKind = "toml";
      collected = collectStructureKeys(parse(source.text), limits);
    } else if (extension === ".plist") {
      sourceKind = "plist";
      collected = plistKeys(source.text, limits);
    } else {
      throw new Error("structured file format is unsupported");
    }
  } catch (error) {
    if (error instanceof Error && /unsupported/.test(error.message)) throw error;
    throw new Error(`structured ${extension.slice(1) || "file"} is malformed`);
  }
  return evidenceForStructure(
    source.path,
    sourceKind,
    collected.keys,
    collected.keys,
    collected.status,
    limits,
    catalog,
  );
}
