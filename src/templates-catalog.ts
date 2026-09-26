import { readdirSync, readFileSync } from "node:fs";
import { dirname, join, relative, sep } from "node:path";
import { PACKAGE_RELEASE_ROOT, resolveTemplateFile, resolveTemplatesManifestPath } from "./catalog-paths.ts";
import { exact, ID, parseClosedToml, safeRelativePath, table, text, type TomlTable } from "./closed-toml.ts";
import { governanceContract } from "./contract-fixture.ts";

export type TemplateCategory = "git" | "delivery" | "review" | "context" | "communication" | "external_effects";
export const TEMPLATE_CATEGORIES = governanceContract.templateCategories as readonly TemplateCategory[];

const TEMPLATE_FIELDS = governanceContract.templateFields;

export interface TemplateEntry {
  readonly id: string;
  readonly path: string;
  readonly category: TemplateCategory;
  readonly format: string;
}

export interface TemplateIndex {
  readonly schemaVersion: 1;
  readonly templates: Readonly<Record<string, TemplateEntry>>;
}

function isCategory(value: TomlTable[keyof TomlTable] | undefined): value is TemplateCategory {
  return typeof value === "string" && (TEMPLATE_CATEGORIES as readonly string[]).includes(value);
}

export function parseTemplatesManifestText(content: string): TemplateIndex {
  const manifest = parseClosedToml(content, "templates manifest");
  exact(manifest, ["schema_version", "templates"], "templates manifest");
  if (manifest.schema_version !== 1) throw new Error("templates manifest schema is invalid");
  const entries = table(manifest.templates, "templates manifest entries");
  if (Object.keys(entries).length === 0) throw new Error("templates manifest is empty");
  const seenPaths = new Set<string>();
  const templates: Record<string, TemplateEntry> = {};
  for (const [id, raw] of Object.entries(entries)) {
    if (!ID.test(id)) throw new Error(`templates manifest contains an invalid template ID: ${id}`);
    const entry = table(raw, `templates.${id}`);
    exact(entry, TEMPLATE_FIELDS, `templates.${id}`);
    const path = safeRelativePath(entry.path, `templates.${id}.path`);
    if (!/\.md$/.test(path)) throw new Error(`templates.${id}.path has an invalid format`);
    if (seenPaths.has(path)) throw new Error("templates manifest contains duplicate template paths");
    seenPaths.add(path);
    const category = entry.category;
    if (!isCategory(category)) throw new Error(`templates.${id}.category is unknown`);
    const format = text(entry.format, `templates.${id}.format`);
    if (!governanceContract.templateFormats.includes(format)) throw new Error(`templates.${id}.format is unsupported`);
    templates[id] = Object.freeze({ id, path, category, format });
  }
  return Object.freeze({ schemaVersion: 1, templates: Object.freeze(templates) });
}

function assertNoOrphanTemplates(templatesRoot: string, registered: ReadonlySet<string>): void {
  const orphans: string[] = [];
  const walk = (directory: string): void => {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const absolute = join(directory, entry.name);
      if (entry.isSymbolicLink()) throw new Error("templates directory must not contain symlinks");
      if (entry.isDirectory()) walk(absolute);
      else if (entry.isFile() && entry.name.endsWith(".md")) {
        const relativePath = relative(templatesRoot, absolute).split(sep).join("/");
        if (!registered.has(relativePath)) orphans.push(relativePath);
      }
    }
  };
  walk(templatesRoot);
  if (orphans.length > 0) throw new Error(`templates contains unregistered files: ${orphans.join(", ")}`);
}

export function loadTemplateIndex(releaseRoot?: string): { index: TemplateIndex; templateFile: (id: string) => string } {
  const manifestPath = resolveTemplatesManifestPath(releaseRoot ?? PACKAGE_RELEASE_ROOT);
  const index = parseTemplatesManifestText(readFileSync(manifestPath, "utf8"));
  const registered = new Set(Object.values(index.templates).map((entry) => entry.path));
  for (const entry of Object.values(index.templates)) {
    resolveTemplateFile(manifestPath, entry.path);
  }
  assertNoOrphanTemplates(dirname(manifestPath), registered);
  return {
    index,
    templateFile: (id) => {
      const entry = index.templates[id];
      if (entry === undefined) throw new Error(`templates manifest does not register template ${id}`);
      return resolveTemplateFile(manifestPath, entry.path);
    },
  };
}
