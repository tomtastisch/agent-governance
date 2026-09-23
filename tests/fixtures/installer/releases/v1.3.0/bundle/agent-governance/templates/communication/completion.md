# Abschlussaussage

- Stable ID: `communication_completion`
- Kategorie: `communication`
- Format: `markdown`
- Registry: [`templates/manifest.toml`](../manifest.toml)

## Verantwortung

Dieser Vertrag standardisiert die Abschlussaussage: Gegenstand, exakter Stand, ausgeführte Gates,
Ergebnisse, offene Risiken und autorisierte nächste Entscheidung. Die Sprache „abgeschlossen" ist
nur zulässig, wenn [EVD-004](../../modules/evidence.md#evd-004--abschlussnachweis) erfüllt ist.

## Pflichtfelder

- Gegenstand,
- Exact Head oder Artefaktidentität,
- ausgeführte Gates,
- Ergebnisse,
- offene Risiken,
- autorisierte nächste Entscheidung.

## Optionale Felder

Keine.

## Form

```text
Gegenstand: <subject>
Exact Head/Artefakt: <Exact-Head-SHA or artifact identity>
Ausgeführte Gates: <checks with result and identity>
Ergebnisse: <results>
Offene Risiken: <none or precise remainder>
Autorisierte nächste Entscheidung: <one authorized continuation>
```

Andernfalls endet die Aussage mit genau dem verbleibenden Blocker.

## Nicht verantwortlich

- Prüfungen ausführen (dies leistet die Evidenzpflicht),
- ungeprüfte Freigaben oder Veröffentlichungen behaupten.
