import { createHash } from "node:crypto";
import { lstat, readFile, readdir, realpath } from "node:fs/promises";
import { isAbsolute, join, normalize, relative, sep } from "node:path";
import { validateGovernanceContract } from "./governance-contract.ts";

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
  readonly bundleDigest: string;
  readonly localRulesPath: string;
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

function validateNormativeText(content: Buffer, path: string): void {
  let text: string;
  try { text = new TextDecoder("utf-8", { fatal: true }).decode(content); } catch { throw new Error(`normative text contains invalid UTF-8 encoding: ${path}`); }
  if (/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/.test(text)) throw new Error(`normative text contains a raw control character: ${path}`);
}

export async function verifyRelease(releaseRoot: string): Promise<VerifiedRelease> {
  if (!isAbsolute(releaseRoot)) {
    throw new Error("release root must be absolute");
  }
  const rootStat = await lstat(releaseRoot);
  if (rootStat.isSymbolicLink() || !rootStat.isDirectory() || await realpath(releaseRoot) !== releaseRoot) throw new Error("release root must be a canonical non-symlink directory");
  for (const directory of [join(releaseRoot, "bundle"), join(releaseRoot, "bundle", "agent-governance")]) {
    const stat = await lstat(directory);
    if (stat.isSymbolicLink() || !stat.isDirectory() || await realpath(directory) !== directory) throw new Error("release bundle root must be a canonical non-symlink directory");
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
    if (path.startsWith("bundle/") && /\.(?:md|toml)$/i.test(path)) validateNormativeText(content, path);
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
  let manifest: string; try { manifest = new TextDecoder("utf-8", { fatal: true }).decode(await safeRegularFile(join(releaseRoot, "bundle", "agent-governance", "manifest.toml"))); } catch { throw new Error("release manifest contains invalid UTF-8 encoding"); }
  const contract = await validateGovernanceContract(join(releaseRoot, "bundle", "agent-governance"), manifest, entries);
  const localRelative = contract.localRulesPath;
  const knownInventoryFiles = new Set([
    "bundle/GOVERNANCE.md",
    "bundle/agent-governance/manifest.toml",
    ...[...contract.referencedPaths].map((path) => `bundle/agent-governance/${path}`),
    `bundle/agent-governance/${localRelative.replace(/\.md$/i, ".example.md")}`,
  ]);
  for (const path of entries.keys()) if (path.startsWith("bundle/") && !knownInventoryFiles.has(path)) throw new Error(`release contains an unknown or unreferenced normative file: ${path}`);
  const allowedLocal = `bundle/agent-governance/${localRelative}`;
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
    bundleDigest: createHash("sha256").update([...entries].sort(([left], [right]) => left.localeCompare(right)).map(([path, digest]) => `${digest}  ${path}\n`).join("")).digest("hex"),
    localRulesPath: localRelative,
    inventory: entries,
  };
}
