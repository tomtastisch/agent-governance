import assert from "node:assert/strict";
import test from "node:test";

import {
  createTerminalTheme,
  describeHarness,
  renderHarnessRow,
  renderLegend,
  stripAnsi,
  visibleWidth,
} from "../../src/init/theme.ts";
import type { HarnessRow } from "../../src/init/types.ts";

interface RowOverrides {
  id?: string;
  displayName?: string;
  supported?: boolean;
  targetRoot?: string;
  entryFile?: string;
  state?: NonNullable<HarnessRow["state"]>;
  localVersion?: string;
  latestVersion?: string;
}

function row(overrides: RowOverrides = {}): HarnessRow {
  return {
    id: "claude",
    displayName: "Anthropic Claude Code",
    supported: true,
    targetRoot: "/home/u/.claude",
    entryFile: "CLAUDE.md",
    state: "CURRENT",
    localVersion: "1.4.5",
    latestVersion: "1.4.5",
    ...overrides,
  };
}

test("unsupported harnesses are gray and never selectable as automatic targets", () => {
  const status = describeHarness({ id: "pi", displayName: "Pi Coding Agent", supported: false });
  assert.deepEqual(status, { symbol: "–", color: "gray", text: "erkannt · nicht unterstützt" });
});

test("tampered and recovery-required bindings never render a green status", () => {
  for (const state of ["TAMPERED", "RECOVERY_REQUIRED", "DOWNGRADE_BLOCKED"] as const) {
    const status = describeHarness(row({ state }));
    assert.equal(status.symbol, "!", state);
    assert.equal(status.color, "red", state);
    assert.match(status.text, /Reparatur/, state);
  }
});

test("absent and fresh bindings are not initialized", () => {
  for (const state of ["ABSENT", "FRESH"] as const) {
    const status = describeHarness(row({ state }));
    assert.deepEqual(status, { symbol: "○", color: "red", text: "Governance nicht initialisiert" }, state);
  }
});

test("an integer binding with local == latest is green", () => {
  assert.deepEqual(describeHarness(row()), {
    symbol: "✓",
    color: "green",
    text: "Governance v1.4.5",
  });
});

test("local < latest shows the update target version", () => {
  const status = describeHarness(row({ localVersion: "1.4.4", latestVersion: "1.4.5" }));
  assert.deepEqual(status, { symbol: "⚠", color: "yellow", text: "Governance v1.4.4 → v1.4.5 verfügbar" });
});

test("an unknown latest shows integrity without claiming currency", () => {
  const status = describeHarness({
    id: "claude",
    displayName: "Anthropic Claude Code",
    supported: true,
    targetRoot: "/home/u/.claude",
    entryFile: "CLAUDE.md",
    state: "CURRENT",
    localVersion: "1.4.5",
  });
  assert.deepEqual(status, { symbol: "✓", color: "green", text: "Governance v1.4.5 · ? latest unbekannt" });
});

test("render keeps symbol, text, and color independent of focus and selection", () => {
  const theme = createTerminalTheme({ columns: 80, environment: { TERM: "xterm-256color" }, color: true });
  const rendered = renderHarnessRow(row(), { focused: true, selected: true }, theme);
  assert.match(rendered, /\u001b\[32m\[✓\]\u001b\[0m/u);
  assert.doesNotMatch(rendered, /\[fokus\]|\[ausgewählt\]/u);
  assert.match(stripAnsi(rendered), /^\[✓\] Anthropic Claude Code/mu);
});

test("NO_COLOR and reduced terminals preserve the symbol without ANSI", () => {
  for (const environment of [{ NO_COLOR: "1", TERM: "xterm-256color" }, { TERM: "dumb" }]) {
    const theme = createTerminalTheme({ columns: 60, environment, color: true });
    const rendered = renderHarnessRow(row(), { focused: true, selected: true }, theme);
    assert.equal(theme.color, false);
    assert.equal(rendered.includes("\u001b["), false);
    assert.match(rendered, /^\[✓\] Anthropic Claude Code/mu);
  }
});

test("display names and status text cannot inject terminal control sequences", () => {
  const theme = createTerminalTheme({ columns: 80, environment: {}, color: false });
  const rendered = renderHarnessRow(
    row({ displayName: "Evil\u001b]8;;https://example.invalid\u0007label" }),
    { focused: false, selected: false },
    theme,
  );
  assert.equal(rendered.includes("\u001b"), false);
  assert.equal(rendered.includes("\u0007"), false);
  assert.match(rendered, /Evil\?/u);
});

test("rows and legend stay within a 60-column terminal", () => {
  const theme = createTerminalTheme({ columns: 60, environment: {}, color: false });
  const rendered = renderHarnessRow(
    row({ displayName: "Anthropic Claude Code with a very long display name".repeat(2) }),
    { focused: true, selected: true },
    theme,
  );
  const legend = renderLegend(theme);
  for (const line of `${rendered}\n${legend}`.split("\n")) {
    assert.ok(visibleWidth(line) <= 60, `${visibleWidth(line)} columns: ${line}`);
  }
  assert.match(legend, /✓.*⚠.*nicht init/u);
  assert.match(legend, /\[fokus\].*Auswahl/u);
  assert.match(legend, /↑\/↓.*Leertaste.*Enter.*Ctrl\+C/u);
});

test("visibleWidth measures terminal cells for wide, combining, and emoji characters", () => {
  assert.equal(visibleWidth("界".repeat(30)), 60);
  assert.equal(visibleWidth(("e\u0301").repeat(30)), 30);
  assert.equal(visibleWidth("👩‍💻".repeat(20)), 40);
});
