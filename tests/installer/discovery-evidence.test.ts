import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import { mkdir, mkdtemp, realpath, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { analyzePackageMetadata } from "../../src/discovery/package-metadata.ts";
import { analyzeSqliteSchema } from "../../src/discovery/sqlite.ts";
import { analyzeStructuredFile } from "../../src/discovery/structured.ts";
import type { DiscoveryLimits, EvidenceRecord } from "../../src/discovery/types.ts";

const LIMITS: DiscoveryLimits = Object.freeze({
  maxDepth: 4,
  maxFiles: 64,
  maxEntries: 64,
  maxFileBytes: 8_192,
  maxSqliteObjects: 8,
  maxSqliteColumns: 8,
  maxDurationMs: 1_000,
  maxMetadataLength: 48,
});

function serialized(records: readonly EvidenceRecord[]): string {
  return JSON.stringify(records);
}

async function canonicalTemporary(prefix: string): Promise<string> {
  return realpath(await mkdtemp(join(tmpdir(), prefix)));
}

test("structured analysis emits bounded sanitized keys for JSON, TOML, and plist without values", async () => {
  const root = await canonicalTemporary("agent-governance-structured-");
  const secret = "VALUE-MUST-NEVER-LEAVE-THE-FILE";
  try {
    const fixtures = [
      ["runtime.json", JSON.stringify({ transport: secret, command: secret, nested: { providers: [secret] } })],
      ["runtime.toml", `transport = "${secret}"\ncommand = "${secret}"\n[models]\nprimary = "${secret}"\n`],
      [
        "runtime.plist",
        `<?xml version="1.0"?><plist><dict><key>transport</key><string>${secret}</string><key>bad\u0007key</key><string>${secret}</string></dict></plist>`,
      ],
    ] as const;

    for (const [name, content] of fixtures) {
      const path = join(root, name);
      await writeFile(path, content);
      const records = await analyzeStructuredFile(path, LIMITS);
      const output = serialized(records);
      assert.equal(records.length > 0, true, name);
      assert.equal(output.includes(secret), false, name);
      assert.doesNotMatch(output, /[\u0000-\u001f\u007f-\u009f]/u, name);
      assert.equal(records.every(({ metadata }) => metadata.length <= LIMITS.maxEntries), true, name);
      assert.equal(records.every(({ metadata }) => metadata.every((item) => item.length <= LIMITS.maxMetadataLength)), true, name);
    }
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("structured analysis rejects malformed, oversized, over-deep, over-entry, and symlink inputs", async () => {
  const root = await canonicalTemporary("agent-governance-structured-limits-");
  try {
    const malformed = join(root, "malformed.json");
    const oversized = join(root, "oversized.json");
    const deep = join(root, "deep.json");
    const entries = join(root, "entries.json");
    const link = join(root, "linked.json");
    await writeFile(malformed, "{");
    await writeFile(oversized, JSON.stringify({ state: "x".repeat(256) }));
    await writeFile(deep, JSON.stringify({ state: { a: { b: { c: { d: true } } } } }));
    await writeFile(entries, JSON.stringify({ state: { a: 1, b: 2, c: 3, d: 4 } }));
    await symlink(entries, link);

    await assert.rejects(() => analyzeStructuredFile(malformed, LIMITS), /malformed|invalid/i);
    await assert.rejects(
      () => analyzeStructuredFile(oversized, { ...LIMITS, maxFileBytes: 32 }),
      /size|large|limit/i,
    );
    const deepRecords = await analyzeStructuredFile(deep, { ...LIMITS, maxDepth: 2 });
    assert.equal(deepRecords.every(({ status }) => status === "INCOMPLETE"), true);
    const entryRecords = await analyzeStructuredFile(entries, { ...LIMITS, maxEntries: 2 });
    assert.equal(entryRecords.every(({ status }) => status === "INCOMPLETE"), true);
    await assert.rejects(() => analyzeStructuredFile(link, LIMITS), /symlink|canonical/i);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("structured analysis rejects an unclosed plist key instead of accepting partial metadata", async () => {
  const root = await canonicalTemporary("agent-governance-plist-malformed-");
  const path = join(root, "malformed.plist");
  try {
    await writeFile(path, "<plist><dict><key>state</dict></plist>");
    await assert.rejects(() => analyzeStructuredFile(path, LIMITS), /malformed/i);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("package metadata stays local, bounded, value-free, and never stronger than uncertain evidence", async () => {
  const root = await canonicalTemporary("agent-governance-package-metadata-");
  const path = join(root, "package.json");
  const secret = "PACKAGE-VALUE-MUST-NOT-ESCAPE";
  try {
    await writeFile(path, JSON.stringify({
      name: secret,
      bin: { launcher: secret },
      engines: { node: secret },
      dependencies: { dependency: secret },
      scripts: { start: secret },
    }));
    const records = await analyzePackageMetadata(path, LIMITS);
    assert.equal(records.length, 1);
    assert.equal(records[0]?.family, "package_metadata");
    assert.equal(records[0]?.strength, "weak");
    assert.equal(serialized(records).includes(secret), false);
    assert.equal(records[0]!.metadata.length <= LIMITS.maxEntries, true);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("SQLite analysis opens read-only, inspects only bounded schema metadata, and closes", async () => {
  const root = await canonicalTemporary("agent-governance-sqlite-schema-");
  const path = join(root, "state.sqlite");
  const secret = "ROW-VALUE-MUST-NOT-ESCAPE";
  const database = new DatabaseSync(path);
  database.exec("CREATE TABLE sessions (id INTEGER PRIMARY KEY, payload TEXT, created_at TEXT)");
  database.prepare("INSERT INTO sessions(payload, created_at) VALUES (?, ?)").run(secret, secret);
  database.close();

  const originalPrepare = DatabaseSync.prototype.prepare;
  const originalClose = DatabaseSync.prototype.close;
  const statements: string[] = [];
  let closes = 0;
  let readOnlyVerified = false;
  DatabaseSync.prototype.prepare = function prepare(sql: string) {
    statements.push(sql);
    if (!readOnlyVerified) {
      readOnlyVerified = true;
      assert.throws(() => this.exec("CREATE TABLE forbidden_write (id INTEGER)"), /readonly/i);
    }
    return originalPrepare.call(this, sql);
  };
  DatabaseSync.prototype.close = function close() {
    closes += 1;
    return originalClose.call(this);
  };

  try {
    const records = await analyzeSqliteSchema(path, LIMITS);
    assert.equal(readOnlyVerified, true);
    assert.equal(closes, 1);
    assert.equal(statements.length > 0, true);
    assert.equal(statements.every((sql) => /sqlite_schema|pragma_table_info/i.test(sql)), true);
    assert.equal(statements.some((sql) => /select\s+.+\s+from\s+sessions/i.test(sql)), false);
    assert.equal(serialized(records).includes(secret), false);
    assert.equal(records.every(({ metadata }) => metadata.length <= LIMITS.maxSqliteColumns + LIMITS.maxSqliteObjects), true);
  } finally {
    DatabaseSync.prototype.prepare = originalPrepare;
    DatabaseSync.prototype.close = originalClose;
    await rm(root, { recursive: true, force: true });
  }
});

test("SQLite analysis applies object and column budgets and closes after a schema-query failure", async () => {
  const root = await canonicalTemporary("agent-governance-sqlite-limits-");
  const path = join(root, "state.sqlite");
  const database = new DatabaseSync(path);
  database.exec("CREATE TABLE state (a TEXT, b TEXT, c TEXT); CREATE TABLE history (id INTEGER)");
  database.close();

  const bounded = await analyzeSqliteSchema(path, {
    ...LIMITS,
    maxSqliteObjects: 1,
    maxSqliteColumns: 1,
  });
  assert.equal(bounded.every(({ status }) => status === "INCOMPLETE"), true);
  assert.equal(bounded.every(({ metadata }) => metadata.length <= 2), true);

  const originalPrepare = DatabaseSync.prototype.prepare;
  const originalClose = DatabaseSync.prototype.close;
  let closes = 0;
  DatabaseSync.prototype.prepare = function prepare() {
    throw new Error("synthetic schema failure");
  };
  DatabaseSync.prototype.close = function close() {
    closes += 1;
    return originalClose.call(this);
  };
  try {
    await assert.rejects(() => analyzeSqliteSchema(path, LIMITS), /schema failure/i);
    assert.equal(closes, 1);
  } finally {
    DatabaseSync.prototype.prepare = originalPrepare;
    DatabaseSync.prototype.close = originalClose;
    await rm(root, { recursive: true, force: true });
  }
});

test("SQLite analysis rejects malformed database files", async () => {
  const root = await canonicalTemporary("agent-governance-sqlite-malformed-");
  const path = join(root, "malformed.sqlite");
  try {
    await mkdir(root, { recursive: true });
    await writeFile(path, "not a sqlite database");
    await assert.rejects(() => analyzeSqliteSchema(path, LIMITS), /sqlite|database|malformed/i);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
