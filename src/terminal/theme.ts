const ANSI_PATTERN = /\u001b\[[0-?]*[ -/]*[@-~]/gu;
const GRAPHEME_SEGMENTER = new Intl.Segmenter(undefined, { granularity: "grapheme" });
const MARK_PATTERN = /^\p{Mark}$/u;

function isCombiningCodePoint(codePoint: number): boolean {
  return MARK_PATTERN.test(String.fromCodePoint(codePoint));
}

function isWideCodePoint(codePoint: number): boolean {
  return (codePoint >= 0x1100 && codePoint <= 0x115f)
    || codePoint === 0x2329 || codePoint === 0x232a
    || (codePoint >= 0x2e80 && codePoint <= 0x303e)
    || (codePoint >= 0x3040 && codePoint <= 0xa4cf)
    || (codePoint >= 0xac00 && codePoint <= 0xd7a3)
    || (codePoint >= 0xf900 && codePoint <= 0xfaff)
    || (codePoint >= 0xfe10 && codePoint <= 0xfe6f)
    || (codePoint >= 0xff01 && codePoint <= 0xff60)
    || (codePoint >= 0xffe0 && codePoint <= 0xffe6)
    || (codePoint >= 0x1f000 && codePoint <= 0x1faff)
    || (codePoint >= 0x20000 && codePoint <= 0x3fffd);
}

function codePointCellWidth(codePoint: number): number {
  if (codePoint === 0x200c || codePoint === 0x200d || (codePoint >= 0xe0020 && codePoint <= 0xe007f)) return 0;
  if (isCombiningCodePoint(codePoint) || (codePoint >= 0x1f3fb && codePoint <= 0x1f3ff)) return 0;
  if (codePoint < 0x20 || (codePoint >= 0x7f && codePoint < 0xa0)) return 0;
  return isWideCodePoint(codePoint) ? 2 : 1;
}

function graphemeCellWidth(grapheme: string): number {
  const codePoints = [...grapheme].map((character) => character.codePointAt(0)!);
  if (codePoints.some((codePoint) => codePoint === 0x200d)) return 2;
  if (codePoints.length === 2 && codePoints.every((codePoint) => codePoint >= 0x1f1e6 && codePoint <= 0x1f1ff)) return 2;
  return codePoints.reduce((width, codePoint) => width + codePointCellWidth(codePoint), 0);
}

function graphemes(value: string): string[] {
  return Array.from(GRAPHEME_SEGMENTER.segment(value), ({ segment }) => segment);
}

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
  readonly red: (value: string) => string;
  readonly dim: (value: string) => string;
}

export function sanitizeDisplay(value: string, maximumLength: number): string {
  return value.replace(/[\u0000-\u001f\u007f-\u009f]/gu, "?").slice(0, maximumLength);
}

export function stripAnsi(value: string): string {
  return value.replace(ANSI_PATTERN, "");
}

export function visibleWidth(value: string): number {
  return graphemes(stripAnsi(value)).reduce((width, grapheme) => width + graphemeCellWidth(grapheme), 0);
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
    red: style(31, color),
    dim: style(2, color),
  });
}

export function wrapPlain(value: string, width: number): string[] {
  const normalized = value.replace(/\s+/gu, " ").trim();
  if (normalized === "") return [""];
  const lines: string[] = [];
  let remaining = normalized;
  while (visibleWidth(remaining) > width) {
    const remainingGraphemes = graphemes(remaining);
    let cellWidth = 0;
    let graphemeCount = 0;
    while (graphemeCount < remainingGraphemes.length) {
      const nextWidth = graphemeCellWidth(remainingGraphemes[graphemeCount]!);
      if (cellWidth + nextWidth > width) break;
      cellWidth += nextWidth;
      graphemeCount += 1;
    }
    if (graphemeCount === 0) graphemeCount = 1;
    const slice = remainingGraphemes.slice(0, graphemeCount).join("");
    const boundary = slice.lastIndexOf(" ");
    const end = boundary > Math.floor(width / 2) ? boundary : slice.length;
    lines.push(slice.slice(0, end).trimEnd());
    remaining = `${slice.slice(end)}${remainingGraphemes.slice(graphemeCount).join("")}`.trimStart();
  }
  if (remaining !== "") lines.push(remaining);
  return lines;
}
