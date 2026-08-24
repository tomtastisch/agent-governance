import { createHash } from "node:crypto";
import { lstat, readFile, readdir } from "node:fs/promises";
import { isAbsolute, join, normalize, relative, sep } from "node:path";

const REQUIRED = [
  "VERSION",
  "bundle/GOVERNANCE.md",
  "bundle/agent-governance/manifest.toml",
] as const;
const DIGEST_LINE = /^([0-9a-f]{64})  ([^\0\r\n]+)$/;

export interface VerifiedRelease {
  readonly version: string;
  readonly fileCount: number;
  readonly governanceDigest: string;
  readonly manifestDigest: string;
  readonly inventory: ReadonlyMap<string, string>;
}

function validateInventoryPath(path: string): void {
  const canonical = normalize(path);
  if (
    path === "" ||
    isAbsolute(path) ||
    path.includes("\\") ||
    canonical !== path ||
    path === ".." ||
    path.startsWith(`..${sep}`)
  ) {
    throw new Error("invalid release inventory path");
  }
}

function validateManifest(manifest: string, entries: ReadonlyMap<string, string>): string | undefined {
  const schemas = [...manifest.matchAll(/^schema_version\s*=\s*(\d+)\s*$/gm)];
  if (schemas.length !== 1 || schemas[0]?.[1] !== "2") throw new Error("release manifest schema is invalid");
  const locals = [...manifest.matchAll(/^local_rules\s*=\s*"([^"\\]+)"\s*$/gm)];
  if (locals.length > 1) throw new Error("release manifest local rules declaration is ambiguous");
  const local = locals[0]?.[1];
  if (local !== undefined) {
    try { validateInventoryPath(local); } catch { throw new Error("release manifest local rules path is invalid"); }
    if (!/\.md$/i.test(local)) throw new Error("release manifest local rules path is invalid");
  } else if (/^local_rules\s*=/m.test(manifest)) throw new Error("release manifest local rules path is invalid");
  for (const match of manifest.matchAll(/^(?:triggers|policy_tags|scopes|tools|path)\s*=\s*"([^"\\]+)"\s*$/gm)) {
    const value = match[1]!;
    try { validateInventoryPath(value); } catch { throw new Error("release manifest reference path is invalid"); }
    const inventoryPath = `bundle/agent-governance/${value}`;
    if (!entries.has(inventoryPath)) throw new Error(`release manifest reference is missing from inventory: ${value}`);
  }
  return local;
}

async function safeRegularFile(path: string): Promise<Buffer> {
  const stat = await lstat(path);
  if (stat.isSymbolicLink() || !stat.isFile()) {
    throw new Error("release inventory entry must be a regular non-symlink file");
  }
  if (stat.size > 64 * 1024 * 1024) {
    throw new Error("release inventory entry exceeds size limit");
  }
  return readFile(path);
}

export async function verifyRelease(releaseRoot: string): Promise<VerifiedRelease> {
  if (!isAbsolute(releaseRoot)) {
    throw new Error("release root must be absolute");
  }
  const inventoryText = (await safeRegularFile(join(releaseRoot, "release.files.sha256"))).toString(
    "utf8",
  );
  const entries = new Map<string, string>();
  for (const line of inventoryText.split("\n")) {
    if (line === "") continue;
    const match = DIGEST_LINE.exec(line);
    if (match === null) throw new Error("invalid release inventory line");
    const digest = match[1];
    const path = match[2];
    if (digest === undefined || path === undefined) throw new Error("invalid release inventory line");
    validateInventoryPath(path);
    if (entries.has(path)) throw new Error("duplicate release inventory path");
    entries.set(path, digest);
  }
  for (const required of REQUIRED) {
    if (!entries.has(required)) throw new Error(`missing required release file: ${required}`);
  }
  for (const [path, expected] of entries) {
    const content = await safeRegularFile(join(releaseRoot, path));
    const actual = createHash("sha256").update(content).digest("hex");
    if (actual !== expected) throw new Error(`release digest mismatch: ${path}`);
  }
  const actualBundleFiles: string[] = [];
  async function walk(directory: string): Promise<void> {
    for (const item of await readdir(directory, { withFileTypes: true })) {
      const absolute = join(directory, item.name);
      const path = relative(releaseRoot, absolute).split(sep).join("/");
      const stat = await lstat(absolute);
      if (stat.isSymbolicLink()) throw new Error(`release bundle contains a symlink: ${path}`);
      if (stat.isDirectory()) await walk(absolute);
      else if (stat.isFile()) actualBundleFiles.push(path);
      else throw new Error(`release bundle contains an unexpected file type: ${path}`);
    }
  }
  await walk(join(releaseRoot, "bundle"));
  const expectedBundleFiles = [...entries.keys()].filter((path) => path.startsWith("bundle/")).sort();
  const manifest = (await safeRegularFile(join(releaseRoot, "bundle", "agent-governance", "manifest.toml"))).toString("utf8");
  const localRelative = validateManifest(manifest, entries);
  const allowedLocal = localRelative === undefined ? undefined : `bundle/agent-governance/${localRelative}`;
  const normativeBundleFiles = actualBundleFiles.filter((path) => path !== allowedLocal).sort();
  if (normativeBundleFiles.join("\0") !== expectedBundleFiles.join("\0")) {
    throw new Error("release bundle contains additional or unlisted inventory files");
  }
  const version = (await safeRegularFile(join(releaseRoot, "VERSION"))).toString("utf8").trim();
  if (!/^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$/.test(version)) {
    throw new Error("invalid release version");
  }
  return {
    version,
    fileCount: entries.size,
    governanceDigest: entries.get("bundle/GOVERNANCE.md")!,
    manifestDigest: entries.get("bundle/agent-governance/manifest.toml")!,
    inventory: entries,
  };
}
