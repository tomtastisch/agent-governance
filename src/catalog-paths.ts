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

export function resolveManifestPath(releaseRoot: string = PACKAGE_RELEASE_ROOT): string {
  const root = requireReleaseRoot(releaseRoot);
  return requireRegularFile(join(root, "bundle", "agent-governance", "manifest.toml"), "command manifest");
}

export function resolveCatalogPath(manifestPath: string, rawPath: unknown): string {
  if (typeof rawPath !== "string" || rawPath.length === 0 || isAbsolute(rawPath) || rawPath.includes("\\")) {
    throw new Error("command catalog path is invalid");
  }
  const parts = rawPath.split("/");
  if (parts.some((part) => part === "" || part === "." || part === ".." || part === "~")) {
    throw new Error("command catalog path contains traversal");
  }
  const manifestRoot = dirname(manifestPath);
  let current = manifestRoot;
  for (const part of parts) {
    current = join(current, part);
    let metadata;
    try {
      metadata = lstatSync(current);
    } catch {
      throw new Error("command catalog path must reference an existing file");
    }
    if (metadata.isSymbolicLink()) throw new Error("command catalog path must not contain symlinks");
  }
  const resolved = requireRegularFile(current, "command catalog");
  const offset = relative(manifestRoot, resolved);
  if (offset === ".." || offset.startsWith(`..${sep}`) || isAbsolute(offset)) throw new Error("command catalog path escapes manifest root");
  return resolved;
}
