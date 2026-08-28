import { readFileSync } from "node:fs";
import { parse } from "smol-toml";
import { resolveCatalogPath, resolveManifestPath } from "./catalog-paths.ts";
import type { PublicCommandDefinition, PublicCommandId } from "./contracts.ts";

export const PUBLIC_COMMAND_IDS = ["inspect", "plan", "install", "verify", "status", "update", "uninstall", "rollback", "init"] as const;
export type { PublicCommandDefinition, PublicCommandId } from "./contracts.ts";

const COMMAND_FIELDS = new Set(["id", "path", "description", "capability", "effect", "orchestrates", "interactive"]);
const EXPECTED_SEMANTICS: Readonly<Record<PublicCommandId, Omit<PublicCommandDefinition, "id" | "description">>> = Object.freeze({
  inspect: { path: ["inspect"], capability: "transaction", effect: "read", orchestrates: false, interactive: false },
  plan: { path: ["plan"], capability: "transaction", effect: "read", orchestrates: false, interactive: false },
  install: { path: ["install"], capability: "transaction", effect: "write", orchestrates: false, interactive: false },
  verify: { path: ["verify"], capability: "transaction", effect: "read", orchestrates: false, interactive: false },
  status: { path: ["status"], capability: "transaction", effect: "read", orchestrates: false, interactive: false },
  update: { path: ["update"], capability: "transaction", effect: "write", orchestrates: false, interactive: false },
  uninstall: { path: ["uninstall"], capability: "transaction", effect: "write", orchestrates: false, interactive: false },
  rollback: { path: ["rollback"], capability: "transaction", effect: "write", orchestrates: false, interactive: false },
  init: { path: ["init"], capability: "orchestration", effect: "write", orchestrates: true, interactive: true },
});

function record(value: unknown, context: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error(`${context} must be a table`);
  return value as Record<string, unknown>;
}

function parseTomlText(content: string, context: string): Record<string, unknown> {
  try {
    return record(parse(content), context);
  } catch (cause) {
    if (cause instanceof Error && cause.message.startsWith(`${context} `)) throw cause;
    throw new Error(`${context} is invalid TOML`, { cause });
  }
}

function parseToml(path: string, context: string): Record<string, unknown> {
  return parseTomlText(readFileSync(path, "utf8"), context);
}

function samePath(actual: readonly string[], expected: readonly string[]): boolean {
  return actual.length === expected.length && actual.every((segment, index) => segment === expected[index]);
}

function validateCommand(raw: unknown): PublicCommandDefinition {
  const command = record(raw, "command entry");
  const unknown = Object.keys(command).filter((field) => !COMMAND_FIELDS.has(field));
  const missing = [...COMMAND_FIELDS].filter((field) => !(field in command));
  if (unknown.length > 0) throw new Error(`command entry contains unknown fields: ${unknown.join(", ")}`);
  if (missing.length > 0) throw new Error(`command entry contains missing fields: ${missing.join(", ")}`);
  const { id, path, description, capability, effect, orchestrates, interactive } = command;
  if (typeof id !== "string" || !PUBLIC_COMMAND_IDS.includes(id as PublicCommandId)) throw new Error("command id is invalid");
  if (!Array.isArray(path) || path.length === 0 || path.some((segment) => typeof segment !== "string" || !/^[a-z][a-z0-9-]*$/.test(segment))) throw new Error(`command ${id} path is invalid`);
  if (typeof description !== "string" || description.trim().length === 0 || /[\0\r\n\x1b]/.test(description)) throw new Error(`command ${id} description is invalid`);
  if (typeof capability !== "string" || !["transaction", "orchestration"].includes(capability)) throw new Error(`command ${id} capability is invalid`);
  if (typeof effect !== "string" || !["read", "write"].includes(effect)) throw new Error(`command ${id} effect is invalid`);
  if (typeof orchestrates !== "boolean") throw new Error(`command ${id} orchestrates must be boolean`);
  if (typeof interactive !== "boolean") throw new Error(`command ${id} interactive must be boolean`);
  const expected = EXPECTED_SEMANTICS[id as PublicCommandId];
  if (!samePath(path as string[], expected.path) || capability !== expected.capability || effect !== expected.effect || orchestrates !== expected.orchestrates || interactive !== expected.interactive) {
    throw new Error(`command ${id} semantics are invalid`);
  }
  return Object.freeze({ id: id as PublicCommandId, path: Object.freeze([...(path as string[])]), description, capability: capability as PublicCommandDefinition["capability"], effect: effect as PublicCommandDefinition["effect"], orchestrates, interactive });
}

export function parseCommandCatalogText(content: string): readonly PublicCommandDefinition[] {
  const catalog = parseTomlText(content, "command catalog");
  const unknownTopLevel = Object.keys(catalog).filter((field) => field !== "schema_version" && field !== "commands");
  if (unknownTopLevel.length > 0 || Object.keys(catalog).length !== 2) throw new Error("command catalog has invalid top-level fields");
  if (catalog.schema_version !== 1) throw new Error("command catalog schema_version must be integer 1");
  if (!Array.isArray(catalog.commands)) throw new Error("command catalog commands must be an array");
  const rawPaths = catalog.commands.map((raw, index) => {
    const command = record(raw, `command entry ${index}`);
    return Array.isArray(command.path) && command.path.every((segment) => typeof segment === "string") ? command.path.join("\0") : undefined;
  }).filter((path): path is string => path !== undefined);
  if (new Set(rawPaths).size !== rawPaths.length) throw new Error("command catalog contains duplicate paths");
  const commands = catalog.commands.map(validateCommand);
  const ids = commands.map(({ id }) => id);
  if (new Set(ids).size !== ids.length) throw new Error("command catalog contains duplicate IDs");
  if (ids.length !== PUBLIC_COMMAND_IDS.length || PUBLIC_COMMAND_IDS.some((id) => !ids.includes(id))) throw new Error("command catalog must define exactly the public command IDs");
  return Object.freeze(commands);
}

export function loadCommandCatalog(releaseRoot?: string): readonly PublicCommandDefinition[] {
  const manifestPath = resolveManifestPath(releaseRoot);
  const manifest = parseToml(manifestPath, "command manifest");
  const catalogs = record(manifest.catalogs, "command manifest catalogs");
  const catalogPath = resolveCatalogPath(manifestPath, catalogs.commands);
  return parseCommandCatalogText(readFileSync(catalogPath, "utf8"));
}
