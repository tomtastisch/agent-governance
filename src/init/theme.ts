import { sanitizeDisplay } from "../discovery/structured.ts";
import { resolveCandidateIdentity } from "../discovery/identity.ts";
import type { Candidate } from "../discovery/types.ts";

const ANSI_PATTERN = /\u001b\[[0-?]*[ -/]*[@-~]/gu;

export interface TerminalThemeOptions {
  readonly columns?: number;
  readonly environment?: Readonly<Record<string, string | undefined>>;
  readonly color?: boolean;
}

export interface TerminalTheme {
  readonly columns: number;
  readonly color: boolean;
  readonly green: (value: string) => string;
  readonly yellow: (value: string) => string;
  readonly cyan: (value: string) => string;
  readonly dim: (value: string) => string;
}

export interface CandidateRenderState {
  readonly focused: boolean;
  readonly selected: boolean;
}

export function stripAnsi(value: string): string {
  return value.replace(ANSI_PATTERN, "");
}

export function visibleWidth(value: string): number {
  return [...stripAnsi(value)].length;
}

function style(code: number, enabled: boolean): (value: string) => string {
  return enabled ? (value) => `\u001b[${code}m${value}\u001b[0m` : (value) => value;
}

export function createTerminalTheme(options: TerminalThemeOptions = {}): TerminalTheme {
  const environment = options.environment ?? process.env;
  const columns = Math.max(20, Math.floor(options.columns ?? process.stdout.columns ?? 80));
  const requestedColor = options.color ?? Boolean(process.stdout.isTTY);
  const color = requestedColor && environment.NO_COLOR === undefined && environment.TERM !== "dumb";
  return Object.freeze({
    columns,
    color,
    green: style(32, color),
    yellow: style(33, color),
    cyan: style(36, color),
    dim: style(2, color),
  });
}

function wrapPlain(value: string, width: number): string[] {
  const normalized = value.replace(/\s+/gu, " ").trim();
  if (normalized === "") return [""];
  const lines: string[] = [];
  let remaining = normalized;
  while ([...remaining].length > width) {
    const slice = [...remaining].slice(0, width).join("");
    const boundary = slice.lastIndexOf(" ");
    const end = boundary > Math.floor(width / 2) ? boundary : width;
    lines.push([...remaining].slice(0, end).join("").trimEnd());
    remaining = [...remaining].slice(end).join("").trimStart();
  }
  if (remaining !== "") lines.push(remaining);
  return lines;
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
  const second = `${theme.cyan("[fokus]")} Cursor  ${theme.green("◼")} Auswahl`;
  const third = "↑/↓ navigieren · Leertaste wählen · Enter weiter · Ctrl+C abbrechen";
  return [first, second, ...wrapPlain(third, theme.columns)].join("\n");
}
