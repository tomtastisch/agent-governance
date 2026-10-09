import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import test from "node:test";

test("Typecheck verwendet den deklarierten Compiler trotz zusätzlicher Legacy-AST-API", () => {
  const metadata = JSON.parse(readFileSync("package.json", "utf8"));
  const result = spawnSync("npm", ["run", "--silent", "typecheck", "--", "--version"], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stdout.trim(), `Version ${metadata.devDependencies.typescript}`);
});
