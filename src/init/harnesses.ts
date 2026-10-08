import { execFileSync } from "node:child_process";
import { HARNESS_DISCOVERY } from "./harness-discovery.generated.ts";
import type { DiscoveredHarness } from "./types.ts";

export interface HarnessDiscoveryPort {
  readonly discover: () => Promise<readonly DiscoveredHarness[]>;
}

export function createAgntnHarnessesAdapter(): HarnessDiscoveryPort {
  return Object.freeze({
    async discover(): Promise<readonly DiscoveredHarness[]> {
      return Object.freeze(
        HARNESS_DISCOVERY
          .filter((harness) => harness.binaries.some((binary) => {
            try {
              execFileSync(process.platform === "win32" ? "where" : "which", [binary], { stdio: "pipe" });
              return true;
            } catch {
              return false;
            }
          }))
          .map((harness) => Object.freeze({ id: harness.id, displayName: harness.displayName })),
      );
    },
  });
}
