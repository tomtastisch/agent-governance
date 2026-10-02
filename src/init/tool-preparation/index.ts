import type { ToolPreparationModule, ToolPreparationOrchestrator, ToolPreparationResult } from "./types.ts";
import { ghPreparationModule } from "./gh.ts";

const PREPARATION_MODULES: readonly ToolPreparationModule[] = Object.freeze([ghPreparationModule]);

async function promptUserAuthorization(module: ToolPreparationModule, message: string): Promise<boolean> {
  const { stdin, stdout } = process;
  
  // If not a TTY, skip interactively (safe default for CI/non-interactive environments)
  if (!stdin.isTTY) {
    const { createTerminalTheme } = await import("../../terminal/theme.ts");
    const theme = createTerminalTheme({ color: true });
    console.log(`${theme.cyan("USER:")} ${message}`);
    console.log(`${theme.dim("Non-interactive environment, skipping preparation.")}`);
    return false;
  }
  
  return new Promise(async (resolve) => {
    const { createTerminalTheme } = await import("../../terminal/theme.ts");
    const theme = createTerminalTheme({ color: true });
    console.log(`${theme.cyan("USER:")} ${message}`);
    console.log(`${theme.dim("Press 'y' to continue, any other key to skip:")}`);
    
    const onData = (data: Buffer) => {
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
        
        if (inspectResult.status === "MISSING" || inspectResult.status === "AUTH_REQUIRED") {
          const userAuthorized = await promptUserAuthorization(module, inspectResult.message ?? `Prepare ${module.toolId}?`);
          const prepareResult = await module.prepare({ userAuthorized });
          results.push(prepareResult);
          continue;
        }
        
        results.push(inspectResult);
      }
      
      return Object.freeze(results);
    },
  });
}

export const toolPreparationOrchestrator = createToolPreparationOrchestrator();

export async function runToolPreparation(skipTools: boolean): Promise<readonly ToolPreparationResult[]> {
  return toolPreparationOrchestrator.run({ skipTools });
}