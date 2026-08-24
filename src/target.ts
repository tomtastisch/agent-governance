import { lstat, realpath } from "node:fs/promises";
import { dirname, isAbsolute, join, normalize, relative, resolve, sep } from "node:path";

import { captureIdentity, type PathIdentity } from "./filesystem.ts";

export interface TargetInspection {
  readonly targetRoot: string;
  readonly entryPath: string;
  readonly installationRoot: string;
  readonly targetIdentity: PathIdentity;
  readonly entryParentIdentity: PathIdentity;
  readonly entryIdentity?: PathIdentity;
  readonly installationAncestorPath: string;
  readonly installationAncestorIdentity: PathIdentity;
  readonly entryExists: boolean;
}

export async function inspectTarget(
  targetRoot: string,
  entryFile: string,
  installationRoot: string,
): Promise<TargetInspection> {
  if (!isAbsolute(targetRoot) || !isAbsolute(installationRoot)) {
    throw new Error("target and installation roots must be absolute");
  }
  if (resolve(targetRoot) !== targetRoot || resolve(installationRoot) !== installationRoot) {
    throw new Error("roots must be canonical absolute paths");
  }
  if (entryFile === "" || isAbsolute(entryFile) || entryFile.includes("\\") || normalize(entryFile) !== entryFile) {
    throw new Error("entry file must be a canonical relative path without traversal");
  }
  if (!/\.(?:md|markdown)$/i.test(entryFile)) throw new Error("entry file must be Markdown");

  let rootStat: Awaited<ReturnType<typeof lstat>>;
  try {
    rootStat = await lstat(targetRoot);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") throw new Error("target root is missing");
    throw error;
  }
  if (rootStat.isSymbolicLink() || !rootStat.isDirectory()) {
    throw new Error("target root must be a non-symlink directory");
  }
  if ((await realpath(targetRoot)) !== targetRoot) throw new Error("target root is not canonical or contains a symlink");

  const entryPath = join(targetRoot, entryFile);
  const rel = relative(targetRoot, entryPath);
  if (rel === ".." || rel.startsWith(`..${sep}`) || isAbsolute(rel)) throw new Error("entry escapes target root");

  async function validateChain(path: string, finalKind: "entry" | "installation"): Promise<boolean> {
    const parts = relative(targetRoot, path).split(sep).filter(Boolean);
    let current = targetRoot;
    let missing = false;
    for (const [index, part] of parts.entries()) {
      current = join(current, part);
      if (missing) continue;
      try {
        const stat = await lstat(current);
        if (stat.isSymbolicLink()) throw new Error(`${finalKind} path contains a symlink`);
        const final = index === parts.length - 1;
        if (!final && !stat.isDirectory()) throw new Error(`${finalKind} parent must be a directory`);
        if (final && finalKind === "entry" && !stat.isFile()) throw new Error("entry must be a regular file");
        if (final && finalKind === "installation" && !stat.isDirectory()) {
          throw new Error("installation root must be a directory");
        }
      } catch (error) {
        if ((error as NodeJS.ErrnoException).code === "ENOENT") missing = true;
        else throw error;
      }
    }
    return !missing;
  }

  const entryExists = await validateChain(entryPath, "entry");
  const entryParent = dirname(entryPath);
  let entryParentStat: Awaited<ReturnType<typeof lstat>>;
  try { entryParentStat = await lstat(entryParent); }
  catch (error) { if ((error as NodeJS.ErrnoException).code === "ENOENT") throw new Error("entry parent is missing"); throw error; }
  if (entryParentStat.isSymbolicLink() || !entryParentStat.isDirectory() || (await realpath(entryParent)) !== entryParent) {
    throw new Error("entry parent must be a canonical non-symlink directory");
  }
  if (installationRoot === targetRoot || installationRoot.startsWith(`${targetRoot}${sep}`)) {
    await validateChain(installationRoot, "installation");
  }
  let installationAncestorPath = installationRoot;
  while (true) {
    try {
      const stat = await lstat(installationAncestorPath);
      if (stat.isSymbolicLink() || !stat.isDirectory()) throw new Error("installation path contains a symlink or non-directory");
      if ((await realpath(installationAncestorPath)) !== installationAncestorPath) throw new Error("installation path is not canonical");
      break;
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
      const parent = dirname(installationAncestorPath);
      if (parent === installationAncestorPath) throw new Error("installation root has no existing parent");
      installationAncestorPath = parent;
    }
  }

  return {
    targetRoot,
    entryPath,
    installationRoot,
    targetIdentity: await captureIdentity(targetRoot),
    entryParentIdentity: await captureIdentity(entryParent),
    ...(entryExists ? { entryIdentity: await captureIdentity(entryPath) } : {}),
    installationAncestorPath,
    installationAncestorIdentity: await captureIdentity(installationAncestorPath),
    entryExists,
  };
}
