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

async function readAtMostOneOverflowByte(
  handle: Awaited<ReturnType<typeof open>>,
  maximumBytes: number,
): Promise<Buffer> {
  const chunks: Buffer[] = [];
  let total = 0;
  while (total <= maximumBytes) {
    const remaining = maximumBytes - total;
    const capacity = remaining > 0 ? Math.min(64 * 1024, remaining) : 1;
    const chunk = Buffer.allocUnsafe(capacity);
    const { bytesRead } = await handle.read(chunk, 0, capacity, total);
    if (bytesRead === 0) break;
    chunks.push(chunk.subarray(0, bytesRead));
    total += bytesRead;
  }
  return Buffer.concat(chunks, total);
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

  const handle = await open(normalized, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
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
    const bytes = await readAtMostOneOverflowByte(handle, limits.maxFileBytes);
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
  if (/<!DOCTYPE|<!--|-->|<!\[CDATA\[|<\?(?!xml\b)/i.test(text)) throw new Error("structured plist is malformed");
  const declarations = [...text.matchAll(/<\?xml\b[^?]*\?>/gi)];
  if (
    declarations.length > 1
    || (declarations[0] !== undefined && text.slice(0, declarations[0].index).trim() !== "")
    || text.replace(/<\?xml\b[^?]*\?>/gi, "").includes("?>")
  ) {
    throw new Error("structured plist is malformed");
  }
  if (/&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-f]+);)/iu.test(text)) {
    throw new Error("structured plist is malformed");
  }
  const tagNames = [...text.matchAll(/<\/?\s*([A-Za-z][A-Za-z0-9_-]*)\b[^>]*>/g)].map((match) => match[1]!.toLowerCase());
  const allowedTags = new Set(["plist", "dict", "array", "key", "string", "integer", "real", "true", "false", "date", "data"]);
  if (tagNames.some((tag) => !allowedTags.has(tag))) throw new Error("structured plist is malformed");
  if ((text.match(/<plist\b/gi)?.length ?? 0) !== 1 || (text.match(/<\/plist\s*>/gi)?.length ?? 0) !== 1) {
    throw new Error("structured plist is malformed");
  }
  if ((text.match(/<key\b[^>]*>/gi)?.length ?? 0) !== (text.match(/<\/key\s*>/gi)?.length ?? 0)) {
    throw new Error("structured plist is malformed");
  }

  type PlistFrame = {
    readonly tag: string;
    childCount?: number;
    expecting?: "key" | "value";
  };
  const valueTags = new Set(["dict", "array", "string", "integer", "real", "true", "false", "date", "data"]);
  const stack: PlistFrame[] = [];
  let containerDepth = 0;
  let rootClosed = false;
  let incomplete = false;
  for (const match of text.matchAll(/<(\/?)\s*(plist|dict|array|key|string|integer|real|true|false|date|data)\b[^>]*>/gi)) {
    const closing = match[1] === "/";
    const tag = match[2]!.toLowerCase();
    if (closing) {
      const frame = stack.pop();
      if (frame?.tag !== tag) throw new Error("structured plist is malformed");
      if (tag === "dict" || tag === "array") containerDepth -= 1;
      if (tag === "dict" && frame.expecting !== "key") throw new Error("structured plist is malformed");
      if (tag === "plist" && frame.childCount !== 1) throw new Error("structured plist is malformed");
      const parent = stack.at(-1);
      if (tag === "key") {
        if (parent?.tag !== "dict" || parent.expecting !== "key") throw new Error("structured plist is malformed");
        parent.expecting = "value";
      } else if (valueTags.has(tag) && parent?.tag === "dict") {
        if (parent.expecting !== "value") throw new Error("structured plist is malformed");
        parent.expecting = "key";
      } else if (tag === "plist") {
        rootClosed = true;
      }
      continue;
    }

    if (rootClosed) throw new Error("structured plist is malformed");
    const parent = stack.at(-1);
    if (tag === "plist") {
      if (parent !== undefined || stack.length !== 0) throw new Error("structured plist is malformed");
    } else if (tag === "key") {
      if (parent?.tag !== "dict" || parent.expecting !== "key") throw new Error("structured plist is malformed");
    } else if (valueTags.has(tag)) {
      if (parent?.tag === "plist") {
        if (parent.childCount !== 0) throw new Error("structured plist is malformed");
        parent.childCount = 1;
      } else if (parent?.tag === "dict") {
        if (parent.expecting !== "value") throw new Error("structured plist is malformed");
      } else if (parent?.tag !== "array") {
        throw new Error("structured plist is malformed");
      }
    } else {
      throw new Error("structured plist is malformed");
    }

    const frame: PlistFrame = tag === "plist"
      ? { tag, childCount: 0 }
      : tag === "dict"
      ? { tag, expecting: "key" }
      : { tag };
    stack.push(frame);
    if (tag === "dict" || tag === "array") {
      containerDepth += 1;
      if (containerDepth > limits.maxDepth) throw new Error("structured plist exceeds depth limit");
    }
    if (/\/\s*>$/u.test(match[0])) {
      if (tag === "key" || tag === "plist") throw new Error("structured plist is malformed");
      stack.pop();
      if (tag === "dict" || tag === "array") containerDepth -= 1;
      const container = stack.at(-1);
      if (container?.tag === "dict") {
        if (container.expecting !== "value") throw new Error("structured plist is malformed");
        container.expecting = "key";
      }
    }
  }
  if (stack.length > 0 || !rootClosed) throw new Error("structured plist is malformed");

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
