import assert from "node:assert/strict";
import test from "node:test";
import { loadCommandCatalog } from "../../src/command-catalog.ts";
import { renderCommandHelp, renderGlobalHelp } from "../../src/public-commands.ts";
import { createTerminalTheme, stripAnsi } from "../../src/terminal/theme.ts";

const commands = loadCommandCatalog();
const colorTheme = createTerminalTheme({ color: true, environment: { TERM: "xterm-256color" } });

test("global help renders the plain structure without color by default", () => {
  const help = renderGlobalHelp();
  assert.equal(help.includes("\u001b["), false);
  assert.match(help, /^Usage: agent-governance <command> \[options\]$/m);
  assert.match(help, /^Commands:$/m);
  for (const { path, description } of commands) assert.equal(help.includes(path.join(" ")), true);
  for (const { description } of commands) assert.equal(help.includes(description), true);
  assert.match(help, /Run agent-governance <command> --help for command-specific help\./);
});

test("global help colors the visual hierarchy through the shared terminal theme", () => {
  const help = renderGlobalHelp(commands, colorTheme);
  assert.equal(help.includes("\u001b[36mUsage:\u001b[0m"), true);
  assert.equal(help.includes("\u001b[36m<command>\u001b[0m"), true);
  assert.equal(help.includes("\u001b[2m[options]\u001b[0m"), true);
  assert.equal(help.includes("\u001b[36mCommands:\u001b[0m"), true);
  assert.match(help, /\u001b\[36minspect\s+\u001b\[0m/u);
  assert.match(help, /\u001b\[2mRun agent-governance <command> --help/u);
});

test("NO_COLOR and TERM=dumb disable ANSI in help output", () => {
  for (const environment of [{ NO_COLOR: "1", TERM: "xterm-256color" }, { TERM: "dumb" }]) {
    const theme = createTerminalTheme({ color: true, environment });
    assert.equal(theme.color, false);
    assert.equal(renderGlobalHelp(commands, theme).includes("\u001b["), false);
    assert.equal(renderCommandHelp("install", commands, theme).includes("\u001b["), false);
  }
});

test("colored help keeps command names and descriptions aligned independent of ANSI", () => {
  const width = Math.max(...commands.map(({ path }) => path.join(" ").length));
  const plain = stripAnsi(renderGlobalHelp(commands, colorTheme));
  for (const { path, description } of commands) {
    const line = plain.split("\n").find((candidate) => candidate.includes(path.join(" ")) && candidate.includes(description));
    assert.ok(line, path.join(" "));
    assert.equal(line.indexOf(description), 2 + width + 2, path.join(" "));
  }
});

test("command help applies the same visual schema to usage and options", () => {
  const help = renderCommandHelp("install", commands, colorTheme);
  assert.equal(help.includes("\u001b[36mUsage:\u001b[0m"), true);
  assert.equal(help.includes("\u001b[36mOptions:\u001b[0m"), true);
  assert.equal(help.includes("\u001b[36minstall\u001b[0m"), true);
  assert.match(stripAnsi(help), /^Usage: agent-governance install /m);
  assert.match(stripAnsi(help), /^Options:$/m);
});

test("command help aligns option names and descriptions independent of ANSI", () => {
  const optionNames = ["--target-root <path>", "--entry-file <path>", "--scope global", "--installation-root <path>", "--local-rules <path>", "--dry-run", "--non-interactive", "--json", "-h, --help"];
  const descriptions = ["Explicit target root.", "Relative Markdown entry file.", "Required global scope.", "Explicit installation root.", "Optional local rules file.", "Do not mutate the target.", "Disable interactive behavior.", "Emit structured JSON.", "Show this help."];
  const width = Math.max(...optionNames.map((name) => name.length));
  const plain = stripAnsi(renderCommandHelp("install", commands, colorTheme));
  for (let index = 0; index < optionNames.length; index += 1) {
    const name = optionNames[index]!;
    const description = descriptions[index]!;
    const line = plain.split("\n").find((candidate) => candidate.includes(name) && candidate.includes(description));
    assert.ok(line, name);
    assert.equal(line.indexOf(description), 2 + width + 2, name);
  }
});

test("init command help uses the orchestration-specific invocation", () => {
  const plain = stripAnsi(renderCommandHelp("init", commands, colorTheme));
  assert.match(plain, /^Usage: agent-governance init$/m);
  assert.match(plain, /-h, --help/);
});
