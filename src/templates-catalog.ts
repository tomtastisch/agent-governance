import { lstatSync, readFileSync, realpathSync } from "node:fs";
import { dirname, join, relative, sep } from "node:path";
import { PACKAGE_RELEASE_ROOT } from "./catalog-paths.ts";
import { exact, ID, parseClosedToml, safeRelativePath, table, text, type TomlTable } from "./closed-toml.ts";

export const TEMPLATE_CATEGORIES = ["git", "delivery", "review", "context", "communication", "external_effects"] as const;
export type TemplateCategory = (typeof TEMPLATE_CATEGORIES)[number];

const TEMPLATE_FIELDS = ["path", "category", "format"] as const;

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
    if (!/\.md$/i.test(path)) throw new Error(`templates.${id}.path has an invalid format`);
    if (seenPaths.has(path)) throw new Error("templates manifest contains duplicate template paths");
    seenPaths.add(path);
    const category = entry.category;
    if (!isCategory(category)) throw new Error(`templates.${id}.category is unknown`);
    const format = text(entry.format, `templates.${id}.format`);
    if (format !== "markdown") throw new Error(`templates.${id}.format is unsupported`);
    templates[id] = Object.freeze({ id, path, category, format });
  }
  return Object.freeze({ schemaVersion: 1, templates: Object.freeze(templates) });
}

function requireRegularFile(path: string, label: string): string {
  let metadata;
  try {
    metadata = lstatSync(path);
  } catch {
    throw new Error(`${label} must be a readable regular file`);
  }
  if (metadata.isSymbolicLink() || !metadata.isFile()) throw new Error(`${label} must be a regular non-symlink file`);
  return realpathSync(path);
}

export function resolveTemplatesManifestPath(releaseRoot: string): string {
  let metadata;
  try {
    metadata = lstatSync(releaseRoot);
  } catch {
    throw new Error("release root must be a readable directory");
  }
  if (metadata.isSymbolicLink() || !metadata.isDirectory()) throw new Error("release root must be a non-symlink directory");
  const manifestPath = join(releaseRoot, "bundle", "agent-governance", "templates", "manifest.toml");
  return requireRegularFile(manifestPath, "templates manifest");
}

function resolveTemplateFile(templatesManifestPath: string, rawPath: string, id: string): string {
  const parts = rawPath.split("/");
  const templatesRoot = dirname(templatesManifestPath);
  let current = templatesRoot;
  for (const part of parts) {
    current = join(current, part);
    let metadata;
    try {
      metadata = lstatSync(current);
    } catch {
      throw new Error(`templates.${id} path must reference an existing file`);
    }
    if (metadata.isSymbolicLink()) throw new Error(`templates.${id} path must not contain symlinks`);
  }
  const resolved = requireRegularFile(current, `templates.${id}`);
  const offset = relative(templatesRoot, resolved);
  if (offset === ".." || offset.startsWith(`..${sep}`) || offset.startsWith("/")) throw new Error(`templates.${id} path escapes the templates root`);
  return resolved;
}

export function loadTemplateIndex(releaseRoot?: string): { index: TemplateIndex; templateFile: (id: string) => string } {
  const manifestPath = resolveTemplatesManifestPath(releaseRoot ?? PACKAGE_RELEASE_ROOT);
  const index = parseTemplatesManifestText(readFileSync(manifestPath, "utf8"));
  for (const id of Object.keys(index.templates)) {
    resolveTemplateFile(manifestPath, index.templates[id]!.path, id);
  }
  return {
    index,
    templateFile: (id) => {
      const entry = index.templates[id];
      if (entry === undefined) throw new Error(`templates manifest does not register template ${id}`);
      return resolveTemplateFile(manifestPath, entry.path, id);
    },
  };
}
