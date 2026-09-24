import { lstat, readFile, realpath } from "node:fs/promises";
import { join } from "node:path";
import { exact, ID, idList, parseClosedToml, safeRelativePath, table, type TomlTable, type TomlValue } from "./closed-toml.ts";
import { parseSsotManifestText } from "./ssot-manifest.ts";
import { parseRoutingCatalogs, type RoutingCatalogs } from "./routing-catalog.ts";
import { parseDiscoveryCatalogText } from "./discovery-catalog.ts";
import { parseCommandCatalogText } from "./command-catalog.ts";
import { parseTemplatesManifestText } from "./templates-catalog.ts";
import { parseClassificationsText, parseProjectionsText } from "./work-items.ts";

const CORE_CATALOGS = ["triggers", "policy_tags", "scopes", "tools"] as const;
const OPTIONAL_CATALOGS = ["commands", "discovery_signals"] as const;
const MODULE_FIELDS = ["path", "triggers", "dependencies"] as const;
const ROLE_FIELDS = ["path", "triggers", "modules"] as const;

interface CatalogTexts {
  readonly triggers: string;
  readonly policyTags: string;
  readonly scopes: string;
  readonly tools: string;
  readonly commands?: string;
  readonly discovery?: string;
  readonly classifications?: string;
  readonly githubLabels?: string;
}

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

async function readCatalogFile(manifestRoot: string, rawPath: string, label: string, inventory: ReadonlyMap<string, string>, referencedPaths: Set<string>): Promise<string> {
  const path = safeRelativePath(rawPath, `release manifest ${label} path`);
  if (!/\.toml$/i.test(path)) throw new Error(`release manifest ${label} has an invalid format`);
  referencedPaths.add(path);
  return safeIndexedFile(manifestRoot, path, inventory, label);
}

function exactCatalogKeys(entries: Readonly<Record<string, string>>, expected: readonly string[], label: string): void {
  const actual = Object.keys(entries).sort().join("\0");
  const wanted = [...expected].sort().join("\0");
  if (actual !== wanted) throw new Error(`${label} has missing or unknown fields`);
}

function validateCatalogs(texts: CatalogTexts): RoutingCatalogs {
  const routing = parseRoutingCatalogs({
    triggers: texts.triggers,
    policyTags: texts.policyTags,
    scopes: texts.scopes,
    tools: texts.tools,
  });
  if (texts.commands !== undefined) parseCommandCatalogText(texts.commands);
  if (texts.discovery !== undefined) parseDiscoveryCatalogText(texts.discovery);
  if (texts.classifications !== undefined && texts.githubLabels !== undefined) {
    parseProjectionsText(texts.githubLabels, parseClassificationsText(texts.classifications));
  }
  return routing;
}

async function readSsotCatalogs(manifestRoot: string, ssotPath: string, inventory: ReadonlyMap<string, string>, referencedPaths: Set<string>): Promise<CatalogTexts> {
  const ssotText = await safeIndexedFile(manifestRoot, ssotPath, inventory, "ssot manifest");
  const ssotIndex = parseSsotManifestText(ssotText);
  const routingEntries = ssotIndex.domains.routing;
  exactCatalogKeys(routingEntries, ["triggers", "policy_tags", "scopes", "tools"], "routing domain");
  const commandEntries = ssotIndex.domains.commands;
  exactCatalogKeys(commandEntries, ["commands"], "commands domain");
  const discoveryEntries = ssotIndex.domains.discovery;
  exactCatalogKeys(discoveryEntries, ["discovery_signals"], "discovery domain");
  const workItemsEntries = ssotIndex.domains.work_items;
  if (workItemsEntries !== undefined) exactCatalogKeys(workItemsEntries, ["classifications", "github_labels"], "work_items domain");
  async function read(relative: string, label: string): Promise<string> {
    const path = `ssot/${relative}`;
    referencedPaths.add(path);
    return safeIndexedFile(manifestRoot, path, inventory, label);
  }
  return {
    triggers: await read(routingEntries.triggers!, "triggers catalog"),
    policyTags: await read(routingEntries.policy_tags!, "policy tags catalog"),
    scopes: await read(routingEntries.scopes!, "scopes catalog"),
    tools: await read(routingEntries.tools!, "tools catalog"),
    commands: await read(commandEntries.commands!, "commands catalog"),
    discovery: await read(discoveryEntries.discovery_signals!, "discovery catalog"),
    ...(workItemsEntries === undefined ? {} : {
      classifications: await read(workItemsEntries.classifications!, "classifications catalog"),
      githubLabels: await read(workItemsEntries.github_labels!, "github labels projection catalog"),
    }),
  };
}

async function readLegacyCatalogs(manifestRoot: string, catalogs: TomlTable, inventory: ReadonlyMap<string, string>, referencedPaths: Set<string>): Promise<CatalogTexts> {
  const catalogFields = Object.keys(catalogs).sort().join("\0");
  const legacyCatalogFields = [...CORE_CATALOGS].sort().join("\0");
  const discoveryCatalogFields = [...CORE_CATALOGS, ...OPTIONAL_CATALOGS].sort().join("\0");
  if (catalogFields !== legacyCatalogFields && catalogFields !== discoveryCatalogFields) throw new Error("release manifest catalogs has missing or unknown fields");
  const read = (name: string, label: string) => readCatalogFile(manifestRoot, catalogs[name] as string, label, inventory, referencedPaths);
  return {
    triggers: await read("triggers", "triggers catalog"),
    policyTags: await read("policy_tags", "policy tags catalog"),
    scopes: await read("scopes", "scopes catalog"),
    tools: await read("tools", "tools catalog"),
    ...(catalogs.commands === undefined ? {} : { commands: await read("commands", "commands catalog") }),
    ...(catalogs.discovery_signals === undefined ? {} : { discovery: await read("discovery_signals", "discovery catalog") }),
  };
}

async function readTemplates(manifestRoot: string, rawPath: TomlValue | undefined, inventory: ReadonlyMap<string, string>, referencedPaths: Set<string>): Promise<void> {
  const templatesPath = safeRelativePath(rawPath, "release manifest templates path");
  if (templatesPath !== "templates/manifest.toml") throw new Error("release manifest templates path must be canonical");
  referencedPaths.add(templatesPath);
  const templatesIndex = parseTemplatesManifestText(await safeIndexedFile(manifestRoot, templatesPath, inventory, "templates manifest"));
  for (const entry of Object.values(templatesIndex.templates)) {
    const templatePath = `templates/${entry.path}`;
    referencedPaths.add(templatePath);
    await safeIndexedFile(manifestRoot, templatePath, inventory, `template ${entry.id}`);
  }
}

function validateIndex(manifestRoot: string, manifest: TomlTable, inventory: ReadonlyMap<string, string>, routing: RoutingCatalogs, referencedPaths: Set<string>): Promise<void> {
  const routingTable = table(manifest.routing, "release manifest routing"); exact(routingTable, ["unknown", "ambiguous"], "release manifest routing");
  if (routingTable.unknown !== "block" || routingTable.ambiguous !== "block") throw new Error("release manifest routing must fail closed");

  const modules = table(manifest.modules, "release manifest modules");
  if (Object.keys(modules).length === 0) throw new Error("release manifest modules are empty");
  const dependencies = new Map<string, string[]>();
  const moduleChecks: Promise<void>[] = [];
  for (const [id, raw] of Object.entries(modules)) {
    if (!ID.test(id)) throw new Error("release manifest contains an invalid module ID");
    const module = table(raw, `modules.${id}`); exact(module, MODULE_FIELDS, `modules.${id}`);
    const path = safeRelativePath(module.path, `modules.${id}.path`); if (!/\.md$/i.test(path)) throw new Error(`modules.${id}.path has an invalid format`); referencedPaths.add(path); moduleChecks.push(safeIndexedFile(manifestRoot, path, inventory, `module ${id}`).then(() => undefined));
    known(idList(module.triggers, `modules.${id}.triggers`, true), routing.triggers, `modules.${id}.triggers`);
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
  const roleChecks: Promise<void>[] = [];
  for (const [id, raw] of Object.entries(roles)) {
    if (!ID.test(id)) throw new Error("release manifest contains an invalid role ID");
    const role = table(raw, `roles.${id}`); exact(role, ROLE_FIELDS, `roles.${id}`);
    const path = safeRelativePath(role.path, `roles.${id}.path`); if (!/\.md$/i.test(path)) throw new Error(`roles.${id}.path has an invalid format`); referencedPaths.add(path); roleChecks.push(safeIndexedFile(manifestRoot, path, inventory, `role ${id}`).then(() => undefined));
    known(idList(role.triggers, `roles.${id}.triggers`, true), routing.triggers, `roles.${id}.triggers`);
    known(idList(role.modules, `roles.${id}.modules`, true), moduleIds, `roles.${id}.modules`);
  }
  return Promise.all([...moduleChecks, ...roleChecks]).then(() => undefined);
}

async function validateContract(manifestRoot: string, manifestText: string, inventory: ReadonlyMap<string, string>): Promise<{ localRulesPath: string; referencedPaths: ReadonlySet<string> }> {
  const manifest = parseClosedToml(manifestText, "release manifest");
  const localRules = safeRelativePath(manifest.local_rules, "release manifest local rules path");
  if (!/\.md$/i.test(localRules)) throw new Error("release manifest local rules path is invalid");
  const referencedPaths = new Set<string>();

  let routing: RoutingCatalogs;
  if (manifest.schema_version === 4) {
    exact(manifest, ["schema_version", "local_rules", "ssot", "templates", "routing", "modules", "roles"], "release manifest");
    const ssotPath = safeRelativePath(manifest.ssot, "release manifest ssot path");
    if (ssotPath !== "ssot/manifest.toml") throw new Error("release manifest ssot path must be canonical");
    referencedPaths.add(ssotPath);
    routing = validateCatalogs(await readSsotCatalogs(manifestRoot, ssotPath, inventory, referencedPaths));
    await readTemplates(manifestRoot, manifest.templates, inventory, referencedPaths);
  } else if (manifest.schema_version === 2) {
    exact(manifest, ["schema_version", "local_rules", "catalogs", "routing", "modules", "roles"], "release manifest");
    routing = validateCatalogs(await readLegacyCatalogs(manifestRoot, table(manifest.catalogs, "release manifest catalogs"), inventory, referencedPaths));
  } else {
    throw new Error("release manifest schema is invalid");
  }

  await validateIndex(manifestRoot, manifest, inventory, routing, referencedPaths);
  return { localRulesPath: localRules, referencedPaths };
}

export function validateGovernanceContract(manifestRoot: string, manifestText: string, inventory: ReadonlyMap<string, string>): Promise<{ localRulesPath: string; referencedPaths: ReadonlySet<string> }> {
  return validateContract(manifestRoot, manifestText, inventory);
}
