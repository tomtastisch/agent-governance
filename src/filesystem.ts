import { lstat, realpath } from "node:fs/promises";
import { dirname, isAbsolute, relative, resolve, sep } from "node:path";

export type PathExpectation = "file" | "directory" | "missing" | "any";

export interface PathIdentity {
  readonly device: bigint;
  readonly inode: bigint;
  readonly mode: number;
}

function contained(path: string, root: string): boolean {
  const rel = relative(root, path);
  return rel === "" || (!rel.startsWith(`..${sep}`) && rel !== ".." && !isAbsolute(rel));
}

export async function validateAllowedPath(
  path: string,
  allowedRoot: string,
  expectation: PathExpectation,
): Promise<void> {
  if (!isAbsolute(path) || !isAbsolute(allowedRoot)) {
    throw new Error("path and allowed root must be absolute");
  }
  const root = resolve(allowedRoot);
  const target = resolve(path);
  if (!contained(target, root)) {
    throw new Error("path is outside allowed root");
  }

  const rootStat = await lstat(root);
  if (rootStat.isSymbolicLink() || !rootStat.isDirectory()) {
    throw new Error("allowed root must be a non-symlink directory");
  }
  if ((await realpath(root)) !== root) {
    throw new Error("allowed root contains a symlink");
  }

  const rel = relative(root, target);
  const components = rel === "" ? [] : rel.split(sep);
  let current = root;
  let finalStat: Awaited<ReturnType<typeof lstat>> | undefined;
  for (const [index, component] of components.entries()) {
    current = resolve(current, component);
    try {
      const stat = await lstat(current, { bigint: true });
      if (stat.isSymbolicLink()) {
        throw new Error("path contains a symlink");
      }
      if (index < components.length - 1 && !stat.isDirectory()) {
        throw new Error("path intermediate component is not a directory");
      }
      if (index === components.length - 1) {
        finalStat = stat;
      }
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") {
        if (index !== components.length - 1 || expectation !== "missing") {
          throw new Error("required path component is missing");
        }
        finalStat = undefined;
        break;
      }
      throw error;
    }
  }

  if (expectation === "missing" && finalStat !== undefined) {
    throw new Error("path must be missing");
  }
  if (expectation === "file" && (finalStat === undefined || !finalStat.isFile())) {
    throw new Error("path must be a regular file");
  }
  if (expectation === "directory" && (finalStat === undefined || !finalStat.isDirectory())) {
    throw new Error("path must be a directory");
  }
}

export async function captureIdentity(path: string): Promise<PathIdentity> {
  const stat = await lstat(path, { bigint: true });
  if (stat.isSymbolicLink()) {
    throw new Error("cannot capture symlink identity");
  }
  return { device: stat.dev, inode: stat.ino, mode: Number(stat.mode) };
}

export async function assertIdentity(path: string, expected: PathIdentity): Promise<void> {
  const actual = await captureIdentity(path);
  if (
    actual.device !== expected.device ||
    actual.inode !== expected.inode ||
    actual.mode !== expected.mode
  ) {
    throw new Error(`path identity changed: ${dirname(path)}`);
  }
}
