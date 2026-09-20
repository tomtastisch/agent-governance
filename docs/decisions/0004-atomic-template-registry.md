# ADR 0004 — Atomare Governance-Templates mit kanonischer Registry

> **Historische Evidenz - nicht normativ.** Diese Architekturbegründung wird vom aktuellen
> Governance-Bundle nicht geladen. Sie dokumentiert Entscheidungen und ist keine ausführbare
> Anleitung.

- Status: angenommen
- Datum: 2026-09-20

## Kontext

Wiederverwendbare Form- und Interaktionsverträge wurden bislang gemeinsam im Sammelmodul
`bundle/agent-governance/modules/templates.md` gepflegt. Mit zunehmendem Funktionsumfang entstehen
dadurch Drift, erschwerte unabhängige Tests, unsichtbare Lücken und das Risiko paralleler
Fachvorlagen.

## Entscheidung

Jeder eigenständige, wiederverwendbare generische Formvertrag erhält genau eine atomare
Template-Datei unter `bundle/agent-governance/templates/` und genau einen Eintrag in der
kanonischen Registry `templates/manifest.toml` (schema_version 1). Das Root-Manifest
(schema_version 4) referenziert die Registry über `templates = "templates/manifest.toml"`.

```text
ein wiederverwendbarer Formvertrag
        ↓
eine atomare Template-Datei
        ↓
eine kanonische Registry
        ↓
beliebig viele kontrollierte Konsumenten
```

Die Registry erfasst je Template: stabile Template-ID (TOML-Schlüssel), relativen Pfad, semantische
Kategorie und Format. Sie beschreibt keine Fachsemantik, die bereits im Template oder dessen
Ownerdomain definiert ist.

### Kategorien (logisches Ownership-Modell)

`git`, `delivery`, `review`, `context`, `communication`, `external_effects`.

### Stabile Template-IDs

Die IDs folgen der vorhandenen Repository-Konvention `[a-z][a-z0-9_]*` (Module-, Trigger- und
Tool-IDs). Die in Issue #52 genannten Punkt-IDs (`git.commit` usw.) werden zu `git_commit`,
`delivery_push_pr_checkpoint` usw. normalisiert; im geschlossenen TOML-Parser sind Punkte in
Schlüsseln nicht zulässig. Es gibt keine parallelen Alias-IDs.

### Gap-Analyse

Zwei reale generische Lücken wurden ergänzt:

1. `delivery_release_checkpoint` — standardisiert die Release-Nachweisform (Exact Head, Version,
   Tag, Artefaktidentität, Prüf-/Publizierzustand, autorisierte nächste Aktion), implementiert
   aber keine Releaseengine.
2. `external_effects_approval_checkpoint` — dokumentiert die Form einer bestehenden oder
   einzuholenden Freigabe für externe Wirkungen, erzeugt aber keine Autorisierung.

### Resume-Entscheidung

Kein generisches `context/resume.md`. Die Resume-Checkpoint-Form ist domain-spezifisch
(Owner: Resume-Capability, `RES-005`) und unterscheidet sich von `context/handoff` durch
bindungsbasierte Pflichtfelder (Task-/Scope-Identität, Dirty-State, Evidence-Bindungsmatrix
`REUSE`/`RERUN`/`INVALIDATE`/`INCOMPLETE`, TOON-Projektion). Eine Erweiterung von `handoff` würde
dessen generische Semantik verschlechtern. Die Form verbleibt im Resume-Modul
(`modules/resume.md`) und ist nicht Teil der generischen Registry.

## Folgen

- Das Modul `modules/templates.md` ist eine rein erklärende Übersicht (Regel `TPL-001` bleibt).
- Registry-, Pfad-, Traversal- und Symlinkgrenzen werden fail-closed validiert (TypeScript
  `src/templates-catalog.ts`, Python `tests/support/catalog_validator.py`).
- Konsumenten lösen Templates über stabile IDs auf, nicht über Dateipfade.
- Keine Template-DSL, keine Vererbung, keine leeren Zukunftsdomains (YAGNI).

## Verworfenen Alternativen

- Templates als vierte SSOT-Domain — verworfen, weil der SSOT-Index ausschließlich TOML-Kataloge
  registriert und Markdown-Formverträge ein eigenes Format und eine eigene Registry erfordern.
- Eine zweite Registry parallel zum Root-Manifest — verworfen (eine kanonische Authority).
- Drei rollenspezifische Finding-Dateien (`qa-`, `sec-`, `arch-finding.md`) — verworfen, da
  `review_finding` die Semantik generisch abdeckt.
