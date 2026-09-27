import { lstat, readFile, readdir, realpath } from "node:fs/promises";
import { posix, resolve } from "node:path";
import { verifyRelease } from "../src/release.ts";

const root = await realpath(process.cwd());
function packagePath(value, exportTarget = false) {
  const path = exportTarget && typeof value === "string" && value.startsWith("./") ? value.slice(2) : value;
  if (typeof path !== "string" || path === "" || path === "." || path === ".."
    || posix.isAbsolute(path) || posix.normalize(path) !== path || path.startsWith("../")
    || /[\\\x00-\x1f\x7f*?\[\]{}!]/.test(path)) {
    throw new Error("invalid package path");
  }
  return path;
}
async function safeEntry(path) {
  const absolute = resolve(root, packagePath(path));
  const stat = await lstat(absolute);
  if (stat.isSymbolicLink() || await realpath(absolute) !== absolute || (!stat.isFile() && !stat.isDirectory())) {
    throw new Error(`unsafe package entry: ${path}`);
  }
  return stat;
}
await safeEntry("package.json");
const metadata = JSON.parse(await readFile(resolve(root, "package.json"), "utf8"));

const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const rawReport = JSON.parse(Buffer.concat(chunks).toString("utf8"));
const expectedPackageName = "@tomtastisch/agent-governance";
if (metadata.name !== expectedPackageName || !Array.isArray(metadata.files) || metadata.files.length === 0) {
  throw new Error("invalid package metadata");
}
let report;
if (Array.isArray(rawReport)) {
  report = rawReport;
} else if (typeof rawReport === "object" && rawReport !== null) {
  const entries = Object.entries(rawReport);
  report = entries.length === 1
    && entries[0][0] === expectedPackageName
    && entries[0][1]?.name === expectedPackageName
    ? [entries[0][1]]
    : [];
} else {
  report = [];
}
if (report.length !== 1 || report[0]?.name !== expectedPackageName || !Array.isArray(report[0]?.files)) {
  throw new Error("npm pack report has an unexpected schema");
}
const paths = report[0].files.map((entry) => packagePath(entry?.path));
if (new Set(paths).size !== paths.length) throw new Error("duplicate tarball path");

// The release verifier owns manifest traversal, inventory parsing and digest checks.
const release = await verifyRelease(root);
const requiredPaths = new Set(["package.json", "release.files.sha256", ...release.inventory.keys()]);
async function include(path) {
  const stat = await safeEntry(path);
  if (stat.isDirectory()) {
    for (const name of await readdir(resolve(root, path))) await include(`${path}/${name}`);
  } else requiredPaths.add(path);
}
for (const value of metadata.files) {
  const path = packagePath(value);
  // Bundle membership comes exclusively from the verified release inventory.
  if (path === "bundle" || path.startsWith("bundle/")) continue;
  await include(path);
}
async function includeTargets(value) {
  if (typeof value === "string") {
    const path = packagePath(value, true);
    if (path.startsWith("bundle/") && !release.inventory.has(path)) {
      throw new Error(`unlisted bundle target: ${path}`);
    }
    if (!(await safeEntry(path)).isFile()) throw new Error(`package target must be a file: ${path}`);
    requiredPaths.add(path);
  } else if (value !== null && typeof value === "object") {
    for (const target of Object.values(value)) await includeTargets(target);
  } else if (value !== null) throw new Error("invalid package target");
}
await includeTargets(metadata.bin);
await includeTargets(metadata.exports);

const forbiddenFiles = new Set(["INSTALL.md", "docs/harness-recipes.md"]);
for (const path of paths) {
  if (forbiddenFiles.has(path) || /^(?:integrations|tests|tools)\//.test(path) || /hooks?/i.test(path)) {
    throw new Error(`forbidden runtime path: ${path}`);
  }
  if (!requiredPaths.has(path)) throw new Error(`unexpected tarball path: ${path}`);
  if (path.startsWith("prebuilds/") && !/^prebuilds\/(?:darwin|linux)-(?:arm64|x64)\/agent_governance_fs\.node$/.test(path)) {
    throw new Error(`unexpected native tarball path: ${path}`);
  }
}
for (const required of requiredPaths) {
  if (!paths.includes(required)) throw new Error(`missing tarball path: ${required}`);
}
const nativePlatforms = process.env.REQUIRE_ALL_NATIVE_PREBUILDS === "1"
  ? ["darwin-arm64", "darwin-x64", "linux-arm64", "linux-x64"]
  : [`${process.platform}-${process.arch}`];
for (const platform of nativePlatforms) {
  const required = `prebuilds/${platform}/agent_governance_fs.node`;
  if (!paths.includes(required)) throw new Error(`missing native tarball path: ${required}`);
}
const secretPattern = /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bnpm_[A-Za-z0-9]{30,}\b|\bgh[pousr]_[A-Za-z0-9]{30,}\b|\bAKIA[0-9A-Z]{16}\b/;
for (const path of paths) {
  await safeEntry(path);
  const content = await readFile(resolve(root, path));
  if (secretPattern.test(content.toString("utf8"))) throw new Error(`potential secret material in tarball path: ${path}`);
}
for (const path of paths.filter((value) => value.startsWith("dist/") && value.endsWith(".js"))) {
  const source = await readFile(path, "utf8");
  if (/hooks\.json|PreToolUse|agent_governance__execute/i.test(source)) {
    throw new Error(`forbidden harness-specific runtime content: ${path}`);
  }
}
console.log(`OK: ${paths.length} tarball entries are generic and allowlisted`);
