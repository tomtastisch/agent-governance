import assert from "node:assert/strict";
import test from "node:test";

import type { Candidate } from "../../src/discovery/types.ts";
import {
  createTerminalTheme,
  renderCandidate,
  renderLegend,
  stripAnsi,
  visibleWidth,
} from "../../src/init/theme.ts";

function candidate(root: string, confidence: Candidate["confidence"]): Candidate {
  return {
    root,
    candidateClass: "DIRECTORY",
    status: "COMPLETE",
    confidence,
    score: confidence === "HIGH_CONFIDENCE" ? 9 : 3,
    families: ["runtime", "state", "tooling"],
    independentSources: 3,
    evidence: [],
    fileCount: 3,
    evidenceDensity: 1,
    activityAt: null,
    evidenceDigest: "a".repeat(64),
  };
}

test("renderCandidate leaves live focus and selection chrome to the Clack primitive", () => {
  const theme = createTerminalTheme({ columns: 80, environment: { TERM: "xterm-256color" }, color: true });
  const rendered = renderCandidate(
    candidate("/synthetic/Alpha", "HIGH_CONFIDENCE"),
    { focused: true, selected: true },
    theme,
  );

  assert.match(rendered, /\u001b\[32m\[hoch\]\u001b\[0m/u);
  assert.doesNotMatch(rendered, /\[fokus\]|\[ausgewählt\]/u);
  assert.match(stripAnsi(rendered), /^\[hoch\] Alpha/mu);
});

test("uncertain candidates remain distinguishable without changing their local label", () => {
  const theme = createTerminalTheme({ columns: 80, environment: {}, color: false });
  const rendered = renderCandidate(
    candidate("/synthetic/Local Target", "UNCERTAIN"),
    { focused: false, selected: false },
    theme,
  );

  assert.match(rendered, /^\[unsicher\] Local Target/mu);
  assert.doesNotMatch(rendered, /Local Target \(unsicher\)/u);
});

test("NO_COLOR and reduced terminals preserve marker semantics without ANSI", () => {
  for (const environment of [{ NO_COLOR: "1", TERM: "xterm-256color" }, { TERM: "dumb" }]) {
    const theme = createTerminalTheme({ columns: 60, environment, color: true });
    const rendered = renderCandidate(
      candidate("/synthetic/Beta", "UNCERTAIN"),
      { focused: true, selected: true },
      theme,
    );
    assert.equal(theme.color, false);
    assert.equal(rendered.includes("\u001b["), false);
    assert.match(rendered, /^\[unsicher\] Beta/mu);
    assert.doesNotMatch(rendered, /\[fokus\]|\[ausgewählt\]/u);
  }
});

test("candidate and legend rendering stay within a 60-column terminal", () => {
  const theme = createTerminalTheme({ columns: 60, environment: {}, color: false });
  const rendered = renderCandidate(
    candidate(`/synthetic/${"very-long-local-label-".repeat(5)}`, "HIGH_CONFIDENCE"),
    { focused: true, selected: true },
    theme,
  );
  const legend = renderLegend(theme);

  for (const line of `${rendered}\n${legend}`.split("\n")) {
    assert.ok(visibleWidth(line) <= 60, `${visibleWidth(line)} columns: ${line}`);
  }
  assert.match(legend, /\[hoch\].*\[unsicher\]/u);
  assert.match(legend, /\[fokus\].*◼ Auswahl/u);
  assert.match(legend, /↑\/↓.*Leertaste.*Enter.*Ctrl\+C/u);
});

test("candidate labels and paths cannot inject terminal control sequences", () => {
  const theme = createTerminalTheme({ columns: 80, environment: {}, color: false });
  const rendered = renderCandidate(
    candidate("/synthetic/Evil\u001b]8;;https://example.invalid\u0007label", "HIGH_CONFIDENCE"),
    { focused: false, selected: false },
    theme,
  );

  assert.equal(rendered.includes("\u001b"), false);
  assert.equal(rendered.includes("\u0007"), false);
  assert.match(rendered, /Evil\?/u);
});
