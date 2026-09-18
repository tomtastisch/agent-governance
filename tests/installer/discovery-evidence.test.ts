import assert from "node:assert/strict";
import { constants, renameSync, symlinkSync } from "node:fs";
import fsPromises from "node:fs/promises";
import { DatabaseSync } from "node:sqlite";
import { appendFile, mkdir, mkdtemp, open, realpath, rm, symlink, writeFile } from "node:fs/promises";
import { syncBuiltinESMExports } from "node:module";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { analyzePackageMetadata } from "../../src/discovery/package-metadata.ts";
import { analyzeSqliteSchema } from "../../src/discovery/sqlite.ts";
import { analyzeStructuredFile, readBoundedTextFile } from "../../src/discovery/structured.ts";
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

test("plist evidence accepts dictionary keys and rejects keys outside dictionary hierarchy", async () => {
  const root = await canonicalTemporary("agent-governance-plist-hierarchy-");
  try {
    const valid = join(root, "valid.plist");
    const direct = join(root, "direct.plist");
    const array = join(root, "array.plist");
    await writeFile(valid, "<plist><dict><key>transport</key><string>local</string><key>state</key><dict><key>sessions</key><array></array></dict></dict></plist>");
    await writeFile(direct, "<plist><key>transport</key><string>local</string></plist>");
    await writeFile(array, "<plist><array><key>transport</key><string>local</string></array></plist>");

    assert.equal((await analyzeStructuredFile(valid, LIMITS)).length > 0, true);
    await assert.rejects(() => analyzeStructuredFile(direct, LIMITS), /malformed/i);
    await assert.rejects(() => analyzeStructuredFile(array, LIMITS), /malformed/i);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("plist evidence rejects commented signals, malformed entities, and excessive nesting", async () => {
  const root = await canonicalTemporary("agent-governance-plist-structure-");
  try {
    const commented = join(root, "commented.plist");
    const malformedEntity = join(root, "entity.plist");
    const deep = join(root, "deep.plist");
    await writeFile(commented, "<plist><dict><!-- <key>transport</key><string>local</string> --></dict></plist>");
    await writeFile(malformedEntity, "<plist><dict><key>state</key><string>bare & invalid</string></dict></plist>");
    await writeFile(deep, `<plist>${"<array>".repeat(32)}<dict></dict>${"</array>".repeat(32)}</plist>`);

    await assert.rejects(() => analyzeStructuredFile(commented, LIMITS), /malformed/i);
    await assert.rejects(() => analyzeStructuredFile(malformedEntity, LIMITS), /malformed/i);
    await assert.rejects(() => analyzeStructuredFile(deep, { ...LIMITS, maxDepth: 4 }), /malformed|depth/i);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("a regular file replaced by a FIFO is opened nonblocking, rejected, and closed", async (t) => {
  if (process.platform === "win32") {
    t.skip("POSIX FIFO regression");
    return;
  }
  const root = await canonicalTemporary("agent-governance-fifo-structured-");
  const path = join(root, "replaced.json");
  const original = join(root, "original.json");
  await writeFile(path, '{"state":"ok"}');
  const originalRealpath = fsPromises.realpath;
  const originalOpen = fsPromises.open;
  let replaced = false;
  let closeCalls = 0;
  fsPromises.realpath = (async (value: Parameters<typeof originalRealpath>[0], options?: Parameters<typeof originalRealpath>[1]) => {
    const canonical = await originalRealpath(value, options as never);
    if (!replaced && canonical === path) {
      replaced = true;
      renameSync(path, original);
      const created = spawnSync("mkfifo", [path], { encoding: "utf8" });
      assert.equal(created.status, 0, created.stderr);
    }
    return canonical;
  }) as typeof originalRealpath;
  fsPromises.open = (async (...args: Parameters<typeof originalOpen>) => {
    assert.equal(Number(args[1]) & constants.O_NONBLOCK, constants.O_NONBLOCK);
    const handle = await originalOpen(...args);
    const close = handle.close.bind(handle);
    handle.close = async () => {
      closeCalls += 1;
      await close();
    };
    return handle;
  }) as typeof originalOpen;
  syncBuiltinESMExports();

  try {
    await assert.rejects(() => readBoundedTextFile(path, LIMITS), /changed type|regular/i);
    assert.equal(replaced, true);
    assert.equal(closeCalls, 1);
  } finally {
    fsPromises.realpath = originalRealpath;
    fsPromises.open = originalOpen;
    syncBuiltinESMExports();
    await rm(root, { recursive: true, force: true });
  }
});

test("a file that grows after opening is rejected after at most one bounded overflow byte", async () => {
  const root = await canonicalTemporary("agent-governance-growing-structured-");
  const path = join(root, "growing.json");
  const probe = await open(path, "w+");
  const prototype = Object.getPrototypeOf(probe) as object;
  const statDescriptor = Object.getOwnPropertyDescriptor(prototype, "stat")!;
  const readDescriptor = Object.getOwnPropertyDescriptor(prototype, "read")!;
  const readFileDescriptor = Object.getOwnPropertyDescriptor(prototype, "readFile")!;
  const originalStat = statDescriptor.value as (...args: unknown[]) => Promise<unknown>;
  const originalRead = readDescriptor.value as (...args: unknown[]) => Promise<{ bytesRead: number }>;
  const originalReadFile = readFileDescriptor.value as (...args: unknown[]) => Promise<Buffer>;
  await probe.close();
  await writeFile(path, '{"state":"ok"}');
  let grew = false;
  let consumedBytes = 0;

  Object.defineProperty(prototype, "stat", {
    ...statDescriptor,
    value: async function stat(this: unknown, ...args: unknown[]): Promise<unknown> {
      const metadata = await originalStat.apply(this, args);
      if (!grew) {
        grew = true;
        await appendFile(path, "x".repeat(1_024));
      }
      return metadata;
    },
  });
  Object.defineProperty(prototype, "readFile", {
    ...readFileDescriptor,
    value: async function readFile(this: unknown, ...args: unknown[]): Promise<Buffer> {
      const bytes = await originalReadFile.apply(this, args);
      consumedBytes = bytes.byteLength;
      return bytes;
    },
  });
  Object.defineProperty(prototype, "read", {
    ...readDescriptor,
    value: async function read(this: unknown, ...args: unknown[]): Promise<{ bytesRead: number }> {
      const result = await originalRead.apply(this, args);
      consumedBytes += result.bytesRead;
      return result;
    },
  });

  try {
    await assert.rejects(
      () => readBoundedTextFile(path, { ...LIMITS, maxFileBytes: 32 }),
      /size|large|limit/i,
    );
    assert.equal(grew, true);
    assert.equal(consumedBytes <= 33, true, `consumed ${consumedBytes} bytes`);
  } finally {
    Object.defineProperty(prototype, "stat", statDescriptor);
    Object.defineProperty(prototype, "read", readDescriptor);
    Object.defineProperty(prototype, "readFile", readFileDescriptor);
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

test("SQLite analysis revalidates filesystem identity after the path-based open and closes on replacement", async () => {
  const root = await canonicalTemporary("agent-governance-sqlite-identity-");
  const path = join(root, "state.sqlite");
  const moved = join(root, "state-opened.sqlite");
  const replacement = join(root, "replacement.sqlite");
  for (const databasePath of [path, replacement]) {
    const database = new DatabaseSync(databasePath);
    database.exec("CREATE TABLE state (id INTEGER)");
    database.close();
  }

  const originalLocation = DatabaseSync.prototype.location;
  const originalClose = DatabaseSync.prototype.close;
  let swapped = false;
  let closes = 0;
  DatabaseSync.prototype.location = function location(databaseName?: string) {
    if (!swapped) {
      swapped = true;
      renameSync(path, moved);
      symlinkSync(replacement, path);
    }
    return databaseName === undefined
      ? originalLocation.call(this)
      : originalLocation.call(this, databaseName);
  };
  DatabaseSync.prototype.close = function close() {
    closes += 1;
    return originalClose.call(this);
  };

  try {
    await assert.rejects(() => analyzeSqliteSchema(path, LIMITS), /canonical|changed|identity|symlink/i);
    assert.equal(swapped, true);
    assert.equal(closes, 1);
  } finally {
    DatabaseSync.prototype.location = originalLocation;
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
