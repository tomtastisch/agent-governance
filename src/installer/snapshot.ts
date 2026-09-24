import { createHash } from "node:crypto";
import { access, lstat, open, readFile } from "node:fs/promises";
import { constants } from "node:fs";
import type { FileSnapshotIdentity } from "../native-filesystem.ts";

export async function exists(path: string): Promise<boolean> { try { await access(path); return true; } catch (error) { if ((error as NodeJS.ErrnoException).code === "ENOENT") return false; throw error; } }

export async function optionalBytes(path: string): Promise<Buffer | undefined> { try { const stat = await lstat(path); if (stat.isSymbolicLink() || !stat.isFile()) throw new Error(`unsafe regular file: ${path}`); return await readFile(path); } catch (error) { if ((error as NodeJS.ErrnoException).code === "ENOENT") return undefined; throw error; } }

export async function requiredBytes(path: string, label: string): Promise<Buffer> { const value = await optionalBytes(path); if (value === undefined) throw new Error(`${label} is missing`); return value; }

export async function requiredSnapshot(path: string, label: string): Promise<{ readonly bytes: Buffer; readonly identity: FileSnapshotIdentity }> { const handle = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW); try { const before = await handle.stat({ bigint: true }); if (!before.isFile()) throw new Error(`${label} is not a regular file`); const bytes = await handle.readFile(); const after = await handle.stat({ bigint: true }); if (!sameFileSnapshot(before, after)) throw new Error(`${label} changed while reading`); return { bytes, identity: { device: before.dev, inode: before.ino, mode: Number(before.mode), size: before.size, mtimeNs: before.mtimeNs, ctimeNs: before.ctimeNs } }; } finally { await handle.close(); } }

export function sameFileIdentity(left: { dev: bigint; ino: bigint }, right: { dev: bigint; ino: bigint }): boolean { return left.dev === right.dev && left.ino === right.ino; }

export function sameFileSnapshot(left: { dev: bigint; ino: bigint; size: bigint; mtimeNs: bigint; ctimeNs: bigint }, right: { dev: bigint; ino: bigint; size: bigint; mtimeNs: bigint; ctimeNs: bigint }): boolean { return sameFileIdentity(left, right) && left.size === right.size && left.mtimeNs === right.mtimeNs && left.ctimeNs === right.ctimeNs; }

export function matchesSnapshot(live: Buffer | undefined, expected: Buffer | undefined): boolean { return live === undefined ? expected === undefined : expected !== undefined && live.equals(expected); }

export function digest(value: Buffer): string { return createHash("sha256").update(value).digest("hex"); }

export function parseObject<T>(bytes: Buffer, keys: readonly string[], label: string): T { let value: unknown; try { value = JSON.parse(bytes.toString("utf8")); } catch { throw new Error(`${label} is invalid JSON`); } if (typeof value !== "object" || value === null || Array.isArray(value) || Object.keys(value).sort().join("\0") !== [...keys].sort().join("\0")) throw new Error(`${label} has invalid schema`); return value as T; }
