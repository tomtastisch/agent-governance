import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import test from "node:test";

// Das Buildwerkzeug ist absichtlich kein Teil der Runtime.
const { extractHarnessDescriptors } = await import("../../tools/project-harness-discovery.ts");
const fixture = `var Harness = class { isInstalled() {} };
var One = class extends Harness { id = "one"; name = "Eins"; binaries = ["one", "one-cli"]; };
var Two = class extends Harness { id = "two"; name = "Zwei"; binaries = ["two"]; };
const harnesses = [Two, One];`;

test("Discovery-Projektion erhält Registry-Reihenfolge, Namen und alternative Binärnamen", () => {
  assert.deepEqual(extractHarnessDescriptors(fixture), [
    { id: "two", displayName: "Zwei", binaries: ["two"] },
    { id: "one", displayName: "Eins", binaries: ["one", "one-cli"] },
  ]);
});

for (const [name, source] of [
  ["dynamischer Name", fixture.replace('name = "Eins"', 'name = getName()')],
  ["dynamische Registry", fixture.replace('[Two, One]', '[...others, One]')],
  ["statischer Block", fixture.replace('id = "one";', 'static { this.prototype.isInstalled = () => false; } id = "one";')],
  ["Konstruktor", fixture.replace('id = "one";', 'constructor() { super(); } id = "one";')],
  ["abweichende Installed-Prüfung", fixture.replace('id = "one";', 'isInstalled() { return true; } id = "one";')],
  ["doppelte ID", fixture.replace('id = "two"', 'id = "one"')],
  ["Option als Binärname", fixture.replace('["two"]', '["--version"]')],
  ["doppelte Registryreferenz", fixture.replace('[Two, One]', '[One, One]')],
  ["unbekannte Basisklasse", fixture.replace('class extends Harness', 'class extends Unknown')],
] as const) {
  test(`Discovery-Projektion blockiert ${name}`, () => {
    assert.throws(() => extractHarnessDescriptors(source));
  });
}

test("eingecheckte Discovery-Projektion und Lizenz stimmen mit dem verifizierten Archiv überein", () => {
  const result = spawnSync(process.execPath, ["tools/project-harness-discovery.ts", "--check"], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /13 Discovery-Einträge/u);
  const metadata = JSON.parse(readFileSync("package.json", "utf8"));
  assert.equal(metadata.dependencies["@agntn/harnesses"], undefined);
  assert.ok(metadata.files.includes("THIRD_PARTY_NOTICES.md"));
});

test("Archiv-, Lizenz- und Projektionsdrift werden vor dem Build blockiert", async () => {
  const { cp, mkdir, mkdtemp, rm, writeFile } = await import("node:fs/promises");
  const { tmpdir } = await import("node:os");
  const { join } = await import("node:path");
  const { checkProjection, discoveryBehaviorDigest } = await import("../../tools/project-harness-discovery.ts");
  const root = await mkdtemp(join(tmpdir(), "governance-projection-"));
  try {
    await mkdir(join(root, "src/init"), { recursive: true });
    await mkdir(join(root, "integrations"));
    await cp("integrations/agntn-harnesses", join(root, "integrations/agntn-harnesses"), { recursive: true });
    for (const path of ["src/init/harness-discovery.generated.ts", "THIRD_PARTY_NOTICES.md"]) {
      await cp(path, join(root, path));
    }
    checkProjection(false, root);
    for (const path of ["src/init/harness-discovery.generated.ts", "THIRD_PARTY_NOTICES.md", "integrations/agntn-harnesses/upstream/harnesses-0.3.0.tgz"]) {
      const original = readFileSync(join(root, path));
      await writeFile(join(root, path), "manipuliert");
      assert.throws(() => checkProjection(false, root), /Nicht unterstützte Upstream-Discovery/u);
      await writeFile(join(root, path), original);
    }
    const source = fixture + "function getRegistry() { return []; } function getAllHarnesses() { return []; }";
    assert.notEqual(discoveryBehaviorDigest(source), discoveryBehaviorDigest(source.replace('isInstalled() {}', 'isInstalled() { return true; }')));
    assert.notEqual(discoveryBehaviorDigest(source), discoveryBehaviorDigest(source.replace('binaries = ["two"];', 'binaries = ["two"]; mutate = (this.binaries = ["different"]);')));
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
