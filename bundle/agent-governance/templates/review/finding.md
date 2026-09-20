# Finding

- Stable ID: `review_finding`
- Kategorie: `review`
- Format: `markdown`
- Registry: [`templates/manifest.toml`](../manifest.toml)

## Verantwortung

Dieser Vertrag standardisiert die Form eines Review-Findings. Er ist generisch und wird von QA,
SEC und ARCH gemeinsam genutzt. Klassifikation und Re-Review folgen
[DEL-009](../../modules/delivery.md#del-009--finding-lifecycle).

## Pflichtfelder

- `Rolle`, `Provider`, `Exact Head`, `Finding` (ID und Klassifikation), `Ort`, `Evidenz`,
  `Auswirkung`, `Abhilfe/Begründung`, `Re-Review`.

## Optionale Felder

- `Re-Review` darf `pending` sein; `Evidenz` verweist auf Reproduktion oder autoritative Referenz.

## Form

```text
Rolle: <QA|SEC|ARCH>
Provider: <provider>
Exact Head: <Exact-Head-SHA>
Finding: <id> — <blocking-valid|nonblocking-valid|invalid|not-applicable>
Ort: <file/object/rule>
Evidenz: <reproduction or authoritative reference>
Auswirkung: <bounded consequence>
Abhilfe/Begründung: <minimal fix or technical rationale>
Re-Review: <required|not required> — <reference or pending>
```

## Nicht verantwortlich

- QA-/SEC-/ARCH-Engine betreiben,
- Findings priorisieren,
- Code automatisch ändern oder Findings selbst reparieren.
