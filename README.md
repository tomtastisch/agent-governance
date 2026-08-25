<p align="center">
  <img src="https://raw.githubusercontent.com/tomtastisch/agent-governance/main/assets/branding/agent-governance-icon.png" alt="Agent Governance" width="96">
</p>

# Agent Governance

Agent Governance installiert versionierte, harness-neutrale Regeln kontrolliert, überprüfbar und reversibel an expliziten globalen Zielpfaden.

[![npm](https://img.shields.io/npm/v/@tomtastisch/agent-governance?style=flat-square)](https://www.npmjs.com/package/@tomtastisch/agent-governance) [![CI](https://github.com/tomtastisch/agent-governance/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/tomtastisch/agent-governance/actions/workflows/ci.yml) [![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-0D9BF2?style=flat-square)](https://github.com/tomtastisch/agent-governance/blob/main/LICENSE)

## Was ist Agent Governance?

Das Projekt verbindet den kanonischen Governance-Bestand mit einem providerneutralen,
adapterlosen Installer. Er verwaltet ausschließlich seinen Markdownblock im bewusst gewählten
Einstieg.

## Warum Agent Governance?

Agent-Harnesses unterscheiden sich in ihren globalen Einstiegspunkten. Der Installer hält die
Verantwortung deshalb bei expliziten Pfaden und einem einheitlichen, überprüfbaren Bundle statt
bei Harness-Erkennung, Adaptern oder impliziten Zielannahmen.

- Konsistente Regeln über mehrere Harnesses hinweg
- Weniger Konfigurationsdrift durch einen zentralen Governance-Bestand
- Nachvollziehbare, verifizierbare und reversible Installation
- Keine stillen Harness-Mutationen oder impliziten Zielpfade

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

Die [CLI-Referenz](https://github.com/tomtastisch/agent-governance/blob/main/docs/installer-cli-reference.md) erklärt Bedeutung, Pflichtangaben und Optionen; die [Harness-Rezepte](https://github.com/tomtastisch/agent-governance/blob/main/docs/harness-recipes.md) helfen, den harness-spezifischen aktiven globalen Zielpfad vor der Installation zu prüfen.

## Wie funktioniert es?

Der Installer prüft ein geschlossenes, versioniertes Bundle, sichert den bestehenden Einstieg und
verwaltet genau seinen eigenen Markdownblock. Die Details zu Commands, Lifecycle, Recovery,
Sicherheitsgrenzen und Datenstrukturen liegen jeweils bei ihrer zuständigen Referenz.

![Übersicht: Agent Governance verbindet klare Regeln, Toolwahl, Grenzen und nachvollziehbare Ergebnisse.](https://raw.githubusercontent.com/tomtastisch/agent-governance/main/assets/diagrams/governance-overview.png)

## Dokumentation

- [Commands, Optionen und Exitverhalten](https://github.com/tomtastisch/agent-governance/blob/main/docs/installer-cli-reference.md)
- [Verifizierte Harness-Rezepte](https://github.com/tomtastisch/agent-governance/blob/main/docs/harness-recipes.md)
- [Installerarchitektur und Lifecycle](https://github.com/tomtastisch/agent-governance/blob/main/docs/installer-architecture.md)
- [Trust Boundaries und Residual Risks](https://github.com/tomtastisch/agent-governance/blob/main/docs/installer-threat-model.md)
- [JSON-Strukturen und Feldsemantik](https://github.com/tomtastisch/agent-governance/blob/main/docs/installer-json-schemas.md)
- [Versionen und Migrationen](https://github.com/tomtastisch/agent-governance/blob/main/CHANGELOG.md)
- [Normative Governancequelle](https://github.com/tomtastisch/agent-governance/blob/main/bundle/GOVERNANCE.md)

## Support und Lizenz

[![Buy Me a Coffee](https://img.buymeacoffee.com/button-api/?text=Buy%20me%20a%20coffee&emoji=&slug=tomtastisch&button_colour=FFDD00&font_colour=000000&font_family=Cookie&outline_colour=000000&coffee_colour=ffffff)](https://buymeacoffee.com/tomtastisch)

Lizenz: [Apache-2.0](https://github.com/tomtastisch/agent-governance/blob/main/LICENSE)
