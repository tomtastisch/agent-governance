# Agent Governance

## Was dies ist

Agent Governance (v1.9.4) ist ein harness-neutrales Governance-Framework für KI-Agent-Installationen. Es stellt ein kanonisches Governance-Bundle (`bundle/`) als einzige Bootstrap-Quelle bereit, zusammen mit TypeScript-Validatoren, Python-Test-Referenzen, einem transaktionalen expliziten-Pfad-Installer und Dokumentation. Das Projekt existiert als Node.js/npm-Paket `@tomtastisch/agent-governance` mit 19 LOCKED ADR-Entscheidungen, 9 SPEC-Dokumenten (~168 Anforderungen) und ~101 Constraints. Alle Intel-Quellen liegen unter `.planning/intel/` (31 Klassifikationsdateien, 26+ Quelldokumente).

## Kernwert

Ein einzelnes, unveränderliches, harness-agnostisches Governance-Bundle als einzige Bootstrap-Quelle für KI-Agent-Installationen — fail-closed, SSOT-konform und ohne Harness-spezifische Adapter.

## Anforderungen

### Validiert

Alle 19 ADR-Entscheidungen sind LOCKED (adoptiert/angenommen/angenommen). Die folgenden SPEC-Bereiche sind vollständig spezifiziert:

- Dokumentationsarchitektur (Issue #39): 34 Anforderungen
- Copilot-QA-Binding: 22 Anforderungen
- Globaler explizit-Pfad-Installer: 24 Anforderungen
- Init-Onboarding (Issue #44): 33 Anforderungen
- Forward-only Replacement (#123): 16 Anforderungen
- Resume-Materialisierung (#87): 16 Anforderungen
- Cross-Language Conformance (#90): 14 Anforderungen
- Resume-Candidate-Resolution (#95): 12 Anforderungen

### Aktiv

(Keine — alle SPEC-Anforderungen sind spezifiziert; nächste Phase folgt aus ROADMAP.md)

### Out of Scope

- Harness-CLI-Ausführung und neue Support-/Binding-Authority (CON-SEC-001)
- Eigener Materializer, Generator oder Synchronisations-Engine (CON-DEP-003)
- Socket.dev als Runtime-Dependency oder Release-Authority (CON-DEP-002)
- Privilegierter Broker, Daemon, root-Helfer oder setuid-Binary (CON-PLT-004)

## Kontext

- Technische Umgebung: Node.js >=24, TypeScript 7.0.2 (NodeNext ESM), Python 3.11+
- Repository: /Users/tomtastisch/Projects/github/agent-governance (brownfield, v1.9.4)
- Vorherige Arbeit: 10 Phasen von Juli 2026 bis Oktober 2026 (siehe ROADMAP.md)
- Bekannte Probleme: INGEST-CONFLICTS.md dokumentiert 2 BLOCKER (gemildert/dokumentiert), 6 WARNINGS (auto-resolved), 8 INFO

## Constraints

- **[Node.js]**: >=24 erforderlich — Installer und CLI laufen auf Node 24
- **[TypeScript]**: 7.0.2, strict Mode, NodeNext ESM — kein experimental-strip-types für Production-Build
- **[Dependencies]**: Keine third-party Runtime-Dependencies für den Installer-CLI; `@clack/prompts` nur für `init`; `@toon-format/toon` 4.1.1 einzige erlaubte neue Production-Dependency (Resume Fast-Path)
- **[Python]**: 3.11+ für Test-Referenz (`tomllib`, `unittest`)
- **[Security]**: Fail-closed Validierung überall; Socket.dev nicht-autoritativ; keine Secrets in Outputs
- **[Pfade]**: Explicit-over-implicit — kein cwd-Fallback, keine automatische Erkennung, alle Ziele explizit

## Key Decisions

| Entscheidung | Begründung | Ausgang |
|--------------|------------|---------|
| ADR 0001: Branch-/PR-Tag nach Änderungstyp statt Agenten-Präfix | Identität ist redundant (Commit-Metadaten); fachliche Art ist relevanter | ✓ Good |
| ADR 0003: Kanonisches, harness-neutrales Governance-Bundle | Vermeidung von Drift und widersprüchlichen Quellen | ✓ Good |
| ADR 0004: Atomare Governance-Templates mit kanonischer Registry | Drift und erschwerte Tests in Sammelmodul vermeiden | ✓ Good |
| ADR 0005: Kanonische Work-Item-Klassifikation | Eine einzige Wahrheit statt mehrerer (Titel, Label, Template) | ✓ Good |
| ADR 0006: Socket.dev als externe, nicht-autoritative Security-Evidence | Supply-Chain-Prüfung ohne Release-Authority | ✓ Good |
| ADR 0007: Cross-Language-Conformance-Vertrag | Drift zwischen TS- und Python-Validatoren vermeiden | ✓ Good |

---\
*Letzte Aktualisierung: 2026-10-29 nach Intel-Synthese aus .planning/intel/*
