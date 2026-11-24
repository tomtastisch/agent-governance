import { execFileSync } from "node:child_process";
import { readFile } from "node:fs/promises";

const packageJson = JSON.parse(await readFile("package.json", "utf8"));
const lock = JSON.parse(await readFile("package-lock.json", "utf8"));

// Derive expected runtime dependencies from package.json (SSOT) rather than hardcoding
const runtimeDependencies = packageJson.dependencies;
if (packageJson.license !== "Apache-2.0") {
  throw new Error("package must remain Apache-2.0");
}
if (!runtimeDependencies || Object.keys(runtimeDependencies).length === 0) {
  throw new Error("package must declare direct runtime dependencies");
}
// Verify lockfile contains exactly the declared runtime dependencies (plus transitive)
const lockRuntimeDeps = Object.fromEntries(
  Object.entries(lock.packages ?? {})
    .filter(([path, meta]) => path && !meta.dev && !meta.optional)
    .map(([path, meta]) => [path.replace("node_modules/", ""), meta.version])
);
for (const [name, version] of Object.entries(runtimeDependencies)) {
  const lockKey = name.startsWith("@") ? name : name;
  const found = Object.entries(lockRuntimeDeps).find(([k]) => k === lockKey || k.endsWith("/" + lockKey));
  if (!found || found[1] !== version) {
    throw new Error(`lockfile version mismatch for ${name}: expected ${version}, found ${found?.[1] ?? "missing"}`);
  }
}
const allowed = new Set(["Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "MIT"]);
for (const [path, metadata] of Object.entries(lock.packages ?? {})) {
  if (typeof metadata !== "object" || metadata === null || !allowed.has(metadata.license)) {
    throw new Error(`unapproved or missing dependency license: ${path || "package root"}`);
  }
}
execFileSync(process.execPath, ["--experimental-strip-types", "tools/project-harness-discovery.ts", "--check"], { stdio: "inherit" });
console.log(`OK: ${Object.keys(lock.packages).length} package license records are allowlisted; exact direct runtime dependencies are declared`);
