import { spawn } from "node:child_process";
import { platform } from "node:os";

import { createTerminalTheme } from "../../terminal/theme.ts";
import type { ToolPreparationModule, ToolPreparationResult, ToolPreparationStatus } from "./types.ts";

const GH_TOOL_ID = "github_cli";

export interface GhPreparationDependencies {
  readonly runCommand: (command: string, args: readonly string[], options?: { readonly stdio?: "inherit" | ["ignore", "pipe", "pipe"] }) => Promise<{ readonly exitCode: number; readonly stdout: string; readonly stderr: string }>;
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

function createDefaultDependencies(): GhPreparationDependencies {
  const runCommand = (command: string, args: readonly string[], options?: { readonly stdio?: "inherit" | ["ignore", "pipe", "pipe"] }) =>
    new Promise<{ readonly exitCode: number; readonly stdout: string; readonly stderr: string }>((resolve) => {
      const child = spawn(command, args, { stdio: options?.stdio ?? ["ignore", "pipe", "pipe"] });
      let stdout = "";
      let stderr = "";
      child.stdout?.on("data", (data: Buffer) => { stdout += data.toString(); });
      child.stderr?.on("data", (data: Buffer) => { stderr += data.toString(); });
      child.on("close", (code: number | null) => resolve({ exitCode: code ?? 1, stdout, stderr }));
      child.on("error", () => resolve({ exitCode: 127, stdout, stderr: "command not found" }));
    });

  return {
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
      const result = await runCommand("gh", ["auth", "login", "--web"], { stdio: "inherit" });
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

    checkAptPrivileges: async () => {
      const result = await runCommand("apt", ["update"]);
      return result.exitCode === 0;
    },

    formatInstallGuidance: () => {
      const currentPlatform = platform();
      if (currentPlatform === "darwin") {
        return "Install via Homebrew: brew install gh";
      }
      if (currentPlatform === "linux") {
        return "Install via apt: sudo apt update && sudo apt install -y gh";
      }
      return "No supported installation method for this platform. See https://cli.github.com/ for manual installation.";
    },
  };
}

function detectInstallMethod(deps: GhPreparationDependencies): { readonly command: string; readonly args: readonly string[] } | null {
  const currentPlatform = platform();
  if (currentPlatform === "darwin") {
    return { command: "brew", args: ["install", "gh"] };
  }
  if (currentPlatform === "linux") {
    return { command: "apt", args: ["update"] };
  }
  return null;
}

async function checkAptPrivileges(deps: GhPreparationDependencies): Promise<boolean> {
  try {
    const result = await deps.runCommand("apt", ["update"]);
    return result.exitCode === 0;
  } catch {
    return false;
  }
}

export function createGhPreparationModule(deps?: Partial<GhPreparationDependencies>): ToolPreparationModule {
  const d = { ...createDefaultDependencies(), ...deps };

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
      const { exists, version } = await d.checkGhExists();

      if (!exists) {
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
        const currentPlatform = platform();
        if (currentPlatform === "darwin") {
          const brewAvailable = await d.checkBrewAvailable();
          if (!brewAvailable) {
            return Object.freeze({
              toolId: GH_TOOL_ID,
              status: "UNAVAILABLE",
              message: "Homebrew not found. Please install Homebrew first: https://brew.sh",
            });
          }
        } else if (currentPlatform === "linux") {
          const aptAvailable = await d.checkAptAvailable();
          if (!aptAvailable) {
            return Object.freeze({
              toolId: GH_TOOL_ID,
              status: "UNAVAILABLE",
              message: "apt not found. Cannot install gh on this system.",
            });
          }
          const aptPrivileges = await d.checkAptPrivileges();
          if (!aptPrivileges) {
            return Object.freeze({
              toolId: GH_TOOL_ID,
              status: "UNAVAILABLE",
              message: "Insufficient privileges to run apt. Please run with sudo or install gh manually.",
            });
          }
        }

        const { stderr } = process;
        stderr.write(`${theme.cyan("USER:")} Starting gh installation via ${installMethod.command}...\n`);

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

        const { exists: reinstalled, version: newVersion } = await d.checkGhExists();
        if (!reinstalled) {
          return Object.freeze({
            toolId: GH_TOOL_ID,
            status: "UNAVAILABLE",
            message: "gh was installed but cannot be verified.",
          });
        }
      }

      const { authenticated, user } = await d.checkGhAuth();
      if (!authenticated) {
        if (!authorizeLogin) {
          return Object.freeze({
            toolId: GH_TOOL_ID,
            status: "SKIPPED",
            message: "User declined gh authentication.",
          });
        }

        const { stderr } = process;
        stderr.write(`${theme.cyan("USER:")} Starting gh authentication via web flow (interactive)...\n`);
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