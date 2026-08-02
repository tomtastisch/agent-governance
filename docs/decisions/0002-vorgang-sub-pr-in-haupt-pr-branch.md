# ADR 0002 — Schritt-Lieferung als Sub-PR in den Haupt-PR-Branch, verallgemeinerter Vorgang

> **Historische Evidenz - nicht normativ.** Diese Datei dokumentiert eine frühere Entscheidung,
> wird vom aktuellen Governance-Bundle nicht geladen und erteilt keine Handlungsanweisung.

Status: akzeptiert · Datum: 2026-07-25

## Kontext

Das Slicing-/Liefermodell war an zwei Punkten unscharf bzw. unnötig streng:

1. Die Aufgabenverfolgung war durchgängig an „Issue" gebunden, obwohl Aufgaben auch aus
   Ticket-Systemen (Jira, Linear o. Ä.) stammen können.
2. Ein verbreitetes (nicht im Kern verschriftlichtes) Denkmodell verlangte, jeden Slice
   eigenständig nach main mergebar zu halten. Das erzwingt grobe Schnitte, weil jeder Zwischenstand
   schon produktionssicher/fail-closed sein müsste.

## Entscheidung

- Neutraler Oberbegriff **Vorgang**: die Aufgabenquelle als Tracking-Artefakt (GitHub-Issue,
  Ticket oder Vergleichbares). Ein Vorgang trägt eine **Schritt-Checkliste** als fachliche
  Gesamtspezifikation und bleibt über die gesamte Umsetzung genau ein Vorgang.
- Pro Vorgang genau ein **Haupt-PR** auf einem Integrations-/Feature-Branch (Draft bis Merge-Gate).
- Jeder **Schritt (= ein Cluster, §5.2)** wird in den **Haupt-PR-Branch** geliefert — bevorzugt als
  kleiner Sub-PR, für triviale Schritte als Checkpoint-Push. Dokumentiert im Vorgang als
  „Schritt X ✓ via Sub-PR #N" (bzw. Commit-SHA).
- **Zwischen-Sub-PRs mergen in den Haupt-PR-Branch, nicht nach main.** main-Tauglichkeit/fail-closed
  wird einmal am Haupt-PR erzwungen (§16), nicht je Schritt.
- Der Merge des Haupt-PRs schließt den Vorgang vollständig ab.
- Das fail-closed Merge-Gate (§16) gilt für den Haupt-PR → main; Zwischen-Sub-PRs unterliegen der
  laufenden Cluster-QA (§5.5), nicht dem Gate.

Der Begriff **Cluster** bleibt und wird ausdrücklich mit **Schritt** gleichgesetzt, damit keine
zwei parallelen Vokabulare entstehen. Neu gefundene Defekte bleiben getrennt und werden weiterhin
als Issue nach §18 erfasst — unabhängig davon, woher der Vorgang kommt.

## Begründung

- Feinere Schnitte ohne halbfertige Zustände auf main: Zwischenstände bleiben auf den
  Feature-Branch begrenzt; nur der Haupt-PR muss main-tauglich sein.
- Ein Prüfpunkt statt vieler: das strenge Gate greift einmal (Haupt-PR), die frühzeitige
  Cluster-QA (§5.5) sichert die Zwischenstände.
- Harness- und quellenagnostisch: das Modell trägt für Issues wie für Tickets.
- Eine Vokabel je Konzept (Vorgang, Schritt=Cluster) — keine Doppel-Wahrheiten.

## Konsequenzen

- Kern angepasst: §5.2 (Cluster = Schritt), §5.5 (Schritt im Vorgang vermerken), §15 (Modell),
  §16 (Geltungsbereich des Gates), §14 und §20 (Terminologie). §17 nutzt „diese Aktion" statt
  „diesen Vorgang", um die Wortkollision mit dem definierten Begriff zu vermeiden.
- §18 (Issue-Pflicht für neu entdeckte Defekte) bleibt unverändert und bewusst getrennt vom Vorgang.
- Bestehende Formulierungen mit „Issue" für die Aufgabenverfolgung sind auf „Vorgang" gehoben; die
  Git-Issue-Syntax (`Relates to`/`Closes #N`) bleibt als der Git-Fall erhalten.

## Alternativen (verworfen)

- Slice eigenständig nach main mergebar halten: erzwingt grobe Schnitte und verhindert frühe,
  kleine Checkpoints ohne fachlichen Mehrwert.
- „Issue" als alleinigen Begriff behalten: schließt Ticket-basierte Aufgabenquellen sprachlich aus
  und vermischt die Aufgabenverfolgung mit der §18-Defektpflicht.
