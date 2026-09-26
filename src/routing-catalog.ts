import { exact, ID, idList, parseClosedToml, table, text, type TomlTable } from "./closed-toml.ts";
import { governanceContract } from "./contract-fixture.ts";

const TOOL_FIELDS = governanceContract.toolFields;

export interface RoutingCatalogs {
  readonly triggers: ReadonlySet<string>;
  readonly policyTags: ReadonlySet<string>;
  readonly scopes: ReadonlySet<string>;
  readonly requiredToolTriggers: ReadonlySet<string>;
}

function validateVocabulary(catalog: TomlTable, name: "triggers" | "policy_tags" | "scopes"): Set<string> {
  exact(catalog, ["schema_version", name], `${name} catalog`);
  if (catalog.schema_version !== 1) throw new Error(`${name} catalog schema is invalid`);
  const entries = table(catalog[name], `${name} entries`);
  if (Object.keys(entries).length === 0) throw new Error(`${name} catalog is empty`);
  for (const [id, raw] of Object.entries(entries)) {
    if (!ID.test(id)) throw new Error(`${name} contains an invalid ID`);
    const entry = table(raw, `${name}.${id}`);
    exact(entry, governanceContract.vocabularyFields, `${name}.${id}`);
    text(entry.label, `${name}.${id}.label`); text(entry.description, `${name}.${id}.description`);
  }
  return new Set(Object.keys(entries));
}

function known(values: readonly string[], vocabulary: ReadonlySet<string>, label: string): void {
  if (values.some((value) => !vocabulary.has(value))) throw new Error(`${label} contains unknown references`);
}

export function parseRoutingCatalogs(texts: { readonly triggers: string; readonly policyTags: string; readonly scopes: string; readonly tools: string }): RoutingCatalogs {
  const triggers = validateVocabulary(parseClosedToml(texts.triggers, "triggers catalog"), "triggers");
  const policyTags = validateVocabulary(parseClosedToml(texts.policyTags, "policy tags catalog"), "policy_tags");
  const scopes = validateVocabulary(parseClosedToml(texts.scopes, "scopes catalog"), "scopes");

  const toolCatalog = parseClosedToml(texts.tools, "tools catalog");
  exact(toolCatalog, ["schema_version", "tools"], "tools catalog");
  if (toolCatalog.schema_version !== 1) throw new Error("tools catalog schema is invalid");
  const tools = table(toolCatalog.tools, "tools entries");
  if (Object.keys(tools).length === 0) throw new Error("tools catalog is empty");
  const requiredToolTriggers = new Set<string>(["tool_selection"]);
  for (const [id, raw] of Object.entries(tools)) {
    if (!ID.test(id)) throw new Error("tools catalog contains an invalid ID");
    const tool = table(raw, `tools.${id}`); exact(tool, TOOL_FIELDS, `tools.${id}`);
    for (const field of ["name", "purpose", "evidence", "fallback", "constraints"] as const) text(tool[field], `tools.${id}.${field}`);
    const required = idList(tool.required_on, `tools.${id}.required_on`); known(required, triggers, `tools.${id}.required_on`); required.forEach((value) => requiredToolTriggers.add(value));
    known(idList(tool.useful_on, `tools.${id}.useful_on`), triggers, `tools.${id}.useful_on`);
    known(idList(tool.policy_tags, `tools.${id}.policy_tags`), policyTags, `tools.${id}.policy_tags`);
    known(idList(tool.scopes, `tools.${id}.scopes`), scopes, `tools.${id}.scopes`);
  }
  return { triggers, policyTags, scopes, requiredToolTriggers };
}
