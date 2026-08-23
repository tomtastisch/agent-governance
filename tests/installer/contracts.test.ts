import assert from "node:assert/strict";
import test from "node:test";

import {
  EXIT_CODES,
  INSTALL_PHASES,
  INSTALL_STATES,
  exitCodeFor,
} from "../../src/contracts.ts";

test("contract exposes closed installation states and phases", () => {
  assert.deepEqual(INSTALL_STATES, [
    "FRESH",
    "CURRENT",
    "LEGACY",
    "UNKNOWN",
    "UNSUPPORTED",
  ]);
  assert.deepEqual(INSTALL_PHASES, [
    "inspect",
    "classify",
    "plan",
    "backup",
    "stage",
    "activate",
    "verify",
    "rollback",
  ]);
});

test("contract maps terminal outcomes to stable exit codes", () => {
  assert.equal(exitCodeFor("SUCCESS"), EXIT_CODES.SUCCESS);
  assert.equal(exitCodeFor("INVALID_INVOCATION"), 2);
  assert.equal(exitCodeFor("UNSUPPORTED_HARNESS"), 3);
  assert.equal(exitCodeFor("UNSAFE_STATE"), 4);
  assert.equal(exitCodeFor("VERIFICATION_ROLLED_BACK"), 5);
  assert.equal(exitCodeFor("ROLLBACK_FAILED"), 6);
});
