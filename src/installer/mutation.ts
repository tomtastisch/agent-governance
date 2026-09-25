import { lstat, readFile, realpath } from "node:fs/promises";
import { basename, dirname, isAbsolute, join, relative } from "node:path";
import { ConcurrentEntryChange } from "../errors.ts";
import { assertIdentity, captureIdentity, type PathIdentity } from "../filesystem.ts";
import { secureCreateDirectory, secureCreateNoReplace, secureRemoveFile, secureWriteFile, type FileSnapshotIdentity } from "../native-filesystem.ts";
import { requiredSnapshot } from "./snapshot.ts";

export async function ensureDirectoryTree(ancestor: string, ancestorIdentity: PathIdentity, target: string): Promise<PathIdentity> { const rel = relative(ancestor, target); if (rel === "") { await assertIdentity(ancestor, ancestorIdentity); return ancestorIdentity; } if (isAbsolute(rel) || rel === ".." || rel.startsWith("../")) throw new Error("directory target is outside its bound ancestor"); let parent = ancestor; let parentIdentity = ancestorIdentity; for (const name of rel.split("/")) { const child = join(parent, name); try { await secureCreateDirectory({ directory: parent, name, directoryIdentity: parentIdentity }); } catch (error) { if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw error; } const stat = await lstat(child); if (stat.isSymbolicLink() || !stat.isDirectory() || await realpath(child) !== child) throw new Error(`unsafe symlink or non-canonical directory: ${child}`); parent = child; parentIdentity = await captureIdentity(child); } return parentIdentity; }

export async function atomicWrite(path: string, value: Buffer | string, parentIdentity: PathIdentity, expectedPrevious: Buffer, boundSnapshot?: FileSnapshotIdentity): Promise<void> {
  const expected = Buffer.isBuffer(value) ? value : Buffer.from(value);
  try {
    const previous = await requiredSnapshot(path, "atomic write target");
    if (!previous.bytes.equals(expectedPrevious)) throw new Error("atomic write preimage changed");
    // An entry's earlier ownership binding survives this helper's byte read and reaches
    // the native snapshot check. Equal content never authorizes adopting a new inode.
    await secureWriteFile({ directory: dirname(path), name: basename(path), directoryIdentity: parentIdentity, objectIdentity: boundSnapshot ?? previous.identity }, expected);
    if (!(await readFile(path)).equals(expected)) throw new Error("atomic write readback failed");
  } catch (error) {
    if (boundSnapshot !== undefined) throw new ConcurrentEntryChange("bound entry write failed; preserve live ownership");
    throw error;
  }
}

export async function atomicRemove(path: string, parentIdentity: PathIdentity, expectedPrevious: Buffer): Promise<void> { const previous = await requiredSnapshot(path, "atomic remove target"); if (!previous.bytes.equals(expectedPrevious)) throw new Error("atomic remove preimage changed"); await secureRemoveFile({ directory: dirname(path), name: basename(path), directoryIdentity: parentIdentity, objectIdentity: previous.identity }); }

export async function atomicCreate(path: string, value: Buffer | string, parentIdentity: PathIdentity): Promise<void> { const expected = Buffer.isBuffer(value) ? value : Buffer.from(value); try { await secureCreateNoReplace({ directory: dirname(path), name: basename(path), directoryIdentity: parentIdentity }, expected); } catch (error) { if ((error as NodeJS.ErrnoException).code === "EEXIST") throw new ConcurrentEntryChange("entry no longer absent"); throw error; } if (!(await readFile(path)).equals(expected)) throw new Error("atomic create readback failed"); }
