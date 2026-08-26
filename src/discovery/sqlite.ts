import { lstat, realpath } from "node:fs/promises";
import { isAbsolute, resolve } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { evidenceForStructure, sanitizeDisplay } from "./structured.ts";
import type { DiscoveryLimits, EvidenceRecord } from "./types.ts";

async function canonicalSqlitePath(path: string): Promise<string> {
  if (!isAbsolute(path)) throw new Error("SQLite path must be absolute");
  const normalized = resolve(path);
  const metadata = await lstat(normalized);
  if (metadata.isSymbolicLink() || !metadata.isFile()) {
    throw new Error("SQLite path must be a regular non-symlink file");
  }
  if ((await realpath(normalized)) !== normalized) {
    throw new Error("SQLite path must be canonical and contain no symlinks");
  }
  return normalized;
}

function validateLimits(limits: DiscoveryLimits): void {
  for (const [name, value] of Object.entries(limits)) {
    if (!Number.isSafeInteger(value) || value <= 0) throw new Error(`${name} must be a positive integer`);
  }
}

export async function analyzeSqliteSchema(
  path: string,
  limits: DiscoveryLimits,
): Promise<readonly EvidenceRecord[]> {
  validateLimits(limits);
  const canonicalPath = await canonicalSqlitePath(path);
  let database: DatabaseSync | undefined;
  try {
    database = new DatabaseSync(canonicalPath, { readOnly: true });
    const objects = database.prepare(
      "SELECT type, name FROM sqlite_schema " +
      "WHERE type IN ('table', 'view', 'index', 'trigger') AND name NOT LIKE 'sqlite_%' " +
      "ORDER BY type, name LIMIT ?",
    ).all(limits.maxSqliteObjects);
    let incomplete = objects.length >= limits.maxSqliteObjects;
    let remainingColumns = limits.maxSqliteColumns;
    const matchKeys: string[] = [];
    const metadata: string[] = [];

    for (const object of objects) {
      if (typeof object.type !== "string" || typeof object.name !== "string") {
        throw new Error("SQLite schema returned invalid metadata");
      }
      const type = sanitizeDisplay(object.type, limits.maxMetadataLength);
      const name = sanitizeDisplay(object.name, limits.maxMetadataLength);
      matchKeys.push(type, name);
      metadata.push(`${type}:${name}`);
      if ((type !== "table" && type !== "view") || remainingColumns === 0) continue;
      const columns = database.prepare(
        "SELECT name, type FROM pragma_table_info(?) ORDER BY cid LIMIT ?",
      ).all(object.name, remainingColumns);
      if (columns.length >= remainingColumns) incomplete = true;
      for (const column of columns) {
        if (typeof column.name !== "string" || typeof column.type !== "string") {
          throw new Error("SQLite schema returned invalid column metadata");
        }
        const columnName = sanitizeDisplay(column.name, limits.maxMetadataLength);
        const columnType = sanitizeDisplay(column.type, limits.maxMetadataLength);
        matchKeys.push(columnName);
        metadata.push(`column:${columnName}:${columnType}`);
      }
      remainingColumns -= columns.length;
    }

    return evidenceForStructure(
      canonicalPath,
      "sqlite_schema",
      matchKeys,
      metadata,
      incomplete ? "INCOMPLETE" : "COMPLETE",
      limits,
    );
  } finally {
    database?.close();
  }
}
