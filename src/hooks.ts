const TOOL_NAME = "agent_governance__execute";

interface HookGroup {
  matcher?: unknown;
  hooks?: unknown;
  [key: string]: unknown;
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function mergeGovernanceHook(existing: string | undefined, commandPath: string): string {
  let root: Record<string, unknown> = {};
  if (existing !== undefined && existing.trim() !== "") {
    try {
      const parsed: unknown = JSON.parse(existing);
      if (!record(parsed)) throw new Error("root is not an object");
      root = parsed;
    } catch {
      throw new Error("hooks configuration is not valid JSON");
    }
  }
  const hooksValue = root.hooks ?? {};
  if (!record(hooksValue)) throw new Error("hooks must be an object");
  const hooks = { ...hooksValue };
  const currentValue = hooks.PreToolUse ?? [];
  if (!Array.isArray(currentValue)) throw new Error("PreToolUse must be an array");
  const current = currentValue.map((item) => {
    if (!record(item)) throw new Error("PreToolUse entry must be an object");
    return item as HookGroup;
  });
  const matching = current.filter((item) => item.matcher === TOOL_NAME);
  if (matching.length > 1) throw new Error("governance hook configuration is ambiguous");
  const governance: HookGroup = {
    matcher: TOOL_NAME,
    hooks: [{ type: "command", command: `node ${JSON.stringify(commandPath)}`, timeout: 30 }],
  };
  hooks.PreToolUse = matching.length === 0
    ? [...current, governance]
    : current.map((item) => (item.matcher === TOOL_NAME ? governance : item));
  return `${JSON.stringify({ ...root, hooks }, null, 2)}\n`;
}
