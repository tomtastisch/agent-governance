# Phase 15: Work-Item Lifecycle (Issue #54) — Specification

**Created:** 2026-10-29
**Ambiguity score:** 0.09 (gate: ≤ 0.20)
**Requirements:** 13 locked

## Goal

Agent Governance erhält genau eine kanonische, plattformneutrale Work-Item-Lifecycle-Semantik: Zustände (work.ready, work.in_progress, work.blocked, work.completed), Ereignisse (work_started, work_blocked, work_resumed, work_completed), validierte Transitionen mit Required Evidence, Idempotenz und Ordering sowie managed in-progress Projektion — ohne GitHub-Schreibwirkung in Issue #54.

## Background

Die bestehende Work-Item-SSOT enthält statische Classification und GitHub-Label-Projektionen (z. B. `delivery_role.slice → delivery-slice`). Sie enthält noch keinen allgemeinen Lifecycle-Vertrag für `in-progress`; `buildLabelProjectionPlan` plant Labeländerungen read-only. Der bei dieser Konsolidierung geprüfte Repository-Stand ist `76536316e1e3dfec66b71c96fae4dfc2969b4e66`, Release `v1.8.0`. `work_started` wird aus Issue #55 konsumiert. `resume_continuation` ist keine Lifecycle-Transition. Materialisierung erfolgt nach Issue #57 oder #79, Planung nach Issue #56.

## Requirements

1. **Lifecycle Authority**: Genau eine Lifecycle-Authority mit klarer Trennung von Classification, Darstellung, fachlicher Entscheidung und Apply.
   - Current: Keine Lifecycle-Authority; Status wird konkurrierend aus Labels, Kommentaren, Branches, PR-Existenz oder freier Prosa abgeleitet.
   - Target: Eine zentrale Lifecycle-Authority besitzt Zustände, Ereignisse, Transitionen, Evidence und Statusprojektionen.
   - Acceptance: Nachweisbar, dass genau eine Lifecycle-Authority existiert und Classification/Darstellung/Entscheidung/Apply getrennt sind.

2. **work_started Transition**: Tatsächlicher autorisierter Bearbeitungsbeginn nach Current-State Resolution, eindeutiger Identität, bestätigtem Scope und erfüllten Startvoraussetzungen; regulär `work.ready → work.in_progress`.
   - Current: Keine work_started-Transition definiert; Status wird willkürlich gesetzt.
   - Target: `work_started` Event mit eindeutiger Work-Item-Identität, erwartetem Ausgangsstand, Evidence-Referenzen und Ereignisidentität; Transition nur von `work.ready` nach `work.in_progress`.
   - Acceptance: Ein validierter `work_started` mit allen Preconditions führt zu `work.in_progress`; ohne Preconditions wird die Transition abgelehnt.

3. **work_blocked Transition**: Konkreter fachlicher Blocker mit betroffenem Scope, Ursache, Evidence und notwendiger Auflösung; regulär `work.in_progress → work.blocked`.
   - Current: Keine Blockierungs-Transition definiert.
   - Target: `work_blocked` Event dokumentiert Blocker mit Scope, Ursache, Evidence und Auflösung; Transition nur von `work.in_progress` nach `work.blocked`.
   - Acceptance: Ein validierter `work_blocked` mit vollständigem Blocker-Contract führt zu `work.blocked`.

4. **work_resumed Transition**: Nur aus fachlicher Blockierung mit belegter Blockerauflösung; regulär `work.blocked → work.in_progress`.
   - Current: Keine Resume-Transition definiert; technischer Session-Resume wird fälschlich als fachlicher Resume behandelt.
   - Target: `work_resumed` Event nur zulässig aus `work.blocked` mit belegter Auflösung; führt zu `work.in_progress`.
   - Acceptance: `work_resumed` aus `work.blocked` mit Auflösung-Evidence führt zu `work.in_progress`; ohne Auflösung wird abgelehnt.

5. **work_completed Transition**: Fachliches Outcome und Akzeptanzkriterien erfüllt, relevante Tests und erforderliche Reviews bestanden, keine offenen `blocking-valid` Findings und alle für die gelieferte Arbeit zwingenden Wirkungen verifiziert; regulär `work.in_progress → work.completed`.
   - Current: Keine Completion-Transition definiert; Issue-Closure oder Merge werden fälschlich als Completion behandelt.
   - Target: `work_completed` Event nur nach erfülltem Outcome, Tests, Reviews, keine offenen blocking-valid Findings; Transition nur von `work.in_progress` nach `work.completed`.
   - Acceptance: Ein validierter `work_completed` mit allen Preconditions führt zu `work.completed`; Issue-Closure allein führt nicht zu Completion.

6. **No false starts**: Materialisierung, Planung, PR-Existenz und technischer Resume lösen keinen `work_started` aus.
   - Current: Bisherige Praxis setzt Status bei Issue-Anlage, PR-Erstellung oder technischem Resume.
   - Target: Nur tatsächlicher, autorisierter Bearbeitungsbeginn nach Current-State Resolution erzeugt `work_started`.
   - Acceptance: Materialisierung, Planung, PR-Erstellung und technischer Resume erzeugen kein `work_started` und keine `in-progress`-Projektion.

7. **Managed `in-progress`-Projektion**: Ein gültiger `work_started` erzeugt deterministisch die Sollzuordnung des managed Labels `in-progress` zum gestarteten Work Item; `work_completed` erzeugt die Entfernung von `in-progress` am selben Work Item.
   - Current: Keine deterministische Projektion von Lifecycle-Zuständen auf Labels.
   - Target: Validierter Start → managed Label-Zuordnung `in-progress`; validierte Completion → Label-Entfernung; Apply über Issue #79 Vertrag, Read-back, Teilfehler separat ausgewiesen.
   - Acceptance: Start projiziert `in-progress`; Completion plant Entfernung und koordiniert autorisierten Abschluss ohne zirkuläre Preconditions.

8. **Slice isolation**: Ein Delivery-Slice besitzt seinen eigenen Lifecycle; ein aktiver Child startet den Parent nicht; Parent erhält das Label nur bei eigener aktiver Arbeit.
   - Current: Keine Slice/Parent-Lifecycle-Trennung definiert.
   - Target: Slice-Start verändert keinen Parent-Lifecycle; eigene Parent-Arbeit ist separat nachgewiesen.
   - Acceptance: Slice-Start ändert nicht den Parent-Lifecycle-Status.

9. **No false completion**: Administrative Closure, Merge allein und fehlende Completion-Evidence liefern keinen fachlichen Abschluss.
   - Current: Geschlossenes Issue oder gemergter PR wird fälschlich als fachlicher Abschluss behandelt.
   - Target: `closed != completed`; manuelle oder administrative Closure erzeugt kein `work_completed`.
   - Acceptance: Administrative Closure, Merge allein und fehlende Completion-Evidence führen nicht zu `work.completed`.

10. **Idempotency and ordering**: Identische relevante Eingaben ergeben identische fachliche Entscheidungen; ungültige Transitionen werden abgewiesen; identische bereits angewandte Events sind idempotent; erwarteter Ausgangsstand und Ereignisreihenfolge verhindern Lost Updates und Rücksetzungen.
    - Current: Keine Idempotenz- oder Ordering-Garantien definiert.
    - Target: Transition Decision enthält Work Item, Event, Ausgangs-/Zielzustand, Entscheidung, vorhandene/fehlende Evidence, Grund und Projection Plan; fail-closed bei Stale/Drift; konkurrierende kanonische Authorities scheitern fail-closed.
    - Acceptance: Wiederholung, verspätete Events, stale Ausgangsstände und konkurrierende Änderungen sind abgesichert; identische bereits angewandte Events sind idempotent.

11. **Label from Projection-SSOT**: Labeldefinition, Beschreibung, Farbe und Aliasse der GitHub-Darstellung stammen ausschließlich aus der bestehenden Projection-SSOT; fehlende Definitionen, Kollisionen und unmanaged Bestand bleiben geschützt.
    - Current: Keine klare Zuordnung von Labeldefinitionen zur Projection-SSOT.
    - Target: Lifecycle-Semantik bleibt in #54; Name, Beschreibung, Farbe und Aliasse gehören ausschließlich in die Projection-SSOT.
    - Acceptance: Keine zweite Farbtabelle, kein hardcodiertes Ersatzlabel, keine stillschweigende Schema-Erweiterung durch Consumer.

12. **No implicit tools/auth**: Fehlende Tools/GitHub blockieren nur abhängige Gates; keine automatische Toolinstallation oder Authentifizierung; keine positive Wirkungsbehauptung ohne Read-back.
    - Current: Keine klare Regel für fehlende Tools/GitHub im Lifecycle.
    - Target: GitHub ist keine allgemeine Voraussetzung für die Lifecycle-Semantik; fehlendes GitHub, Pflichttool, Recht oder Authentifizierung blockiert ausschließlich die davon abhängige Wirkung bzw. das Gate.
    - Acceptance: Fehlende Tools/GitHub blockieren nur abhängige Gates; keine Installation oder Authentifizierung erfolgt implizit.

13. **Decision-only tests**: Decision-only-Tests belegen null GitHub-Schreibaufrufe; Consumer-Integration prüft Start-/Completion-Projektion, fehlende Autorisierung, Partial Apply und Read-back.
    - Current: Keine Decision-only-Testvorgabe definiert.
    - Target: Tests validieren Lifecycle-Entscheidungen ohne externe Schreibwirkungen.
    - Acceptance: Decision-only-Tests führen null GitHub-Schreibaufrufe aus; Consumer-Integration validiert Projektion, Autorisierung, Partial Apply und Read-back.

## Boundaries

**In scope:**
- Zustände: `work.ready`, `work.in_progress`, `work.blocked`, `work.completed`
- Ereignisse: `work_started`, `work_blocked`, `work_resumed`, `work_completed`
- Transition-Verträge mit Event, zulässigen Ausgangszuständen, Zielzustand, Preconditions, Required Evidence, Autorisierungsanforderung, Idempotenz und Projektionswirkungen
- Evidence-Anforderungen pro Transition
- Idempotenz und Ordering für Events
- Managed `in-progress`-Projektionssemantik
- Consumer-Integration über Issue #79 Apply-Vertrag
- Entscheidungen, Tests und Dokumentation für den Lifecycle-Kontrakt

**Out of scope:**
- Eigene GitHub-Apply-Implementierung — gehört zu Issue #79
- Statische Taxonomie / neue Classification-Werte für dynamische Zustände
- Neue Template-Registry
- PR-Erstellung oder Merge
- Slice-Planung, -Materialisierung oder -Aggregation — gehört zu Issue #58
- Technische Resume-Engine
- Management-CLI
- Rulesets
- Automatische Installation von Tools oder Authentifizierung

## Constraints

- `Lifecycle State != GitHub Label` — ein hiervon abweichender kanonischer Zustand darf nicht still denselben positiven Status behalten.
- `Lifecycle Event != Chatphrase` — Freitext liefert höchstens einen zu validierenden Intent.
- `Transition Decision != externe Schreibfreigabe` — Entscheidungen sind unabhängig von externen Schreibwirkungen.
- `work_started` wird aus Issue #55 konsumiert.
- `resume_continuation` ist keine Lifecycle-Transition.
- Materialisierung nach Issue #57 oder #79.
- Planung nach Issue #56.
- `closed != completed` — administrative Closure erzeugt kein `work_completed`.
- Keine GitHub-Schreibwirkung in Issue #54.
- GitHub ist keine allgemeine Voraussetzung für die Lifecycle-Semantik.

## Acceptance Criteria

- [ ] Genau eine Lifecycle-Authority existiert mit Trennung von Classification, Darstellung, fachlicher Entscheidung und Apply.
- [ ] `work_started` hat validierte positive und negative Transitiontests samt Required Evidence.
- [ ] `work_blocked` hat validierte positive und negative Transitiontests samt Required Evidence.
- [ ] `work_resumed` hat validierte positive und negative Transitiontests samt Required Evidence.
- [ ] `work_completed` hat validierte positive und negative Transitiontests samt Required Evidence.
- [ ] Materialisierung, Planung, PR-Existenz und technischer Resume lösen keinen `work_started` aus.
- [ ] Start projiziert `in-progress`; Completion plant Entfernung und koordiniert autorisierten Abschluss ohne zirkuläre Preconditions.
- [ ] Slice-Start verändert keinen Parent-Lifecycle; eigene Parent-Arbeit ist separat nachgewiesen.
- [ ] Administrative Closure, Merge allein und fehlende Completion-Evidence liefern keinen fachlichen Abschluss.
- [ ] Wiederholung, verspätete Events, stale Ausgangsstände und konkurrierende Änderungen sind abgesichert.
- [ ] Labeldefinition und Farben stammen nur aus der Projection-SSOT; fehlende Definitionen, Kollisionen und unmanaged Bestand bleiben geschützt.
- [ ] Fehlende Tools/GitHub blockieren nur abhängige Gates; keine Installation oder Authentifizierung erfolgt implizit.
- [ ] Decision-only-Tests belegen null GitHub-Schreibaufrufe.

## Edge Coverage

**Coverage:** 4/4 applicable edges resolved · 0 unresolved

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| Stale Transition / Lost Updates | R10 | ✅ covered | Acceptance Criterion 10: fail-closed bei Stale/Drift; erwarteter Ausgangsstand und Ereignisreihenfolge verhindern Lost Updates |
| Concurrent authorities | R10 | ✅ covered | Acceptance Criterion 10: konkurrierende kanonische Authorities scheitern fail-closed |
| Idempotent events | R10 | ✅ covered | Acceptance Criterion 10: identische bereits angewandte Events sind idempotent |
| Late events | R10 | ✅ covered | Acceptance Criterion 10: verspätete Events sind abgesichert |

## Prohibitions (must-NOT)

**Coverage:** 3/3 applicable prohibitions resolved · 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| MUST NOT perform GitHub writes in decision-only tests | R13 | resolved / test | Decision-only-Tests belegen null GitHub-Schreibaufrufe |
| MUST NOT treat administrative Closure as completion | R9 | resolved / test | `closed != completed`; administrative Closure erzeugt kein `work_completed` |
| MUST NOT start work from materialization, planning, PR-existence or technical resume | R6 | resolved / test | Diese Aktionen erzeugen kein `work_started` und keine `in-progress`-Projektion |

## Ambiguity Report

| Dimension | Score | Min | Status | Notes |
|-----------|-------|-----|--------|-------|
| Goal Clarity | 0.95 | 0.75 | ✓ | Issue #54 definiert Ziel präzise und messbar |
| Boundary Clarity | 0.90 | 0.70 | ✓ | Explizite In- und Out-of-Scope-Listen |
| Constraint Clarity | 0.85 | 0.65 | ✓ | Klare Regeln (State != Label, Event != Chatphrase, etc.) |
| Acceptance Criteria | 0.90 | 0.70 | ✓ | 13 Pass/Fail-Checkboxen |
| **Ambiguity** | **0.09** | ≤0.20 | ✓ | Gate passed |

Status: ✓ = met minimum, ⚠ = below minimum (planner treats as assumption)

## Interview Log

| Round | Perspective | Question summary | Decision locked |
|-------|-------------|-----------------|-----------------|
| 1–6 | auto-selected | Auto-mode: keine interaktiven Fragen; alle Entscheidungen aus Issue #54, Governance 1.9.4 und Intel-Dateien abgeleitet. | SPEC.md mit 13 Requirements, 13 Acceptance Criteria, 4 Edge Coverage, 3 Prohibitions geschrieben. Ambiguity 0.09 ≤ 0.20. |

---

*Phase: 15-work-item-lifecycle-issue-54*
*Spec created: 2026-10-29*
*Next step: /gsd-discuss-phase 15 — implementation decisions (how to build what's specified above)*
