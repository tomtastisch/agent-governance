import { randomUUID } from "node:crypto";
import {
  access,
  cp,
  lstat,
  mkdir,
  mkdtemp,
  readFile,
  rename,
  rm,
  writeFile,
} from "node:fs/promises";
import { dirname, join } from "node:path";

import { classifyCodex, inspectCodex } from "./codex.ts";
import type { InstallPhase, InstallResult, InstallerRequest } from "./contracts.ts";
import { InstallerFailure } from "./errors.ts";
import { captureIdentity, assertIdentity, validateAllowedPath, type PathIdentity } from "./filesystem.ts";
import { mergeGovernanceHook } from "./hooks.ts";
import { planCodex } from "./planner.ts";
import { verifyRelease } from "./release.ts";

export interface TransactionRequest extends InstallerRequest {
  readonly faultAfter?: InstallPhase;
}

interface ActivationEntry {
  readonly target: string;
  readonly staged: string;
  readonly retired: string;
  existed: boolean;
  activated: boolean;
}

interface RollbackReceipt {
  readonly schemaVersion: 1;
  readonly backupRoot: string;
  readonly rolledBack: boolean;
  readonly resources: readonly { readonly target: string; readonly existed: boolean; readonly index: number }[];
}

async function exists(path: string): Promise<boolean> {
  try {
    await access(path);
    return true;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return false;
    throw error;
  }
}

async function copySafe(source: string, target: string): Promise<void> {
  const stat = await lstat(source);
  if (stat.isSymbolicLink()) throw new Error("backup source is a symlink");
  await cp(source, target, { recursive: stat.isDirectory(), dereference: false, errorOnExist: true });
}

async function sameTree(left: string, right: string): Promise<boolean> {
  const [leftStat, rightStat] = await Promise.all([lstat(left), lstat(right)]);
  if (leftStat.isSymbolicLink() || rightStat.isSymbolicLink()) return false;
  if (leftStat.isFile() && rightStat.isFile()) {
    const [a, b] = await Promise.all([readFile(left), readFile(right)]);
    return a.equals(b) && (leftStat.mode & 0o777) === (rightStat.mode & 0o777);
  }
  if (leftStat.isDirectory() && rightStat.isDirectory()) {
    const { readdir } = await import("node:fs/promises");
    const [a, b] = await Promise.all([readdir(left), readdir(right)]);
    a.sort(); b.sort();
    if (a.join("\0") !== b.join("\0")) return false;
    for (const name of a) if (!(await sameTree(join(left, name), join(right, name)))) return false;
    return true;
  }
  return false;
}

export class InstallerTransaction {
  private readonly request: TransactionRequest;

  constructor(request: TransactionRequest) {
    this.request = request;
  }

  private fault(phase: InstallPhase): void {
    if (this.request.faultAfter === phase) throw new Error(`injected failure after ${phase}`);
  }

  async inspect(): Promise<InstallResult> {
    await validateAllowedPath(this.request.home, this.request.allowedRoot, "directory");
    await verifyRelease(this.request.releaseRoot);
    if (this.request.harness !== "codex") throw new Error(`unsupported harness: ${this.request.harness}`);
    const state = classifyCodex(await inspectCodex(this.request.home, this.request.installRoot));
    return { outcome: "SUCCESS", state, phase: "classify", rollbackStatus: "NOT_REQUIRED" };
  }

  async plan(): Promise<InstallResult> {
    return new InstallerTransaction({ ...this.request, dryRun: true }).install();
  }

  async verify(): Promise<InstallResult> {
    const result = await this.inspect();
    if (result.state !== "CURRENT") throw new Error(`verification failed: ${result.state}`);
    return { ...result, phase: "verify" };
  }

  async status(): Promise<InstallResult> {
    return this.inspect();
  }

  async rollback(): Promise<InstallResult> {
    const receiptPath = join(this.request.home, ".agent-governance-rollback.json");
    await validateAllowedPath(receiptPath, this.request.allowedRoot, "file");
    const raw = await readFile(receiptPath, "utf8");
    const receipt = this.parseReceipt(raw);
    await validateAllowedPath(receipt.backupRoot, this.request.allowedRoot, "directory");
    if (this.request.dryRun) {
      return { outcome: "SUCCESS", state: "CURRENT", phase: "plan", rollbackStatus: "NOT_REQUIRED" };
    }
    if (receipt.rolledBack) {
      return { outcome: "SUCCESS", state: "FRESH", phase: "rollback", rollbackStatus: "SUCCEEDED" };
    }
    for (const resource of [...receipt.resources].reverse()) {
      await validateAllowedPath(resource.target, this.request.allowedRoot, (await exists(resource.target)) ? "any" : "missing");
      if (await exists(resource.target)) await rm(resource.target, { recursive: true, force: true });
      if (resource.existed) {
        const backup = join(receipt.backupRoot, String(resource.index));
        await validateAllowedPath(backup, this.request.allowedRoot, "any");
        await copySafe(backup, resource.target);
        if (!(await sameTree(backup, resource.target))) throw new Error("rollback readback failed");
      } else if (await exists(resource.target)) {
        throw new Error("rollback absence readback failed");
      }
    }
    await this.writeReceipt(receiptPath, { ...receipt, rolledBack: true });
    return { outcome: "SUCCESS", state: "FRESH", phase: "rollback", rollbackStatus: "SUCCEEDED" };
  }

  private parseReceipt(raw: string): RollbackReceipt {
    let value: unknown;
    try { value = JSON.parse(raw); } catch { throw new Error("rollback receipt is invalid JSON"); }
    const candidate = value as Partial<RollbackReceipt>;
    if (candidate.schemaVersion !== 1 || typeof candidate.backupRoot !== "string" ||
        typeof candidate.rolledBack !== "boolean" || !Array.isArray(candidate.resources)) {
      throw new Error("rollback receipt has invalid schema");
    }
    if (!candidate.backupRoot.startsWith(`${this.request.allowedRoot}/`)) throw new Error("rollback backup escapes allowed root");
    const expectedTargets = [
      join(this.request.home, "AGENTS.md"),
      join(this.request.home, "hooks.json"),
      this.request.installRoot,
    ];
    if (candidate.resources.length !== expectedTargets.length) throw new Error("rollback receipt resource count is invalid");
    for (const resource of candidate.resources) {
      if (typeof resource !== "object" || resource === null || typeof resource.target !== "string" ||
          typeof resource.existed !== "boolean" || !Number.isInteger(resource.index)) {
        throw new Error("rollback receipt resource is invalid");
      }
      if (resource.index < 0 || resource.index >= expectedTargets.length ||
          resource.target !== expectedTargets[resource.index]) {
        throw new Error("rollback receipt resource target is invalid");
      }
    }
    return candidate as RollbackReceipt;
  }

  async install(): Promise<InstallResult> {
    const request = this.request;
    if (request.harness !== "codex") throw new Error(`unsupported harness: ${request.harness}`);
    await validateAllowedPath(request.home, request.allowedRoot, "directory");
    await validateAllowedPath(request.installRoot, request.allowedRoot, (await exists(request.installRoot)) ? "directory" : "missing");
    await verifyRelease(request.releaseRoot);
    const inventory = await inspectCodex(request.home, request.installRoot);
    const state = classifyCodex(inventory);
    this.fault("inspect");
    if (state === "UNKNOWN" || state === "UNSUPPORTED") throw new Error(`unsafe install state: ${state}`);
    this.fault("classify");
    const plan = planCodex({ harness: "codex", state, home: request.home, installRoot: request.installRoot });
    this.fault("plan");
    if (state === "CURRENT") {
      return { outcome: "SUCCESS", state, phase: "verify", rollbackStatus: "NOT_REQUIRED", plan };
    }
    if (request.dryRun) {
      return { outcome: "SUCCESS", state, phase: "plan", rollbackStatus: "NOT_REQUIRED", plan };
    }

    const transactionId = randomUUID();
    const backupParent = join(request.allowedRoot, ".agent-governance-backups");
    const receiptPath = join(request.home, ".agent-governance-rollback.json");
    await validateAllowedPath(receiptPath, request.allowedRoot, "missing");
    const backupParentExists = await exists(backupParent);
    await validateAllowedPath(backupParent, request.allowedRoot, backupParentExists ? "directory" : "missing");
    if (!backupParentExists) await mkdir(backupParent, { mode: 0o700 });
    const backupRoot = join(backupParent, transactionId);
    const stageRoot = await mkdtemp(join(request.allowedRoot, ".agent-governance-stage-"));
    const retiredRoot = join(request.allowedRoot, `.agent-governance-retired-${transactionId}`);
    await mkdir(backupRoot, { mode: 0o700 });
    await mkdir(retiredRoot, { mode: 0o700 });
    const targets = [join(request.home, "AGENTS.md"), join(request.home, "hooks.json"), request.installRoot];
    const parentIdentities = new Map<string, PathIdentity>();
    for (const target of targets) {
      const parent = dirname(target);
      if (!parentIdentities.has(parent)) parentIdentities.set(parent, await captureIdentity(parent));
    }

    const backupPresence: boolean[] = [];
    for (const [index, target] of targets.entries()) {
      const present = await exists(target);
      backupPresence.push(present);
      if (present) {
        const backup = join(backupRoot, String(index));
        await copySafe(target, backup);
        if (!(await sameTree(target, backup))) throw new Error("backup readback failed");
      } else {
        await writeFile(join(backupRoot, `${index}.absent`), "absent\n", { mode: 0o600 });
      }
    }
    this.fault("backup");

    const stagedInstall = join(stageRoot, "installation");
    await this.materializeRelease(stagedInstall);
    if (state === "LEGACY" && inventory.agents !== undefined) {
      const personalRules = inventory.agents
        .split(/(?<=\n)/)
        .filter((line) => {
          const normalized = line.replace(/\r?\n$/, "");
          return normalized !== "@~/agent-governance/adapters/AGENTS.md" &&
            normalized !== "@~/agent-governance/adapters/codex.md";
        })
        .join("");
      if (personalRules !== "") {
        const manifest = await readFile(
          join(stagedInstall, "bundle", "agent-governance", "manifest.toml"),
          "utf8",
        );
        const match = /^local_rules\s*=\s*"([^"\\]+)"\s*$/m.exec(manifest);
        if (match?.[1] === undefined || match[1].split("/").includes("..")) {
          throw new Error("manifest local_rules path is ambiguous");
        }
        const localRules = join(stagedInstall, "bundle", "agent-governance", match[1]);
        await mkdir(dirname(localRules), { recursive: true });
        await writeFile(localRules, personalRules, { mode: 0o600 });
      }
    }
    const governance = await readFile(join(stagedInstall, "bundle", "GOVERNANCE.md"));
    const stagedAgents = join(stageRoot, "AGENTS.md");
    await writeFile(stagedAgents, governance, { mode: 0o600 });
    const oldHooks = inventory.hooksPresent ? await readFile(join(request.home, "hooks.json"), "utf8") : undefined;
    const stagedHooks = join(stageRoot, "hooks.json");
    await writeFile(
      stagedHooks,
      mergeGovernanceHook(oldHooks, join(request.installRoot, "integrations", "microsoft-agent-governance-toolkit", "bridge", "codex-hook.mjs")),
      { mode: 0o600 },
    );
    this.fault("stage");

    for (const [parent, identity] of parentIdentities) await assertIdentity(parent, identity);
    const entries: ActivationEntry[] = [
      { target: targets[0]!, staged: stagedAgents, retired: join(retiredRoot, "0"), existed: backupPresence[0]!, activated: false },
      { target: targets[1]!, staged: stagedHooks, retired: join(retiredRoot, "1"), existed: backupPresence[1]!, activated: false },
      { target: targets[2]!, staged: stagedInstall, retired: join(retiredRoot, "2"), existed: backupPresence[2]!, activated: false },
    ];
    let activePhase: InstallPhase = "activate";
    try {
      for (const entry of entries) {
        if (entry.existed) await rename(entry.target, entry.retired);
        await rename(entry.staged, entry.target);
        entry.activated = true;
      }
      this.fault("activate");
      activePhase = "verify";
      const activeGovernance = await readFile(join(request.installRoot, "bundle", "GOVERNANCE.md"));
      const activeAgents = await readFile(join(request.home, "AGENTS.md"));
      if (!activeGovernance.equals(activeAgents)) throw new Error("instruction readback mismatch");
      await verifyRelease(request.installRoot);
      this.fault("verify");
      const receipt: RollbackReceipt = {
        schemaVersion: 1,
        backupRoot,
        rolledBack: false,
        resources: targets.map((target, index) => ({ target, existed: backupPresence[index]!, index })),
      };
      await this.writeReceipt(receiptPath, receipt);
      await rm(retiredRoot, { recursive: true, force: true });
      await rm(stageRoot, { recursive: true, force: true });
      return { outcome: "SUCCESS", state, phase: "verify", rollbackStatus: "NOT_REQUIRED", plan };
    } catch (error) {
      try {
        await this.rollbackEntries(entries);
        await rm(stageRoot, { recursive: true, force: true });
      } catch (rollbackError) {
        throw new InstallerFailure(
          "ROLLBACK_FAILED",
          activePhase,
          "installation",
          "ROLLBACK_FAILED",
          `${(error as Error).message}; rollback failed: ${(rollbackError as Error).message}`,
          "FAILED",
        );
      }
      throw new InstallerFailure(
        "VERIFICATION_ROLLED_BACK",
        activePhase,
        "installation",
        "VERIFICATION_ROLLED_BACK",
        (error as Error).message,
        "SUCCEEDED",
      );
    }
  }

  private async materializeRelease(destination: string): Promise<void> {
    await mkdir(destination, { recursive: true });
    const inventory = await readFile(join(this.request.releaseRoot, "release.files.sha256"), "utf8");
    for (const line of inventory.trimEnd().split("\n")) {
      const path = line.slice(66);
      const target = join(destination, path);
      await mkdir(dirname(target), { recursive: true });
      await copySafe(join(this.request.releaseRoot, path), target);
    }
    await copySafe(join(this.request.releaseRoot, "release.files.sha256"), join(destination, "release.files.sha256"));
  }

  private async rollbackEntries(entries: ActivationEntry[]): Promise<void> {
    for (const entry of [...entries].reverse()) {
      if (entry.activated && (await exists(entry.target))) await rm(entry.target, { recursive: true, force: true });
      if (entry.existed && (await exists(entry.retired))) await rename(entry.retired, entry.target);
    }
  }

  private async writeReceipt(receiptPath: string, receipt: RollbackReceipt): Promise<void> {
    const temporary = `${receiptPath}.${randomUUID()}.tmp`;
    await validateAllowedPath(temporary, this.request.allowedRoot, "missing");
    await writeFile(temporary, `${JSON.stringify(receipt, null, 2)}\n`, { mode: 0o600, flag: "wx" });
    await rename(temporary, receiptPath);
    await validateAllowedPath(receiptPath, this.request.allowedRoot, "file");
    const readback = this.parseReceipt(await readFile(receiptPath, "utf8"));
    if (JSON.stringify(readback) !== JSON.stringify(receipt)) throw new Error("rollback receipt readback failed");
  }
}
