import { readFile } from "node:fs/promises";

const packageJson = JSON.parse(await readFile("package.json", "utf8"));
const lock = JSON.parse(await readFile("package-lock.json", "utf8"));
if (packageJson.license !== "Apache-2.0" || packageJson.dependencies !== undefined) {
  throw new Error("package must remain Apache-2.0 with zero runtime dependencies");
}
const allowed = new Set(["Apache-2.0", "MIT"]);
for (const [path, metadata] of Object.entries(lock.packages ?? {})) {
  if (typeof metadata !== "object" || metadata === null || !allowed.has(metadata.license)) {
    throw new Error(`unapproved or missing dependency license: ${path || "package root"}`);
  }
}
console.log(`OK: ${Object.keys(lock.packages).length} package license records are allowlisted`);
