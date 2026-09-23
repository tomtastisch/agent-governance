# Issue #94: Routing, Baseline und Verifikation

## Auftrag und autoritative Basis

[Issue #94](https://github.com/tomtastisch/agent-governance/issues/94), gelesen am 23.09.2026.
Basis-Head `27610238d69fc94f276f988785bc2b54b9897e35`, Package `1.4.1`, `semver:patch`.
Der bestehende andere offene PR wurde nicht als Quelle verwendet. #50 ist geschlossen, #93
offen; die Änderung führt keine zweite Resume- oder Evidence-Reuse-Authority ein.

## Änderung

1. Neues Modul `modules/verification.md` hält die lokalen Regeln
   DEL-001, DEL-002, DEL-004, DEL-006. `delivery` behält die Liefer-/Review-Gates
   DEL-003, DEL-005, DEL-007, DEL-008, DEL-009, DEL-010 und hängt von `verification` ab.
2. `tool_routing → evidence` (statt `security`); `templates → evidence` (statt `delivery`).
   Die Review-Providerregeln verbleiben beim Delivery-Owner; Tool-Routing delegiert die
   Providerwahl ausdrücklich an `quality_review`/`security_review`.
3. `external_effect` löst zusätzlich das Security-Modul aus (SEC-004 „Begrenzte externe
   Wirkung“). `security → delivery` bleibt erhalten, damit SEC-001 die Referenzen auf
   DEL-003/DEL-007 auflösen kann.
4. `GOV-006` benennt explizit Abhängigkeiten, Governance-Regeln und
   Release-/Publishing-Sicherheit. Schritt 3 des Routings beschreibt die
   Phasen-Neuklassifikation: vor Scope-, Risiko-, Wirkungs- oder Lieferphasenwechsel wird
   erneut klassifiziert und vor der abhängigen Aktion nachgeladen; ausstehende Gates bleiben
   erforderlich.
5. Keine neue Routingprimitive, Projektion, Runtime-Dependency oder Cachelogik. Die
   bestehenden Trigger sind weiterhin die Routing-Authority.

## Messmethode

`tests.support.routing_measurement.measure_route` verwendet den vorhandenen
`NeutralHarness._resolve_routes` und instrumentiert die tatsächlichen Datei-Inhaltsreads
(einschließlich TOML). Pfadvalidierung ohne Inhaltsread zählt nicht als Kontext. Kataloge und
Templateindex werden vollständig validiert; Templatekörper werden nicht pauschal geladen.
Private lokale Regeln werden nie gelesen oder vermessen. Gemessen wird ein frischer
Bundle-Routinglauf ohne Session-/Evidence-Wiederverwendung.

Der deterministische Messprozess ruft keine externen Tools oder Modelle auf
(`tool_calls=0`, `model_cycles=0`); diese Zähler belegen keine Ersparnis echter
Agentenzyklen. Tokenmetriken sind nicht verfügbar (`null`) und werden nicht geschätzt.

Die Baseline liegt unverändert und an Git gebunden in
`tests/fixtures/routing/baseline.json`; der Korpus in `tests/fixtures/routing/corpus.json`.

## Baseline vs. optimiert (identische Fälle)

| Fall | Module alt→neu | Dateien alt→neu | Bytes alt→neu | Δ |
|---|---:|---:|---:|---:|
| Read-only Analyse | 4→2 | 16→14 | 64.405→57.387 | −7.018 |
| Lokale Implementierung | 6→6 | 18→18 | 68.763→66.086 | −2.677 |
| Lokaler Test | 5→5 | 17→17 | 66.749→64.072 | −2.677 |
| Normales Tool-Routing | 4→2 | 16→14 | 64.405→57.387 | −7.018 |
| Context-Handoff | 4→3 | 16→15 | 64.529→59.476 | −5.053 |
| Status-Bericht | 3→2 | 15→14 | 62.252→57.199 | −5.053 |

Die vier im Issue geforderten risikoarmen Positivfälle laden messbar weniger Governance-Kontext
(Dateien und Bytes). Laufzeit (Median) wird wegen Rauscharmut nicht als Speedup behauptet.

Security-/Negativkorpus (Authentifizierung, Autorisierung, Secrets, Dependency, Policy,
Governance, Prompt-Injection, Tool-Berechtigung, externe Datei/Wirkung, Publishing,
destruktive Operation) lädt weiterhin sämtliche KERNEL-, LOCAL-, SECURITY- und PROMOTION-Regeln;
die Modulzahl wächst dort um exakt ein Modul (`verification`) als Preis der strukturellen
Trennung, ohne dass eine Regel entfällt.

## Shadow-Vergleich

`python3 -m tests.support.routing_shadow` vergleicht die an Git gebundene Baseline mit dem
aktuellen Bundle über denselben 28-Fälle-Korpus, prüft entfernte Regeln, erforderliche Regeln
und Semantikdrift. Ergebnis: keine ungeklärte, sicherheitsrelevante oder Required-Gate-Divergenz.

## Fixture-Korrektur

Die historische v1.3.0-Release-Fixture rekonstruierte den veröffentlichten Stand aus dem
aktuellen Bundle und setzte Modul-Dateien als seit v1.3.0 unverändert voraus. Da #94 diese
Dateien verändert, ist die Fixture jetzt ein vollständiger, an den Tag `v1.3.0` gebundener
Snapshot unter `tests/fixtures/installer/releases/v1.3.0/bundle/`; die Rekonstruktion kopiert
diesen Snapshot deterministisch statt vom laufenden Bundle abzuleiten.

## Verifikation

- `python3 -m unittest discover -s tests -q`: 519 Tests; bis auf einen bereits bestehenden,
  umgebungsbedingten Flake im Microsoft-Provider-Bridge-Build (`rm: Directory not empty` im
  npm-Lauf, unabhängig vom Bundle) grün.
- `npm test`: 361 Tests grün.
- `npm run typecheck`, `npm run lint`: grün.
- `python3 tools/release_manifest.py check`: aktuell.
- `tests.test_routing_performance`: 14/14 grün (Kernel immer aktiv, lokale Arbeit ohne
  Promotion-Gates, Security-Korpus ohne Schutzregression, unbekannt/mehrdeutig fail-closed,
  manipuliertes Manifest/fehlende Evidence fail-closed, Phasenwechsel lädt Gates nach).

## Verifikationsmarker

Jeder Marker ist durch einen konkreten Test in `tests/test_routing_performance.py` oder einen
Mess-/Shadow-Lauf belegt; siehe Testnamen für die Zuordnung. Kein Marker wurde ohne reale
Evidence auf `PASS` gesetzt.

## Phase 2 — Lazy Domain Loading

### Messung des verbleibenden festen Overheads

Für `bare_analysis` (nur `analysis` → nur `evidence`) lud der PR-#100-Stand 13 Dateien mit
54.855 Bytes. Davon waren 32.419 Bytes Domänenkataloge, die für eine reine Analyse fachlich
irrelevant sind: Tools (13.541), Scopes (3.315), Policy-Tags (449), Commands (1.854),
Discovery (2.334), Work-Items (9.435) und Template-Index (1.491). Die Hypothese „der
wesentliche verbleibende Overhead entsteht durch den vor dem Routing vollständig geladenen
Katalogzustand“ ist damit bestätigt; die Gegenhypothese (vollständige Katalogverarbeitung
für eine sichere Routingentscheidung zwingend) ist widerlegt.

### Umsetzung

`load_routing_index` lädt nur Manifest, SSOT-Index und Trigger-Katalog; `load_tool_domain`
lädt Tools/Policy-Tags/Scopes erst bei `tool_routing`, `load_template_index` den
Template-Index erst bei `templates`. Commands, Discovery und Work-Items gehören nicht zur
Auftrags-Klassifikation und werden beim Modulrouting nicht geladen. GOVERNANCE.md Schritt 2
und 4 beschreiben dieses faule Domänenladen; ein dann benötigter, aber ungültiger Katalog
hält die abhängige Entscheidung nach GOV-004 an. Die Installer-Integrity-Prüfung des
vollständigen Bundles bleibt unverändert und verifiziert weiterhin alle Kataloge beim
Installieren/Aktivieren.

### Baseline PR #100 vs. Phase 2 (identische Fälle)

| Fall | PR #100 | Phase 2 | Δ |
|---|---:|---:|---:|
| bare analysis | 54.855 | 23.162 | −31.693 |
| read-only Analyse | 57.387 | 42.999 | −14.388 |
| lokale Implementierung | 66.086 | 53.189 | −12.897 |
| lokaler Test | 64.072 | 51.175 | −12.897 |
| normales Tool-Routing | 57.387 | 42.999 | −14.388 |
| Statusbericht | 57.199 | 26.997 | −30.202 |
| Context-Handoff | 59.476 | 29.274 | −30.202 |

### Small-Task-Korpus

| Small Task | Trigger | Dateien | Bytes |
|---|---|---:|---:|
| Git-Status lesen | `git_repository` | 9 | 42.999 |
| Dokumentationssuche | `documentation` | 9 | 31.338 |
| gezielter Test | `testing` | 13 | 51.175 |

Jeder Small Task behält den vollständigen Safety Kernel, lädt keine irrelevanten Domänen und
keine Promotion-/Release-Gates (gepinnt durch `LazyDomainLoading`).

### Projektions-Entscheidung (nicht eingeführt)

Eine kompakte Runtime-Projektion wurde **nicht** eingeführt. Nach dem Lazy-Domain-Loading
besteht der verbleibende feste Anteil aus dem immer aktiven Safety Kernel
(`GOVERNANCE.md`, GOV-001…006, nicht lazy-fähig), dem für GOV-006-Klassifikation benötigten
Trigger-Vokabular (`triggers.toml`, 9.784 Bytes, ohne Duplikation nicht projizierbar) und dem
Manifest-Graph (3.571 Bytes). Eine Projektion könnte nur den Manifest-Graph ersetzen
(~2 KB Ersparnis), würde aber eine zweite abgeleitete Routing-Struktur mit Generator-,
Drift- und Integrity-Bindung erzeugen — unverhältnismäßig gegenüber dem Nutzen und nahe an
der im Issue untersagten parallelen Policy-SSOT. Der Nachweis der Nicht-Reduzierbarkeit ist
damit evidenzbasiert erbracht.

### Modell-/Subagent-Routing

Das im Auftrag genannte kleine Worker-Modell (`opencode/nemotron-3.5-lightning-free`) ist im
aktuellen Harness nicht verfügbar; es wurden keine funktionalen Abhängigkeiten darauf
erzeugt. Der Hauptpfad (`high`) bleibt für alle fachlichen, Security- und
Governance-Entscheidungen allein verantwortlich; Subagenten (nur Explore/General/Scout)
wurden ausschließlich für unabhängige, read-only Reviews genutzt.

