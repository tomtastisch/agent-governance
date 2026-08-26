import { readFile } from "node:fs/promises";

const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const rawReport = JSON.parse(Buffer.concat(chunks).toString("utf8"));
const expectedPackageName = "@tomtastisch/agent-governance";
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
const paths = report[0].files.map((entry) => entry.path);
const forbiddenFiles = new Set(["INSTALL.md", "docs/harness-recipes.md"]);
const runtimeBrandingPath = "assets/branding/agent-governance-terminal.png";
for (const path of paths) {
  if (typeof path !== "string") {
    throw new Error(`unexpected tarball path: ${String(path)}`);
  }
  if (forbiddenFiles.has(path) || path.startsWith("assets/") && path !== runtimeBrandingPath || path.startsWith("docs/") && path !== "docs/installer-cli-reference.md") {
    throw new Error(`forbidden runtime path: ${path}`);
  }
  if (path !== runtimeBrandingPath && !/^(?:CHANGELOG\.md|LICENSE|README\.md|VERSION|package\.json|release\.files\.sha256|docs\/installer-cli-reference\.md|bundle\/|dist\/|prebuilds\/(?:darwin|linux)-(?:arm64|x64)\/agent_governance_fs\.node$)/.test(path)) {
    throw new Error(`unexpected tarball path: ${path}`);
  }
  if (/^(?:integrations|tests|tools)\//.test(path) || /(?:codex|claude|opencode|openclaw|hooks?)/i.test(path)) {
    throw new Error(`forbidden runtime path: ${path}`);
  }
}
for (const required of ["README.md", "LICENSE", "CHANGELOG.md", "dist/cli.js", "bundle/GOVERNANCE.md", "bundle/agent-governance/manifest.toml", "docs/installer-cli-reference.md", "release.files.sha256", "VERSION", runtimeBrandingPath]) {
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
