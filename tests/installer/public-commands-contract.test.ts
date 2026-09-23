import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { loadCommandCatalog } from "../../src/command-catalog.ts";
import { COMMANDS } from "../../src/contracts.ts";
import { PUBLIC_COMMAND_HANDLERS } from "../../src/public-commands.ts";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const ORACLE_PATH = join(ROOT, "tests", "contracts", "public-commands.json");

interface OracleCommand {
  readonly id: string;
  readonly path: string[];
  readonly capability: "transaction" | "orchestration";
  readonly effect: "read" | "write";
  readonly orchestrates: boolean;
  readonly interactive: boolean;
}

function loadOracle(): readonly OracleCommand[] {
  const parsed = JSON.parse(readFileSync(ORACLE_PATH, "utf8")) as { commands: readonly OracleCommand[] };
  if (!Array.isArray(parsed.commands)) throw new Error("public-commands.json must define a commands array");
  return parsed.commands;
}

function toContract(command: OracleCommand): OracleCommand {
  return {
    id: command.id,
    path: [...command.path],
    capability: command.capability,
    effect: command.effect,
    orchestrates: command.orchestrates,
    interactive: command.interactive,
  };
}

test("public command SSOT semantically matches the independent test oracle, in order", () => {
  const oracle = loadOracle();
  const commands = loadCommandCatalog();
  const actual = commands.map(({ id, path, capability, effect, orchestrates, interactive }) => ({
    id,
    path: [...path],
    capability,
    effect,
    orchestrates,
    interactive,
  }));
  assert.deepEqual(actual, oracle);
  assert.deepEqual(actual.map(toContract), oracle.map(toContract));
});

test("SSOT command IDs exactly cover the executable handler registry", () => {
  const commands = loadCommandCatalog();
  const ssotIds = commands.map(({ id }) => id);
  const handlerIds = Object.keys(PUBLIC_COMMAND_HANDLERS);
  assert.deepEqual([...handlerIds].sort(), [...ssotIds].sort());
  assert.equal(new Set(handlerIds).size, handlerIds.length, "handler IDs must be unique");
  assert.equal(new Set(ssotIds).size, ssotIds.length, "SSOT IDs must be unique");
});

test("the transaction command boundary matches the SSOT capability split", () => {
  const commands = loadCommandCatalog();
  const transactionIds = commands.filter(({ capability }) => capability === "transaction").map(({ id }) => id);
  const orchestrationIds = commands.filter(({ capability }) => capability === "orchestration").map(({ id }) => id);
  assert.deepEqual([...COMMANDS], transactionIds);
  assert.deepEqual(orchestrationIds, ["init"]);
});

test("every command carries a non-empty, control-character-free description", () => {
  for (const { id, description } of loadCommandCatalog()) {
    assert.equal(description.trim().length > 0, true, id);
    assert.equal(/[\0\r\n\x1b]/.test(description), false, id);
  }
});
