import { isAbsolute, normalize, resolve } from "node:path";

import type { Candidate } from "../discovery/types.ts";
import type { InitManualInput, InitTarget } from "./types.ts";

function validateRoot(root: string): void {
  if (root === "" || /[\0\r\n]/.test(root) || !isAbsolute(root) || resolve(root) !== root) {
    throw new Error("target root must be a canonical absolute path");
  }
}

function validateEntry(entryFile: string): void {
  if (
    entryFile === ""
    || /[\0\r\n]/.test(entryFile)
    || isAbsolute(entryFile)
    || entryFile.includes("\\")
    || entryFile === ".."
    || entryFile.startsWith("../")
    || normalize(entryFile) !== entryFile
  ) {
    throw new Error("entry file must be a canonical relative path without traversal");
  }
  if (!/\.(?:md|markdown)$/i.test(entryFile)) {
    throw new Error("entry file must be Markdown");
  }
}

export function resolveBinding(
  candidate: Candidate | undefined,
  manualInput: InitManualInput,
): InitTarget {
  if (candidate?.confidence === "REJECTED") {
    throw new Error("rejected discovery candidate cannot become an init target");
  }
  if (
    candidate !== undefined
    && manualInput.targetRoot !== undefined
    && manualInput.targetRoot !== candidate.root
  ) {
    throw new Error("manual target root conflicts with the selected candidate");
  }
  const targetRoot = candidate?.root ?? manualInput.targetRoot;
  if (targetRoot === undefined) throw new Error("manual target root is required");
  validateRoot(targetRoot);
  validateEntry(manualInput.entryFile);
  return Object.freeze({ targetRoot, entryFile: manualInput.entryFile });
}
