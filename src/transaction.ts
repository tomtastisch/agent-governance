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
    const backupRoot = join(request.allowedRoot, ".agent-governance-backups", transactionId);
    const stageRoot = await mkdtemp(join(request.allowedRoot, ".agent-governance-stage-"));
    const retiredRoot = join(request.allowedRoot, `.agent-governance-retired-${transactionId}`);
    await mkdir(backupRoot, { recursive: true, mode: 0o700 });
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
        .filter((line) => !line.includes("@~/agent-governance/adapters/AGENTS.md") && !line.includes("@~/agent-governance/adapters/codex.md"))
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
    try {
      for (const entry of entries) {
        if (entry.existed) await rename(entry.target, entry.retired);
        await rename(entry.staged, entry.target);
        entry.activated = true;
      }
      this.fault("activate");
      const activeGovernance = await readFile(join(request.installRoot, "bundle", "GOVERNANCE.md"));
      const activeAgents = await readFile(join(request.home, "AGENTS.md"));
      if (!activeGovernance.equals(activeAgents)) throw new Error("instruction readback mismatch");
      await verifyRelease(request.installRoot);
      this.fault("verify");
      await rm(retiredRoot, { recursive: true, force: true });
      await rm(stageRoot, { recursive: true, force: true });
      return { outcome: "SUCCESS", state, phase: "verify", rollbackStatus: "NOT_REQUIRED", plan };
    } catch (error) {
      await this.rollbackEntries(entries);
      await rm(stageRoot, { recursive: true, force: true });
      throw error;
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
}
