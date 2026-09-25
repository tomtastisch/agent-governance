import { chmod, lstat, mkdir, readFile, readdir, rename, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { mock } from "node:test";
import * as native from "../../../src/native-filesystem.ts";
import * as mutation from "../../../src/installer/mutation.ts";

const request = JSON.parse(process.argv[2]!);
const mode = process.argv[3]!;
const entry = join(request.targetRoot, request.entryFile);
let substituted: string | undefined;
let foreignInode: bigint | undefined;
mock.module("../../../src/native-filesystem.ts", { namedExports: {
  ...native,
  secureCreateDirectory: async (input: Parameters<typeof native.secureCreateDirectory>[0]) => {
    const created = await native.secureCreateDirectory(input);
    const path = join(input.directory, input.name);
    if (substituted === undefined && (mode.startsWith("quarantine") && input.name.startsWith(".agent-governance-quarantine-") || mode.startsWith("destination") && path === request.installationRoot)) {
      substituted = path;
      await rename(path, `${path}.created`);
      await mkdir(path);
      await chmod(path, mode.endsWith("777") ? 0o777 : 0o700);
    }
    return created;
  },
} });
mock.module("../../../src/installer/mutation.ts", { namedExports: {
  ...mutation,
  atomicWrite: async (...args: Parameters<typeof mutation.atomicWrite>) => {
    if (mode.startsWith("late-entry") && args[0] === entry && foreignInode === undefined) {
      const bytes = await readFile(entry);
      await rename(entry, `${entry}.owned`);
      await writeFile(entry, bytes);
      foreignInode = (await lstat(entry, { bigint: true })).ino;
    }
    return mutation.atomicWrite(...args);
  },
} });
const { replaceInstallation } = await import("../../../src/replacement.ts");
let outcome: string;
if (mode === "late-entry-transaction") {
  const { InstallerTransaction } = await import("../../../src/transaction.ts");
  try { await new InstallerTransaction({ ...request, dryRun: false, scope: "global", nonInteractive: true }).install(); outcome = "SUCCESS"; } catch { outcome = "FAILURE"; }
} else outcome = (await replaceInstallation(request)).outcome;
console.log(JSON.stringify({ outcome, injected: substituted !== undefined || foreignInode !== undefined, foreignPreserved: foreignInode === undefined || (await lstat(entry, { bigint: true })).ino === foreignInode, substituteEmpty: substituted === undefined || (await readdir(substituted)).length === 0 }));
