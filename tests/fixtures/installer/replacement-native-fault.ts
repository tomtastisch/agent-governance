import { mock } from "node:test";
import * as native from "../../../src/native-filesystem.ts";

mock.module("../../../src/native-filesystem.ts", { namedExports: {
  ...native,
  secureRenameNoReplace: async (request: native.SecureRenameRequest) => {
    await native.secureRenameNoReplace(request);
    if (request.destinationName === "detached.bin" && process.argv[3] === "kill") process.kill(process.pid, "SIGKILL");
    if (request.destinationName === "detached.bin") throw new Error("synthetic close failure after rename");
  },
} });
const { replaceInstallation } = await import("../../../src/replacement.ts");
console.log(JSON.stringify(await replaceInstallation(JSON.parse(process.argv[2]!))));
