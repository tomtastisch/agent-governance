# Harness-Rezepte

Diese nicht normative Referenz beschreibt vier manuell verifizierte globale Zielpfade. Sie fügt
keine Harness-Erkennung, Adapter, Hooks oder weitere Runtime-Verhalten hinzu. Die vollständige
Semantik von Commands und Optionen steht in der
[Installer-CLI-Referenz](installer-cli-reference.md).

Jedes Rezept verwendet `--scope global`, einen expliziten absoluten `--installation-root`, einen
vor der Mutation verifizierten absoluten `--target-root` und einen relativen Markdown-
`--entry-file`. Vor `install` ist der tatsächlich aktive globale Zielpfad im jeweiligen Harness
zu prüfen; der Installer leitet ihn nicht selbst ab.

## Codex

Die [Codex-Dokumentation zu AGENTS.md](https://developers.openai.com/codex/guides/agents-md)
nennt `${CODEX_HOME:-$HOME/.codex}/AGENTS.md` als globalen Ort, sofern kein vorrangiges
`AGENTS.override.md` aktiv ist. Nach dieser Prüfung lautet ein Beispiel:

```sh
npx @tomtastisch/agent-governance@1.0.1 install --scope global \
  --installation-root "$HOME/.agent-governance" \
  --target-root "$HOME/.codex" --entry-file AGENTS.md --non-interactive
```

Wenn `CODEX_HOME` gesetzt ist, wird dessen tatsächlich aufgelöster absoluter Wert statt
`$HOME/.codex` als `--target-root` verwendet.

## Claude Code

Die [Claude-Code-Dokumentation zu Memory](https://code.claude.com/docs/en/memory) beschreibt
`$HOME/.claude/CLAUDE.md` für persönliche, projektübergreifende Instruktionen. Nach Prüfung dieses
aktiven Pfads:

```sh
npx @tomtastisch/agent-governance@1.0.1 install --scope global \
  --installation-root "$HOME/.agent-governance" \
  --target-root "$HOME/.claude" --entry-file CLAUDE.md --non-interactive
```

## OpenCode V2

Die [OpenCode-V2-Instruktionsdokumentation](https://opencode.ai/v2/docs/instructions) nennt
`$XDG_CONFIG_HOME/opencode/AGENTS.md`; ohne gesetztes `XDG_CONFIG_HOME` ist dies normalerweise
`$HOME/.config/opencode/AGENTS.md`. Nach Auflösung des tatsächlich aktiven absoluten Konfigurations-
roots, beispielsweise:

```sh
npx @tomtastisch/agent-governance@1.0.1 install --scope global \
  --installation-root "$HOME/.agent-governance" \
  --target-root "$HOME/.config/opencode" --entry-file AGENTS.md --non-interactive
```

## OpenClaw

Die [OpenClaw-Dokumentation zum Agent-Workspace](https://docs.openclaw.ai/agent-workspace)
verwendet `AGENTS.md` im tatsächlich aktiven Agent-Workspace. Der Default
`$HOME/.openclaw/workspace` kann durch Profile, State-Directory, Environment und Agentkonfiguration
abweichen. Nur wenn dieser Default nachweislich aktiv ist, ist dieses Beispiel passend:

```sh
npx @tomtastisch/agent-governance@1.0.1 install --scope global \
  --installation-root "$HOME/.agent-governance" \
  --target-root "$HOME/.openclaw/workspace" --entry-file AGENTS.md --non-interactive
```

Bei einem anderen aktiven Workspace wird ausschließlich dessen verifizierter absoluter Pfad
eingesetzt.
