import { closeSync, constants, fstatSync, lstatSync, openSync, readFileSync, realpathSync } from "node:fs";
import { open } from "node:fs/promises";
import type { PathIdentity } from "../filesystem.ts";
import type { CreatedDirectoryIdentity, FileSnapshotIdentity } from "../native-filesystem.ts";
import { sameFileSnapshot } from "./snapshot.ts";

export interface EntrySnapshot { readonly bytes: Buffer; readonly identity: FileSnapshotIdentity; }

export function assertMissing(path: string): void {
  try { lstatSync(path); } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return;
    throw error;
  }
  throw new Error("replacement requires an absent resource");
}

export function assertDirectory(path: string, expected: PathIdentity): void {
  const stat = lstatSync(path, { bigint: true });
  if (!stat.isDirectory() || realpathSync(path) !== path || stat.dev !== expected.device || stat.ino !== expected.inode || Number(stat.mode) !== expected.mode) throw new Error("replacement directory changed");
}

export function assertPrivateDirectory(path: string, expected: CreatedDirectoryIdentity): void {
  assertDirectory(path, expected);
  const stat = lstatSync(path, { bigint: true });
  if ((Number(stat.mode) & 0o7777) !== 0o700 || Number(stat.uid) !== expected.uid || expected.uid !== process.geteuid?.()) throw new Error("replacement directory is not private and owned");
}

export function entrySnapshot(path: string): EntrySnapshot {
  const fd = openSync(path, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
  try {
    const before = fstatSync(fd, { bigint: true });
    if (!before.isFile() || before.nlink !== 1n) throw new Error("unsafe replacement entry");
    const bytes = readFileSync(fd);
    const after = fstatSync(fd, { bigint: true });
    const live = lstatSync(path, { bigint: true });
    if (!sameFileSnapshot(before, after) || !sameFileSnapshot(after, live) || after.mode !== live.mode || live.nlink !== 1n || realpathSync(path) !== path) throw new Error("replacement entry changed");
    return { bytes, identity: { device: before.dev, inode: before.ino, mode: Number(before.mode), size: before.size, mtimeNs: before.mtimeNs, ctimeNs: before.ctimeNs } };
  } finally { closeSync(fd); }
}

export function assertEntry(path: string, expected: EntrySnapshot, renamed = false): void {
  const actual = entrySnapshot(path);
  const a = actual.identity;
  const e = expected.identity;
  if (a.device !== e.device || a.inode !== e.inode || a.mode !== e.mode || a.size !== e.size || a.mtimeNs !== e.mtimeNs || !renamed && a.ctimeNs !== e.ctimeNs || !actual.bytes.equals(expected.bytes)) throw new Error("replacement entry changed");
}

export async function syncDirectory(path: string, identity: PathIdentity): Promise<void> {
  assertDirectory(path, identity);
  const handle = await open(path, constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW);
  try {
    const stat = await handle.stat({ bigint: true });
    if (stat.dev !== identity.device || stat.ino !== identity.inode || Number(stat.mode) !== identity.mode) throw new Error("replacement directory changed");
    await handle.sync();
    assertDirectory(path, identity);
  } finally { await handle.close(); }
}
