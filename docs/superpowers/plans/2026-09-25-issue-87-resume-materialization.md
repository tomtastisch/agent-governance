# Resume-Materialisierung Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans and test-driven-development.

**Goal:** Den bestehenden #50-Vertrag während laufender Arbeit atomar materialisieren.
**Architecture:** Geschlossene Metadaten, immutable Generationen, vorhandene native
Create-/Rename-Primitiven; bestehender Resume-/TOON-Vertrag bleibt Authority.
**Tech Stack:** TypeScript, Node-Test-Runner, vorhandenes natives Dateisystemmodul.
**Spec:** `docs/superpowers/specs/2026-09-25-issue-87-resume-materialization-design.md`.

## Review Focus

SIGKILL vor/nach Veröffentlichung; konkurrierende Prozesse; stale Writer mit
geänderter Event-ID; Symlink-/Hardlink-/Schema-Manipulation; falsches COMMITTED
ohne Readback; manipuliertes TOON mit unverändertem Fingerprint.

### Task 1: Persistente Generationen und Projektionsbindung

**Files:** `src/resume-checkpoint.ts`, `src/resume-checkpoint-schema.ts`,
`tests/installer/resume-checkpoint.test.ts`, `tests/fixtures/resume/*`.
**Consumes:** `validateResumeProjection`, `encodeResumeProjection`,
`decodeResumeProjection`; vorhandene native Create-/Rename-Primitiven.
**Produces:** `ResumeCheckpointStore.open(directory)`, `read()`,
`materialize({eventId, trigger, expected, state})`, `flush()`, `toToon(expected)`,
`validateToon(text, expected)`; `expected` bindet Generation und Fingerprint.

- [x] RED: Erste Materialisierung, Schema, Trigger, Generation/CAS, Idempotenz,
  echte konkurrierende Prozesse und Abbruch an Persistenzgrenzen prüfen.
- [x] Run: `node --experimental-strip-types --test tests/installer/resume-checkpoint.test.ts`.
  Expected: fehlendes Modul/Verhalten, dann nach minimaler Implementierung alle grün.
- [x] GREEN: Geschlossene Validierung, atomare Publikation, sichere Pfade,
  readbackgebundene TOON-Projektion implementieren; vorhandene Codec-Tests laufen mit.

### Task 2: Externe Wirkungen, Workflowvertrag und Distribution

**Files:** `src/resume-checkpoint.ts`, `src/resume-checkpoint-schema.ts`,
`tests/installer/resume-checkpoint.test.ts`, `bundle/agent-governance/modules/{context,resume}.md`,
`docs/resume-checkpoints.md`, `package.json`, `CHANGELOG.md`, `release.files.sha256`,
`tests/test_resume.py`, `tests/e2e/run_package_consumers.sh`.
**Consumes:** Task 1 Store und identische Resume-State-Validierung.
**Produces:** `executeEffect`/`recoverEffect` mit PREPARED, UNKNOWN,
COMMITTED und NOT_APPLIED; Workflow verwendet Materialisierung vor Kontextverlust.

- [x] RED: Write-ahead vor Effekt, Recovery bereits/nicht ausgeführt/unklar,
  fehlende Evidence, Scope-/Dirty-Wechsel, Abbruch ohne Hook und optionaler Flush.
- [x] GREEN: Nur fehlende Semantik ergänzen und Dokumentation an reale APIs binden.
- [ ] Alle relevanten lokalen Gates aus `.github/workflows/ci.yml`, zusätzlich
  `npm run lint`, `actionlint`, Release-Manifest und Tree ausführen.
- [ ] Signierten Commit erstellen, PR erstellen, Remote-CI und unabhängige QA/SEC
  auf genau diesem Head ausführen; Findings klassifizieren und gezielt korrigieren.

## Durchführung und Evidenz

- Baseline: Node 316/316, macOS arm64; npm/GitHub Stable 1.5.2.
- Governance: Codex und OpenCode offiziell auf 1.5.2 aktualisiert; beide CURRENT,
  DIGEST_VERIFIED. Worktree vom frisch abgeglichenen origin/main.
- Pre-flight: Task 2 konsumiert exakt die Generation/Fingerprint-Bindung von Task 1.
- Ruling: Native Umsetzung in derselben Sitzung, unabhängige QA/SEC am Lieferhead;
  der vollständige Umsetzungsauftrag enthält bereits Scope und Akzeptanzvertrag.

- TDD-Nachweis: initial fehlendes Modul; danach fehlende Effect-Methoden, ungeschützte
  Operation-Bindung und widersprüchliche INCOMPLETE/REUSE-Evidence; anschließend
  Aufrufermutation und fehlende progressive Evidence-Auflösung jeweils RED→GREEN.
- Gezielter Stand: 58 Node-Tests (Checkpoint/TOON/Packaging), 24 Resume-Contracttests
  und Typecheck bestanden. Echte SIGKILL- und Concurrent-Writer-Tests enthalten.
- Ruling: unabhängige, permanente Generationen verwenden vorhandene native Create-/
  Rename-Primitiven; kein neuer Installer-Lock und keine neue Persistence-Authority.
  Stage-Artefakte bleiben ausdrücklich unpubliziert; keine automatische Bereinigung.
