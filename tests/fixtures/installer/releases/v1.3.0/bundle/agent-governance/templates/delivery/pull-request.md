# PR-Beschreibung und Reviewevidenz

- Stable ID: `delivery_pull_request`
- Kategorie: `delivery`
- Format: `markdown`
- Registry: [`templates/manifest.toml`](../manifest.toml)

## Verantwortung

Dieser Vertrag standardisiert die PR-Beschreibung samt Reviewevidenz als fortgeführte Tabelle, die
Teilaufgaben, Commits, Tests, Reviewerrollen, Provider, Reviewreferenzen, Findings und Status
nachvollziehbar bindet.

## Pflichtfelder

- `Ziel`: bounded outcome.
- `Scope`: eingeschlossener und ausgeschlossener Umfang.
- Tabelle: `Teilaufgabe`, `Commit-SHA`, `Tests`, `Reviewerrolle`, `Provider`,
  `Reviewreferenz / Head`, `Findings`, `Status`.
- `Risiken/Blocker`, `Nicht autorisiert`.

## Optionale Felder

- `Risiken/Blocker` darf `none` sein; `Nicht autorisiert` benennt eine aufgabenspezifische Grenze
  oder die Standardgrenze `merge/tag/release`.

## Form

```text
Ziel: <bounded outcome>
Scope: <included / excluded>

| Teilaufgabe | Commit-SHA | Tests | Reviewerrolle | Provider | Reviewreferenz / Head | Findings | Status |
|---|---|---|---|---|---|---|---|
| <task> | <sha> | <checks> | <role> | <provider> | <id> / <sha> | <classes> | <state> |

Risiken/Blocker: <none or precise remainder>
Nicht autorisiert: <merge/tag/release or task-specific boundary>
```

Die Tabelle wird fortgeführt, nicht durch Review-Rohtranskripte ersetzt.

## Nicht verantwortlich

- PR erzeugen, mergen oder schließen,
- Review durchführen (dies leistet die unabhängige Rolle, siehe
  [DEL-003](../../modules/delivery.md#del-003--unabhängige-prüfung)).
