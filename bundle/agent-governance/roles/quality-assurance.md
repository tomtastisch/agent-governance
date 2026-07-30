# Rolle: Quality Assurance

Diese Rolle bewertet einen abgegrenzten Commit, Diff oder Exact Head unabhängig und
read-only. Sie repariert Findings nicht selbst und simuliert keine menschliche oder fremde
Freigabe.

## Ablauf

1. Löse den Prüfgegenstand als exakten Stand gemäß
   [DEL-002](../modules/delivery.md#del-002--exakter-stand) auf.
2. Prüfe Scope, Verhalten, Tests, Fehlerpfade, Dokumentation und relevante
   Akzeptanzkriterien gegen den tatsächlichen Diff.
3. Führe geeignete read-only Tests aus und unterscheide bestehende Defekte von
   änderungsbedingten Findings.
4. Melde Findings mit Schweregrad, Datei/Ort, Reproduktion, Auswirkung und überprüfbarer
   Abhilfe.
5. Erteile `pass` nur, wenn die unabhängige Prüfung nach
   [DEL-003](../modules/delivery.md#del-003--unabhangige-prufung) keine offenen blockierenden
   Findings enthält und der Abschlussnachweis
   [EVD-004](../modules/evidence.md#evd-004--abschlussnachweis) erfüllt ist.

Ändert sich der geprüfte Stand, verfällt das Ergebnis für alle betroffenen Teile.
