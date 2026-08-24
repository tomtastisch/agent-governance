import assert from "node:assert/strict";
import { access, mkdir, open, readFile, rename, symlink, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { spawnSync } from "node:child_process";
import { mkdirSync, renameSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { probeNativeFilesystemCapability, secureCreateDirectory, secureCreateNoReplace, secureRemoveFile, secureRenameDirectoryNoReplace, secureRenameNoReplace, secureWriteFile } from "../../src/native-filesystem.ts";
import { captureIdentity } from "../../src/filesystem.ts";
import { createTestRoot } from "../fixtures/installer/workspace.ts";

interface NativeTestBinding {
  secureRenameNoReplace(sourceFd: number, sourceName: string, sourceDev: bigint, sourceIno: bigint, destinationFd: number, destinationName: string, destinationDev: bigint, destinationIno: bigint): void;
  secureCreateNoReplace(directoryFd: number, name: string, directoryDev: bigint, directoryIno: bigint, content: Buffer): void;
  secureWriteFile(directoryFd: number, name: string, directoryDev: bigint, directoryIno: bigint, objectDev: bigint, objectIno: bigint, objectMode: bigint, content: Buffer): void;
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

test("native directory creation remains bound to the validated parent", async () => {
  const root = await createTestRoot("agent-governance-native-mkdir-swap-"); const parent = join(root, "parent"); const retired = join(root, "retired"); await mkdir(parent); const identity = await captureIdentity(parent);
  await secureCreateDirectory({ directory: parent, name: "reserved", directoryIdentity: identity, onDirectoryBound: async () => { renameSync(parent, retired); mkdirSync(parent); writeFileSync(join(parent, "foreign.md"), "foreign\n"); } });
  await access(join(retired, "reserved")); await assert.rejects(access(join(parent, "reserved"))); assert.equal(await readFile(join(parent, "foreign.md"), "utf8"), "foreign\n");
});

test("native create removes its exclusive partial file after an injected write failure", async () => {
  const root = await createTestRoot("agent-governance-native-create-failure-"); const directory = join(root, "directory"); await mkdir(directory); const repository = join(dirname(fileURLToPath(import.meta.url)), "..", ".."); const output = join(root, "failure.node");
  const includeCandidates = [join(dirname(process.execPath), "..", "include", "node"), "/usr/local/include/node", "/opt/homebrew/include/node", "/usr/include/node"]; let include: string | undefined; for (const candidate of includeCandidates) { try { await access(join(candidate, "node_api.h")); include = candidate; break; } catch { /* next local header root */ } } assert.notEqual(include, undefined);
  const platformFlags = process.platform === "darwin" ? ["-bundle", "-undefined", "dynamic_lookup"] : ["-shared", "-fPIC"]; const build = spawnSync(process.env.CC ?? "cc", ["-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", ...platformFlags, `-I${include!}`, "-DNODE_GYP_MODULE_NAME=agent_governance_fs", "-DAGENT_GOVERNANCE_TEST_FAIL_AFTER_CREATE=1", join(repository, "native", "agent_governance_fs.c"), "-o", output]); assert.equal(build.status, 0, build.stderr.toString());
  const binding = createRequire(import.meta.url)(output) as NativeTestBinding; const handle = await open(directory, "r"); try { const identity = await handle.stat({ bigint: true }); assert.throws(() => binding.secureCreateNoReplace(handle.fd, "entry.md", identity.dev, identity.ino, Buffer.from("content\n")), /write|input\/output|I\/O/i); await assert.rejects(access(join(directory, "entry.md"))); } finally { await handle.close(); }
});

test("native replace and remove remain bound to the validated parent across pathname swaps", async () => {
  const root = await createTestRoot("agent-governance-native-file-parent-swap-"); const parent = join(root, "parent"); const retired = join(root, "retired"); await mkdir(parent); await writeFile(join(parent, "entry.json"), "trusted old\n"); const identity = await captureIdentity(parent); let swapped = false;
  const entryIdentity = await captureIdentity(join(parent, "entry.json")); await secureWriteFile({ directory: parent, name: "entry.json", directoryIdentity: identity, objectIdentity: entryIdentity, onDirectoryBound: async () => { renameSync(parent, retired); mkdirSync(parent); writeFileSync(join(parent, "entry.json"), "foreign\n"); swapped = true; } }, Buffer.from("trusted new\n")); assert.equal(swapped, true); assert.equal(await readFile(join(retired, "entry.json"), "utf8"), "trusted new\n"); assert.equal(await readFile(join(parent, "entry.json"), "utf8"), "foreign\n");
  await secureRemoveFile({ directory: retired, name: "entry.json", directoryIdentity: identity, objectIdentity: await captureIdentity(join(retired, "entry.json")) }); await assert.rejects(access(join(retired, "entry.json"))); assert.equal(await readFile(join(parent, "entry.json"), "utf8"), "foreign\n");
});

test("native replace and remove reject a final-component substitution before the syscall", async () => {
  const root = await createTestRoot("agent-governance-native-final-object-swap-"); const parent = join(root, "parent"); await mkdir(parent); const identity = await captureIdentity(parent);
  await writeFile(join(parent, "entry.json"), "trusted old\n"); const entryIdentity = await captureIdentity(join(parent, "entry.json")); const retiredWrite = join(parent, "trusted-write-retired.json"); await assert.rejects(secureWriteFile({ directory: parent, name: "entry.json", directoryIdentity: identity, objectIdentity: entryIdentity, onDirectoryBound: async () => { await rename(join(parent, "entry.json"), retiredWrite); await writeFile(join(parent, "entry.json"), "foreign write\n"); } }, Buffer.from("installer new\n")), /identity|stale/i); assert.equal(await readFile(join(parent, "entry.json"), "utf8"), "foreign write\n");
  await writeFile(join(parent, "owner.json"), "trusted owner\n"); const ownerIdentity = await captureIdentity(join(parent, "owner.json")); const retiredRemove = join(parent, "trusted-owner-retired.json"); await assert.rejects(secureRemoveFile({ directory: parent, name: "owner.json", directoryIdentity: identity, objectIdentity: ownerIdentity, onDirectoryBound: async () => { await rename(join(parent, "owner.json"), retiredRemove); await writeFile(join(parent, "owner.json"), "foreign owner\n"); } }), /identity|stale/i); assert.equal(await readFile(join(parent, "owner.json"), "utf8"), "foreign owner\n");
});

test("native replace and remove reject substitution after the caller snapshot", async () => {
  const root = await createTestRoot("agent-governance-native-snapshot-handoff-"); const parent = join(root, "parent"); await mkdir(parent); const parentIdentity = await captureIdentity(parent);
  await writeFile(join(parent, "current.json"), "trusted current\n"); const currentIdentity = await captureIdentity(join(parent, "current.json")); await rename(join(parent, "current.json"), join(parent, "trusted-current-retired.json")); await writeFile(join(parent, "current.json"), "foreign current\n"); await assert.rejects(secureWriteFile({ directory: parent, name: "current.json", directoryIdentity: parentIdentity, objectIdentity: currentIdentity }, Buffer.from("installer current\n")), /identity|stale/i); assert.equal(await readFile(join(parent, "current.json"), "utf8"), "foreign current\n");
  await writeFile(join(parent, "owner.json"), "trusted owner\n"); const ownerIdentity = await captureIdentity(join(parent, "owner.json")); await rename(join(parent, "owner.json"), join(parent, "trusted-owner-retired.json")); await writeFile(join(parent, "owner.json"), "foreign owner\n"); await assert.rejects(secureRemoveFile({ directory: parent, name: "owner.json", directoryIdentity: parentIdentity, objectIdentity: ownerIdentity }), /identity|stale/i); assert.equal(await readFile(join(parent, "owner.json"), "utf8"), "foreign owner\n");
});

test("native replace rejects a substituted visible temporary source", async () => {
  const root = await createTestRoot("agent-governance-native-temp-swap-"); const directory = join(root, "directory"); await mkdir(directory); await writeFile(join(directory, "entry.json"), "trusted old\n"); const repository = join(dirname(fileURLToPath(import.meta.url)), "..", ".."); const output = join(root, "temp-swap.node");
  const includeCandidates = [join(dirname(process.execPath), "..", "include", "node"), "/usr/local/include/node", "/opt/homebrew/include/node", "/usr/include/node"]; let include: string | undefined; for (const candidate of includeCandidates) { try { await access(join(candidate, "node_api.h")); include = candidate; break; } catch { /* next local header root */ } } assert.notEqual(include, undefined);
  const platformFlags = process.platform === "darwin" ? ["-bundle", "-undefined", "dynamic_lookup"] : ["-shared", "-fPIC"]; const build = spawnSync(process.env.CC ?? "cc", ["-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", ...platformFlags, `-I${include!}`, "-DNODE_GYP_MODULE_NAME=agent_governance_fs", "-DAGENT_GOVERNANCE_TEST_SWAP_REPLACE_TEMP=1", join(repository, "native", "agent_governance_fs.c"), "-o", output]); assert.equal(build.status, 0, build.stderr.toString());
  const binding = createRequire(import.meta.url)(output) as NativeTestBinding; const handle = await open(directory, "r"); try { const parent = await handle.stat({ bigint: true }); const object = await import("node:fs/promises").then(({ lstat }) => lstat(join(directory, "entry.json"), { bigint: true })); assert.throws(() => binding.secureWriteFile(handle.fd, "entry.json", parent.dev, parent.ino, object.dev, object.ino, object.mode, Buffer.from("installer new\n")), /temporary.*identity|stale/i); } finally { await handle.close(); } assert.equal(await readFile(join(directory, "entry.json"), "utf8"), "trusted old\n");
});

test("native directory activation remains bound to validated source and destination parents", async () => {
  const root = await createTestRoot("agent-governance-native-directory-parent-swap-"); const sourceParent = join(root, "source"); const destinationParent = join(root, "destination"); const retiredSource = join(root, "source-retired"); const retiredDestination = join(root, "destination-retired"); await mkdir(sourceParent); await mkdir(destinationParent); await mkdir(join(sourceParent, "release")); await writeFile(join(sourceParent, "release", "marker"), "trusted\n"); const sourceIdentity = await captureIdentity(sourceParent); const destinationIdentity = await captureIdentity(destinationParent); const releaseIdentity = await captureIdentity(join(sourceParent, "release"));
  await secureRenameDirectoryNoReplace({ sourceDirectory: sourceParent, sourceName: "release", sourceDirectoryIdentity: sourceIdentity, sourceObjectIdentity: releaseIdentity, destinationDirectory: destinationParent, destinationName: "release", destinationDirectoryIdentity: destinationIdentity, onDirectoriesBound: async () => { renameSync(sourceParent, retiredSource); renameSync(destinationParent, retiredDestination); mkdirSync(sourceParent); mkdirSync(destinationParent); } }); assert.equal(await readFile(join(retiredDestination, "release", "marker"), "utf8"), "trusted\n"); await assert.rejects(access(join(destinationParent, "release")));
});

test("native capability probe exercises the actual rename contract and leaves no artifact", async () => {
  const root = await createTestRoot("agent-governance-native-probe-"); const identity = await captureIdentity(root); await probeNativeFilesystemCapability(root, identity); assert.deepEqual(await import("node:fs/promises").then(({ readdir }) => readdir(root)), []);
});
