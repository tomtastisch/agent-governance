import { lstat, readFile, realpath } from "node:fs/promises";
import { isAbsolute, join, normalize, sep } from "node:path";

type TomlValue = string | number | TomlValue[] | TomlTable;
type TomlTable = { [key: string]: TomlValue };

const ID = /^[a-z][a-z0-9_]*$/;
const CATALOGS = ["triggers", "policy_tags", "scopes", "tools"] as const;
const MODULE_FIELDS = ["path", "triggers", "dependencies"] as const;
const ROLE_FIELDS = ["path", "triggers", "modules"] as const;
const TOOL_FIELDS = ["name", "purpose", "required_on", "useful_on", "policy_tags", "scopes", "evidence", "fallback", "constraints"] as const;

function exact(table: TomlTable, expected: readonly string[], label: string): void {
  const actual = Object.keys(table).sort();
  const wanted = [...expected].sort();
  if (actual.join("\0") !== wanted.join("\0")) throw new Error(`${label} has missing or unknown fields`);
}

function parseString(raw: string, label: string): string {
  try {
    for (let index = 1; index < raw.length - 1; index += 1) {
      if (raw[index] !== "\\") continue;
      const escape = raw[index + 1];
      if (escape === "u" && /^[0-9A-Fa-f]{4}$/.test(raw.slice(index + 2, index + 6)) && !/^d[89ab][0-9a-f]{2}$/i.test(raw.slice(index + 2, index + 6))) { index += 5; continue; }
      if (escape !== undefined && '"\\btnfr'.includes(escape)) { index += 1; continue; }
      throw new Error();
    }
    const value: unknown = JSON.parse(raw);
    if (typeof value !== "string") throw new Error();
    return value;
  } catch { throw new Error(`${label} contains invalid TOML string syntax`); }
}

function parseValue(raw: string, label: string): TomlValue {
  const value = raw.trim();
  if (/^(?:0|[1-9]\d*)$/.test(value)) return Number(value);
  if (value.startsWith('"') && value.endsWith('"')) return parseString(value, label);
  if (value.startsWith("[") && value.endsWith("]")) {
    const inside = value.slice(1, -1).trim();
    if (inside === "") return [];
    const parts = inside.split(",").map((item) => item.trim()).filter(Boolean);
    return parts.map((item) => parseString(item, label));
  }
  throw new Error(`${label} contains unsupported or invalid TOML value`);
}

export function parseClosedToml(text: string, label: string): TomlTable {
  const root: TomlTable = {};
  const explicitTables = new Set<string>();
  let table = root;
  const lines = text.split(/\r?\n/);
  for (let index = 0; index < lines.length; index += 1) {
    const trimmed = lines[index]!.trim();
    if (trimmed === "" || trimmed.startsWith("#")) continue;
    const header = /^\[([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*)\]$/.exec(trimmed);
    if (header !== null) {
      if (explicitTables.has(header[1]!)) throw new Error(`${label} contains a duplicate TOML table`);
      explicitTables.add(header[1]!);
      table = root;
      for (const part of header[1]!.split(".")) {
        const existing = table[part];
        if (existing === undefined) table[part] = {};
        else if (typeof existing !== "object" || Array.isArray(existing)) throw new Error(`${label} has conflicting TOML tables`);
        table = table[part] as TomlTable;
      }
      continue;
    }
    const assignment = /^([a-z][a-z0-9_]*)\s*=\s*(.*)$/.exec(trimmed);
    if (assignment === null) throw new Error(`${label} contains unsupported TOML syntax`);
    const key = assignment[1]!;
    if (table[key] !== undefined) throw new Error(`${label} contains a duplicate field`);
    let raw = assignment[2]!;
    if (raw.startsWith('"""')) {
      let content = raw.slice(3);
      while (!content.includes('"""')) {
        index += 1;
        if (index >= lines.length) throw new Error(`${label} contains an incomplete multiline string`);
        content += `\n${lines[index]!}`;
      }
      const end = content.indexOf('"""');
      if (content.slice(end + 3).trim() !== "") throw new Error(`${label} contains trailing TOML content`);
      table[key] = content.slice(0, end);
      continue;
    }
    if (raw.startsWith("[") && !raw.includes("]")) {
      while (!raw.includes("]")) {
        index += 1;
        if (index >= lines.length) throw new Error(`${label} contains an incomplete array`);
        raw += `\n${lines[index]!.trim()}`;
      }
    }
    table[key] = parseValue(raw, label);
  }
  return root;
}

function idList(value: TomlValue | undefined, label: string, nonempty = false): string[] {
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string" || !ID.test(item))) throw new Error(`${label} must be an ID array`);
  const values = value as string[];
  if (nonempty && values.length === 0) throw new Error(`${label} must not be empty`);
  if (new Set(values).size !== values.length) throw new Error(`${label} contains duplicate IDs`);
  return values;
}

function text(value: TomlValue | undefined, label: string): string {
  if (typeof value !== "string" || value.trim() === "") throw new Error(`${label} must be nonempty text`);
  return value;
}

function table(value: TomlValue | undefined, label: string): TomlTable {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error(`${label} must be a table`);
  return value;
}

function safeIndexPath(value: TomlValue | undefined, label: string): string {
  const path = text(value, label);
  if (isAbsolute(path) || path.includes("\\") || normalize(path) !== path || path === ".." || path.startsWith(`..${sep}`) || path.split("/").some((part) => part === "" || part === "." || part === ".." || part === "~")) throw new Error(`${label} is an invalid manifest path`);
  return path;
}

async function safeIndexedFile(root: string, path: string, inventory: ReadonlyMap<string, string>, label: string): Promise<string> {
  const inventoryPath = `bundle/agent-governance/${path}`;
  if (!inventory.has(inventoryPath)) throw new Error(`${label} is missing from release inventory`);
  const absolute = join(root, path);
  const stat = await lstat(absolute);
  if (stat.isSymbolicLink() || !stat.isFile() || await realpath(absolute) !== absolute) throw new Error(`${label} must be a canonical regular non-symlink file`);
  return readFile(absolute, "utf8");
}

function validateVocabulary(catalog: TomlTable, name: "triggers" | "policy_tags" | "scopes"): Set<string> {
  exact(catalog, ["schema_version", name], `${name} catalog`);
  if (catalog.schema_version !== 1) throw new Error(`${name} catalog schema is invalid`);
  const entries = table(catalog[name], `${name} entries`);
  if (Object.keys(entries).length === 0) throw new Error(`${name} catalog is empty`);
  for (const [id, raw] of Object.entries(entries)) {
    if (!ID.test(id)) throw new Error(`${name} contains an invalid ID`);
    const entry = table(raw, `${name}.${id}`);
    exact(entry, ["label", "description"], `${name}.${id}`);
    text(entry.label, `${name}.${id}.label`); text(entry.description, `${name}.${id}.description`);
  }
  return new Set(Object.keys(entries));
}

function known(values: readonly string[], vocabulary: ReadonlySet<string>, label: string): void {
  if (values.some((value) => !vocabulary.has(value))) throw new Error(`${label} contains unknown references`);
}

export async function validateGovernanceContract(manifestRoot: string, manifestText: string, inventory: ReadonlyMap<string, string>): Promise<{ localRulesPath: string; referencedPaths: ReadonlySet<string> }> {
  const manifest = parseClosedToml(manifestText, "release manifest");
  exact(manifest, ["schema_version", "local_rules", "catalogs", "routing", "modules", "roles"], "release manifest");
  if (manifest.schema_version !== 2) throw new Error("release manifest schema is invalid");
  const localRules = safeIndexPath(manifest.local_rules, "release manifest local rules path");
  if (!/\.md$/i.test(localRules)) throw new Error("release manifest local rules path is invalid");

  const catalogs = table(manifest.catalogs, "release manifest catalogs");
  exact(catalogs, CATALOGS, "release manifest catalogs");
  const parsed = new Map<string, TomlTable>();
  const referencedPaths = new Set<string>();
  for (const name of CATALOGS) {
    const path = safeIndexPath(catalogs[name], `release manifest ${name} catalog`);
    referencedPaths.add(path);
    parsed.set(name, parseClosedToml(await safeIndexedFile(manifestRoot, path, inventory, `${name} catalog`), `${name} catalog`));
  }
  const triggers = validateVocabulary(parsed.get("triggers")!, "triggers");
  const policyTags = validateVocabulary(parsed.get("policy_tags")!, "policy_tags");
  const scopes = validateVocabulary(parsed.get("scopes")!, "scopes");

  const toolCatalog = parsed.get("tools")!;
  exact(toolCatalog, ["schema_version", "tools"], "tools catalog");
  if (toolCatalog.schema_version !== 1) throw new Error("tools catalog schema is invalid");
  const tools = table(toolCatalog.tools, "tools entries");
  if (Object.keys(tools).length === 0) throw new Error("tools catalog is empty");
  const requiredToolTriggers = new Set<string>(["tool_selection"]);
  for (const [id, raw] of Object.entries(tools)) {
    if (!ID.test(id)) throw new Error("tools catalog contains an invalid ID");
    const tool = table(raw, `tools.${id}`); exact(tool, TOOL_FIELDS, `tools.${id}`);
    for (const field of ["name", "purpose", "evidence", "fallback", "constraints"] as const) text(tool[field], `tools.${id}.${field}`);
    const required = idList(tool.required_on, `tools.${id}.required_on`); known(required, triggers, `tools.${id}.required_on`); required.forEach((value) => requiredToolTriggers.add(value));
    known(idList(tool.useful_on, `tools.${id}.useful_on`), triggers, `tools.${id}.useful_on`);
    known(idList(tool.policy_tags, `tools.${id}.policy_tags`), policyTags, `tools.${id}.policy_tags`);
    known(idList(tool.scopes, `tools.${id}.scopes`), scopes, `tools.${id}.scopes`);
  }

  const routing = table(manifest.routing, "release manifest routing"); exact(routing, ["unknown", "ambiguous"], "release manifest routing");
  if (routing.unknown !== "block" || routing.ambiguous !== "block") throw new Error("release manifest routing must fail closed");
  const modules = table(manifest.modules, "release manifest modules");
  if (Object.keys(modules).length === 0) throw new Error("release manifest modules are empty");
  const dependencies = new Map<string, string[]>();
  for (const [id, raw] of Object.entries(modules)) {
    if (!ID.test(id)) throw new Error("release manifest contains an invalid module ID");
    const module = table(raw, `modules.${id}`); exact(module, MODULE_FIELDS, `modules.${id}`);
    const path = safeIndexPath(module.path, `modules.${id}.path`); referencedPaths.add(path); await safeIndexedFile(manifestRoot, path, inventory, `module ${id}`);
    known(idList(module.triggers, `modules.${id}.triggers`, true), triggers, `modules.${id}.triggers`);
    dependencies.set(id, idList(module.dependencies, `modules.${id}.dependencies`));
  }
  const moduleIds = new Set(dependencies.keys());
  for (const [id, values] of dependencies) known(values, moduleIds, `modules.${id}.dependencies`);
  const visited = new Set<string>(); const visiting = new Set<string>();
  const visit = (id: string): void => { if (visiting.has(id)) throw new Error("release manifest module dependencies are cyclic"); if (visited.has(id)) return; visiting.add(id); for (const dependency of dependencies.get(id)!) visit(dependency); visiting.delete(id); visited.add(id); };
  moduleIds.forEach(visit);
  const toolRouting = table(modules.tool_routing, "release manifest tool_routing module");
  const routed = new Set(idList(toolRouting.triggers, "modules.tool_routing.triggers"));
  if (routed.size !== requiredToolTriggers.size || [...requiredToolTriggers].some((value) => !routed.has(value))) throw new Error("release manifest tool routing is incomplete");

  const roles = table(manifest.roles, "release manifest roles");
  if (Object.keys(roles).length === 0) throw new Error("release manifest roles are empty");
  for (const [id, raw] of Object.entries(roles)) {
    if (!ID.test(id)) throw new Error("release manifest contains an invalid role ID");
    const role = table(raw, `roles.${id}`); exact(role, ROLE_FIELDS, `roles.${id}`);
    const path = safeIndexPath(role.path, `roles.${id}.path`); referencedPaths.add(path); await safeIndexedFile(manifestRoot, path, inventory, `role ${id}`);
    known(idList(role.triggers, `roles.${id}.triggers`, true), triggers, `roles.${id}.triggers`);
    known(idList(role.modules, `roles.${id}.modules`, true), moduleIds, `roles.${id}.modules`);
  }
  return { localRulesPath: localRules, referencedPaths };
}
