<p align="center">
  <img src="https://raw.githubusercontent.com/tomtastisch/agent-governance/main/assets/branding/agent-governance-icon.png" alt="Agent Governance" width="160">
</p>

# Agent Governance

Agent Governance verbindet harness-neutrale Regeln mit sicherer Installation und deterministischen Verträgen für Resume, Work Items und Sources of Truth.

[![npm](https://img.shields.io/npm/v/@tomtastisch/agent-governance?style=flat-square)](https://www.npmjs.com/package/@tomtastisch/agent-governance) [![CI](https://github.com/tomtastisch/agent-governance/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/tomtastisch/agent-governance/actions/workflows/ci.yml) [![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-0D9BF2?style=flat-square)](https://github.com/tomtastisch/agent-governance/blob/main/LICENSE)

## Was ist Agent Governance?

Das Projekt liefert ein geschlossenes Governance-Bundle, einen providerneutralen, adapterlosen
Installer und öffentliche Paketoberflächen für zustandsgebundenes Resume und
Work-Item-Klassifikation. Normative Regeln bleiben im Bundle; README und technische Referenzen
erklären und projizieren diesen Stand.

## Warum Agent Governance?

Agent-Harnesses unterscheiden sich in ihren globalen Einstiegspunkten. Agent Governance hält
Mutation und fachliche Zielentscheidung deshalb bei expliziten Pfaden und bewusster Bestätigung;
passive Discovery unterstützt nur die Auswahl.

- Konsistente Regeln und weniger Konfigurationsdrift über mehrere Harnesses hinweg
- Nachvollziehbare, verifizierbare und reversible Installation
- Keine stillen Harness-Mutationen oder impliziten Zielpfade
- Zustandsgebundenes Resume und kanonische Work-Item-Klassifikation
- Deklarative SSOT-Domains, Template-Registry und Governance-Modulrouting

## Schnellstart

Installiere das Paket und starte den interaktiven, geführten Einstieg:

```sh
npm i @tomtastisch/agent-governance
npx agent-governance init
```

Der Wizard nutzt passive, nicht mutierende Discovery zur Auswahlunterstützung; sie ist keine
automatische Zielannahme, keine implizite Harness-Mutation und keine fachliche Authority; nach
bewusster Auswahl ermittelt `init` Status und Plan für die expliziten Ziele, und erst nach
gemeinsamer Bestätigung installiert oder aktualisiert es diese und verifiziert das Ergebnis.
Für Advanced-Automation, CI und manuelle Diagnose erklären die
[CLI-Referenz](https://github.com/tomtastisch/agent-governance/blob/main/docs/installer-cli-reference.md)
und [Harness-Rezepte](https://github.com/tomtastisch/agent-governance/blob/main/docs/harness-recipes.md)
den expliziten Pfadvertrag.

## Wie funktioniert es?

Der Installer prüft ein geschlossenes, versioniertes Bundle, sichert den bestehenden Einstieg und
verwaltet genau seinen eigenen Markdownblock. Der Export `resume-toon` projiziert den Vertrag des
[Resume-Moduls](https://github.com/tomtastisch/agent-governance/blob/main/bundle/agent-governance/modules/resume.md);
`work-items` projiziert die SSOT-Domain `work_items`. Template-Registry und
Governance-Modulrouting sind getrennte, manifestgebundene Oberflächen.

### Öffentliche Oberfläche

- CLI: `agent-governance`
- Paketexport: `@tomtastisch/agent-governance/resume-toon`
- Paketexport: `@tomtastisch/agent-governance/work-items`
- SSOT-Domains: `routing`, `commands`, `discovery`, `work_items`
- Template-Registry: [`templates/manifest.toml`](https://github.com/tomtastisch/agent-governance/blob/main/bundle/agent-governance/templates/manifest.toml)
- Governance-Modulrouting: [`manifest.toml`](https://github.com/tomtastisch/agent-governance/blob/main/bundle/agent-governance/manifest.toml)

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
