import { readFile } from "node:fs/promises";

const packageJson = JSON.parse(await readFile("package.json", "utf8"));
const lock = JSON.parse(await readFile("package-lock.json", "utf8"));
const runtimeDependencies = { "@clack/prompts": "1.7.0", "smol-toml": "1.8.0" };
if (packageJson.license !== "Apache-2.0" || JSON.stringify(packageJson.dependencies) !== JSON.stringify(runtimeDependencies)) {
  throw new Error("package must remain Apache-2.0 with the exact direct runtime dependency contract");
}
const allowed = new Set(["Apache-2.0", "BSD-3-Clause", "MIT"]);
for (const [path, metadata] of Object.entries(lock.packages ?? {})) {
  if (typeof metadata !== "object" || metadata === null || !allowed.has(metadata.license)) {
    throw new Error(`unapproved or missing dependency license: ${path || "package root"}`);
  }
}
console.log(`OK: ${Object.keys(lock.packages).length} package license records are allowlisted; exact direct runtime dependencies are declared`);
