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

## Resume nach Implementierungscommit `8284e83`

- Git bestätigt denselben sauberen #87-Branch und Head, keine Folgecommits;
  Remote-Basis weiterhin `4e50cbffd75866deaa37b263ebe4d99442420a70`.
- Bekannten Fehler isoliert reproduziert: Der Branding-Packtest scheiterte vor
  seiner Branding-Prüfung an `missing tarball path: dist/resume-checkpoint.js`.
  Sein separates Paket-Fixture war gegenüber dem #87-Paketvertrag veraltet.
- Kleinste Korrektur: denselben Branding-Test zum bestehenden Pack-Fixture
  verschoben und das zweite manuelle Inventar entfernt. Keine neue Authority.
- RED/GREEN: `node --experimental-strip-types --test
  --test-name-pattern='^pack verifier requires exactly the terminal branding asset path$'`
  zunächst mit `tests/installer/init-branding.test.ts` FAIL, nach der Korrektur
  mit `tests/installer/pack-verifier.test.ts` PASS (1 Test).
- Evidence-Reuse: Resume-/TOON-Code, Contracttests, Package-/Exportvertrag,
  SSOT und Buildkonfiguration unverändert. Nur die beiden geänderten Testdateien
  invalidieren ihre bisherige Test-/Typecheck-Evidence. Erneuerung im ohnehin
  erforderlichen Gesamtgate, keine zusätzliche fokussierte Testsuite.
- Nächste atomare Aktion: signierten Korrekturhead sichern, vollständige lokale
  Gates auf diesem Head abschließen. SEC bleibt INCOMPLETE; QA/SEC und Remote-CI
  benötigen anschließend jeweils belegte Exact-Head-Ergebnisse. Diese werden
  an den tatsächlichen Lieferhead gebunden im PR dokumentiert.

### Follow-up der Liefergates

- `d72f5fc`: Node-/Package-/Installer-Gates PASS. Python-Gate deckte zwei weitere
  veraltete Dokumentationsannahmen auf. `df87f19` registriert die öffentliche
  Checkpoint-Referenz beim bestehenden Dokumentlink-Owner und beseitigt das
  parallele Dokumentlink-Fixture-Inventar. Gezielte drei Regressionen PASS.
- Unabhängiger SEC-Review auf `df87f19` (Referenz
  `ses_f264f1560ffeQ4COKOCKrMtIUH`) klassifiziert SEC-87-001 und SEC-87-002 jeweils
  als Medium / blocking-valid: Retry nach fehlgeschlagenem Directory-Sync und
  veränderbare Expected-Identität über asynchrone Grenzen.
- Beide Befunde im Executor mit drei Regressionen RED reproduziert, dann GREEN:
  Wiederholungen synchronisieren und lesen die exakte Generation erneut;
  Expected-Identitäten werden vor asynchronen Grenzen als eigenes Wertepaar
  erfasst, einschließlich progressiver Evidence-Callbacks. Betroffene Evidence:
  Checkpoint-Runtime, ihre Tests, Build/Package/Consumer und SEC; keine neue SSOT.
- Ein Python-Gesamtlauf auf `df87f19` scheiterte nach erfolgreichem Providerbuild
  ausschließlich beim temporären Cleanup (`Directory not empty`). Derselbe
  unveränderte Provider-Test bestand isoliert. Keine fachfremde Änderung am
  Provider vorgenommen; vollständiger Abschlusslauf bleibt erforderlich.
- Nächste Aktion: finalen Korrekturhead sichern, lokale Gesamtgates und unabhängigen
  SEC-Recheck abschließen; QA und PR-CI an denselben Lieferhead binden.
