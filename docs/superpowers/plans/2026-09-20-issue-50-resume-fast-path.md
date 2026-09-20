# Issue #50 — Resume Fast-Path und Evidence-Reuse (zustandsgebunden) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Einen allgemeinen, harnessneutralen, zustandsgebundenen Resume Fast-Path in die kanonische Governance integrieren, der einen unveränderten Arbeitsauftrag nach Unterbrechung fortsetzt, ohne gültige Evidence pauschal zu rekonstruieren.

**Architecture:** Die Resume-Capability ist ein reiner Governance-Vertrag: ein neuer Trigger `resume_continuation`, ein neues Modul `modules/resume.md` (Regeln `RES-001`–`RES-015`) und eine strikte `Resume-Checkpoint`-Vorlage in `templates.md`. Keine Runtime, keine Dependency, keine zweite SSOT. Der Installer bleibt unberührt (ARC-002). TOON ist ausschließlich eine deterministisch abgeleitete Transport-/Projektionsschicht.

**Tech Stack:** Markdown-Regelwerk, TOML-Kataloge (Manifest-Schema 2), Python-`unittest`-Contract-Tests.

**Spec:** GitHub Issue #50 (`tomtastisch/agent-governance`), inklusive Edit vom 19.09.2026 (Fresh-Chat-Resume, TOON-Projektion, Progressive Context Loading).

## Global Constraints

- Sprache Deutsch für normative Prosa; IDs/Bezeichner englisch.
- Keine neue Runtime-/Production-Dependency; Installer (`src/`) nicht anfassen.
- Keine parallele Resume-Engine, Checkpoint-Authority, Evidence-Authority oder Hash-Primitive.
- Manifest-Schema 2 bleibt unverändert; `routing.unknown/ambiguous = block`.
- Keine `<…>`-Platzhalter außerhalb von `templates.md` (Test `test_template_markers_have_one_normative_owner`).
- Keine operationalen Verträge (Test `test_normative_bundle_contains_no_operational_execution_contract`): keine Paketmanager-Provisionierung, kein APM-/Backup-/Deployment-Provisioning.
- Keine Home-/Host-/absoluten Pfade in normativen Dateien.
- `[Unreleased]` im CHANGELOG behält alle vier Kategorien und den `**Breaking changes:** none`-Marker.
- Verifikation: `python3 -m unittest discover -s tests -v`, `python3 tools/release_check.py tree`, `npm run typecheck`, `npm run lint`, `git diff --check`.

---

## Task 1: Resume-Trigger in den Triggerkatalog aufnehmen

**Files:**
- Modify: `bundle/agent-governance/catalogs/triggers.toml`

- [ ] **Step 1: Fehlschlagenden Test schreiben**

`tests/test_resume.py` neu anlegen (siehe Task 2). Zuerst den Test `test_resume_module_is_wired_exactly_once` schreiben, der `resume_continuation` im Katalog und exakt im `modules.resume`-Eintrag erwartet.

- [ ] **Step 2: Test ausführen und Fehlschlag bestätigen**

Run: `cd /Users/tomwerner/agent-governance-issue50 && python3 -m unittest tests.test_resume -v`
Expected: FAIL — `resume_continuation` fehlt im Katalog/Manifest.

- [ ] **Step 3: Trigger implementieren**

In `triggers.toml` am Ende hinzufügen:

```toml
[triggers.resume_continuation]
label = "Resume Continuation"
description = """
Technische, kontextuelle oder Session-Fortsetzung eines bereits begonnenen, unveränderten
Arbeitsauftrags ohne fachlichen Work-Item-Statuswechsel.
"""
```

- [ ] **Step 4: Test ausführen (schlägt weiterhin fehl, bis Manifest verdrahtet ist)**

Expected: FAIL mit Verweis auf fehlenden Manifesteintrag.

- [ ] **Step 5: Commit**

```bash
git add bundle/agent-governance/catalogs/triggers.toml
git commit -m "feat(resume): add resume_continuation trigger"
```

## Task 2: Resume-Modul mit Regeln RES-001–RES-015

**Files:**
- Create: `bundle/agent-governance/modules/resume.md`
- Modify: `bundle/agent-governance/manifest.toml`
- Test: `tests/test_resume.py`

- [ ] **Step 1: Fehlschlagenden Contract-Test schreiben**

`tests/test_resume.py` (siehe Task 3, vollständiger Inhalt) legt fest, dass `modules/resume.md` existiert, `resume_continuation` exakt dem Modul zugeordnet ist und alle Pflichtbegriffe (Resume statt Reconstruct, REUSE/RERUN/INVALIDATE, INCOMPLETE, Duplicate-Execution, Dirty-Worktree, TOON/Token-Oriented Object Notation, Progressive Context Loading, Fresh-Chat, fail-closed, getrennte Identitäten/Fingerprints, "Chat context is transport, not authority", "keine zweite Source of Truth") enthält und verbotene Inhalte (Datenbank, Daemon, Netzwerkdienst, Work-Item-Mutation, Embeddings als Identität, provider-/modellspezifische Limits) ausschließt.

- [ ] **Step 2: Test ausführen und Fehlschlag bestätigen**

Run: `python3 -m unittest tests.test_resume -v`
Expected: FAIL — `resume.md` fehlt.

- [ ] **Step 3: Modul implementieren**

`modules/resume.md` mit Regeln `RES-001`…`RES-015` schreiben (Inhalt im Plan-Anhang):

- `RES-001 — Resume-Fall und Trigger`
- `RES-002 — Trennung vom Work-Item-Lifecycle`
- `RES-003 — Deterministische Zustandsidentität und Fingerprints`
- `RES-004 — Minimaler Resume-Preflight`
- `RES-005 — Checkpoint-Auflösung und kanonische Wahrheit`
- `RES-006 — Evidence-Identität und granulare Bindung`
- `RES-007 — Evidence-Reuse und -Invalidation`
- `RES-008 — INCOMPLETE-Semantik`
- `RES-009 — Freshness-sensitive Evidence`
- `RES-010 — Duplicate-Execution Guard`
- `RES-011 — Dirty-Worktree-Identität`
- `RES-012 — Context-Compaction und Fresh-Chat-Resume`
- `RES-013 — TOON-Projektion`
- `RES-014 — Progressive Context Loading`
- `RES-015 — Nächste atomare Aktion und Fail-Closed-Fallback`

Manifest-Eintrag:

```toml
[modules.resume]
path = "modules/resume.md"
triggers = ["resume_continuation"]
dependencies = ["evidence", "delivery", "security", "invariants", "context"]
```

- [ ] **Step 4: Test ausführen und grün bestätigen**

Run: `python3 -m unittest tests.test_resume -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bundle/agent-governance/modules/resume.md bundle/agent-governance/manifest.toml tests/test_resume.py
git commit -m "feat(resume): add resume fast-path module and contract tests"
```

## Task 3: Resume-Checkpoint-Vorlage in templates.md

**Files:**
- Modify: `bundle/agent-governance/modules/templates.md`

- [ ] **Step 1: Fehlschlagenden Test schreiben**

`tests/test_resume.py::test_resume_checkpoint_is_a_strict_template` erwartet in `templates.md` eine `### Resume-Checkpoint`-Überschrift unter `## Strikte Vorlagen` und referenzierte Pflichtfelder.

- [ ] **Step 2: Test ausführen und Fehlschlag bestätigen**

Expected: FAIL — Template fehlt.

- [ ] **Step 3: Vorlage implementieren**

`### Resume-Checkpoint` unter `## Strikte Vorlagen` einfügen (Felder: Auftrag, Scope, Task-/Scope-Identität, Repository/Worktree/Branch, Exact state, Dirty state, Kanonische SSOT, Abgeschlossene Evidence, Unvollständige Evidence, Offene Findings, Nächste atomare Aktion, TOON-Projektion, Nicht übernehmen).

- [ ] **Step 4: Test ausführen und grün bestätigen**

- [ ] **Step 5: Commit**

```bash
git add bundle/agent-governance/modules/templates.md
git commit -m "feat(resume): add Resume-Checkpoint template"
```

## Task 4: CHANGELOG und Verifikation

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: CHANGELOG ergänzen**

Unter `## [Unreleased]` → `### Added` den Eintrag zum Resume Fast-Path ergänzen; `**Breaking changes:** none` bleibt.

- [ ] **Step 2: Gesamte Gates ausführen**

```bash
python3 -m unittest discover -s tests -v
python3 tools/release_check.py tree
npm run typecheck
npm run lint
git diff --check
```

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs(resume): record resume fast-path in changelog"
```

## Task 5: Unabhängige Reviews

- [ ] **Step 1:** Unabhängigen QA-Review (read-only) auf dem exakten finalen Head dispatchen; Findings nach `DEL-009` klassifizieren.
- [ ] **Step 2:** Unabhängigen SEC-Review (read-only) auf demselben Head dispatchen (security_sensitive_change wegen Persistenz-, File-State-, Fail-closed- und TOON-Validierungsgrenzen).
- [ ] **Step 3:** Valide Findings reproduzieren und testgetrieben beheben; Reviews auf neuem Head wiederholen.

---

## Selbst-Review

**Spec-Abdeckung:** Scope-Punkte → Regeln: Resume-Fall erkennen (RES-001), Auftrag deterministisch identifizieren (RES-003, RES-005), minimaler Preflight (RES-004), Checkpoint-Auflösung (RES-005), Task/Scope-Identität (RES-003), Evidence-Identität/Bindung (RES-006), Reuse/Invalidation (RES-007), INCOMPLETE (RES-008), Freshness (RES-009), Duplicate-Execution (RES-010), Context-Compaction (RES-012), Fresh-Chat (RES-012), Dirty-Worktree (RES-011), persistenter Zustand + content-addressed (RES-003, RES-005), TOON (RES-013), Progressive Loading (RES-014), nächste atomare Aktion (RES-015), fail-closed (RES-015).

**Platzhalter:** keine TBD/TODO.

**Typkonsistenz:** Regelnummern `RES-001`…`RES-015` konsistent; Trigger-ID `resume_continuation` konsistent; Testdatei `tests/test_resume.py` konsistent.
