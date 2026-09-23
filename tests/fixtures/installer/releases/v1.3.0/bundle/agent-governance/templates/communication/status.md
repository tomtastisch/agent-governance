# Antwort und Status

- Stable ID: `communication_status`
- Kategorie: `communication`
- Format: `markdown`
- Registry: [`templates/manifest.toml`](../manifest.toml)

## Verantwortung

Dieser Vertrag standardisiert eine sichtbare Arbeitsantwort: zuerst das Umgesetzte/Geprüfte, dann
Status, Evidenz und verbleibende Risiken. Bei längeren Aufgaben folgt eine kumulative
Fortschrittsliste mit höchstens einem aktiven Schritt.

## Pflichtfelder

- Was umgesetzt oder geprüft wurde,
- aktueller Status,
- Evidenz,
- verbleibende Risiken.

## Optionale Felder

- Kumulative Fortschrittsliste (nur bei längeren Aufgaben); Statuswörter bezeichnen nur den durch
  Nachweise gedeckten Scope.

## Form

Die vier Teile werden ausdrücklich benannt:

```text
Umgesetzt/Geprüft: <result>
Status: <evidence-backed status>
Evidenz: <checks/reviews with result and identity>
Verbleibende Risiken: <none or precise remainder>
```

Wenn keine bekannten Risiken verbleiben, lautet das letzte Feld `Verbleibende Risiken: keine`.

## Nicht verantwortlich

- Status von Work-Items oder Issues setzen,
- Evidenz erfinden oder ungeprüfte Erfolgsbehauptungen aufstellen.
