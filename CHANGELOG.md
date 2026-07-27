# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- Dieser CHANGELOG

[0.1.0]: https://github.com/tomtastisch/agent-governance/releases/tag/v0.1.0
