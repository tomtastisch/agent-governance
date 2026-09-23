# Toolfehler und Blocker

- Stable ID: `communication_tool_error_blocker`
- Kategorie: `communication`
- Format: `markdown`
- Registry: [`templates/manifest.toml`](../manifest.toml)

## Verantwortung

Dieser Vertrag standardisiert die Meldung eines Toolfehlers oder Blockers, damit Ursache,
Auswirkung und kleinste notwendige Entscheidung reproduzierbar bleiben. Ein Toolfehler blockiert
nicht automatisch unabhängige Arbeit und wird nie als positiver Nachweis umgedeutet.

## Pflichtfelder

- betroffener Schritt,
- tatsächlicher Aufruf oder Prüfpfad,
- beobachtetes Ergebnis,
- fachliche Auswirkung,
- bereits ausgeschöpfte sichere Alternative,
- kleinste notwendige Entscheidung.

## Optionale Felder

Keine.

## Form

```text
Betroffener Schritt: <step>
Aufruf/Prüfpfad: <actual invocation or check path>
Beobachtetes Ergebnis: <observed result>
Fachliche Auswirkung: <bounded consequence>
Ausgeschöpfte Alternative: <safe alternative already tried>
Kleinste notwendige Entscheidung: <one required decision>
```

## Nicht verantwortlich

- Blocker automatisch auflösen,
- unabhängige Arbeit anhalten,
- fehlgeschlagene Pflichtpfade als positiven Nachweis umdeuten.
