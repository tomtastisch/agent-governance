# ADR 0007 — Cross-Language-Conformance-Vertrag der Governance-Validatoren

> **Historische Evidenz - nicht normativ.** Diese Architekturbegründung wird vom aktuellen
> Governance-Bundle nicht geladen. Sie beschreibt die Entscheidung, die produktiven
> TypeScript-Validatoren und die unabhängige Python-Testreferenz über einen expliziten
> Conformance-Vertrag zu koppeln (Issue #90), und ist keine ausführbare Anleitung.

- Status: angenommen
- Datum: 2026-09-26

## Kontext

Die Governance wird produktiv über mehrere TypeScript-Validatoren geprüft
(`governance-contract.ts`, `ssot-manifest.ts`, `routing-catalog.ts`, `discovery-catalog.ts`,
`command-catalog.ts`, `templates-catalog.ts`, `work-items.ts`). Parallel existiert mit
`tests/support/catalog_validator.py` eine unabhängige Python-Testreferenz. Beide pflegten
zahlreiche Schema-, Feld-, Domain- und Vokabular-Definitionen parallel manuell, wodurch
unbemerkte Drift zwischen Runtime-Validator und Testreferenz entstehen konnte.

## Entscheidung

Eine sprachneutrale Contract-Fixture `contracts/governance-contract.json` wird zur einzigen
Quelle der Strukturdefinitionen. Beide Implementierungen lesen dieselbe Datei:

- **TypeScript** über einen typisierten, fail-closed Loader `src/contract-fixture.ts`, der die
  Fixture strikt validiert und gefrorene Konstanten exportiert. Die sieben Validator-Module
  ersetzen ihre hartkodierten Feld-/Vokabularmengen durch diese Werte; die Validierungslogik
  bleibt je Modul unverändert.
- **Python** über `catalog_validator._load_contract_fixture()`, das dieselbe Datei lädt und die
  Feld-/Vokabularmengen daraus ableitet.

Ein Cross-Language-Conformance-Gate prüft beide Validatoren gegen das reale Bundle und eine
gemeinsame Mutation-Batterie (`tests/contracts/conformance-mutations.json`) und erzwingt
identische Accept/Reject-Verdicts. Die Python-Seite läuft in `tests/test_conformance.py`, die
TypeScript-Seite in `tests/installer/conformance.test.ts` (`npm test`); beide teilen sich
ausschließlich die Fixture-Dateien, keine Implementierungslogik.

## Abgrenzungen

- Keine zweite produktive Authority: die Fixture ist reine Deklaration, keine Validierungslogik;
  die produktive Authority bleibt die Governance-SSOT.
- Keine Konsumption der TypeScript-Implementierung durch Python: beide lesen dieselbe neutrale
  JSON-Datei, nicht gegenseitigen Code.
- Keine Aufhebung der unabhängigen Testwirkung: geteilt wird ausschließlich die Strukturdeklaration,
  nicht die Validierungslogik; Regex- und Vergleichssemantik bleiben je Sprache unabhängig.
- Command-spezifische Redundanz (Issue #88) bleibt unberührt.

## Auslieferung

Die Fixture liegt außerhalb von `bundle/` und beeinflusst `release.files.sha256` nicht. Sie wird
über `package.json` `files` ausgeliefert; `tools/verify-pack.mjs` schreibt sie als erwarteten
Laufzeitpfad fest.
