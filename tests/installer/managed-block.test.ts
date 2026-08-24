import assert from "node:assert/strict";
import test from "node:test";

import {
  installManagedBlock,
  removeManagedBlock,
  verifyManagedBlock,
  type GovernanceBinding,
} from "../../src/managed-block.ts";

const binding: GovernanceBinding = {
  version: "1.0.0-rc.1",
  installationRoot: "/safe/.agent-governance",
  governancePath: "/safe/.agent-governance/releases/1.0.0-rc.1/bundle/GOVERNANCE.md",
  manifestPath: "/safe/.agent-governance/releases/1.0.0-rc.1/bundle/agent-governance/manifest.toml",
  governanceDigest: "a".repeat(64),
  manifestDigest: "b".repeat(64),
  bundleDigest: "e".repeat(64),
};

const begin = "<!-- BEGIN AGENT_GOVERNANCE_MANAGED_V1 -->";
const end = "<!-- END AGENT_GOVERNANCE_MANAGED_V1 -->";

test("managed block creates a deterministic UTF-8 LF entry and verifies it", () => {
  const first = installManagedBlock(Buffer.alloc(0), binding);
  const second = installManagedBlock(Buffer.alloc(0), binding);
  assert.deepEqual(first, second);
  const text = first.toString("utf8");
  assert.equal(text.endsWith("\n"), true);
  assert.equal(text.includes("\r"), false);
  for (const value of [
    begin, end, "generated projection", binding.version, binding.installationRoot,
    binding.governancePath, binding.manifestPath, binding.governanceDigest,
    binding.manifestDigest, binding.bundleDigest, "personal local rules", "fail closed",
  ]) assert.equal(text.includes(value), true, value);
  assert.match(text, /before every response/i);
  assert.doesNotThrow(() => verifyManagedBlock(first, binding));
});

test("managed block preserves every user byte around one block with LF or CRLF", () => {
  for (const original of [
    Buffer.from("before\nafter without final newline", "utf8"),
    Buffer.from("Grüße\r\nzweite Zeile\r\n", "utf8"),
  ]) {
    const installed = installManagedBlock(original, binding);
    const eol = original.includes(Buffer.from("\r\n")) ? "\r\n" : "\n";
    assert.equal(installed.toString("utf8").includes(`${begin}${eol}`), true);
    assert.deepEqual(removeManagedBlock(installed), original);
  }
});

test("managed block preserves a UTF-8 BOM and all surrounding user bytes", () => {
  const original = Buffer.concat([
    Buffer.from([0xef, 0xbb, 0xbf]),
    Buffer.from("before\r\nafter without final newline", "utf8"),
  ]);
  const installed = installManagedBlock(original, binding);
  assert.deepEqual(installed.subarray(0, 3), Buffer.from([0xef, 0xbb, 0xbf]));
  assert.doesNotThrow(() => verifyManagedBlock(installed, binding));
  assert.deepEqual(removeManagedBlock(installed), original);
  assert.deepEqual(installManagedBlock(installed, binding), installed);
});

test("managed block update changes only its own bytes and reinstall is idempotent", () => {
  const outside = Buffer.from("user prefix\n", "utf8");
  const first = installManagedBlock(outside, binding);
  const updatedBinding = {
    ...binding,
    version: "1.0.0-rc.2",
    governancePath: binding.governancePath.replaceAll("1.0.0-rc.1", "1.0.0-rc.2"),
    manifestPath: binding.manifestPath.replaceAll("1.0.0-rc.1", "1.0.0-rc.2"),
    governanceDigest: "c".repeat(64),
  };
  const updated = installManagedBlock(first, updatedBinding);
  assert.equal(updated.subarray(0, outside.length).equals(outside), true);
  assert.equal(updated.toString("utf8").includes("1.0.0-rc.2"), true);
  assert.equal(updated.toString("utf8").includes("1.0.0-rc.1"), false);
  assert.deepEqual(installManagedBlock(updated, updatedBinding), updated);
  assert.deepEqual(removeManagedBlock(updated), outside);
});

test("managed block rejects duplicate, incomplete, foreign, and tampered blocks", () => {
  const valid = installManagedBlock(Buffer.alloc(0), binding).toString("utf8");
  for (const [text, pattern] of [
    [`${valid}${valid}`, /duplicate|ambiguous/],
    [`${begin}\nmissing end\n`, /incomplete/],
    [`<!-- BEGIN AGENT_GOVERNANCE_MANAGED_V2 -->\nforeign\n<!-- END AGENT_GOVERNANCE_MANAGED_V2 -->\n`, /foreign/],
  ] as const) {
    assert.throws(() => installManagedBlock(Buffer.from(text), binding), pattern);
    assert.throws(() => removeManagedBlock(Buffer.from(text)), pattern);
  }
  const tampered = Buffer.from(valid.replace(binding.manifestDigest, "d".repeat(64)));
  assert.throws(() => verifyManagedBlock(tampered, binding), /tampered|mismatch/);
});

test("managed block rejects malformed UTF-8", () => {
  assert.throws(() => installManagedBlock(Buffer.from([0xc3, 0x28]), binding), /UTF-8/);
});
