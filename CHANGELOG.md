# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Triggerbasiertes Tool-Routing mit Microsoft APM als Standard für deklarative Agent-Skill- und
  Agent-Paket-Evidenz.
- Exact-Head-Verträge für unabhängige QA- und risikobasierte Security-Prüfungen.
- Zentrale strikte Templates für driftanfällige Delivery-, Review- und Kontextübergaben.
- Sitzungsledger- und Checkpoint-Regeln für nachvollziehbare lange Aufgaben.
- Regressionstests für Scope, SSOT, Manifest, Tool-Routing, Review, Templates, Kontext und
  hostunabhängige Git-Fixtures.

### Changed

- Governance ist auf Regeln, Rollen, Templates, Source-of-Truth-Verträge, Tool-Routing und
  Verifikation begrenzt.
- Die kanonische Einstiegskette führt ausschließlich vom Bootstrap über das statische Manifest
  zu triggergerecht geladenen Modulen und Rollen.
- Reviewerrollen und Reviewprovider sind getrennt; GitHub Copilot ist ein bevorzugter
  QA-Provider mit unabhängigem Fallback.
- APM- und andere Toolregeln beschreiben fachliche Trigger und Evidenzgrenzen, jedoch weder
  Installations- noch Verfügbarkeitszustände.

### Fixed

- Git-Test-Fixtures verwenden deterministisch `main`, repository-lokale Identität und geprüfte
  Rückgabecodes ohne globale Git-Konfiguration.

### Removed

- Alte Harness-Adapter, Bootstrap-Templates, Rollenwrapper, Core-/Rollenquellen, Branch-Tags und
  die Profilvorlage als konkurrierende Governance-Autorität.
- **BREAKING:** Operative Projekt-, Werkzeug-, Provider- und Runtimeverträge sowie Verweise auf
  entfernte Legacy-Quellen gehören nicht mehr zum öffentlichen Governance-Vertrag.

**Breaking changes:** present

## [0.1.0] — 2026-07-27

### Added

- Harness-agnostisches Kernregelwerk (`core/core.md`) mit 20 Abschnitten:
  Rolle, Kommunikation, Goldene Regeln, Evidenz & Hypothesen, Arbeitsweise,
  Rollen & Routing, Blocker-Protokoll, Abschlussformat, Architektur/SSOT,
  Code-Standards, Tests, Dokumentation & Versionierung, CI-Pipeline,
  Definition of Done, Branch-/Commit-/PR-Disziplin, Review- & Merge-Gate,
  Sicherheit & Instruktionsgrenze, Issue-Dokumentationspflicht, Werkzeuge &
  Manifest, Selbstprüfung
- Hexagonale Architektur: Kern — Ports (`[BINDING:*]`/`[PROFILE:*]`) — Adapter
  — genau eine Verdrahtungsstelle je Harness
- Claude-Code-Adapter mit Subagenten-Routing (AK/ST/QA/SEC)
- Codex-Adapter mit separatem Rollenkontext
- Rollenerweiterungen `core/roles/{ak,st,qa,sec}.md`
- Branch-/PR-Tag-Schema (`core/branch-tags.toml`): geschlossene Tag-Liste nach
  Conventional-Commit-Typen, SSOT für Branch, PR-Titel und Commit-Präfix
- Werkzeug-Katalog (`tools/tools.md`) mit Freigabe-Ebenen und
  deterministischer CLI-Installation (`tools/Brewfile`)
- CI-Pipeline (`.github/workflows/ci.yml`): blockierende Konsistenz-/
  Drift-Tests, advisory Link-Check
- Konsistenz-Testsuite (`tests/test_governance.py`): Port-Vertrag, Profil,
  Referenzen, Rollen, Pfadfreiheit, Katalog, Templates, Branch-Tags
- ADRs für strukturelle Entscheidungen (`docs/decisions/`)
- Kopierfertige Verdrahtungs-Templates (`templates/`)
- Gehärteter Installations-Prompt (`INSTALL.md`)
- Profilvorlage (`profile/profile.example.md`)
- Autoritative SemVer-Quelle (`VERSION`)
- Deterministische Release-Metadaten-Validierung (`tools/release_check.py`)
- Dieser CHANGELOG

### Changed

- Keine.

### Fixed

- Keine.

### Removed

- Keine.

**Breaking changes:** none
