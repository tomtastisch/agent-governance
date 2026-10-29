# Roadmap: Agent Governance

## Overview

Agent Governance (v1.9.4) ist ein reifes, harness-neutrales Governance-Framework für KI-Agent-Installationen. Die ersten 10 Phasen (Juli 2026 bis Oktober 2026) sind abgeschlossen und haben das kanonische Governance-Bundle, den transaktionalen explizit-Pfad-Installer, die Resume-Capability, Work-Item-Klassifikation, Cross-Language Conformance und Copilot-QA-Binding etabliert. Die aktuelle Phase konzentriert sich auf die Planungsscaffolding-Erstellung und die Vorbereitung der nächsten Entwicklungsphase auf Basis der consolidierten Intel unter `.planning/intel/`.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Geplante Meilenstein-Arbeit
- Decimal phases (2.1, 2.2): Dringende Einfügungen (markiert mit INSERTED)

Decimal phases erscheinen zwischen ihren umgebenden Integern in numerischer Ordnung.

### Abgeschlossene Phasen (v1.0 – v1.9.4)

- [x] **Phase 1: Initial Governance Model** (2026-07-25) — ADR 0001 (Branch-/PR-Tag nach Änderungstyp), ADR 0002 (Schritt-Lieferung als Sub-PR in Haupt-PR-Branch)
- [x] **Phase 2: Canonical Governance Bundle** (2026-07-30) — ADR 0003 (harness-neutrales Governance-Bundle als einzige Bootstrap-Quelle)
- [x] **Phase 3: Source Migration Analysis** (2026-07-30) — Historische Migrationsmatrix (non-normative Evidenz)
- [x] **Phase 4: Socket.dev Security Evidence** (2026-09-26) — ADR 0006 (extern, nicht-autoritativ)
- [x] **Phase 5: Templates und Work-Item-Klassifikation** (2026-09-20) — ADR 0004 (atomare Templates), ADR 0005 (Work-Item-Klassifikation + GitHub-Label-Projektion)
- [x] **Phase 6: Cross-Language Conformance** (2026-09-26) — ADR 0007 (gemeinsamer Contract-Fixture für TS- und Python-Validatoren)
- [x] **Phase 7: Installer Development** (2026-08-24 bis 2026-10-08) — Globaler explizit-Pfad-Installer, Installer Security Contract Boundary, PR #156 Runtime Security
- [x] **Phase 8: Resume Capability** (2026-08-26 bis 2026-09-26) — Resume Fast-Path, Resume-Materialisierung (#87), Resume-Candidate-Resolution (#95)
- [x] **Phase 9: SSOT Hierarchie und Copilot-QA-Binding** (2026-09-20 bis 2026-08-19) — SSOT-Hierarchie unter `bundle/agent-governance/ssot/`, Copilot-QA-Binding (DEL-008/DEL-010)
- [x] **Phase 10: Forward-Only Replacement** (2026-09-25) — Narrow `./replacement` Package-Capability

### Aktuelle Phase (in Planung)

- [ ] **Phase 11: GDS Planning Scaffold** (2026-10-29) — Erstellung von `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md` basierend auf `.planning/intel/`; Commit via `gsd-tools commit`; kein Merge, kein PR

### Geplante nächste Phasen (nach Phase 11)

- [ ] **Phase 12: INGEST-CONFLICT-B-001-Auflösung** — 32. Klassifikationsdatei lokalisieren und ingesten (BLOCKER B-001)
- [ ] **Phase 13: BLOCKER-B-002-Verifikation** — Jede pathless-Klassifikation gegen ihre zugeordnete Quelldatei verifizieren
- [ ] **Phase 14: W-003-Schema-Version-Verifikation** — `bundle/agent-governance/manifest.toml` auf `schema_version = 4` prüfen

## Phase Details

### Phase 11: GDS Planning Scaffold

**Goal**: Die vier GDS-Planungsdateien (PROJECT.md, REQUIREMENTS.md, ROADMAP.md, STATE.md) basierend auf den consolidierten Intel-Dateien unter `.planning/intel/` erstellen und via `gsd-tools commit` committen.

**Depends on**: Vollständige Lektüre aller Intel-Dateien (SYNTHESIS.md, decisions.md, requirements.md, constraints.md, context.md, INGEST-CONFLICTS.md) — abgeschlossen.

**Requirements**: Alle aus 9 SPEC-Dokumenten extrahierten Anforderungen (~168), alle 19 LOCKED ADRs, alle ~101 Constraints.

**Success Criteria** (was muss wahr sein):
1. `.planning/PROJECT.md` existiert und beschreibt Projekt, Kernwert, Anforderungen, Kontext, Constraints, Key Decisions auf Deutsch
2. `.planning/REQUIREMENTS.md` existiert und listet v1-Requirements gruppiert nach SPEC-Kategorie mit Traceability-Tabelle auf Deutsch
3. `.planning/ROADMAP.md` existiert und listet abgeschlossene Phasen 1–10 sowie aktuelle Phase 11 und geplante Phasen 12–14 auf Deutsch
4. `.planning/STATE.md` existiert und erfasst aktuellen Projektstatus, Position, akkumulierten Kontext auf Deutsch
5. Alle vier Dateien sind mit einer englischen Conventional-Commit-Message committed (kein Merge, kein PR)

**Plans**: 1 plan

Plans:
- [ ] 11-01: Vier GDS-Planungsdateien schreiben und committen

## Progress

**Execution Order:** Phasen führen in numerischer Ordnung aus: 1 → 2 → ... → 10 → 11 → 12 → ...

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Initial Governance Model | 1/1 | Complete | 2026-07-25 |
| 2. Canonical Governance Bundle | 1/1 | Complete | 2026-07-30 |
| 3. Source Migration Analysis | 1/1 | Complete | 2026-07-30 |
| 4. Socket.dev Security Evidence | 1/1 | Complete | 2026-09-26 |
| 5. Templates und Work-Item-Klassifikation | 1/1 | Complete | 2026-09-20 |
| 6. Cross-Language Conformance | 1/1 | Complete | 2026-09-26 |
| 7. Installer Development | 1/1 | Complete | 2026-10-08 |
| 8. Resume Capability | 1/1 | Complete | 2026-09-26 |
| 9. SSOT Hierarchie und Copilot-QA-Binding | 1/1 | Complete | 2026-09-20 |
| 10. Forward-Only Replacement | 1/1 | Complete | 2026-09-25 |
| 11. GDS Planning Scaffold | 0/1 | In progress | - |
| 12. INGEST-CONFLICT-B-001-Auflösung | 0/1 | Not started | - |
| 13. BLOCKER-B-002-Verifikation | 0/1 | Not started | - |
| 14. W-003-Schema-Version-Verifikation | 0/1 | Not started | - |

---\
*Letzte Aktualisierung: 2026-10-29 nach Intel-Synthese aus .planning/intel/*
