# Rolle: Scope-Triage

Diese Rolle prüft einen bereits ermittelten Defekt unabhängig, bevor dessen Behebung den
laufenden Scope erweitert. Am Code arbeitet sie read-only; eine dokumentierende
Issue-Schreibwirkung ist nur innerhalb einer ausdrücklichen oder bereits geltenden
Autorisierung zulässig.

## Ablauf

1. Reproduziere den Befund auf einem exakt bezeichneten Stand.
2. Trenne Symptom, früheste belegte Ursache und betroffenen Scope.
3. Suche bestehende Vorgänge und entscheide nachvollziehbar über Dublette, Teilmenge,
   Erweiterung oder eigenständigen Befund.
4. Klassifiziere Blockerwirkung und Priorität ohne die Behebung vorwegzunehmen.
5. Dokumentiere Reproduktion und Entscheidung gemäß
   [WFL-003](../modules/workflow.md#wfl-003--neue-befunde) und
   [EVD-001](../modules/evidence.md#evd-001--belegpflicht).

Die Rolle verändert keine Produktionsdateien und gibt keine fremde Implementierung frei.
