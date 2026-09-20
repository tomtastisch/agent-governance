# ADR 0005 — Kanonische Work-Item-Klassifikation und getrennte GitHub-Labelprojektion

> **Historische Evidenz - nicht normativ.** Diese Architekturbegründung wird vom aktuellen
> Governance-Bundle nicht geladen. Sie dokumentiert Entscheidungen und ist keine ausführbare
> Anleitung.

- Status: angenommen
- Datum: 2026-09-20

## Kontext

Work Items wurden bisher über frei gewählte GitHub-Labels und Titelpräfixe (z. B. `[FUTURE]`,
`[CLI]`) eingeordnet. Dadurch entstehen mehrere Wahrheiten: Titel, Label, Template, CLI und
interne Logik können dieselbe Bedeutung unterschiedlich schreiben. GitHub-spezifische Namen
drohen zur Fachlogik zu werden, und statische Klassifikation vermischt sich mit dynamischem
Lifecycle (`in-progress`, `superseded`).

## Entscheidung

Es existiert genau eine kanonische, statische Work-Item-Klassifikations-SSOT:

```text
Work-Item-Semantik
        ↓
kanonische Klassifikations-SSOT   (bundle/agent-governance/ssot/work-items/classifications.toml)
        ↓
plattformbezogene Projektion      (bundle/agent-governance/ssot/work-items/projections/github-labels.toml)
        ↓
GitHub Labels / optionale Titelmarker
```

```text
Classification != GitHub Label
GitHub Label   = Projection(Classification)
```

Die SSOT ist als vierte Domain (`work_items`) im gemeinsamen SSOT-Index
`ssot/manifest.toml` registriert (Katalog-IDs `classifications` und `github_labels`).

### Stabile IDs

Stabile kanonische IDs sind `dimension.value`, z. B. `type.refactor`, `area.cli`,
`horizon.future`, `semver.patch`. Im geschlossenen TOML-Parser sind Punkte in Schlüsseln nicht
zulässig (siehe ADR 0004); die ID wird deshalb strukturell aus `[classifications.<dimension>]`
und dem Wert-Schlüssel abgeleitet. Die GitHub-Anzeigenamen (`semver:patch`) sind Projektion und
ändern die kanonische ID nicht.

### Dimensionen und Cardinality

| Dimension | Cardinality | Werte (real genutzte) |
|---|---|---|
| `type` | `one` | feature, fix, refactor, hardening, workflow, documentation, testing, maintenance |
| `area` | `many` | cli, installer, runtime, workflow, github, enforcement, templates, ssot, tools, docs, ux, quality |
| `horizon` | `at_most_one` | current, future |
| `semver` | `at_most_one` | major, minor, patch, none, pending |

Nur tatsächlich verwendete Werte sind aufgenommen (keine Taxonomie auf Vorrat). Die Werte sind
aus dem realen Label- und Titelmarker-Bestand belegt.

### Managed vs. Unmanaged

Jede deklarierte GitHub-Projektion ist managed: Agent Governance besitzt den Projektionsvertrag
und darf bei einer später autorisierten Mutation Existenz, Name, Beschreibung und Farbe gegen die
SSOT prüfen. Unmanaged ist eine Klassifikation des read-only GitHub-Inventars, kein deklariertes
Feld. Bestehende Fremdlabel (GitHub-Defaults, Lifecycle-Labels) werden gelesen und als
`UNMANAGED` gemeldet, nie still übernommen oder verändert.

### Read-only Projection-Plan

Ein deterministischer Plan klassifiziert das Inventar ohne Mutation mit den Aktionen `NOOP`,
`CREATE`, `UPDATE`, `CONFLICT`, `UNMANAGED` und `CANDIDATE` (Alias-/Legacy-Zuordnung). N04 selbst
führt keine GitHub-Schreibwirkung aus.

### Titelmarker

Titelmarker sind eine zusätzliche Projektion, niemals Authority. Formalisiert ist ausschließlich
der real weiterhin genutzte, eindeutig ableitbare Horizontmarker `[FUTURE]`. Ein read-only
Diagnoseparser erkennt weitere Legacy-Marker, ohne daraus eine zweite fachliche Wahrheit zu
erzeugen. Widersprüchliche Projektionen (Titel vs. Label) werden als Drift gemeldet.

### Policy-Tags bleiben getrennt

Die bestehende `policy_tags`-Domain (`read`, `write`) klassifiziert Tool-/Effektfähigkeiten und
bleibt semantisch unverändert getrennt. Sie wird weder wiederverwendet noch umgedeutet.

## Folgen

- Genau eine Work-Item-Classification-SSOT; GitHub-Labelname ist nie fachliche Identität.
- Fail-closed Validierung in TypeScript (`src/work-items.ts`) und Python
  (`tests/support/catalog_validator.py`): Duplikate, unbekannte Dimensionen, unbekannte
  Klassifikations-IDs, Projektionkollisionen und Ownership-Konflikte.
- Die neuen deklarativen Dateien liegen unter `bundle/` und sind über `package.json` `files`
  paketiert; die öffentliche Auflösung ist über den Export `@tomtastisch/agent-governance/work-items`
  zugänglich (SemVer minor).
- Kein Lifecycle-Modell, keine GitHub-Mutation, keine zweite Plattformintegration auf Vorrat.

## Verworfenen Alternativen

- Punkt-IDs als flache TOML-Schlüssel — verworfen, weil der geschlossene Parser Punkte in
  Schlüsseln ablehnt (ADR 0004).
- Titelmarker als primäre fachliche SSOT — verworfen; Titel sind Menschenoberfläche und
  Projektion.
- Eine zweite Registry parallel zum SSOT-Index — verworfen (eine kanonische Authority).
- Lifecycle-Zustände als statische Tags — verworfen; dynamische Zustände gehören in eine
  getrennte Lifecycle-Domain.
