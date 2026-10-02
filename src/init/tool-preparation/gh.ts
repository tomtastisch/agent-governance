import { InterruptedFailure } from "../../errors.ts";
import { spawn } from "node:child_process";
import { platform } from "node:os";

import { createTerminalTheme } from "../../terminal/theme.ts";
import type { ToolPreparationModule, ToolPreparationResult } from "./types.ts";

const GH_TOOL_ID = "github_cli";

export interface GhPreparationDependencies {
  readonly platform: () => NodeJS.Platform;
  readonly effectiveUserId: () => number | undefined;
  readonly write: (value: string) => void;
  readonly runCommand: (command: string, args: readonly string[], options?: { readonly stdio?: "inherit" | ["ignore", "pipe", "pipe"] | ["inherit", 2, 2] }) => Promise<{ readonly exitCode: number; readonly stdout: string; readonly stderr: string }>;
  readonly checkGhExists: () => Promise<{ readonly exists: boolean; readonly version: string | undefined }>;
  readonly checkGhAuth: () => Promise<{ readonly authenticated: boolean; readonly user: string | undefined }>;
  readonly runGhAuthLogin: () => Promise<boolean>;
  readonly runAptUpdate: () => Promise<boolean>;
  readonly runAptInstall: (packageName: string) => Promise<boolean>;
  readonly runBrewInstall: (packageName: string) => Promise<boolean>;
  readonly checkAptAvailable: () => Promise<boolean>;
  readonly checkBrewAvailable: () => Promise<boolean>;
  readonly checkAptPrivileges: () => Promise<boolean>;
  readonly formatInstallGuidance: () => string;
}

function createDefaultDependencies(overrides: Partial<GhPreparationDependencies>): GhPreparationDependencies {
  const effectiveUserId = overrides.effectiveUserId ?? (() => process.geteuid?.());
  const currentPlatform = overrides.platform ?? platform;
  const runCommand: GhPreparationDependencies["runCommand"] = overrides.runCommand ?? ((command: string, args: readonly string[], options?: { readonly stdio?: "inherit" | ["ignore", "pipe", "pipe"] | ["inherit", 2, 2] }) =>
    new Promise<{ readonly exitCode: number; readonly stdout: string; readonly stderr: string }>((resolve, reject) => {
      const child = spawn(command, args, { stdio: options?.stdio ?? ["ignore", "pipe", "pipe"] });
      let stdout = "";
      let stderr = "";
      child.stdout?.on("data", (data: Buffer) => { stdout += data.toString(); });
      child.stderr?.on("data", (data: Buffer) => { stderr += data.toString(); });
      child.on("close", (code, signal) => {
        if (signal === "SIGINT" || signal === "SIGTERM" || code === 130 || code === 143) {
          reject(new InterruptedFailure(signal === "SIGTERM" || code === 143 ? "SIGTERM" : "SIGINT", "inspect", "NOT_REQUIRED"));
        } else resolve({ exitCode: code ?? 1, stdout, stderr });
      });
      child.on("error", () => resolve({ exitCode: 127, stdout, stderr: "command not found" }));
    }));

  return {
    platform: currentPlatform,
    effectiveUserId,
    write: value => { process.stderr.write(value); },
    runCommand,

    checkGhExists: async () => {
      const result = await runCommand("gh", ["--version"]);
      if (result.exitCode === 0) {
        const versionMatch = result.stdout.match(/gh version (\S+)/);
        return { exists: true, version: versionMatch?.[1] };
      }
      return { exists: false, version: undefined };
    },

    checkGhAuth: async () => {
      const result = await runCommand("gh", ["auth", "status", "--active", "--hostname", "github.com"]);
      if (result.exitCode === 0) {
        const userMatch = result.stdout.match(/Logged in to (?:github\.com )?as (\S+)/);
        return { authenticated: true, user: userMatch?.[1] };
      }
      return { authenticated: false, user: undefined };
    },

    runGhAuthLogin: async () => {
      const result = await runCommand("gh", ["auth", "login", "--web", "--hostname", "github.com"], { stdio: ["inherit", 2, 2] });
      return result.exitCode === 0;
    },

    runAptUpdate: async () => {
      const result = await runCommand("apt", ["update"]);
      return result.exitCode === 0;
    },

    runAptInstall: async (packageName: string) => {
      const result = await runCommand("apt", ["install", "-y", packageName]);
      return result.exitCode === 0;
    },

    runBrewInstall: async (packageName: string) => {
      const result = await runCommand("brew", ["install", packageName]);
      return result.exitCode === 0;
    },

    checkAptAvailable: async () => {
      const result = await runCommand("which", ["apt"]);
      return result.exitCode === 0;
    },

    checkBrewAvailable: async () => {
      const result = await runCommand("which", ["brew"]);
      return result.exitCode === 0;
    },

    checkAptPrivileges: async () => effectiveUserId() === 0,

    formatInstallGuidance: () => {
      const detectedPlatform = currentPlatform();
      if (detectedPlatform === "darwin") {
        return "Install via Homebrew: brew install gh";
      }
      if (detectedPlatform === "linux") {
        return "Install via apt: sudo apt update && sudo apt install -y gh";
      }
      return "No supported installation method for this platform. See https://cli.github.com/ for manual installation.";
    },
  };
}

function detectInstallMethod(deps: GhPreparationDependencies): { readonly command: string; readonly args: readonly string[] } | null {
  const currentPlatform = deps.platform();
  if (currentPlatform === "darwin") {
    return { command: "brew", args: ["install", "gh"] };
  }
  if (currentPlatform === "linux") {
    return { command: "apt", args: ["update"] };
  }
  return null;
}

export function createGhPreparationModule(deps?: Partial<GhPreparationDependencies>): ToolPreparationModule {
  const d = { ...createDefaultDependencies(deps ?? {}), ...deps };

  return Object.freeze({
    toolId: GH_TOOL_ID,

    async inspect(): Promise<ToolPreparationResult> {
      const { exists, version } = await d.checkGhExists();
      if (!exists) {
        return Object.freeze({
          toolId: GH_TOOL_ID,
          status: "MISSING",
          message: `GitHub CLI (gh) not found. ${d.formatInstallGuidance()}`,
        });
      }

      const { authenticated, user } = await d.checkGhAuth();
      if (!authenticated) {
        return Object.freeze({
          toolId: GH_TOOL_ID,
          status: "AUTH_REQUIRED",
          message: `GitHub CLI (gh) ${version ?? "unknown"} found but not authenticated. Run 'gh auth login' to authenticate.`,
        });
      }

      return Object.freeze({
        toolId: GH_TOOL_ID,
        status: "READY",
        message: `GitHub CLI (gh) ${version ?? "unknown"} authenticated as ${user ?? "unknown"}.`,
      });
    },

    async prepare(options: { readonly authorizeInstall: boolean; readonly authorizeLogin: boolean }): Promise<ToolPreparationResult> {
      const { authorizeInstall, authorizeLogin } = options;

      const theme = createTerminalTheme({ color: true });
      const { exists } = await d.checkGhExists();

      if (!exists) {
        if (authorizeLogin && !authorizeInstall) {
          return Object.freeze({
            toolId: GH_TOOL_ID,
            status: "UNAVAILABLE",
            message: `gh disappeared before the authorized login. ${d.formatInstallGuidance()}`,
          });
        }
        if (!authorizeInstall) {
          return Object.freeze({
            toolId: GH_TOOL_ID,
            status: "SKIPPED",
            message: "User declined gh installation.",
          });
        }

        const installMethod = detectInstallMethod(d);
        if (installMethod === null) {
          return Object.freeze({
            toolId: GH_TOOL_ID,
            status: "UNAVAILABLE",
            message: `Cannot install gh on this platform. ${d.formatInstallGuidance()}`,
          });
        }

        // Verify package manager is available before mutation
        const currentPlatform = d.platform();
        if (currentPlatform === "darwin") {
          const brewAvailable = await d.checkBrewAvailable();
          if (!brewAvailable) {
            return Object.freeze({
              toolId: GH_TOOL_ID,
              status: "UNAVAILABLE",
              message: "Homebrew not found. Install gh manually using https://cli.github.com/ and rerun agent-governance init tools.",
            });
          }
        } else if (currentPlatform === "linux") {
          const aptAvailable = await d.checkAptAvailable();
          if (!aptAvailable) {
            return Object.freeze({
              toolId: GH_TOOL_ID,
              status: "UNAVAILABLE",
              message: "apt not found. Install gh manually using https://cli.github.com/ and rerun agent-governance init tools.",
            });
          }
          const aptPrivileges = await d.checkAptPrivileges();
          if (!aptPrivileges) {
            return Object.freeze({
              toolId: GH_TOOL_ID,
              status: "UNAVAILABLE",
              message: "Insufficient privileges to run apt. Install gh manually: sudo apt update && sudo apt install -y gh. Then rerun agent-governance init tools without elevating the governance CLI.",
            });
          }
        }

        d.write(`${theme.cyan("USER:")} Starting gh installation via ${installMethod.command}...\n`);

        let installed = false;
        if (currentPlatform === "darwin") {
          installed = await d.runBrewInstall("gh");
        } else if (currentPlatform === "linux") {
          const aptUpdateOk = await d.runAptUpdate();
          if (aptUpdateOk) {
            installed = await d.runAptInstall("gh");
          }
        }

        if (!installed) {
          return Object.freeze({
            toolId: GH_TOOL_ID,
            status: "UNAVAILABLE",
            message: `gh installation failed. ${d.formatInstallGuidance()}`,
          });
        }

        const { exists: reinstalled } = await d.checkGhExists();
        if (!reinstalled) {
          return Object.freeze({
            toolId: GH_TOOL_ID,
            status: "UNAVAILABLE",
            message: "gh was installed but cannot be verified.",
          });
        }
      }

      const { authenticated } = await d.checkGhAuth();
      if (!authenticated) {
        if (!authorizeLogin) {
          return Object.freeze({
            toolId: GH_TOOL_ID,
            status: "SKIPPED",
            message: "User declined gh authentication.",
          });
        }

        d.write(`${theme.cyan("USER:")} Starting gh authentication via web flow (interactive)...\n`);
        const loginSuccess = await d.runGhAuthLogin();
        if (!loginSuccess) {
          return Object.freeze({
            toolId: GH_TOOL_ID,
            status: "AUTH_REQUIRED",
            message: "gh authentication failed or was cancelled.",
          });
        }
      }

      const { exists: finalExists, version: finalVersion } = await d.checkGhExists();
      const { authenticated: finalAuth, user: finalUser } = await d.checkGhAuth();

      if (finalExists && finalAuth) {
        return Object.freeze({
          toolId: GH_TOOL_ID,
          status: "READY",
          message: `GitHub CLI (gh) ${finalVersion ?? "unknown"} authenticated as ${finalUser ?? "unknown"}.`,
        });
      }

      return Object.freeze({
        toolId: GH_TOOL_ID,
        status: "UNAVAILABLE",
        message: "gh preparation incomplete after installation and authentication.",
      });
    },
  });
}

export const ghPreparationModule = createGhPreparationModule();
