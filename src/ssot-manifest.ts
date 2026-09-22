import { readFileSync } from "node:fs";
import { parseClosedToml, exact, safeRelativePath, table } from "./closed-toml.ts";
import { resolveManifestPath, resolveSsotFile } from "./catalog-paths.ts";

export const SSOT_DOMAIN_IDS = ["routing", "commands", "discovery", "work_items"] as const;
const HISTORICAL_SSOT_DOMAIN_IDS = ["routing", "commands", "discovery"] as const;
export type SsotDomainId = (typeof SSOT_DOMAIN_IDS)[number];

export interface SsotIndex {
  readonly schemaVersion: 1;
  readonly domains: Readonly<Record<SsotDomainId, Readonly<Record<string, string>>>>;
}

export interface InstalledSsotIndex {
  readonly schemaVersion: 1;
  readonly domains: Readonly<Record<string, Readonly<Record<string, string>>>>;
}

function parseSsotManifest(content: string, acceptedDomainSets: readonly (readonly string[])[]): InstalledSsotIndex {
  const manifest = parseClosedToml(content, "ssot manifest");
  exact(manifest, ["schema_version", "domains"], "ssot manifest");
  if (manifest.schema_version !== 1) throw new Error("ssot manifest schema is invalid");
  const domains = table(manifest.domains, "ssot manifest domains");
  const domainIds = Object.keys(domains).sort().join("\0");
  if (!acceptedDomainSets.some((expected) => domainIds === [...expected].sort().join("\0"))) throw new Error("ssot manifest domains has missing or unknown fields");
  const result: Record<string, Record<string, string>> = {};
  const seenCatalogIds = new Set<string>();
  const seenPaths = new Set<string>();
  for (const domainId of Object.keys(domains)) {
    const entries = table(domains[domainId], `ssot manifest ${domainId} domain`);
    if (Object.keys(entries).length === 0) throw new Error(`ssot manifest ${domainId} domain is empty`);
    const resolved: Record<string, string> = {};
    for (const [catalogId, raw] of Object.entries(entries)) {
      if (!/^[a-z][a-z0-9_]*$/.test(catalogId)) throw new Error(`ssot manifest ${domainId} domain contains an invalid catalog ID`);
      if (seenCatalogIds.has(catalogId)) throw new Error("ssot manifest contains a duplicate catalog ID");
      seenCatalogIds.add(catalogId);
      const path = safeRelativePath(raw, `ssot manifest ${domainId}.${catalogId}`);
      if (!/\.toml$/i.test(path)) throw new Error(`ssot manifest ${domainId}.${catalogId} has an invalid format`);
      if (seenPaths.has(path)) throw new Error("ssot manifest contains duplicate authority paths");
      seenPaths.add(path);
      resolved[catalogId] = path;
    }
    result[domainId] = resolved;
  }
  return Object.freeze({ schemaVersion: 1, domains: Object.freeze(result) });
}

export function parseSsotManifestText(content: string): SsotIndex {
  return parseSsotManifest(content, [SSOT_DOMAIN_IDS]) as SsotIndex;
}

export function parseInstalledSsotManifestText(content: string): InstalledSsotIndex {
  return parseSsotManifest(content, [SSOT_DOMAIN_IDS, HISTORICAL_SSOT_DOMAIN_IDS]);
}

export function loadSsotIndex(releaseRoot?: string): { index: SsotIndex; catalogFile: (domainId: SsotDomainId, catalogId: string) => string } {
  const manifestPath = resolveManifestPath(releaseRoot);
  const manifest = parseClosedToml(readFileSync(manifestPath, "utf8"), "release manifest");
  const ssotRelative = safeRelativePath(manifest.ssot, "release manifest ssot path");
  if (ssotRelative !== "ssot/manifest.toml") throw new Error("release manifest ssot path must be canonical");
  const ssotManifestPath = resolveSsotFile(manifestPath, ssotRelative);
  const index = parseSsotManifestText(readFileSync(ssotManifestPath, "utf8"));
  return {
    index,
    catalogFile: (domainId, catalogId) => {
      const entries = index.domains[domainId];
      if (entries === undefined || entries[catalogId] === undefined) throw new Error(`ssot manifest does not register ${domainId}.${catalogId}`);
      return resolveSsotFile(ssotManifestPath, entries[catalogId]);
    },
  };
}
