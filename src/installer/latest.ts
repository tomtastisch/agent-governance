const REGISTRY_URL = "https://registry.npmjs.org/@tomtastisch%2fagent-governance";
const DEFAULT_TIMEOUT_MS = 2500;
const SEMVER = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$/;

export async function resolveLatestRelease(
  fetchImpl: typeof fetch = fetch,
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<string | undefined> {
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetchImpl(REGISTRY_URL, {
        signal: controller.signal,
        headers: { accept: "application/json" },
      });
      if (!response.ok) return undefined;
      const payload = (await response.json()) as { "dist-tags"?: { latest?: unknown } };
      const latest = payload["dist-tags"]?.latest;
      if (typeof latest !== "string" || !SEMVER.test(latest)) return undefined;
      return latest;
    } finally {
      clearTimeout(timer);
    }
  } catch {
    return undefined;
  }
}
