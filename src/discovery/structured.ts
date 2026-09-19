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
  readonly sourceIdentity: string;
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
    return { path: normalized, text, sourceIdentity: `${openedMetadata.dev}:${openedMetadata.ino}` };
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
  const declaration = text.match(/^[\t\n\r ]*<\?xml[\t\n\r ]+version=(?:"1\.0"|'1\.0')(?:[\t\n\r ]+encoding=(?:"UTF-8"|'UTF-8'))?[\t\n\r ]*\?>/u);
  const prolog = declaration === null ? text : text.slice(declaration[0].length);
  // Recognize the standard declaration as inert syntax; never load a DTD or expand entities.
  const doctype = prolog.match(/^[\t\n\r ]*<!DOCTYPE[\t\n\r ]+plist[\t\n\r ]+PUBLIC[\t\n\r ]+(?:"-\/\/Apple\/\/DTD PLIST 1\.0\/\/EN"|'-\/\/Apple\/\/DTD PLIST 1\.0\/\/EN')[\t\n\r ]+(?:"http:\/\/www\.apple\.com\/DTDs\/PropertyList-1\.0\.dtd"|'http:\/\/www\.apple\.com\/DTDs\/PropertyList-1\.0\.dtd')[\t\n\r ]*>/u);
  const body = doctype === null ? prolog : prolog.slice(doctype[0].length);
  if (/<!DOCTYPE|<!--|-->|<!\[CDATA\[|<\?|\?>/iu.test(body)) throw new Error("structured plist is malformed");
  for (const character of body) {
    const codePoint = character.codePointAt(0)!;
    if (
      codePoint !== 0x09
      && codePoint !== 0x0a
      && codePoint !== 0x0d
      && !(codePoint >= 0x20 && codePoint <= 0xd7ff)
      && !(codePoint >= 0xe000 && codePoint <= 0xfffd)
      && !(codePoint >= 0x10000 && codePoint <= 0x10ffff)
    ) {
      throw new Error("structured plist is malformed");
    }
  }
  const validNamedEntities = new Set(["amp", "lt", "gt", "quot", "apos"]);
  const validXmlCodePoint = (value: number): boolean => value === 0x09 || value === 0x0a || value === 0x0d
    || value >= 0x20 && value <= 0xd7ff
    || value >= 0xe000 && value <= 0xfffd
    || value >= 0x10000 && value <= 0x10ffff;
  const withoutEntities = body.replace(/&([^&;]*);/gu, (entity, value: string): string => {
    const decimal = value.match(/^#([0-9]+)$/u);
    const hexadecimal = value.match(/^#x([0-9a-fA-F]+)$/u);
    const codePoint = decimal !== null
      ? Number.parseInt(decimal[1]!, 10)
      : hexadecimal !== null
      ? Number.parseInt(hexadecimal[1]!, 16)
      : undefined;
    if (!validNamedEntities.has(value) && (codePoint === undefined || !validXmlCodePoint(codePoint))) {
      throw new Error("structured plist is malformed");
    }
    return entity.startsWith("&") ? "" : entity;
  });
  if (withoutEntities.includes("&")) throw new Error("structured plist is malformed");

  type PlistFrame = {
    readonly tag: string;
    childCount?: number;
    expecting?: "key" | "value";
    text?: string;
  };
  const valueTags = new Set(["dict", "array", "string", "integer", "real", "true", "false", "date", "data"]);
  const textTags = new Set(["key", "string", "integer", "real", "date", "data"]);
  const stack: PlistFrame[] = [];
  const keys: string[] = [];
  let containerDepth = 0;
  let rootClosed = false;
  let incomplete = false;
  let nodeCount = 0;

  const consumeText = (fragment: string): void => {
    if (fragment.includes("<") || fragment.includes("]]>")) throw new Error("structured plist is malformed");
    if (/^[\t\n\r ]*$/u.test(fragment)) return;
    const frame = stack.at(-1);
    if (frame === undefined || !textTags.has(frame.tag)) throw new Error("structured plist is malformed");
    if (frame.tag === "key") frame.text = `${frame.text ?? ""}${fragment}`;
  };

  const closeTag = (tag: string): void => {
    const frame = stack.pop();
    if (frame?.tag !== tag) throw new Error("structured plist is malformed");
    if (tag === "dict" || tag === "array") containerDepth -= 1;
    if (tag === "dict" && frame.expecting !== "key") throw new Error("structured plist is malformed");
    if (tag === "plist" && frame.childCount !== 1) throw new Error("structured plist is malformed");
    const parent = stack.at(-1);
    if (tag === "key") {
      if (parent?.tag !== "dict" || parent.expecting !== "key") throw new Error("structured plist is malformed");
      if (keys.length >= limits.maxEntries) incomplete = true;
      else keys.push(sanitizeDisplay(frame.text ?? "", limits.maxMetadataLength));
      parent.expecting = "value";
    } else if (valueTags.has(tag) && parent?.tag === "dict") {
      if (parent.expecting !== "value") throw new Error("structured plist is malformed");
      parent.expecting = "key";
    } else if (tag === "plist") {
      rootClosed = true;
    }
  };

  let cursor = 0;
  for (const match of body.matchAll(/<[^<>]*>/gu)) {
    consumeText(body.slice(cursor, match.index));
    cursor = match.index + match[0].length;
    const closing = match[0].match(/^<\/(plist|dict|array|key|string|integer|real|true|false|date|data)[\t\n\r ]*>$/u);
    if (closing !== null) {
      closeTag(closing[1]!);
      continue;
    }
    const plist = match[0].match(/^<(plist)(?:[\t\n\r ]+version=(?:"1\.0"|'1\.0'))?[\t\n\r ]*>$/u);
    const opening = plist ?? match[0].match(/^<(dict|array|key|string|integer|real|true|false|date|data)[\t\n\r ]*(\/?)>$/u);
    if (opening === null) throw new Error("structured plist is malformed");
    const tag = opening[1]!;
    const selfClosing = plist === null && opening[2] === "/";
    if (rootClosed) throw new Error("structured plist is malformed");
    nodeCount += 1;
    if (nodeCount > limits.maxEntries) {
      incomplete = true;
      break;
    }
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
      : tag === "key"
      ? { tag, text: "" }
      : { tag };
    stack.push(frame);
    if (tag === "dict" || tag === "array") {
      containerDepth += 1;
      if (containerDepth > limits.maxDepth) throw new Error("structured plist exceeds depth limit");
    }
    if (selfClosing) {
      if (tag === "key" || tag === "plist") throw new Error("structured plist is malformed");
      closeTag(tag);
    }
  }
  if (!incomplete) {
    consumeText(body.slice(cursor));
    if (stack.length > 0 || !rootClosed) throw new Error("structured plist is malformed");
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
  sourceIdentity?: string,
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
      ...(sourceIdentity === undefined ? {} : { sourceIdentity }),
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
    source.sourceIdentity,
  );
}
