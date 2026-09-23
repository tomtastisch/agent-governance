import { S_CHECKBOX_SELECTED, unicodeOr } from "@clack/prompts";

import { sanitizeDisplay } from "../discovery/structured.ts";
import { resolveCandidateIdentity } from "../discovery/identity.ts";
import type { Candidate } from "../discovery/types.ts";
import { visibleWidth, wrapPlain, type TerminalTheme } from "../terminal/theme.ts";

export { createTerminalTheme, stripAnsi, visibleWidth, type TerminalTheme, type TerminalThemeOptions } from "../terminal/theme.ts";

export interface CandidateRenderState {
  readonly focused: boolean;
  readonly selected: boolean;
}

export function renderCandidate(
  candidate: Candidate,
  state: CandidateRenderState,
  theme: TerminalTheme,
): string {
  if (candidate.confidence === "REJECTED") throw new Error("rejected candidate cannot be rendered");
  const identity = resolveCandidateIdentity(candidate);
  const confidence = candidate.confidence === "HIGH_CONFIDENCE"
    ? theme.green("[hoch]")
    : theme.yellow("[unsicher]");
  // Focus and selection are rendered by the live Clack primitive. Keeping the
  // candidate label state-independent prevents stale, duplicated UI markers.
  void state;
  const prefix = confidence;
  const prefixWidth = visibleWidth(prefix) + 1;
  const labelWidth = Math.max(10, theme.columns - prefixWidth);
  const labelLines = wrapPlain(identity.label, labelWidth);
  const first = `${prefix} ${labelLines[0] ?? ""}`;
  const continuation = labelLines.slice(1).map((line) => `${" ".repeat(prefixWidth)}${line}`);
  const safeRoot = sanitizeDisplay(candidate.root, 512);
  const rootLines = wrapPlain(safeRoot, Math.max(10, theme.columns - 2)).map((line) => theme.dim(`  ${line}`));
  return [first, ...continuation, ...rootLines].join("\n");
}

export function renderLegend(theme: TerminalTheme): string {
  const first = `${theme.green("[hoch]")} erkannt  ${theme.yellow("[unsicher]")} prüfen`;
  const second = `${theme.cyan("[fokus]")} Cursor  ${theme.green(S_CHECKBOX_SELECTED)} Auswahl`;
  const third = `${unicodeOr("↑/↓", "Up/Down")} navigieren · Leertaste wählen · Enter weiter · Ctrl+C abbrechen`;
  return [first, second, ...wrapPlain(third, theme.columns)].join("\n");
}
