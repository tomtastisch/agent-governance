import { S_CHECKBOX_SELECTED, unicodeOr } from "@clack/prompts";

import { compareSemver } from "../installer/version.ts";
import { sanitizeDisplay, visibleWidth, wrapPlain, type TerminalTheme } from "../terminal/theme.ts";
import type { HarnessRow } from "./types.ts";

export { createTerminalTheme, sanitizeDisplay, stripAnsi, visibleWidth, type TerminalTheme, type TerminalThemeOptions } from "../terminal/theme.ts";

export interface HarnessRenderState {
  readonly focused: boolean;
  readonly selected: boolean;
}

export interface HarnessStatus {
  readonly symbol: string;
  readonly color: "green" | "yellow" | "red" | "gray";
  readonly text: string;
}

const RECOVERY_STATES = new Set(["TAMPERED", "RECOVERY_REQUIRED", "DOWNGRADE_BLOCKED"]);
const UNINITIALIZED_STATES = new Set(["ABSENT", "FRESH"]);

export function describeHarness(row: HarnessRow): HarnessStatus {
  if (!row.supported) {
    return { symbol: "–", color: "gray", text: "erkannt · nicht unterstützt" };
  }
  if (RECOVERY_STATES.has(row.state ?? "")) {
    return { symbol: "!", color: "red", text: "Reparatur erforderlich" };
  }
  if (UNINITIALIZED_STATES.has(row.state ?? "")) {
    return { symbol: "○", color: "red", text: "Governance nicht initialisiert" };
  }
  const local = row.localVersion;
  if (local === undefined) {
    return { symbol: "!", color: "red", text: "Reparatur erforderlich" };
  }
  const latest = row.latestVersion;
  if (latest === undefined) {
    return { symbol: "✓", color: "green", text: `Governance v${local} · ? latest unbekannt` };
  }
  if (compareSemver(local, latest) < 0) {
    return { symbol: "⚠", color: "yellow", text: `Governance v${local} → v${latest} verfügbar` };
  }
  return { symbol: "✓", color: "green", text: `Governance v${local}` };
}

function colorFor(theme: TerminalTheme, color: HarnessStatus["color"]): (value: string) => string {
  switch (color) {
    case "green": return theme.green;
    case "yellow": return theme.yellow;
    case "red": return theme.red;
    case "gray": return theme.dim;
  }
}

export function renderHarnessRow(
  row: HarnessRow,
  state: HarnessRenderState,
  theme: TerminalTheme,
): string {
  // Focus and selection are rendered by the live Clack primitive. Keeping the
  // label state-independent prevents stale, duplicated UI markers.
  void state;
  const status = describeHarness(row);
  const prefix = colorFor(theme, status.color)(`[${status.symbol}]`);
  const prefixWidth = visibleWidth(prefix) + 1;
  const labelWidth = Math.max(10, theme.columns - prefixWidth);
  const labelLines = wrapPlain(sanitizeDisplay(row.displayName, 96), labelWidth);
  const first = `${prefix} ${labelLines[0] ?? ""}`;
  const continuation = labelLines.slice(1).map((line) => `${" ".repeat(prefixWidth)}${line}`);
  const statusLines = wrapPlain(status.text, Math.max(10, theme.columns - 2)).map((line) => theme.dim(`  ${line}`));
  return [first, ...continuation, ...statusLines].join("\n");
}

export function renderLegend(theme: TerminalTheme): string {
  const first = `${theme.green("✓")} integer  ${theme.yellow("⚠")} Update  ${theme.red("○/!")} nicht init/Reparatur`;
  const second = `${theme.cyan("[fokus]")} Cursor  ${theme.green(S_CHECKBOX_SELECTED)} Auswahl  ${theme.dim("–")} nicht unterstützt`;
  const third = `${unicodeOr("↑/↓", "Up/Down")} navigieren · Leertaste wählen · Enter weiter · Ctrl+C abbrechen`;
  return [first, second, ...wrapPlain(third, theme.columns)].join("\n");
}
