import assert from "node:assert/strict";
import test from "node:test";
import { COMMANDS, EXIT_CODES, INSTALL_PHASES, INSTALL_STATES, exitCodeFor } from "../../src/contracts.ts";
test("contract exposes the closed generic command, state, phase, and exit models", () => {
  assert.deepEqual(COMMANDS, ["inspect", "plan", "install", "verify", "status", "update", "uninstall", "rollback"]);
  assert.deepEqual(INSTALL_STATES, ["FRESH", "CURRENT", "OUTDATED", "DOWNGRADE_BLOCKED", "ABSENT", "TAMPERED", "RECOVERY_REQUIRED"]);
  assert.deepEqual(INSTALL_PHASES, ["inspect", "plan", "backup", "stage", "activate", "verify", "rollback"]);
  assert.equal(exitCodeFor("SUCCESS"), 0); assert.equal(exitCodeFor("INVALID_INVOCATION"), 2); assert.equal(exitCodeFor("UNSAFE_STATE"), 4); assert.equal(EXIT_CODES.ROLLBACK_FAILED, 6);
});
