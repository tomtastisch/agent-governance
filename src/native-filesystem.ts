import { constants } from "node:fs";
import { open } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import type { PathIdentity } from "./filesystem.ts";

interface NativeBinding {
  secureRenameNoReplace(sourceFd: number, sourceName: string, sourceDev: bigint, sourceIno: bigint, destinationFd: number, destinationName: string, destinationDev: bigint, destinationIno: bigint): void;
  secureCreateNoReplace(directoryFd: number, name: string, directoryDev: bigint, directoryIno: bigint, content: Buffer): void;
  secureCreateDirectory(directoryFd: number, name: string, directoryDev: bigint, directoryIno: bigint): void;
  secureWriteFile(directoryFd: number, name: string, directoryDev: bigint, directoryIno: bigint, content: Buffer): void;
  secureRemoveFile(directoryFd: number, name: string, directoryDev: bigint, directoryIno: bigint): void;
  secureRemoveDirectory(directoryFd: number, name: string, directoryDev: bigint, directoryIno: bigint, objectDev: bigint, objectIno: bigint): void;
  secureRenameDirectoryNoReplace(sourceFd: number, sourceName: string, sourceDev: bigint, sourceIno: bigint, sourceObjectDev: bigint, sourceObjectIno: bigint, destinationFd: number, destinationName: string, destinationDev: bigint, destinationIno: bigint): void;
}

export interface SecureRenameRequest {
  readonly sourceDirectory: string;
  readonly sourceName: string;
  readonly destinationDirectory: string;
  readonly destinationName: string;
  readonly sourceDirectoryIdentity: PathIdentity;
  readonly destinationDirectoryIdentity: PathIdentity;
  readonly onDirectoriesBound?: () => void | Promise<void>;
}

export interface SecureCreateRequest {
  readonly directory: string;
  readonly name: string;
  readonly directoryIdentity: PathIdentity;
}

export interface SecureFileRequest extends SecureCreateRequest { readonly onDirectoryBound?: () => void | Promise<void>; }
export interface SecureDirectoryRenameRequest extends SecureRenameRequest { readonly sourceObjectIdentity: PathIdentity; }

function basename(value: string): void {
  if (value.length === 0 || value === "." || value === ".." || value.includes("/") || value.includes("\\") || value.includes("\0")) throw new Error("native filesystem names must be single valid basenames");
}

function loadBinding(): NativeBinding {
  if (!["darwin", "linux"].includes(process.platform) || !["arm64", "x64"].includes(process.arch)) throw new Error(`native filesystem capability is unsupported on ${process.platform}-${process.arch}`);
  const path = join(dirname(fileURLToPath(import.meta.url)), "..", "prebuilds", `${process.platform}-${process.arch}`, "agent_governance_fs.node");
  try { return createRequire(import.meta.url)(path) as NativeBinding; } catch (error) { throw new Error(`native filesystem capability is unavailable: ${(error as Error).message}`); }
}

export async function secureRenameNoReplace(request: SecureRenameRequest): Promise<void> {
  basename(request.sourceName); basename(request.destinationName);
  const binding = loadBinding();
  const flags = constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW;
  let source;
  let destination;
  try {
    source = await open(request.sourceDirectory, flags);
    destination = await open(request.destinationDirectory, flags);
    const sourceIdentity = await source.stat({ bigint: true }); const destinationIdentity = await destination.stat({ bigint: true });
    if (!sourceIdentity.isDirectory() || sourceIdentity.dev !== request.sourceDirectoryIdentity.device || sourceIdentity.ino !== request.sourceDirectoryIdentity.inode || Number(sourceIdentity.mode) !== request.sourceDirectoryIdentity.mode || !destinationIdentity.isDirectory() || destinationIdentity.dev !== request.destinationDirectoryIdentity.device || destinationIdentity.ino !== request.destinationDirectoryIdentity.inode || Number(destinationIdentity.mode) !== request.destinationDirectoryIdentity.mode) throw new Error("native filesystem directory identity changed");
    await request.onDirectoriesBound?.();
    binding.secureRenameNoReplace(source.fd, request.sourceName, sourceIdentity.dev, sourceIdentity.ino, destination.fd, request.destinationName, destinationIdentity.dev, destinationIdentity.ino);
  } finally {
    await destination?.close();
    await source?.close();
  }
}

export async function secureCreateNoReplace(request: SecureCreateRequest, content: Buffer): Promise<void> {
  basename(request.name); const binding = loadBinding(); const flags = constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW; const directory = await open(request.directory, flags);
  try { const identity = await directory.stat({ bigint: true }); if (!identity.isDirectory() || identity.dev !== request.directoryIdentity.device || identity.ino !== request.directoryIdentity.inode || Number(identity.mode) !== request.directoryIdentity.mode) throw new Error("native filesystem directory identity changed"); binding.secureCreateNoReplace(directory.fd, request.name, identity.dev, identity.ino, content); }
  finally { await directory.close(); }
}

export async function secureCreateDirectory(request: SecureFileRequest): Promise<void> {
  basename(request.name); const binding = loadBinding(); const directory = await open(request.directory, constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW);
  try { const identity = await directory.stat({ bigint: true }); if (!identity.isDirectory() || identity.dev !== request.directoryIdentity.device || identity.ino !== request.directoryIdentity.inode || Number(identity.mode) !== request.directoryIdentity.mode) throw new Error("native filesystem directory identity changed"); await request.onDirectoryBound?.(); binding.secureCreateDirectory(directory.fd, request.name, identity.dev, identity.ino); }
  finally { await directory.close(); }
}

export async function secureWriteFile(request: SecureFileRequest, content: Buffer): Promise<void> {
  basename(request.name); const binding = loadBinding(); const directory = await open(request.directory, constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW);
  try { const identity = await directory.stat({ bigint: true }); if (!identity.isDirectory() || identity.dev !== request.directoryIdentity.device || identity.ino !== request.directoryIdentity.inode || Number(identity.mode) !== request.directoryIdentity.mode) throw new Error("native filesystem directory identity changed"); await request.onDirectoryBound?.(); binding.secureWriteFile(directory.fd, request.name, identity.dev, identity.ino, content); }
  finally { await directory.close(); }
}

export async function secureRemoveFile(request: SecureFileRequest): Promise<void> {
  basename(request.name); const binding = loadBinding(); const directory = await open(request.directory, constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW);
  try { const identity = await directory.stat({ bigint: true }); if (!identity.isDirectory() || identity.dev !== request.directoryIdentity.device || identity.ino !== request.directoryIdentity.inode || Number(identity.mode) !== request.directoryIdentity.mode) throw new Error("native filesystem directory identity changed"); await request.onDirectoryBound?.(); binding.secureRemoveFile(directory.fd, request.name, identity.dev, identity.ino); }
  finally { await directory.close(); }
}

export async function secureRemoveDirectory(request: SecureFileRequest & { readonly objectIdentity: PathIdentity }): Promise<void> {
  basename(request.name); const binding = loadBinding(); const directory = await open(request.directory, constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW);
  try { const identity = await directory.stat({ bigint: true }); if (!identity.isDirectory() || identity.dev !== request.directoryIdentity.device || identity.ino !== request.directoryIdentity.inode || Number(identity.mode) !== request.directoryIdentity.mode) throw new Error("native filesystem directory identity changed"); await request.onDirectoryBound?.(); binding.secureRemoveDirectory(directory.fd, request.name, identity.dev, identity.ino, request.objectIdentity.device, request.objectIdentity.inode); }
  finally { await directory.close(); }
}

export async function secureRenameDirectoryNoReplace(request: SecureDirectoryRenameRequest): Promise<void> {
  basename(request.sourceName); basename(request.destinationName); const binding = loadBinding(); const flags = constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW; let source; let destination;
  try { source = await open(request.sourceDirectory, flags); destination = await open(request.destinationDirectory, flags); const sourceIdentity = await source.stat({ bigint: true }); const destinationIdentity = await destination.stat({ bigint: true }); if (!sourceIdentity.isDirectory() || sourceIdentity.dev !== request.sourceDirectoryIdentity.device || sourceIdentity.ino !== request.sourceDirectoryIdentity.inode || Number(sourceIdentity.mode) !== request.sourceDirectoryIdentity.mode || !destinationIdentity.isDirectory() || destinationIdentity.dev !== request.destinationDirectoryIdentity.device || destinationIdentity.ino !== request.destinationDirectoryIdentity.inode || Number(destinationIdentity.mode) !== request.destinationDirectoryIdentity.mode) throw new Error("native filesystem directory identity changed"); await request.onDirectoriesBound?.(); binding.secureRenameDirectoryNoReplace(source.fd, request.sourceName, sourceIdentity.dev, sourceIdentity.ino, request.sourceObjectIdentity.device, request.sourceObjectIdentity.inode, destination.fd, request.destinationName, destinationIdentity.dev, destinationIdentity.ino); }
  finally { await destination?.close(); await source?.close(); }
}

export async function probeNativeFilesystemCapability(directory: string, directoryIdentity: PathIdentity): Promise<void> {
  const token = randomUUID(); const sourceName = `.agent-governance-probe-${token}.source`; const destinationName = `.agent-governance-probe-${token}.destination`;
  await secureCreateNoReplace({ directory, name: sourceName, directoryIdentity }, Buffer.from("probe\n"));
  try { await secureRenameNoReplace({ sourceDirectory: directory, sourceName, sourceDirectoryIdentity: directoryIdentity, destinationDirectory: directory, destinationName, destinationDirectoryIdentity: directoryIdentity }); await secureRemoveFile({ directory, name: destinationName, directoryIdentity }); }
  catch (error) { try { await secureRemoveFile({ directory, name: sourceName, directoryIdentity }); } catch { /* Preserve the capability failure. */ } try { await secureRemoveFile({ directory, name: destinationName, directoryIdentity }); } catch { /* Preserve the capability failure. */ } throw error; }
}
