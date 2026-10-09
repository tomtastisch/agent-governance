import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import ts from "@typescript/typescript6";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const digest = (value: string | Buffer, algorithm = "sha256", encoding: "hex" | "base64" = "hex") =>
  createHash(algorithm).update(value).digest(encoding);
function requireShape(condition: unknown, description: string): asserts condition {
  if (!condition) throw new Error(`Nicht unterstützte Upstream-Discovery: ${description}`);
}
function parse(source: string) {
  return ts.createSourceFile("upstream.mjs", source, ts.ScriptTarget.Latest, true, ts.ScriptKind.JS);
}
function declarations(file: ts.SourceFile) {
  const values = new Map<string, ts.Expression>();
  for (const statement of file.statements) {
    if (!ts.isVariableStatement(statement)) continue;
    for (const declaration of statement.declarationList.declarations) {
      if (ts.isIdentifier(declaration.name) && declaration.initializer) {
        requireShape(!values.has(declaration.name.text), "doppelte Deklaration");
        values.set(declaration.name.text, declaration.initializer);
      }
    }
  }
  return values;
}

export function extractHarnessDescriptors(source: string): Array<{ id: string; displayName: string; binaries: string[] }> {
  const file = parse(source);
  const values = declarations(file);
  const registry = values.get("harnesses");
  requireShape(registry && ts.isArrayLiteralExpression(registry) && registry.elements.length > 0, "Registry");
  const ids = new Set<string>();
  const references = new Set<string>();
  return registry.elements.map((reference) => {
    requireShape(ts.isIdentifier(reference) && !references.has(reference.text), "Registryreferenz");
    references.add(reference.text);
    const harness = values.get(reference.text);
    requireShape(harness && ts.isClassExpression(harness), "Harnessklasse");
    requireShape(harness.heritageClauses?.length === 1 && harness.heritageClauses[0]?.token === ts.SyntaxKind.ExtendsKeyword
      && harness.heritageClauses[0].types.length === 1 && harness.heritageClauses[0].types[0]?.expression.getText(file) === "Harness", "Basisklasse");
    const fields = new Map<string, ts.Expression>();
    for (const member of harness.members) {
      requireShape(!ts.isConstructorDeclaration(member), "Konstruktor");
      requireShape(!ts.isClassStaticBlockDeclaration(member), "statischer Block");
      const name = member.name;
      requireShape(!name || ts.isIdentifier(name), "dynamischer Membername");
      requireShape(name?.text !== "isInstalled", "isInstalled-Override");
      if (!name || !["id", "name", "binaries"].includes(name.text)) continue;
      requireShape(ts.isPropertyDeclaration(member) && member.initializer && !member.modifiers?.length && !fields.has(name.text), "Metadatenfeld");
      fields.set(name.text, member.initializer);
    }
    const id = fields.get("id");
    const name = fields.get("name");
    const binaries = fields.get("binaries");
    requireShape(id && ts.isStringLiteral(id) && /^[a-z0-9][a-z0-9-]*$/.test(id.text) && !ids.has(id.text), "ID");
    requireShape(name && ts.isStringLiteral(name) && name.text.trim().length > 0, "Anzeigename");
    requireShape(binaries && ts.isArrayLiteralExpression(binaries) && binaries.elements.length > 0, "Binärnamen");
    ids.add(id.text);
    return { id: id.text, displayName: name.text, binaries: binaries.elements.map((binary) => {
      requireShape(ts.isStringLiteral(binary) && /^[a-zA-Z0-9][a-zA-Z0-9._-]*$/.test(binary.text), "Binärname");
      return binary.text;
    }) };
  });
}

export function discoveryBehaviorDigest(source: string): string {
  const file = parse(source);
  const base = declarations(file).get("Harness");
  requireShape(base && ts.isClassExpression(base), "Basismethode");
  const installed = base.members.filter((member) => member.name?.getText(file) === "isInstalled");
  const functions = ["getRegistry", "getAllHarnesses"].map((name) => {
    const matches = file.statements.filter((statement) => ts.isFunctionDeclaration(statement) && statement.name?.text === name);
    requireShape(matches.length === 1, name);
    return matches[0]!.getText(file);
  });
  requireShape(installed.length === 1 && ts.isMethodDeclaration(installed[0]!), "isInstalled");
  const values = declarations(file);
  const registry = values.get("harnesses");
  requireShape(registry && ts.isArrayLiteralExpression(registry), "Registry");
  const classes = registry.elements.map((reference) => {
    requireShape(ts.isIdentifier(reference), "Registryreferenz");
    const harness = values.get(reference.text);
    requireShape(harness && ts.isClassExpression(harness), "Harnessklasse");
    return harness.getText(file);
  });
  return digest([base.getText(file), registry.getText(file), ...functions, ...classes].join("\n"));
}

export function checkProjection(write = false, projectRoot = root): void {
  const integration = resolve(projectRoot, "integrations/agntn-harnesses");
  const lock = JSON.parse(readFileSync(resolve(integration, "upstream.lock.json"), "utf8"));
  const archive = resolve(integration, "upstream/harnesses-0.3.0.tgz");
  const bytes = readFileSync(archive);
  requireShape(bytes.length <= 2_000_000 && digest(bytes) === lock.archiveSha256
    && `sha512-${digest(bytes, "sha512", "base64")}` === lock.integrity, "Archivintegration");
  // Liest nur reguläre, begrenzte Archivmember; keinerlei Extraktion ins Dateisystem.
  const files = JSON.parse(execFileSync("python3", ["-c", `
import json, tarfile, sys
with tarfile.open(sys.argv[1], 'r:gz') as archive:
    members = archive.getmembers()
    assert len(members) <= 1000
    assert len({m.name for m in members}) == len(members)
    assert sum(m.size for m in members) <= 20000000
    for m in members:
        assert m.name.startswith('package/') and '..' not in m.name.split('/')
        assert m.isfile() or m.isdir()
    result = {}
    for name in ['package/package.json', 'package/LICENSE', 'package/dist/_chunks/prompt-sync.mjs']:
        member = archive.getmember(name)
        assert member.isfile() and member.size <= 1000000
        result[name] = archive.extractfile(member).read().decode('utf-8')
    print(json.dumps(result))
`, archive], { encoding: "utf8", maxBuffer: 2_000_000 }));
  const metadata = JSON.parse(files["package/package.json"]);
  requireShape(metadata.name === "@agntn/harnesses" && metadata.version === lock.resolvedVersion && metadata.license === "MIT", "Paketidentität/Lizenz");
  const source = files["package/dist/_chunks/prompt-sync.mjs"] as string;
  requireShape(discoveryBehaviorDigest(source) === lock.reviewedDiscoveryBehaviorSha256, "geänderte Installed-/Registry-Semantik");
  const descriptors = extractHarnessDescriptors(source);
  const generated = `// Generiert durch tools/project-harness-discovery.ts; nicht manuell bearbeiten.\n// Quelle: @agntn/harnesses@${lock.resolvedVersion}, SHA-256 ${lock.archiveSha256}.\n// Ausschließlich Discovery-Metadaten; keine Support-/Binding-Authority.\n// MIT-Lizenz und Herkunft: THIRD_PARTY_NOTICES.md.\nexport const HARNESS_DISCOVERY = ${JSON.stringify(descriptors, null, 2)} as const;\n`;
  const notice = `# Third-party notices\n\n## @agntn/harnesses ${lock.resolvedVersion}\n\nDie generierten Discovery-Metadaten stammen aus ${lock.repository}.\nQuelle: ${lock.archiveUrl}\nSHA-256: ${lock.archiveSha256}\n\n${files["package/LICENSE"]}`;
  for (const [path, expected] of [["src/init/harness-discovery.generated.ts", generated], ["THIRD_PARTY_NOTICES.md", notice]]) {
    const destination = resolve(projectRoot, path!);
    if (write) writeFileSync(destination, expected!);
    else requireShape(readFileSync(destination, "utf8") === expected, `Projektionsdrift: ${path}`);
  }
  console.log(`PASS: ${descriptors.length} Discovery-Einträge, Archivintegrität, Semantik und Lizenz geprüft`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  requireShape(process.argv.length === 3 && ["--write", "--check"].includes(process.argv[2]!), "Aufruf");
  checkProjection(process.argv[2] === "--write");
}
