import { createHash } from "node:crypto";
import { lstat, readFile } from "node:fs/promises";
import { isAbsolute, join, normalize, sep } from "node:path";

const REQUIRED = [
  "VERSION",
  "bundle/GOVERNANCE.md",
  "bundle/agent-governance/manifest.toml",
] as const;
const DIGEST_LINE = /^([0-9a-f]{64})  ([^\0\r\n]+)$/;

export interface VerifiedRelease {
  readonly version: string;
  readonly fileCount: number;
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

async function safeRegularFile(path: string): Promise<Buffer> {
  const stat = await lstat(path);
  if (stat.isSymbolicLink() || !stat.isFile()) {
    throw new Error("release inventory entry must be a regular non-symlink file");
  }
  if (stat.size > 16 * 1024 * 1024) {
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
  const version = (await safeRegularFile(join(releaseRoot, "VERSION"))).toString("utf8").trim();
  if (!/^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/.test(version)) {
    throw new Error("invalid release version");
  }
  return { version, fileCount: entries.size };
}
