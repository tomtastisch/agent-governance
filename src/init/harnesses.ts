import type { DiscoveredHarness } from "./types.ts";

export interface HarnessDiscoveryPort {
  readonly discover: () => Promise<readonly DiscoveredHarness[]>;
}

export function createAgntnHarnessesAdapter(): HarnessDiscoveryPort {
  return Object.freeze({
    async discover(): Promise<readonly DiscoveredHarness[]> {
      const { getAllHarnesses } = await import("@agntn/harnesses");
      return Object.freeze(
        getAllHarnesses()
          .filter((harness) => harness.isInstalled())
          .map((harness) => Object.freeze({ id: harness.id, displayName: harness.name })),
      );
    },
  });
}
