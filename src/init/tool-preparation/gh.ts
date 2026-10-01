import { spawn } from "node:child_process";
import { platform } from "node:os";

import { createTerminalTheme } from "../../terminal/theme.ts";
import type { ToolPreparationModule, ToolPreparationResult, ToolPreparationStatus } from "./types.ts";

const GH_TOOL_ID = "github_cli";

function runCommand(command: string, args: readonly string[]): Promise<{ readonly exitCode: number; readonly stdout: string; readonly stderr: string }> {
  return new Promise<{ readonly exitCode: number; readonly stdout: string; readonly stderr: string }>((resolve) => {
    const child = spawn(command, args, { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    child.stdout?.on("data", (data: Buffer) => { stdout += data.toString(); });
    child.stderr?.on("data", (data: Buffer) => { stderr += data.toString(); });
    child.on("close", (code: number | null) => resolve({ exitCode: code ?? 1, stdout, stderr }));
    child.on("error", () => resolve({ exitCode: 127, stdout, stderr: "command not found" }));
  });
}

function detectInstallMethod(): { readonly command: string; readonly args: readonly string[] } | null {
  const currentPlatform = platform();
  if (currentPlatform === "darwin") {
    return { command: "brew", args: ["install", "gh"] };
  }
  if (currentPlatform === "linux") {
    return { command: "apt", args: ["update", "&&", "apt", "install", "-y", "gh"] };
  }
  return null;
}

async function checkGhExists(): Promise<{ readonly exists: boolean; readonly version: string | undefined }> {
  const result = await runCommand("gh", ["--version"]);
  if (result.exitCode === 0) {
    const versionMatch = result.stdout.match(/gh version (\S+)/);
    return { exists: true, version: versionMatch?.[1] };
  }
  return { exists: false, version: undefined };
}

async function checkGhAuth(): Promise<{ readonly authenticated: boolean; readonly user: string | undefined }> {
  const result = await runCommand("gh", ["auth", "status"]);
  if (result.exitCode === 0) {
    const userMatch = result.stdout.match(/Logged in to (?:github\.com )?as (\S+)/);
    return { authenticated: true, user: userMatch?.[1] };
  }
  return { authenticated: false, user: undefined };
}

async function runGhAuthLogin(): Promise<boolean> {
  const result = await runCommand("gh", ["auth", "login", "--web"]);
  return result.exitCode === 0;
}

async function runGhInstall(command: string, args: readonly string[]): Promise<boolean> {
  const result = await runCommand(command, args);
  return result.exitCode === 0;
}

function formatInstallGuidance(): string {
  const currentPlatform = platform();
  if (currentPlatform === "darwin") {
    return "Install via Homebrew: brew install gh";
  }
  if (currentPlatform === "linux") {
    return "Install via apt: sudo apt update && sudo apt install -y gh";
  }
  return "No supported installation method for this platform. See https://cli.github.com/ for manual installation.";
}

export const ghPreparationModule: ToolPreparationModule = Object.freeze({
  toolId: GH_TOOL_ID,

  async inspect(): Promise<ToolPreparationResult> {
    const { exists, version } = await checkGhExists();
    if (!exists) {
      return Object.freeze({
        toolId: GH_TOOL_ID,
        status: "MISSING",
        message: `GitHub CLI (gh) not found. ${formatInstallGuidance()}`,
      });
    }

    const { authenticated, user } = await checkGhAuth();
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

  async prepare({ userAuthorized }: { readonly userAuthorized: boolean }): Promise<ToolPreparationResult> {
    if (!userAuthorized) {
      return Object.freeze({
        toolId: GH_TOOL_ID,
        status: "SKIPPED",
        message: "User declined preparation.",
      });
    }

    const theme = createTerminalTheme({ color: true });
    const { exists, version } = await checkGhExists();

    if (!exists) {
      const installMethod = detectInstallMethod();
      if (installMethod === null) {
        return Object.freeze({
          toolId: GH_TOOL_ID,
          status: "UNAVAILABLE",
          message: `Cannot install gh on this platform. ${formatInstallGuidance()}`,
        });
      }

      console.log(`${theme.cyan("USER:")} Starting gh installation via ${installMethod.command}...`);
      const installed = await runGhInstall(installMethod.command, installMethod.args);
      if (!installed) {
        return Object.freeze({
          toolId: GH_TOOL_ID,
          status: "UNAVAILABLE",
          message: `gh installation failed. ${formatInstallGuidance()}`,
        });
      }

      const { exists: reinstalled, version: newVersion } = await checkGhExists();
      if (!reinstalled) {
        return Object.freeze({
          toolId: GH_TOOL_ID,
          status: "UNAVAILABLE",
          message: "gh was installed but cannot be verified.",
        });
      }
    }

    const { authenticated, user } = await checkGhAuth();
    if (!authenticated) {
      console.log(`${theme.cyan("USER:")} Starting gh authentication via web flow...`);
      const loginSuccess = await runGhAuthLogin();
      if (!loginSuccess) {
        return Object.freeze({
          toolId: GH_TOOL_ID,
          status: "AUTH_REQUIRED",
          message: "gh authentication failed or was cancelled.",
        });
      }
    }

    const { exists: finalExists, version: finalVersion } = await checkGhExists();
    const { authenticated: finalAuth, user: finalUser } = await checkGhAuth();

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