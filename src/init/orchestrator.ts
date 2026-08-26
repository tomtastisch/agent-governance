import { join } from "node:path";

import { resolveBinding } from "./bindings.ts";
import {
  INIT_CANCELLED,
  INIT_STEPS,
  type InitDependencies,
  type InitOptions,
  type InitPlannedTarget,
  type InitResult,
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

  dependencies.prompt.step(INIT_STEPS[0]!);
  const candidates = await dependencies.discoverCandidates({
    environment: options.environment,
    releaseRoot: options.releaseRoot,
  });

  dependencies.prompt.step(INIT_STEPS[1]!);
  const selections = await dependencies.prompt.selectTargets(candidates);
  if (selections === INIT_CANCELLED) return cancelled();
  if (selections.length === 0) throw new Error("no init targets selected");
  const targets = selections
    .map(({ candidate, manualInput }) => resolveBinding(candidate, manualInput))
    .sort(compareTargets);
  const keys = targets.map(targetKey);
  if (new Set(keys).size !== keys.length) throw new Error("duplicate init target");

  dependencies.prompt.step(INIT_STEPS[2]!);
  const installationRoot = options.installationRoot ?? join(options.environment.home, ".agent-governance");
  const prepared: PreparedTarget[] = [];
  for (const target of targets) {
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
    const plan = await transaction.plan();
    prepared.push(Object.freeze({ target, transaction, status, plan }));
  }

  const approvalPlans = prepared.map(({ target, status, plan }) => Object.freeze({ target, status, plan }));
  const approved = await dependencies.prompt.confirm(approvalPlans);
  if (approved === INIT_CANCELLED || !approved) return cancelled();

  const completed: InitTargetResult[] = [];
  for (const item of prepared) {
    const installed = await item.transaction.install();
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
}
