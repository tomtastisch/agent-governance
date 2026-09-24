import { join } from "node:path";
import { lstat } from "node:fs/promises";

import { resolveTarget } from "./bindings.ts";
import { resolveSupport } from "./support.ts";
import {
  INIT_CANCELLED,
  INIT_STEPS,
  type DiscoveredHarness,
  type HarnessRow,
  type InitDependencies,
  type InitOptions,
  type InitPlannedTarget,
  type InitResult,
  type InitSelection,
  type InitTarget,
  type InitTargetResult,
  type InitTransaction,
} from "./types.ts";

interface PreparedTarget extends InitPlannedTarget {
  readonly transaction: InitTransaction;
}

const NO_TARGETS = Object.freeze([]) as readonly [];

function cancelled(): InitResult {
  return Object.freeze({
    schemaVersion: 1,
    command: "init",
    outcome: "INTERRUPTED",
    reason: "CANCELLED",
    targets: NO_TARGETS,
  });
}

function compareTargets(left: InitTarget, right: InitTarget): number {
  if (left.targetRoot !== right.targetRoot) return left.targetRoot < right.targetRoot ? -1 : 1;
  if (left.entryFile === right.entryFile) return 0;
  return left.entryFile < right.entryFile ? -1 : 1;
}

function targetKey(target: InitTarget): string {
  return `${target.targetRoot}\0${target.entryFile}`;
}

function selectionLabel(selection: InitSelection): string {
  return "harness" in selection ? selection.harness.displayName : "Manuell";
}

async function directoryExists(path: string): Promise<boolean> {
  try {
    const stat = await lstat(path);
    return !stat.isSymbolicLink() && stat.isDirectory();
  } catch {
    return false;
  }
}

async function buildRows(
  discovered: readonly DiscoveredHarness[],
  options: InitOptions,
  installationRoot: string,
  latestVersion: string | undefined,
  dependencies: InitDependencies,
): Promise<readonly HarnessRow[]> {
  const rows: HarnessRow[] = [];
  for (const harness of discovered) {
    const decision = resolveSupport(harness.id, options.environment);
    if (!decision.supported) {
      rows.push(Object.freeze({
        id: harness.id,
        displayName: harness.displayName,
        supported: false,
      }));
      continue;
    }
    const rowBase = {
      id: harness.id,
      displayName: harness.displayName,
      supported: true,
      targetRoot: decision.targetRoot,
      entryFile: decision.entryFile,
    };
    if (!await directoryExists(decision.targetRoot)) {
      rows.push(Object.freeze({ ...rowBase, state: "ABSENT" }));
      continue;
    }
    const transaction = dependencies.createTransaction({
      targetRoot: decision.targetRoot,
      entryFile: decision.entryFile,
      scope: "global",
      installationRoot,
      dryRun: false,
      nonInteractive: false,
      releaseRoot: options.releaseRoot,
    });
    const status = await transaction.status();
    const localVersion = await transaction.localVersion();
    rows.push(Object.freeze({
      ...rowBase,
      state: status.state,
      ...(localVersion === undefined ? {} : { localVersion }),
      ...(latestVersion === undefined ? {} : { latestVersion }),
    }));
  }
  return Object.freeze(rows);
}

export async function runInit(options: InitOptions, dependencies: InitDependencies): Promise<InitResult> {
  if (!options.isTTY) {
    return Object.freeze({
      schemaVersion: 1,
      command: "init",
      outcome: "INVALID_INVOCATION",
      reason: "NON_TTY",
      guidance: "Use an explicit transaction command with --non-interactive.",
      targets: NO_TARGETS,
    });
  }

  try {
    const installationRoot = options.installationRoot ?? join(options.environment.home, ".agent-governance");

    dependencies.prompt.step(INIT_STEPS[0]!);
    const discovered = await dependencies.discoverHarnesses({ environment: options.environment });
    const latestVersion = await dependencies.resolveLatestRelease();
    const rows = await buildRows(discovered, options, installationRoot, latestVersion, dependencies);

    dependencies.prompt.step(INIT_STEPS[1]!);
    const selections = await dependencies.prompt.selectTargets(rows);
    if (selections === INIT_CANCELLED) return cancelled();
    if (selections.length === 0) throw new Error("no init targets selected");
    const resolved = selections
      .map((selection) => ({ selection, target: resolveTarget(selection, options.environment) }))
      .sort((left, right) => compareTargets(left.target, right.target));
    const keys = resolved.map(({ target }) => targetKey(target));
    if (new Set(keys).size !== keys.length) throw new Error("duplicate init target");

    dependencies.prompt.step(INIT_STEPS[2]!);
    const prepared: PreparedTarget[] = [];
    for (const { selection, target } of resolved) {
      const transaction = dependencies.createTransaction({
        targetRoot: target.targetRoot,
        entryFile: target.entryFile,
        scope: "global",
        installationRoot,
        dryRun: false,
        nonInteractive: false,
        releaseRoot: options.releaseRoot,
      });
      const status = await transaction.status();
      const operation = status.state === "OUTDATED" ? "update" : "install";
      const plan = await transaction.plan(operation);
      prepared.push(Object.freeze({ target, status, plan, displayName: selectionLabel(selection), transaction }));
    }

    const approvalPlans: readonly InitPlannedTarget[] = prepared.map(
      ({ target, status, plan, displayName }) => Object.freeze({ target, status, plan, displayName }),
    );
    const approved = await dependencies.prompt.confirm(approvalPlans);
    if (approved === INIT_CANCELLED || !approved) return cancelled();

    const completed: InitTargetResult[] = [];
    for (const item of prepared) {
      const installed = item.status.state === "OUTDATED"
        ? await item.transaction.update()
        : await item.transaction.install();
      if (installed.outcome !== "SUCCESS") throw new Error("init installation failed");
      const verified = await item.transaction.verify();
      if (verified.outcome !== "SUCCESS" || verified.state !== "CURRENT") {
        throw new Error("init verification failed");
      }
      completed.push(Object.freeze({
        target: item.target,
        previousState: item.status.state,
        state: "CURRENT",
      }));
    }

    return Object.freeze({
      schemaVersion: 1,
      command: "init",
      outcome: "SUCCESS",
      targets: Object.freeze(completed),
    });
  } finally {
    dependencies.prompt.dispose();
  }
}
