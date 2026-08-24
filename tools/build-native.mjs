import { access, mkdir, rm } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const candidates = [
  resolve(dirname(process.execPath), "..", "include", "node"),
  "/usr/local/include/node",
  "/opt/homebrew/include/node",
  "/usr/include/node",
];
let include;
for (const candidate of candidates) {
  try { await access(join(candidate, "node_api.h")); include = candidate; break; } catch { /* Try the next local Node header root. */ }
}
if (include === undefined) throw new Error("Node-API headers are unavailable; native build cannot proceed");
if (!["darwin", "linux"].includes(process.platform) || !["arm64", "x64"].includes(process.arch)) throw new Error(`unsupported native build target: ${process.platform}-${process.arch}`);
const outputDirectory = join(root, "prebuilds", `${process.platform}-${process.arch}`);
await mkdir(outputDirectory, { recursive: true });
const output = join(outputDirectory, "agent_governance_fs.node");
await rm(output, { force: true });
const platformFlags = process.platform === "darwin" ? ["-bundle", "-undefined", "dynamic_lookup"] : ["-shared", "-fPIC"];
const result = spawnSync(process.env.CC ?? "cc", ["-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", ...platformFlags, `-I${include}`, "-DNODE_GYP_MODULE_NAME=agent_governance_fs", join(root, "native", "agent_governance_fs.c"), "-o", output], { cwd: root, stdio: "inherit" });
if (result.error !== undefined) throw result.error;
if (result.status !== 0) throw new Error(`native compiler exited with status ${String(result.status)}`);
console.log(`built ${output}`);
