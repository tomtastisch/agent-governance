import type { ToolPreparationModule, ToolPreparationOrchestrator, ToolPreparationResult } from "./types.ts";
import { ghPreparationModule } from "./gh.ts";

const PREPARATION_MODULES: readonly ToolPreparationModule[] = Object.freeze([ghPreparationModule]);

async function promptUserAuthorization(module: ToolPreparationModule, message: string): Promise<boolean> {
  const { stdin, stdout, stderr } = process;

  // If not a TTY, skip interactively (safe default for CI/non-interactive environments)
  if (!stdin.isTTY) {
    const { createTerminalTheme } = await import("../../terminal/theme.ts");
    const theme = createTerminalTheme({ color: true });
    stderr.write(`${theme.cyan("USER:")} ${message}\n`);
    stderr.write(`${theme.dim("Non-interactive environment, skipping preparation.\n")}`);
    return false;
  }

  return new Promise(async (resolve) => {
    const { createTerminalTheme } = await import("../../terminal/theme.ts");
    const theme = createTerminalTheme({ color: true });
    stderr.write(`${theme.cyan("USER:")} ${message}\n`);
    stderr.write(`${theme.dim("Press 'y' to continue, any other key to skip:\n")}`);

    const onData = (data: Buffer) => {
      // Handle Ctrl+C (\x03) as cancellation
      if (data[0] === 0x03) {
        stdin.off("data", onData);
        stdin.setRawMode(false);
        stdin.pause();
        stderr.write("\n");
        resolve(false); // Treat Ctrl+C as cancellation
        return;
      }

      stdin.off("data", onData);
      stdin.setRawMode(false);
      stdin.pause();
      resolve(data.toString().toLowerCase().trim() === "y");
    };

    stdin.setRawMode(true);
    stdin.resume();
    stdin.on("data", onData);
  });
}

function createToolPreparationOrchestrator(): ToolPreparationOrchestrator {
  return Object.freeze({
    async run({ skipTools }: { readonly skipTools: boolean }): Promise<readonly ToolPreparationResult[]> {
      if (skipTools) {
        return Object.freeze([]);
      }

      const results: ToolPreparationResult[] = [];

      for (const module of PREPARATION_MODULES) {
        const inspectResult = await module.inspect();

        if (inspectResult.status === "READY") {
          results.push(inspectResult);
          continue;
        }

        let authorizeInstall = false;
        let authorizeLogin = false;

        if (inspectResult.status === "MISSING") {
          authorizeInstall = await promptUserAuthorization(module, inspectResult.message ?? `Install ${module.toolId}?`);
        }

        if (inspectResult.status === "AUTH_REQUIRED" || (inspectResult.status === "MISSING" && authorizeInstall)) {
          // Re-inspect after potential installation
          const freshInspect = await module.inspect();
          if (freshInspect.status === "AUTH_REQUIRED") {
            authorizeLogin = await promptUserAuthorization(module, freshInspect.message ?? `Authenticate ${module.toolId}?`);
          }
        }

        const prepareResult = await module.prepare({ authorizeInstall, authorizeLogin });
        results.push(prepareResult);
      }

      return Object.freeze(results);
    },
  });
}

export const toolPreparationOrchestrator = createToolPreparationOrchestrator();

export async function runToolPreparation(skipTools: boolean): Promise<readonly ToolPreparationResult[]> {
  return toolPreparationOrchestrator.run({ skipTools });
}