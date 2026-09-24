import assert from "node:assert/strict";
import test from "node:test";

import { resolveLatestRelease } from "../../src/installer/latest.ts";

function fetchReturning(payload: unknown, status = 200): typeof fetch {
  return (async () => new Response(JSON.stringify(payload), { status })) as unknown as typeof fetch;
}

test("resolves the registry latest semver once", async () => {
  const value = await resolveLatestRelease(fetchReturning({ "dist-tags": { latest: "1.4.5" } }));
  assert.equal(value, "1.4.5");
});

test("returns undefined when the registry fetch rejects", async () => {
  const failing = (async () => { throw new Error("offline"); }) as unknown as typeof fetch;
  assert.equal(await resolveLatestRelease(failing), undefined);
});

test("returns undefined on a non-ok response", async () => {
  assert.equal(await resolveLatestRelease(fetchReturning({}, 429)), undefined);
});

test("returns undefined for missing or invalid latest semver", async () => {
  assert.equal(await resolveLatestRelease(fetchReturning({ "dist-tags": {} })), undefined);
  assert.equal(await resolveLatestRelease(fetchReturning({ "dist-tags": { latest: "not-semver" } })), undefined);
});
