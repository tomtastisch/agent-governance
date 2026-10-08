import { InterruptedFailure } from "../errors.ts";
import type { ToolPreparationResult } from "./tool-preparation/types.ts";
import { join } from "node:path";
import { lstat } from "node:fs/promises";

import { resolveTarget } from "./bindings.ts";
import { resolveSupport } from "./support.ts";
import { runToolPreparation } from "./tool-preparation/index.ts";
import {
  INIT_CANCELLED,
  INIT_STEPS,
  INIT_STEPS_NO_TOOLS,
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

function cancelled(toolPreparation?: readonly ToolPreparationResult[], interruption?: InterruptedFailure): InitResult {
  return Object.freeze({
    schemaVersion: 1,
    command: "init",
    outcome: "INTERRUPTED",
    reason: "CANCELLED",
    targets: NO_TARGETS,
    ...(toolPreparation === undefined ? {} : { toolPreparation }),
    ...(interruption === undefined ? {} : {
      phase: interruption.phase,
      rollbackStatus: interruption.rollbackStatus,
      signal: interruption.signal,
      code: interruption.code,
      resourceId: interruption.resourceId,
    }),
  });
}

function preparationFailure(results: readonly ToolPreparationResult[]): InitResult | undefined {
  if (!results.some(({ status }) => status !== "READY" && status !== "SKIPPED")) return undefined;
  return Object.freeze({
    schemaVersion: 1,
    command: "init",
    outcome: "UNSAFE_STATE",
    reason: "TOOL_PREPARATION_FAILED",
    guidance: "Resolve the reported tool preparation failure and rerun agent-governance init tools.",
    targets: NO_TARGETS,
    toolPreparation: results,
  });
}

export async function runInitTools(options: InitOptions, prepareTools = runToolPreparation): Promise<InitResult> {
  if (!options.isTTY) return Object.freeze({
    schemaVersion: 1, command: "init", outcome: "INVALID_INVOCATION", reason: "NON_TTY",
    guidance: "Use an explicit transaction command with --non-interactive.", targets: NO_TARGETS,
  });
  try {
    const results = await prepareTools(false);
    return preparationFailure(results) ?? Object.freeze({
      schemaVersion: 1, command: "init", outcome: "SUCCESS", targets: NO_TARGETS, toolPreparation: results,
    });
  } catch (cause) {
    if (cause instanceof InterruptedFailure && cause.signal === "SIGINT") return cancelled(undefined, cause);
    throw cause;
  }
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

  const skipTools = dependencies.skipTools ?? false;
  const steps = skipTools ? INIT_STEPS_NO_TOOLS : INIT_STEPS;
  let toolPreparationResults: readonly ToolPreparationResult[] = Object.freeze([]);

  try {
    const installationRoot = options.installationRoot ?? join(options.environment.home, ".agent-governance");

    // Step 1: Umgebung prüfen
    dependencies.prompt.step(steps[0]!);
    const discovered = await dependencies.discoverHarnesses({ environment: options.environment });
    const latestVersion = await dependencies.resolveLatestRelease();
    const rows = await buildRows(discovered, options, installationRoot, latestVersion, dependencies);

    // Step 2: Coding-Harnesses auswählen
    dependencies.prompt.step(steps[1]!);
    const selections = await dependencies.prompt.selectTargets(rows);
    if (selections === INIT_CANCELLED) return cancelled();
    if (selections.length === 0) throw new Error("no init targets selected");
    const resolved = selections
      .map((selection) => ({ selection, target: resolveTarget(selection, options.environment) }))
      .sort((left, right) => compareTargets(left.target, right.target));
    const keys = resolved.map(({ target }) => targetKey(target));
    if (new Set(keys).size !== keys.length) throw new Error("duplicate init target");

    // Step 3: Tools vorbereiten (only if not skipped)
    if (!skipTools) {
      dependencies.prompt.step(steps[2]!);
      dependencies.prompt.dispose();
      toolPreparationResults = await (dependencies.prepareTools ?? runToolPreparation)(false);
      const failure = preparationFailure(toolPreparationResults);
      if (failure !== undefined) return failure;
    }

    // Step 4 (or 3 if tools skipped): Prüfen und einrichten
    const setupStepIndex = skipTools ? 2 : 3;
    dependencies.prompt.step(steps[setupStepIndex]!);
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
    if (approved === INIT_CANCELLED || !approved) return cancelled(toolPreparationResults);

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
      toolPreparation: toolPreparationResults,
    });
  } catch (cause) {
    if (cause instanceof InterruptedFailure) return cancelled(toolPreparationResults, cause);
    throw cause;
  } finally {
    dependencies.prompt.dispose();
  }
}
