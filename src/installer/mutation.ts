import { createHash } from "node:crypto";
import { access, lstat, open, readFile, realpath } from "node:fs/promises";
import { constants } from "node:fs";
import { basename, dirname, isAbsolute, join, relative } from "node:path";
import { assertIdentity, captureIdentity, type PathIdentity } from "../filesystem.ts";
import { secureCreateDirectory, secureCreateNoReplace, secureRemoveFile, secureWriteFile, type FileSnapshotIdentity } from "../native-filesystem.ts";

export class ConcurrentEntryChange extends Error {}

export async function exists(path: string): Promise<boolean> { try { await access(path); return true; } catch (error) { if ((error as NodeJS.ErrnoException).code === "ENOENT") return false; throw error; } }

export async function optionalBytes(path: string): Promise<Buffer | undefined> { try { const stat = await lstat(path); if (stat.isSymbolicLink() || !stat.isFile()) throw new Error(`unsafe regular file: ${path}`); return await readFile(path); } catch (error) { if ((error as NodeJS.ErrnoException).code === "ENOENT") return undefined; throw error; } }

export async function requiredBytes(path: string, label: string): Promise<Buffer> { const value = await optionalBytes(path); if (value === undefined) throw new Error(`${label} is missing`); return value; }

export async function requiredSnapshot(path: string, label: string): Promise<{ readonly bytes: Buffer; readonly identity: FileSnapshotIdentity }> { const handle = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW); try { const before = await handle.stat({ bigint: true }); if (!before.isFile()) throw new Error(`${label} is not a regular file`); const bytes = await handle.readFile(); const after = await handle.stat({ bigint: true }); if (!sameFileSnapshot(before, after)) throw new Error(`${label} changed while reading`); return { bytes, identity: { device: before.dev, inode: before.ino, mode: Number(before.mode), size: before.size, mtimeNs: before.mtimeNs, ctimeNs: before.ctimeNs } }; } finally { await handle.close(); } }

export function sameFileIdentity(left: { dev: bigint; ino: bigint }, right: { dev: bigint; ino: bigint }): boolean { return left.dev === right.dev && left.ino === right.ino; }

export function sameFileSnapshot(left: { dev: bigint; ino: bigint; size: bigint; mtimeNs: bigint; ctimeNs: bigint }, right: { dev: bigint; ino: bigint; size: bigint; mtimeNs: bigint; ctimeNs: bigint }): boolean { return sameFileIdentity(left, right) && left.size === right.size && left.mtimeNs === right.mtimeNs && left.ctimeNs === right.ctimeNs; }

export function digest(value: Buffer): string { return createHash("sha256").update(value).digest("hex"); }

export function matchesSnapshot(live: Buffer | undefined, expected: Buffer | undefined): boolean { return live === undefined ? expected === undefined : expected !== undefined && live.equals(expected); }

export function parseObject<T>(bytes: Buffer, keys: readonly string[], label: string): T { let value: unknown; try { value = JSON.parse(bytes.toString("utf8")); } catch { throw new Error(`${label} is invalid JSON`); } if (typeof value !== "object" || value === null || Array.isArray(value) || Object.keys(value).sort().join("\0") !== [...keys].sort().join("\0")) throw new Error(`${label} has invalid schema`); return value as T; }

export async function ensureDirectoryTree(ancestor: string, ancestorIdentity: PathIdentity, target: string): Promise<PathIdentity> { const rel = relative(ancestor, target); if (rel === "") { await assertIdentity(ancestor, ancestorIdentity); return ancestorIdentity; } if (isAbsolute(rel) || rel === ".." || rel.startsWith("../")) throw new Error("directory target is outside its bound ancestor"); let parent = ancestor; let parentIdentity = ancestorIdentity; for (const name of rel.split("/")) { const child = join(parent, name); try { await secureCreateDirectory({ directory: parent, name, directoryIdentity: parentIdentity }); } catch (error) { if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw error; } const stat = await lstat(child); if (stat.isSymbolicLink() || !stat.isDirectory() || await realpath(child) !== child) throw new Error(`unsafe symlink or non-canonical directory: ${child}`); parent = child; parentIdentity = await captureIdentity(child); } return parentIdentity; }

export async function atomicWrite(path: string, value: Buffer | string, parentIdentity: PathIdentity, expectedPrevious: Buffer): Promise<void> { const expected = Buffer.isBuffer(value) ? value : Buffer.from(value); const previous = await requiredSnapshot(path, "atomic write target"); if (!previous.bytes.equals(expectedPrevious)) throw new Error("atomic write preimage changed"); await secureWriteFile({ directory: dirname(path), name: basename(path), directoryIdentity: parentIdentity, objectIdentity: previous.identity }, expected); if (!(await readFile(path)).equals(expected)) throw new Error("atomic write readback failed"); }

export async function atomicRemove(path: string, parentIdentity: PathIdentity, expectedPrevious: Buffer): Promise<void> { const previous = await requiredSnapshot(path, "atomic remove target"); if (!previous.bytes.equals(expectedPrevious)) throw new Error("atomic remove preimage changed"); await secureRemoveFile({ directory: dirname(path), name: basename(path), directoryIdentity: parentIdentity, objectIdentity: previous.identity }); }

export async function atomicCreate(path: string, value: Buffer | string, parentIdentity: PathIdentity): Promise<void> { const expected = Buffer.isBuffer(value) ? value : Buffer.from(value); try { await secureCreateNoReplace({ directory: dirname(path), name: basename(path), directoryIdentity: parentIdentity }, expected); } catch (error) { if ((error as NodeJS.ErrnoException).code === "EEXIST") throw new ConcurrentEntryChange("entry no longer absent"); throw error; } if (!(await readFile(path)).equals(expected)) throw new Error("atomic create readback failed"); }
