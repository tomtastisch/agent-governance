import assert from "node:assert/strict";
import { access, mkdir, open, readFile, rename, symlink, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { secureCreateNoReplace, secureRenameNoReplace } from "../../src/native-filesystem.ts";
import { captureIdentity } from "../../src/filesystem.ts";
import { createTestRoot } from "../fixtures/installer/workspace.ts";

interface NativeTestBinding {
  secureRenameNoReplace(sourceFd: number, sourceName: string, sourceDev: bigint, sourceIno: bigint, destinationFd: number, destinationName: string, destinationDev: bigint, destinationIno: bigint): void;
  secureCreateNoReplace(directoryFd: number, name: string, directoryDev: bigint, directoryIno: bigint, content: Buffer): void;
}

function nativeBinding(): NativeTestBinding {
  const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
  return createRequire(import.meta.url)(join(root, "prebuilds", `${process.platform}-${process.arch}`, "agent_governance_fs.node")) as NativeTestBinding;
}

async function renameBound(request: Omit<Parameters<typeof secureRenameNoReplace>[0], "sourceDirectoryIdentity" | "destinationDirectoryIdentity">): Promise<void> {
  await secureRenameNoReplace({ ...request, sourceDirectoryIdentity: await captureIdentity(request.sourceDirectory), destinationDirectoryIdentity: await captureIdentity(request.destinationDirectory) });
}

test("native rename remains bound to opened directory handles across pathname swaps", async () => {
  const root = await createTestRoot("agent-governance-native-swap-");
  const source = join(root, "source"); const destination = join(root, "destination");
  const movedSource = join(root, "source-moved"); const movedDestination = join(root, "destination-moved");
  const replacementSource = join(root, "source-replacement"); const replacementDestination = join(root, "destination-replacement");
  await mkdir(source); await mkdir(destination); await mkdir(replacementSource); await mkdir(replacementDestination);
  await writeFile(join(source, "entry.md"), "trusted bytes\n"); await writeFile(join(replacementDestination, "foreign.md"), "foreign bytes\n");
  await renameBound({ sourceDirectory: source, sourceName: "entry.md", destinationDirectory: destination, destinationName: "entry.bin", onDirectoriesBound: async () => {
    await rename(source, movedSource); await symlink(replacementSource, source);
    await rename(destination, movedDestination); await symlink(replacementDestination, destination);
  } });
  assert.equal(await readFile(join(movedDestination, "entry.bin"), "utf8"), "trusted bytes\n");
  assert.equal(await readFile(join(replacementDestination, "foreign.md"), "utf8"), "foreign bytes\n");
  await assert.rejects(access(join(replacementDestination, "entry.bin")));
});

test("platform characterization: same-UID final-component swaps are not an inode-CAS guarantee", async () => {
  const root = await createTestRoot("agent-governance-native-final-swap-"); const source = join(root, "source"); const destination = join(root, "destination"); const retired = join(source, "trusted-retired.md");
  await mkdir(source); await mkdir(destination); await writeFile(join(source, "entry.md"), "trusted bytes\n");
  await renameBound({ sourceDirectory: source, sourceName: "entry.md", destinationDirectory: destination, destinationName: "entry.bin", onDirectoriesBound: async () => { await rename(join(source, "entry.md"), retired); await writeFile(join(source, "entry.md"), "foreign bytes\n"); } });
  assert.equal(await readFile(retired, "utf8"), "trusted bytes\n"); await assert.rejects(access(join(source, "entry.md"))); assert.equal(await readFile(join(destination, "entry.bin"), "utf8"), "foreign bytes\n");
});

test("native rename atomically refuses an existing destination", async () => {
  const root = await createTestRoot("agent-governance-native-collision-"); const source = join(root, "source"); const destination = join(root, "destination");
  await mkdir(source); await mkdir(destination); await writeFile(join(source, "entry.md"), "source\n"); await writeFile(join(destination, "entry.bin"), "foreign\n");
  await assert.rejects(renameBound({ sourceDirectory: source, sourceName: "entry.md", destinationDirectory: destination, destinationName: "entry.bin" }), /exist|collision/i);
  assert.equal(await readFile(join(source, "entry.md"), "utf8"), "source\n"); assert.equal(await readFile(join(destination, "entry.bin"), "utf8"), "foreign\n");
});

test("native rename rejects unsafe basenames before mutation", async () => {
  const root = await createTestRoot("agent-governance-native-name-"); const source = join(root, "source"); const destination = join(root, "destination");
  await mkdir(source); await mkdir(destination); await writeFile(join(source, "entry.md"), "source\n");
  for (const name of ["", ".", "..", "nested/entry", "/absolute", "nested\\entry", "nul\0name"]) {
    await assert.rejects(renameBound({ sourceDirectory: source, sourceName: name, destinationDirectory: destination, destinationName: "entry.bin" }), /basename|invalid/i);
  }
  assert.equal(await readFile(join(source, "entry.md"), "utf8"), "source\n");
});

test("native rename rejects non-regular source objects", async () => {
  const root = await createTestRoot("agent-governance-native-type-"); const source = join(root, "source"); const destination = join(root, "destination"); const outside = join(root, "outside");
  await mkdir(source); await mkdir(destination); await writeFile(outside, "outside\n"); await symlink(outside, join(source, "entry.md"));
  await assert.rejects(renameBound({ sourceDirectory: source, sourceName: "entry.md", destinationDirectory: destination, destinationName: "entry.bin" }), /regular|type|symbolic/i);
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

test("native create is handle-bound and atomically refuses collisions", async () => {
  const root = await createTestRoot("agent-governance-native-create-"); const directory = join(root, "directory"); await mkdir(directory); const identity = await captureIdentity(directory);
  await secureCreateNoReplace({ directory, name: "entry.md", directoryIdentity: identity }, Buffer.from("created\n")); assert.equal(await readFile(join(directory, "entry.md"), "utf8"), "created\n");
  await assert.rejects(secureCreateNoReplace({ directory, name: "entry.md", directoryIdentity: identity }, Buffer.from("replacement\n")), /exist/i); assert.equal(await readFile(join(directory, "entry.md"), "utf8"), "created\n");
});

test("native create rejects a substituted directory before writing foreign bytes", async () => {
  const root = await createTestRoot("agent-governance-native-create-swap-"); const directory = join(root, "directory"); const retired = join(root, "retired"); await mkdir(directory); const identity = await captureIdentity(directory); await rename(directory, retired); await mkdir(directory); await writeFile(join(directory, "foreign.md"), "foreign\n");
  await assert.rejects(secureCreateNoReplace({ directory, name: "entry.md", directoryIdentity: identity }, Buffer.from("created\n")), /identity changed/); assert.equal(await readFile(join(directory, "foreign.md"), "utf8"), "foreign\n"); await assert.rejects(access(join(directory, "entry.md")));
});

test("native create removes its exclusive partial file after an injected write failure", async () => {
  const root = await createTestRoot("agent-governance-native-create-failure-"); const directory = join(root, "directory"); await mkdir(directory); const repository = join(dirname(fileURLToPath(import.meta.url)), "..", ".."); const output = join(root, "failure.node");
  const includeCandidates = [join(dirname(process.execPath), "..", "include", "node"), "/usr/local/include/node", "/opt/homebrew/include/node", "/usr/include/node"]; let include: string | undefined; for (const candidate of includeCandidates) { try { await access(join(candidate, "node_api.h")); include = candidate; break; } catch { /* next local header root */ } } assert.notEqual(include, undefined);
  const platformFlags = process.platform === "darwin" ? ["-bundle", "-undefined", "dynamic_lookup"] : ["-shared", "-fPIC"]; const build = spawnSync(process.env.CC ?? "cc", ["-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", ...platformFlags, `-I${include!}`, "-DNODE_GYP_MODULE_NAME=agent_governance_fs", "-DAGENT_GOVERNANCE_TEST_FAIL_AFTER_CREATE=1", join(repository, "native", "agent_governance_fs.c"), "-o", output]); assert.equal(build.status, 0, build.stderr.toString());
  const binding = createRequire(import.meta.url)(output) as NativeTestBinding; const handle = await open(directory, "r"); try { const identity = await handle.stat({ bigint: true }); assert.throws(() => binding.secureCreateNoReplace(handle.fd, "entry.md", identity.dev, identity.ino, Buffer.from("content\n")), /write|input\/output|I\/O/i); await assert.rejects(access(join(directory, "entry.md"))); } finally { await handle.close(); }
});
