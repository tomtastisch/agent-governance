import { lstat, readFile, realpath } from "node:fs/promises";
import { join } from "node:path";
import { exact, ID, idList, parseClosedToml, safeRelativePath, table, type TomlTable } from "./closed-toml.ts";
import { parseSsotManifestText } from "./ssot-manifest.ts";
import { parseRoutingCatalogs } from "./routing-catalog.ts";
import { parseDiscoveryCatalogText } from "./discovery/catalog.ts";
import { parseCommandCatalogText } from "./command-catalog.ts";

const MODULE_FIELDS = ["path", "triggers", "dependencies"] as const;
const ROLE_FIELDS = ["path", "triggers", "modules"] as const;

function known(values: readonly string[], vocabulary: ReadonlySet<string>, label: string): void {
  if (values.some((value) => !vocabulary.has(value))) throw new Error(`${label} contains unknown references`);
}

async function safeIndexedFile(root: string, path: string, inventory: ReadonlyMap<string, string>, label: string): Promise<string> {
  const inventoryPath = `bundle/agent-governance/${path}`;
  if (!inventory.has(inventoryPath)) throw new Error(`${label} is missing from release inventory`);
  const absolute = join(root, path);
  const stat = await lstat(absolute);
  if (stat.isSymbolicLink() || !stat.isFile() || await realpath(absolute) !== absolute) throw new Error(`${label} must be a canonical regular non-symlink file`);
  let content: string;
  try { content = new TextDecoder("utf-8", { fatal: true }).decode(await readFile(absolute)); } catch { throw new Error(`${label} contains invalid UTF-8 encoding`); }
  if (/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/.test(content)) throw new Error(`${label} contains a raw control character`);
  return content;
}

function exactCatalogKeys(entries: Readonly<Record<string, string>>, expected: readonly string[], label: string): void {
  const actual = Object.keys(entries).sort().join("\0");
  const wanted = [...expected].sort().join("\0");
  if (actual !== wanted) throw new Error(`${label} has missing or unknown fields`);
}

export async function validateGovernanceContract(manifestRoot: string, manifestText: string, inventory: ReadonlyMap<string, string>): Promise<{ localRulesPath: string; referencedPaths: ReadonlySet<string> }> {
  const manifest = parseClosedToml(manifestText, "release manifest");
  exact(manifest, ["schema_version", "local_rules", "ssot", "routing", "modules", "roles"], "release manifest");
  if (manifest.schema_version !== 3) throw new Error("release manifest schema is invalid");
  const localRules = safeRelativePath(manifest.local_rules, "release manifest local rules path");
  if (!/\.md$/i.test(localRules)) throw new Error("release manifest local rules path is invalid");

  const referencedPaths = new Set<string>();

  const ssotPath = safeRelativePath(manifest.ssot, "release manifest ssot path");
  if (!/\.toml$/i.test(ssotPath)) throw new Error("release manifest ssot path has an invalid format");
  referencedPaths.add(ssotPath);
  const ssotIndex = parseSsotManifestText(await safeIndexedFile(manifestRoot, ssotPath, inventory, "ssot manifest"));

  async function readDomainFile(domain: string, relative: string, label: string): Promise<string> {
    const path = `ssot/${relative}`;
    referencedPaths.add(path);
    return safeIndexedFile(manifestRoot, path, inventory, label);
  }

  const routingEntries = ssotIndex.domains.routing;
  exactCatalogKeys(routingEntries, ["triggers", "policy_tags", "scopes", "tools"], "routing domain");
  const routing = parseRoutingCatalogs({
    triggers: await readDomainFile("routing", routingEntries.triggers!, "triggers catalog"),
    policyTags: await readDomainFile("routing", routingEntries.policy_tags!, "policy tags catalog"),
    scopes: await readDomainFile("routing", routingEntries.scopes!, "scopes catalog"),
    tools: await readDomainFile("routing", routingEntries.tools!, "tools catalog"),
  });
  const triggers = routing.triggers;

  const commandEntries = ssotIndex.domains.commands;
  exactCatalogKeys(commandEntries, ["commands"], "commands domain");
  parseCommandCatalogText(await readDomainFile("commands", commandEntries.commands!, "commands catalog"));

  const discoveryEntries = ssotIndex.domains.discovery;
  exactCatalogKeys(discoveryEntries, ["discovery_signals"], "discovery domain");
  parseDiscoveryCatalogText(await readDomainFile("discovery", discoveryEntries.discovery_signals!, "discovery catalog"));

  const routingTable = table(manifest.routing, "release manifest routing"); exact(routingTable, ["unknown", "ambiguous"], "release manifest routing");
  if (routingTable.unknown !== "block" || routingTable.ambiguous !== "block") throw new Error("release manifest routing must fail closed");

  const modules = table(manifest.modules, "release manifest modules");
  if (Object.keys(modules).length === 0) throw new Error("release manifest modules are empty");
  const dependencies = new Map<string, string[]>();
  for (const [id, raw] of Object.entries(modules)) {
    if (!ID.test(id)) throw new Error("release manifest contains an invalid module ID");
    const module = table(raw, `modules.${id}`); exact(module, MODULE_FIELDS, `modules.${id}`);
    const path = safeRelativePath(module.path, `modules.${id}.path`); if (!/\.md$/i.test(path)) throw new Error(`modules.${id}.path has an invalid format`); referencedPaths.add(path); await safeIndexedFile(manifestRoot, path, inventory, `module ${id}`);
    known(idList(module.triggers, `modules.${id}.triggers`, true), triggers, `modules.${id}.triggers`);
    dependencies.set(id, idList(module.dependencies, `modules.${id}.dependencies`));
  }
  const moduleIds = new Set(dependencies.keys());
  for (const [id, values] of dependencies) known(values, moduleIds, `modules.${id}.dependencies`);
  const visited = new Set<string>(); const visiting = new Set<string>();
  const visit = (id: string): void => { if (visiting.has(id)) throw new Error("release manifest module dependencies are cyclic"); if (visited.has(id)) return; visiting.add(id); for (const dependency of dependencies.get(id)!) visit(dependency); visiting.delete(id); visited.add(id); };
  moduleIds.forEach(visit);
  const toolRouting = table(modules.tool_routing, "release manifest tool_routing module");
  const routed = new Set(idList(toolRouting.triggers, "modules.tool_routing.triggers"));
  if (routed.size !== routing.requiredToolTriggers.size || [...routing.requiredToolTriggers].some((value) => !routed.has(value))) throw new Error("release manifest tool routing is incomplete");

  const roles = table(manifest.roles, "release manifest roles");
  if (Object.keys(roles).length === 0) throw new Error("release manifest roles are empty");
  for (const [id, raw] of Object.entries(roles)) {
    if (!ID.test(id)) throw new Error("release manifest contains an invalid role ID");
    const role = table(raw, `roles.${id}`); exact(role, ROLE_FIELDS, `roles.${id}`);
    const path = safeRelativePath(role.path, `roles.${id}.path`); if (!/\.md$/i.test(path)) throw new Error(`roles.${id}.path has an invalid format`); referencedPaths.add(path); await safeIndexedFile(manifestRoot, path, inventory, `role ${id}`);
    known(idList(role.triggers, `roles.${id}.triggers`, true), triggers, `roles.${id}.triggers`);
    known(idList(role.modules, `roles.${id}.modules`, true), moduleIds, `roles.${id}.modules`);
  }
  return { localRulesPath: localRules, referencedPaths };
}
