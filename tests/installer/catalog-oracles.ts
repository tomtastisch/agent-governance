import { readFileSync } from "node:fs";
import type { TemplateEntry } from "../../src/templates-catalog.ts";

// Independent, manually maintained test expectations. Never derive these from the bundle.
function readOracle(name: string): unknown {
  return JSON.parse(readFileSync(new URL(`../contracts/${name}.json`, import.meta.url), "utf8"));
}

export const routingOracle = readOracle("routing") as {
  tools: string[]; policy_tags: string[]; scopes: string[];
};
export const templatesOracle = readOracle("templates") as Record<string, Omit<TemplateEntry, "id">>;
export const workItemsOracle = readOracle("work-items") as {
  dimensions: Record<string, string>; required_classifications: string[]; required_projection_names: string[];
};
