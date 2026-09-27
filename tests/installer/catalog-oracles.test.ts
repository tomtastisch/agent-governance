import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { parseClosedToml, table } from "../../src/closed-toml.ts";
import { parseRoutingCatalogs } from "../../src/routing-catalog.ts";
import { loadSsotIndex } from "../../src/ssot-manifest.ts";
import { routingOracle } from "./catalog-oracles.ts";

const { catalogFile } = loadSsotIndex();
const readRouting = (id: string) => readFileSync(catalogFile("routing", id), "utf8");

test("routing inventories match the independent domain oracle", () => {
  const texts = { triggers: readRouting("triggers"), policyTags: readRouting("policy_tags"), scopes: readRouting("scopes"), tools: readRouting("tools") };
  const actual = parseRoutingCatalogs(texts);
  assert.deepEqual([...actual.policyTags].sort(), [...routingOracle.policy_tags].sort());
  assert.deepEqual([...actual.scopes].sort(), [...routingOracle.scopes].sort());
  // The routing validator intentionally exposes no tool inventory; inspect its validated input.
  const tools = table(parseClosedToml(texts.tools, "tools").tools, "tools");
  assert.deepEqual(Object.keys(tools).sort(), [...routingOracle.tools].sort());
});

