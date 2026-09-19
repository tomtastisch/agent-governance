import { lstatSync, realpathSync } from "node:fs";
import { isAbsolute, join, resolve } from "node:path";
import type { DiscoveryEnvironment, DiscoveryZone } from "./types.ts";

function canonicalDirectory(path: string, label: string, required: boolean): string | undefined {
  if (!isAbsolute(path)) throw new Error(`${label} must be an absolute path`);
  const normalized = resolve(path);
  let metadata;
  try {
    metadata = lstatSync(normalized);
  } catch (error) {
    if (!required && (error as NodeJS.ErrnoException).code === "ENOENT") return undefined;
    throw new Error(`${label} must be an existing canonical directory`, { cause: error });
  }
  if (metadata.isSymbolicLink() || !metadata.isDirectory()) {
    throw new Error(`${label} must be a non-symlink directory`);
  }
  const canonical = realpathSync(normalized);
  if (canonical !== normalized) throw new Error(`${label} must be canonical and contain no symlinks`);
  return canonical;
}

export function discoverZones(environment: DiscoveryEnvironment): readonly DiscoveryZone[] {
  const home = canonicalDirectory(environment.home, "HOME discovery zone", true)!;
  const definitions: Array<readonly [string, string, DiscoveryZone["candidateClass"], boolean]> = [
    ["home", home, "DIRECTORY", true],
    ["xdg_config", environment.xdgConfigHome ?? join(home, ".config"), "DIRECTORY", false],
    ["xdg_data", environment.xdgDataHome ?? join(home, ".local", "share"), "DIRECTORY", false],
  ];
  if (environment.platform === "darwin") {
    definitions.push(
      ["macos_application_support", join(home, "Library", "Application Support"), "DIRECTORY", false],
      ["macos_user_applications", join(home, "Applications"), "APP_BUNDLE", false],
      ["macos_system_applications", environment.macosSystemApplications ?? "/Applications", "APP_BUNDLE", false],
    );
  }

  const zones: DiscoveryZone[] = [];
  const seen = new Set<string>();
  for (const [id, path, candidateClass, required] of definitions) {
    const root = canonicalDirectory(path, `${id} discovery zone`, required);
    if (root === undefined) continue;
    const identity = `${candidateClass}\0${root}`;
    if (seen.has(identity)) continue;
    seen.add(identity);
    zones.push(Object.freeze({ id, root, candidateClass }));
  }
  return Object.freeze(zones);
}
