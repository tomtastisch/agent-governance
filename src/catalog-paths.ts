import { lstatSync, realpathSync } from "node:fs";
import { dirname, isAbsolute, join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

export const PACKAGE_RELEASE_ROOT = dirname(dirname(fileURLToPath(import.meta.url)));

function requireRegularFile(path: string, label: string): string {
  let metadata;
  try {
    metadata = lstatSync(path);
  } catch {
    throw new Error(`${label} must be a readable regular file`);
  }
  if (metadata.isSymbolicLink() || !metadata.isFile()) throw new Error(`${label} must be a regular non-symlink file`);
  return realpathSync(path);
}

function requireReleaseRoot(releaseRoot: string): string {
  if (!isAbsolute(releaseRoot)) throw new Error("release root path must be absolute");
  const metadata = lstatSync(releaseRoot);
  if (metadata.isSymbolicLink() || !metadata.isDirectory()) throw new Error("release root must be a non-symlink directory");
  return realpathSync(releaseRoot);
}

function resolveIndexedPath(releaseRoot: string, parts: readonly string[], label: string): string {
  let current = releaseRoot;
  for (const [index, part] of parts.entries()) {
    current = join(current, part);
    let metadata;
    try {
      metadata = lstatSync(current);
    } catch {
      throw new Error(`${label} path must exist`);
    }
    if (metadata.isSymbolicLink()) throw new Error(`${label} path must not contain symlinks`);
    const isLeaf = index === parts.length - 1;
    if ((isLeaf && !metadata.isFile()) || (!isLeaf && !metadata.isDirectory())) {
      throw new Error(`${label} path has an invalid component type`);
    }
  }
  const resolved = realpathSync(current);
  const offset = relative(releaseRoot, resolved);
  if (offset === ".." || offset.startsWith(`..${sep}`) || isAbsolute(offset)) {
    throw new Error(`${label} path escapes release root`);
  }
  return resolved;
}

export function resolveManifestPath(releaseRoot: string = PACKAGE_RELEASE_ROOT): string {
  const root = requireReleaseRoot(releaseRoot);
  return resolveIndexedPath(root, ["bundle", "agent-governance", "manifest.toml"], "command manifest");
}

export function resolveSsotFile(ssotManifestPath: string, rawPath: unknown): string {
  if (typeof rawPath !== "string" || rawPath.length === 0 || isAbsolute(rawPath) || rawPath.includes("\\")) {
    throw new Error("ssot file path is invalid");
  }
  const parts = rawPath.split("/");
  if (parts.some((part) => part === "" || part === "." || part === ".." || part === "~")) {
    throw new Error("ssot file path contains traversal");
  }
  const ssotRoot = dirname(ssotManifestPath);
  let current = ssotRoot;
  for (const part of parts) {
    current = join(current, part);
    let metadata;
    try {
      metadata = lstatSync(current);
    } catch {
      throw new Error("ssot file path must reference an existing file");
    }
    if (metadata.isSymbolicLink()) throw new Error("ssot file path must not contain symlinks");
  }
  const resolved = requireRegularFile(current, "ssot file");
  const offset = relative(ssotRoot, resolved);
  if (offset === ".." || offset.startsWith(`..${sep}`) || isAbsolute(offset)) throw new Error("ssot file path escapes the ssot root");
  return resolved;
}
