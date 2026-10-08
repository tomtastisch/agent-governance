import type { InstallPhase } from "../../contracts.ts";
import { InterruptedFailure } from "../../errors.ts";
import { createTerminalTheme } from "../../terminal/theme.ts";
import type { ToolPreparationEffectContext, ToolPreparationModule, ToolPreparationOrchestrator, ToolPreparationResult } from "./types.ts";
import { ghPreparationModule } from "./gh.ts";

const PREPARATION_MODULES: readonly ToolPreparationModule[] = Object.freeze([ghPreparationModule]);

export async function promptUserAuthorization(
  _module: ToolPreparationModule,
  message: string,
  io: {
    stdin: { readonly isTTY?: boolean; readonly isRaw?: boolean; setRawMode(value: boolean): unknown; on(event: string, listener: (...args: any[]) => void): unknown; off(event: string, listener: (...args: any[]) => void): unknown; resume(): unknown; pause(): unknown };
    write: (value: string) => void;
    signals?: {
      on(signal: "SIGINT" | "SIGTERM", listener: () => void): unknown;
      off(signal: "SIGINT" | "SIGTERM", listener: () => void): unknown;
    };
  } = { stdin: process.stdin, write: value => { process.stderr.write(value); } },
): Promise<boolean> {
  const { stdin, write } = io;
  const signals = io.signals ?? process;
  const theme = createTerminalTheme();
  write(`${theme.cyan("USER:")} ${message}\n`);
  if (!stdin.isTTY) {
    write("Non-interactive environment, skipping preparation.\n");
    return false;
  }
  write("Press 'y' to continue, any other key to skip:\n");
  const wasRaw = Boolean(stdin.isRaw);
  return new Promise((resolve, reject) => {
    const cleanup = (): void => {
      stdin.off("data", onData);
      stdin.off("end", onEnd);
      stdin.off("error", onError);
      signals.off("SIGINT", onInterrupt);
      signals.off("SIGTERM", onTerminate);
      stdin.setRawMode(wasRaw);
      stdin.pause();
    };
    const onEnd = (): void => { cleanup(); resolve(false); };
    const onError = (error: Error): void => { cleanup(); reject(error); };
    const interrupt = (signal: "SIGINT" | "SIGTERM"): void => {
      cleanup();
      reject(new InterruptedFailure(signal, "inspect", "NOT_REQUIRED"));
    };
    const onInterrupt = (): void => { interrupt("SIGINT"); };
    const onTerminate = (): void => { interrupt("SIGTERM"); };
    const onData = (data: Buffer): void => {
      cleanup();
      if (data.includes(0x03)) {
        write("\n");
        reject(new InterruptedFailure("SIGINT", "inspect", "NOT_REQUIRED"));
      } else {
        resolve(data.toString().toLowerCase().trim() === "y");
      }
    };
    stdin.on("data", onData);
    stdin.on("end", onEnd);
    stdin.on("error", onError);
    signals.on("SIGINT", onInterrupt);
    signals.on("SIGTERM", onTerminate);
    stdin.setRawMode(true);
    stdin.resume();
  });
}

function publicResult({ effectContext: _effectContext, ...result }: ToolPreparationResult): ToolPreparationResult {
  return Object.freeze(result);
}

export function createToolPreparationOrchestrator(dependencies: {
  readonly modules?: readonly ToolPreparationModule[];
  readonly authorize?: typeof promptUserAuthorization;
} = {}): ToolPreparationOrchestrator {
  const modules = dependencies.modules ?? PREPARATION_MODULES;
  const authorize = dependencies.authorize ?? promptUserAuthorization;
  return Object.freeze({
    async run({ skipTools }: { readonly skipTools: boolean }): Promise<readonly ToolPreparationResult[]> {
      if (skipTools) return Object.freeze([]);
      const results: ToolPreparationResult[] = [];
      for (const module of modules) {
        let effectContext: ToolPreparationEffectContext | undefined;
        let phase: InstallPhase = "inspect";
        try {
          let state = await module.inspect();
          if (state.status === "MISSING") {
            const allowed = await authorize(module, `${state.message ?? module.toolId}\nAuthorize installation of ${module.toolId}?`);
            const installed = await module.prepare({ authorizeInstall: allowed, authorizeLogin: false });
            effectContext = installed.effectContext;
            if (!allowed || installed.status === "UNAVAILABLE" || installed.status === "MISSING") {
              results.push(publicResult(installed));
              continue;
            }
            phase = "verify";
            state = await module.inspect();
          }
          if (state.status === "AUTH_REQUIRED") {
            phase = "plan";
            const allowed = await authorize(module, `${state.message ?? module.toolId}\nAuthorize provider web login for ${module.toolId}?`);
            phase = "verify";
            state = await module.prepare({ authorizeInstall: false, authorizeLogin: allowed });
          }
          results.push(publicResult(state));
        } catch (cause) {
          if (cause instanceof InterruptedFailure && cause.externalEffect === undefined && effectContext !== undefined) {
            throw new InterruptedFailure(cause.signal, phase, cause.rollbackStatus, effectContext);
          }
          throw cause;
        }
      }
      return Object.freeze(results);
    },
  });
}

export const toolPreparationOrchestrator = createToolPreparationOrchestrator();

export async function runToolPreparation(skipTools: boolean): Promise<readonly ToolPreparationResult[]> {
  return toolPreparationOrchestrator.run({ skipTools });
}
