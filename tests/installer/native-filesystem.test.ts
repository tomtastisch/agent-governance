import assert from "node:assert/strict";
import { access, mkdir, open, readFile, rename, symlink, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { secureRenameNoReplace } from "../../src/native-filesystem.ts";
import { createTestRoot } from "../fixtures/installer/workspace.ts";

interface NativeTestBinding {
  secureRenameNoReplace(sourceFd: number, sourceName: string, sourceDev: bigint, sourceIno: bigint, destinationFd: number, destinationName: string, destinationDev: bigint, destinationIno: bigint): void;
}

function nativeBinding(): NativeTestBinding {
  const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
  return createRequire(import.meta.url)(join(root, "prebuilds", `${process.platform}-${process.arch}`, "agent_governance_fs.node")) as NativeTestBinding;
}

test("native rename remains bound to opened directory handles across pathname swaps", async () => {
  const root = await createTestRoot("agent-governance-native-swap-");
  const source = join(root, "source"); const destination = join(root, "destination");
  const movedSource = join(root, "source-moved"); const movedDestination = join(root, "destination-moved");
  const replacementSource = join(root, "source-replacement"); const replacementDestination = join(root, "destination-replacement");
  await mkdir(source); await mkdir(destination); await mkdir(replacementSource); await mkdir(replacementDestination);
  await writeFile(join(source, "entry.md"), "trusted bytes\n"); await writeFile(join(replacementDestination, "foreign.md"), "foreign bytes\n");
  await secureRenameNoReplace({ sourceDirectory: source, sourceName: "entry.md", destinationDirectory: destination, destinationName: "entry.bin", onDirectoriesBound: async () => {
    await rename(source, movedSource); await symlink(replacementSource, source);
    await rename(destination, movedDestination); await symlink(replacementDestination, destination);
  } });
  assert.equal(await readFile(join(movedDestination, "entry.bin"), "utf8"), "trusted bytes\n");
  assert.equal(await readFile(join(replacementDestination, "foreign.md"), "utf8"), "foreign bytes\n");
  await assert.rejects(access(join(replacementDestination, "entry.bin")));
});

test("native rename atomically refuses an existing destination", async () => {
  const root = await createTestRoot("agent-governance-native-collision-"); const source = join(root, "source"); const destination = join(root, "destination");
  await mkdir(source); await mkdir(destination); await writeFile(join(source, "entry.md"), "source\n"); await writeFile(join(destination, "entry.bin"), "foreign\n");
  await assert.rejects(secureRenameNoReplace({ sourceDirectory: source, sourceName: "entry.md", destinationDirectory: destination, destinationName: "entry.bin" }), /exist|collision/i);
  assert.equal(await readFile(join(source, "entry.md"), "utf8"), "source\n"); assert.equal(await readFile(join(destination, "entry.bin"), "utf8"), "foreign\n");
});

test("native rename rejects unsafe basenames before mutation", async () => {
  const root = await createTestRoot("agent-governance-native-name-"); const source = join(root, "source"); const destination = join(root, "destination");
  await mkdir(source); await mkdir(destination); await writeFile(join(source, "entry.md"), "source\n");
  for (const name of ["", ".", "..", "nested/entry", "/absolute", "nested\\entry", "nul\0name"]) {
    await assert.rejects(secureRenameNoReplace({ sourceDirectory: source, sourceName: name, destinationDirectory: destination, destinationName: "entry.bin" }), /basename|invalid/i);
  }
  assert.equal(await readFile(join(source, "entry.md"), "utf8"), "source\n");
});

test("native rename rejects non-regular source objects", async () => {
  const root = await createTestRoot("agent-governance-native-type-"); const source = join(root, "source"); const destination = join(root, "destination"); const outside = join(root, "outside");
  await mkdir(source); await mkdir(destination); await writeFile(outside, "outside\n"); await symlink(outside, join(source, "entry.md"));
  await assert.rejects(secureRenameNoReplace({ sourceDirectory: source, sourceName: "entry.md", destinationDirectory: destination, destinationName: "entry.bin" }), /regular|type|symbolic/i);
  assert.equal(await readFile(outside, "utf8"), "outside\n"); await assert.rejects(access(join(destination, "entry.bin")));
});

test("native boundary rejects invalid directory descriptors and stale identities", async () => {
  const root = await createTestRoot("agent-governance-native-fd-"); const source = join(root, "source"); const destination = join(root, "destination");
  await mkdir(source); await mkdir(destination); await writeFile(join(source, "entry.md"), "source\n");
  const sourceHandle = await open(source, "r"); const destinationHandle = await open(destination, "r");
  try {
    const sourceIdentity = await sourceHandle.stat({ bigint: true }); const destinationIdentity = await destinationHandle.stat({ bigint: true }); const binding = nativeBinding();
    assert.throws(() => binding.secureRenameNoReplace(-1, "entry.md", sourceIdentity.dev, sourceIdentity.ino, destinationHandle.fd, "entry.bin", destinationIdentity.dev, destinationIdentity.ino), /directory fds|invalid/i);
    assert.throws(() => binding.secureRenameNoReplace(sourceHandle.fd, "entry.md", sourceIdentity.dev, sourceIdentity.ino + 1n, destinationHandle.fd, "entry.bin", destinationIdentity.dev, destinationIdentity.ino), /identity|stale/i);
  } finally { await destinationHandle.close(); await sourceHandle.close(); }
  assert.equal(await readFile(join(source, "entry.md"), "utf8"), "source\n"); await assert.rejects(access(join(destination, "entry.bin")));
});
