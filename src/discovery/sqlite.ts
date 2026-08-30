import { lstat, realpath } from "node:fs/promises";
import { isAbsolute, resolve } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { evidenceForStructure, sanitizeDisplay } from "./structured.ts";
import type { DiscoveryCatalog, DiscoveryLimits, EvidenceRecord } from "./types.ts";

interface SqlitePathIdentity {
  readonly path: string;
  readonly device: number;
  readonly inode: number;
}

async function canonicalSqlitePath(path: string): Promise<SqlitePathIdentity> {
  if (!isAbsolute(path)) throw new Error("SQLite path must be absolute");
  const normalized = resolve(path);
  const metadata = await lstat(normalized);
  if (metadata.isSymbolicLink() || !metadata.isFile()) {
    throw new Error("SQLite path must be a regular non-symlink file");
  }
  if ((await realpath(normalized)) !== normalized) {
    throw new Error("SQLite path must be canonical and contain no symlinks");
  }
  return Object.freeze({ path: normalized, device: metadata.dev, inode: metadata.ino });
}

async function assertSqlitePathIdentity(path: string | null, expected: SqlitePathIdentity): Promise<void> {
  if (path !== expected.path) throw new Error("SQLite path identity changed after opening");
  try {
    const metadata = await lstat(expected.path);
    if (
      metadata.isSymbolicLink() ||
      !metadata.isFile() ||
      metadata.dev !== expected.device ||
      metadata.ino !== expected.inode ||
      (await realpath(expected.path)) !== expected.path
    ) {
      throw new Error("SQLite path identity changed after opening");
    }
  } catch (cause) {
    if (cause instanceof Error && cause.message === "SQLite path identity changed after opening") throw cause;
    throw new Error("SQLite path identity changed after opening", { cause });
  }
}

function validateLimits(limits: DiscoveryLimits): void {
  for (const [name, value] of Object.entries(limits)) {
    if (!Number.isSafeInteger(value) || value <= 0) throw new Error(`${name} must be a positive integer`);
  }
}

export async function analyzeSqliteSchema(
  path: string,
  limits: DiscoveryLimits,
  catalog?: DiscoveryCatalog,
): Promise<readonly EvidenceRecord[]> {
  validateLimits(limits);
  const identity = await canonicalSqlitePath(path);
  let database: DatabaseSync | undefined;
  try {
    database = new DatabaseSync(identity.path, { readOnly: true });
    await assertSqlitePathIdentity(database.location("main"), identity);
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
      identity.path,
      "sqlite_schema",
      matchKeys,
      metadata,
      incomplete ? "INCOMPLETE" : "COMPLETE",
      limits,
      catalog,
    );
  } finally {
    database?.close();
  }
}
