import { S_CHECKBOX_SELECTED, unicodeOr } from "@clack/prompts";

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

function truncatePlain(value: string, width: number): string {
  const characters = [...value];
  if (characters.length <= width) return value;
  if (width <= 1) return "…";
  return `${characters.slice(0, width - 1).join("")}…`;
}

function wrapPlainWithFinalWidth(value: string, width: number, finalWidth: number): string[] {
  const normalized = value.replace(/\s+/gu, " ").trim();
  const characters = [...normalized];
  if (characters.length <= finalWidth) return [normalized];
  const split = characters.length - finalWidth;
  const leading = characters.slice(0, split).join("").trimEnd();
  const trailing = characters.slice(split).join("").trimStart();
  return [...wrapPlain(leading, width), trailing];
}

function renderCandidateParts(candidate: Candidate, theme: TerminalTheme): {
  readonly label: string;
  readonly hint: string;
} {
  if (candidate.confidence === "REJECTED") throw new Error("rejected candidate cannot be rendered");
  const identity = resolveCandidateIdentity(candidate);
  const confidence = candidate.confidence === "HIGH_CONFIDENCE"
    ? theme.green("[hoch]")
    : theme.yellow("[unsicher]");
  const focus = theme.cyan("[fokus]");
  const pathPrefix = "Pfad: ";
  const optionChromeWidth = 5;
  const fixedWidth = optionChromeWidth
    + visibleWidth(confidence) + 1
    + visibleWidth(focus) + 1
    + visibleWidth(pathPrefix);
  const availableWidth = Math.max(2, theme.columns - fixedWidth);
  const finalLabelWidth = Math.min(
    [...identity.label].length,
    Math.max(1, Math.min(12, Math.floor(availableWidth * 0.4))),
  );
  const pathWidth = Math.max(1, availableWidth - finalLabelWidth);
  const prefixWidth = visibleWidth(confidence) + 1;
  const labelLines = wrapPlainWithFinalWidth(
    identity.label,
    Math.max(1, theme.columns - prefixWidth),
    finalLabelWidth,
  );
  const first = `${confidence} ${labelLines[0] ?? ""}`;
  const continuation = labelLines.slice(1).map((line) => `${" ".repeat(prefixWidth)}${line}`);
  const path = truncatePlain(sanitizeDisplay(candidate.root, 512), pathWidth);
  return Object.freeze({
    label: [first, ...continuation].join("\n"),
    hint: `${focus} ${theme.dim(`${pathPrefix}${path}`)}`,
  });
}

export function renderCandidate(
  candidate: Candidate,
  state: CandidateRenderState,
  theme: TerminalTheme,
): string {
  // Focus and selection are rendered by the live Clack primitive. Keeping the
  // candidate label state-independent prevents stale, duplicated UI markers.
  void state;
  return renderCandidateParts(candidate, theme).label;
}

export function renderCandidateHint(candidate: Candidate, theme: TerminalTheme): string {
  return renderCandidateParts(candidate, theme).hint;
}

export function renderLegend(theme: TerminalTheme): string {
  const first = `${theme.green("[hoch]")} erkannt  ${theme.yellow("[unsicher]")} prüfen`;
  const second = `${theme.cyan("[fokus]")} Cursor  ${theme.green(S_CHECKBOX_SELECTED)} Auswahl`;
  const third = `${unicodeOr("↑/↓", "Up/Down")} navigieren · Leertaste wählen · Enter weiter · Ctrl+C abbrechen`;
  return [first, second, ...wrapPlain(third, theme.columns)].join("\n");
}
