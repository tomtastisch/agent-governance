# ADR 0004: Zentral konfigurierbare freiwillige Zwischenstatusausgabe

Status: angenommen · Datum: 2026-07-27

## Kontext

Freiwillige Fortschritts- und Präsenzmeldungen können bei längeren agentischen Abläufen unnötig
Tokens verbrauchen. Eine pauschale Stummschaltung wäre jedoch unzulässig: Rückfragen, Blocker,
Freigabeanforderungen, Sicherheitswarnungen, Fehler, materielle Befunde und Abschlussnachweise
müssen unabhängig von einer Komforteinstellung sichtbar bleiben.

Die Entscheidung muss harness-unabhängig, geschlossen validiert und ohne duplizierte
Standardwerte in Python oder Einstiegsvorlagen getroffen werden.

## Entscheidung

`core/interaction.toml` ist die einzige normative maschinenlesbare Quelle für die
Zwischenstatuskonfiguration. Der TOML-Adapter akzeptiert ausschließlich Schema-Version 1, die
geschlossene Tabelle `output` und einen Wert vom exakten Typ Boolean. Fehlende oder unbekannte
Schlüssel, andere Typen, nicht unterstützte Schema-Versionen und fehlerhaftes TOML werden als
`ConfigurationError` abgelehnt.

Der gemeinsame Vertragsrand definiert eine geschlossene `MessageKind`-Menge. Nur
`VOLUNTARY_INTERMEDIATE` folgt dem konfigurierten Schalter. `QUESTION`, `BLOCKER`, `APPROVAL`,
`SECURITY_WARNING`, `ERROR`, `MATERIAL_FINDING` und `FINAL_RESULT` werden unabhängig vom
Schalter immer zur Ausgabe entschieden. Bei aktivierter Zwischenstatusausgabe verändert die
Policy keine Nachrichtenklasse.

Die Entscheidung liegt als reine Funktion hinter `OutputPolicyPort`. Ihre Factory wird
ausschließlich über die paketierte Runtime-SSOT aufgelöst. Damit kennen weder Registry noch
Konsumenten die Implementierung namentlich.

## Konsequenzen

- Der Parser und die Policy sind deterministisch und ohne Harness- oder Netzwerkabhängigkeit
  testbar.
- Ungültige Konfiguration kann nicht durch Python-Truthiness versehentlich als aktiviert gelten.
- Verpflichtende Sicherheits-, Entscheidungs- und Auditkommunikation bleibt technisch von
  freiwilligen Zwischenständen getrennt.
- Die tatsächliche Unterdrückung in Claude, Codex oder einem anderen Harness bleibt bis zu dessen
  eigener Verdrahtung und Abnahme eine promptbasierte beziehungsweise harness-spezifische
  Fähigkeit. Höher priorisierte Systemausgaben kann diese Policy nicht deaktivieren.

## Verworfene Alternativen

- Ein Schalter je Adapter oder Vorlage: dupliziert Konfiguration und erzeugt Drift.
- Ein untypisierter Wert mit Wahrheitswertkonvertierung: würde beispielsweise Zeichenketten
  fälschlich akzeptieren.
- Vollständige Stummschaltung: verbirgt Blocker, Fehler und sicherheitsrelevante Meldungen.
- Direkte Harness-Logik ohne gemeinsamen Port: verhindert eine einheitliche, testbare Semantik.
