import { join } from "node:path";
import type { InstallPlan, InstallerCommand, InstallState, PlannedResource } from "./contracts.ts";
export function planInstallation(input: { command: InstallerCommand; state: InstallState; entryPath: string; installationRoot: string; version: string; localRulesOperation?: "create" | "replace"; localRulesPath?: string; bindingId?: string; }): InstallPlan {
  if (["TAMPERED", "RECOVERY_REQUIRED", "DOWNGRADE_BLOCKED"].includes(input.state)) throw new Error(`cannot plan unsafe state: ${input.state}`);
  const mutating = ["install", "update", "uninstall", "rollback"].includes(input.command);
  const activeOperation: PlannedResource["operation"] = !mutating ? "verify" : input.command === "uninstall" ? "remove" : input.state === "CURRENT" ? "preserve" : input.state === "OUTDATED" ? "replace" : "create";
  const releaseOperation: PlannedResource["operation"] = !mutating ? "verify" : input.command === "uninstall" || input.state === "CURRENT" ? "preserve" : "create";
  const bindingRoot = join(input.installationRoot, "bindings", input.bindingId ?? "<binding-id>");
  const resources: PlannedResource[] = [
    { id: "release", target: join(input.installationRoot, "releases", input.version), operation: releaseOperation },
    { id: "current-metadata", target: join(bindingRoot, "current.json"), operation: activeOperation },
    { id: "entry-file", target: input.entryPath, operation: activeOperation },
    { id: "backup", target: join(input.installationRoot, "backups"), operation: mutating ? "create" : "verify" },
    { id: "receipt", target: join(bindingRoot, "last-transaction.json"), operation: mutating ? "replace" : "verify" },
  ];
  if (input.localRulesOperation !== undefined) {
    if (input.localRulesPath === undefined) throw new Error("local-rules plan requires the verified manifest path");
    resources.push({ id: "local-rules", target: join(input.installationRoot, "releases", input.version, "bundle", "agent-governance", input.localRulesPath), operation: input.localRulesOperation });
  }
  return { schemaVersion: 1, architecture: "GLOBAL_EXPLICIT_PATH_MANAGED_BLOCK", command: input.command, state: input.state, resources, harnessSpecificMutation: false, mcpMutation: false, hookMutation: false, approvalExpansion: false };
}
