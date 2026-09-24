import { isAbsolute, normalize, resolve } from "node:path";

import { resolveSupport } from "./support.ts";
import type { InitEnvironment, InitManualInput, InitSelection, InitTarget } from "./types.ts";

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

export function resolveManualTarget(manualInput: InitManualInput): InitTarget {
  const targetRoot = manualInput.targetRoot;
  if (targetRoot === undefined) throw new Error("manual target root is required");
  validateRoot(targetRoot);
  validateEntry(manualInput.entryFile);
  return Object.freeze({ targetRoot, entryFile: manualInput.entryFile });
}

export function resolveTarget(selection: InitSelection, environment: InitEnvironment): InitTarget {
  if ("harness" in selection) {
    const decision = resolveSupport(selection.harness.id, environment);
    if (!decision.supported) throw new Error("selected harness is not supported");
    return Object.freeze({ targetRoot: decision.targetRoot, entryFile: decision.entryFile });
  }
  return resolveManualTarget(selection.manualInput);
}
