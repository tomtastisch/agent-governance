import { readFile } from "node:fs/promises";

const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const report = JSON.parse(Buffer.concat(chunks).toString("utf8"));
if (!Array.isArray(report) || report.length !== 1 || !Array.isArray(report[0]?.files)) {
  throw new Error("npm pack report has an unexpected schema");
}
const paths = report[0].files.map((entry) => entry.path);
for (const path of paths) {
  if (typeof path !== "string" || !/^(?:CHANGELOG\.md|INSTALL\.md|LICENSE|README\.md|VERSION|package\.json|release\.files\.sha256|bundle\/|dist\/)/.test(path)) {
    throw new Error(`unexpected tarball path: ${String(path)}`);
  }
  if (/^(?:integrations|tests|tools|docs)\//.test(path) || /(?:codex|claude|opencode|openclaw|hooks?)/i.test(path)) {
    throw new Error(`forbidden runtime path: ${path}`);
  }
}
for (const required of ["dist/cli.js", "bundle/GOVERNANCE.md", "bundle/agent-governance/manifest.toml", "release.files.sha256", "VERSION"]) {
  if (!paths.includes(required)) throw new Error(`missing tarball path: ${required}`);
}
const secretPattern = /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bnpm_[A-Za-z0-9]{30,}\b|\bgh[pousr]_[A-Za-z0-9]{30,}\b|\bAKIA[0-9A-Z]{16}\b/;
for (const path of paths) {
  const content = await readFile(path);
  if (secretPattern.test(content.toString("utf8"))) throw new Error(`potential secret material in tarball path: ${path}`);
}
for (const path of paths.filter((value) => value.startsWith("dist/") && value.endsWith(".js"))) {
  const source = await readFile(path, "utf8");
  if (/\b(?:codex|claude|opencode|openclaw)\b|hooks\.json|PreToolUse|agent_governance__execute/i.test(source)) {
    throw new Error(`forbidden harness-specific runtime content: ${path}`);
  }
}
console.log(`OK: ${paths.length} tarball entries are generic and allowlisted`);
