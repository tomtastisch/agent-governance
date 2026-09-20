import { isAbsolute, normalize, sep } from "node:path";

export type TomlValue = string | number | TomlValue[] | TomlTable;
export type TomlTable = { [key: string]: TomlValue };

export const ID = /^[a-z][a-z0-9_]*$/;

export function exact(table: TomlTable, expected: readonly string[], label: string): void {
  const actual = Object.keys(table).sort();
  const wanted = [...expected].sort();
  if (actual.join("\0") !== wanted.join("\0")) throw new Error(`${label} has missing or unknown fields`);
}

function parseString(raw: string, label: string): string {
  try {
    for (let index = 1; index < raw.length - 1; index += 1) {
      if (raw[index] !== "\\") continue;
      const escape = raw[index + 1];
      if (escape === "u" && /^[0-9A-Fa-f]{4}$/.test(raw.slice(index + 2, index + 6)) && !/^d[89a-f][0-9a-f]{2}$/i.test(raw.slice(index + 2, index + 6))) { index += 5; continue; }
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
      const multiline = content.slice(0, end);
      if (multiline.includes("\\")) throw new Error(`${label} contains unsupported or invalid TOML multiline escape syntax`);
      if (/[\u0000-\u0008\u000b-\u001f\u007f]/.test(multiline)) throw new Error(`${label} contains an invalid TOML control character`);
      table[key] = multiline;
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

export function table(value: TomlValue | undefined, label: string): TomlTable {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error(`${label} must be a table`);
  return value;
}

export function text(value: TomlValue | undefined, label: string): string {
  if (typeof value !== "string" || value.trim() === "") throw new Error(`${label} must be nonempty text`);
  return value;
}

export function idList(value: TomlValue | undefined, label: string, nonempty = false): string[] {
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string" || !ID.test(item))) throw new Error(`${label} must be an ID array`);
  const values = value as string[];
  if (nonempty && values.length === 0) throw new Error(`${label} must not be empty`);
  if (new Set(values).size !== values.length) throw new Error(`${label} contains duplicate IDs`);
  return values;
}

export function safeRelativePath(value: TomlValue | undefined, label: string): string {
  const path = text(value, label);
  if (isAbsolute(path) || path.includes("\\") || normalize(path) !== path || path === ".." || path.startsWith(`..${sep}`) || path.split("/").some((part) => part === "" || part === "." || part === ".." || part === "~")) throw new Error(`${label} is an invalid manifest path`);
  return path;
}
