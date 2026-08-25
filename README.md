<p align="center">
  <img src="https://raw.githubusercontent.com/tomtastisch/agent-governance/main/assets/branding/agent-governance-icon.png" alt="Agent Governance" width="96">
</p>

# Agent Governance

[![npm](https://img.shields.io/npm/v/@tomtastisch/agent-governance?style=flat-square)](https://www.npmjs.com/package/@tomtastisch/agent-governance) [![CI](https://github.com/tomtastisch/agent-governance/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/tomtastisch/agent-governance/actions/workflows/ci.yml) [![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-0D9BF2?style=flat-square)](https://github.com/tomtastisch/agent-governance/blob/main/LICENSE)

## Was ist Agent Governance?

Agent Governance ist ein harness- und providerneutrales Rulebook mit einem globalen,
adapterlosen Installer. Es bindet ein versioniertes Governance-Bundle über einen verwalteten
Markdownblock an einen bewusst gewählten globalen Einstieg.

## Warum Agent Governance?

Agent-Harnesses unterscheiden sich in ihren globalen Einstiegspunkten. Der Installer hält die
Verantwortung deshalb bei expliziten Pfaden und einem einheitlichen, überprüfbaren Bundle statt
bei Harness-Erkennung, Adaptern oder impliziten Zielannahmen.

![Übersicht: Agent Governance verbindet klare Regeln, Toolwahl, Grenzen und nachvollziehbare Ergebnisse.](https://raw.githubusercontent.com/tomtastisch/agent-governance/main/assets/diagrams/governance-overview.png)

## Schnellstart

Verwende den Stable-Channel `@latest`. `--installation-root` und `--target-root` müssen
ausdrückliche absolute Pfade sein; `--entry-file` ist ein relativer Markdownpfad innerhalb des
gewählten Target-Roots. Erst planen, dann installieren und verifizieren:

```sh
npx @tomtastisch/agent-governance@latest plan \
  --scope global \
  --installation-root "$HOME/.agent-governance" \
  --target-root "$HOME/.codex" \
  --entry-file "AGENTS.md" \
  --non-interactive

npx @tomtastisch/agent-governance@latest install \
  --scope global \
  --installation-root "$HOME/.agent-governance" \
  --target-root "$HOME/.codex" \
  --entry-file "AGENTS.md" \
  --non-interactive

npx @tomtastisch/agent-governance@latest verify \
  --scope global \
  --installation-root "$HOME/.agent-governance" \
  --target-root "$HOME/.codex" \
  --entry-file "AGENTS.md" \
  --non-interactive
```

## Wie funktioniert es?

Der Installer prüft ein geschlossenes, versioniertes Bundle, sichert den bestehenden Einstieg und
verwaltet genau seinen eigenen Markdownblock. Die Details zu Commands, Lifecycle, Recovery,
Sicherheitsgrenzen und Datenstrukturen liegen jeweils bei ihrer zuständigen Referenz.

## Dokumentation

- [Commands, Optionen und Exitverhalten](https://github.com/tomtastisch/agent-governance/blob/main/docs/installer-cli-reference.md)
- [Verifizierte Harness-Rezepte](https://github.com/tomtastisch/agent-governance/blob/main/docs/harness-recipes.md)
- [Installerarchitektur und Lifecycle](https://github.com/tomtastisch/agent-governance/blob/main/docs/installer-architecture.md)
- [Trust Boundaries und Residual Risks](https://github.com/tomtastisch/agent-governance/blob/main/docs/installer-threat-model.md)
- [JSON-Strukturen und Feldsemantik](https://github.com/tomtastisch/agent-governance/blob/main/docs/installer-json-schemas.md)
- [Versionen und Migrationen](https://github.com/tomtastisch/agent-governance/blob/main/CHANGELOG.md)
- [Normative Governancequelle](https://github.com/tomtastisch/agent-governance/blob/main/bundle/GOVERNANCE.md)

## Support und Lizenz

[Buy me a coffee](https://buymeacoffee.com/tomtastisch) · Lizenz:
[Apache-2.0](https://github.com/tomtastisch/agent-governance/blob/main/LICENSE)
