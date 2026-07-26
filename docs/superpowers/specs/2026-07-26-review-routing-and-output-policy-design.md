# Design — Verfügbarkeits- und risikobasiertes Review-Routing

Status: vom Nutzer fachlich freigegeben · Datum: 2026-07-26 · Vorgang: GitHub-Issue #4

## 1. Zweck

GitHub Copilot Code Review und der unabhängige QA-Agent werden deterministisch anhand von
Reviewzweck, belegbarer Copilot-Verwendbarkeit und Änderungsrisiko geroutet. Die Entscheidung
erfolgt nicht in einem freien LLM-Prompt. Ein read-only Werkzeug liefert getrennte technische
Signale; ein reiner Policy-Kern bestimmt daraus den zulässigen Review-Pfad.

Zusätzlich wird nicht notwendige Statuskommunikation über eine zentrale TOML-Konfiguration
abschaltbar. Das spart Tokens, ohne Rückfragen, Blocker, Freigaben, Fehler, Sicherheitswarnungen
oder den Abschlussnachweis zu unterdrücken.

Die bestehende unabhängige Exact-Head-Reviewpflicht und das fail-closed Merge-Gate bleiben
erhalten. Dieses Design ersetzt weder fehlende CI noch Repository-Schutzregeln.

## 2. Nachgewiesener Ausgangszustand

Referenzstand der Analyse: `origin/main@97c4044f01cebf011f5442bf312dfcc0dcfc0098`.

- Kern §16 definiert Copilot als primären Reviewer über `[BINDING:review.primary]`.
- Kann Copilot kein gültiges Exact-Head-Review liefern, ist QA der verpflichtende Alternativpfad.
- Kern §5.5, die QA-Rollenerweiterung und die QA-Vorlage verlangen aktuell QA nach jedem
  abgeschlossenen Cluster.
- Copilot liefert laut GitHub ein `COMMENTED`-Review, aber kein GitHub-`APPROVED`.
- Es gibt noch kein typisiertes Statusmodell, keine Risikomatrix, keinen Billing-/Availability-
  Probe, keinen JSON-Vertrag und keine Routing-Verhaltenstests.
- Der persönliche Usage-Endpunkt benötigt `Plan: read`. Die vorhandene CLI-Anmeldung besitzt
  diese Berechtigung nicht; der API-Zustand ist deshalb `permission_denied`.
- Der Nutzer hat im GitHub-Webinterface 200/200 enthaltene AI Credits, 10/10 USD zusätzliche
  Nutzung sowie eine erreichte zusätzliche Nutzungsgrenze nachgewiesen.
- GitHub kennzeichnet die betroffenen Actions-Jobs ausdrücklich als nicht gestartet, weil das
  Konto wegen eines Billing-Problems gesperrt ist. Die lokalen Tests bestehen an den untersuchten
  Exact Heads; lokal grün ersetzt nach Kern §16 keine GitHub-CI.
- `main` besitzt derzeit weder Branch Protection noch Ruleset. Dieser eigenständige Defekt ist
  in Issue #3 dokumentiert.

## 3. Fachliche Entscheidungen

### 3.1 Restbudget ist kein Routing-Eingang

Verbrauch, Limit, Budget und Restwert bleiben Diagnosefelder. Sie dürfen die Verwendbarkeit
belegen, wenn GitHub ausdrücklich eine Blockade oder Erschöpfung meldet. Ein berechnetes oder
geschätztes Restbudget entscheidet jedoch nicht, welcher Reviewer verwendet wird.

Insbesondere gibt es:

- keine statischen Tariflimits im Kern;
- keine Hochrechnung aus Planname oder historischem Tarif;
- keine Ableitung von `remaining`, wenn `used` oder `limit` unbekannt ist;
- keine Reservierung eines angenommenen Restkontingents;
- keinen Zustand „wahrscheinlich noch verfügbar“.

Der diagnostische Zustand `low_budget` bleibt unterscheidbar, weil die verbindliche Aufgabenquelle
ihn verlangt. Solange GitHub einen Review tatsächlich zulässt, bildet er sich jedoch genau wie
`available` auf `copilot_usable = true` ab und verändert die Route nicht.

### 3.2 Binäre Routing-Eingabe mit erhaltener Diagnose

Die Routing-Policy erhält genau eine Copilot-Entscheidung:

```text
copilot_usable = true | false
```

Die Diagnose behält trotzdem die präzise Ursache:

```text
available
low_budget
quota_exhausted
budget_blocked
rate_limited
provider_unavailable
permission_denied
unknown
```

Abbildung:

| Diagnose | `copilot_usable` | Begründung |
|---|---:|---|
| `available` | `true` | Positive, aktuelle und vollständige Evidenz |
| `low_budget` | `true` | Nutzbar; Restbudget beeinflusst die Route nicht |
| `quota_exhausted` | `false` | Nur mit expliziter Provider-/API-/Operator-Evidenz |
| `budget_blocked` | `false` | Explizite Nutzungsblockade |
| `rate_limited` | `false` | Kein belastbarer Reviewpfad in diesem Versuch |
| `provider_unavailable` | `false` | Providerpfad nicht erreichbar |
| `permission_denied` | `false` | Verwendbarkeit kann nicht belastbar belegt werden |
| `unknown` | `false` | Fail-closed, keine optimistische Annahme |

Mehrere Signale werden nicht vernichtet. Die Ausgabe enthält beispielsweise gleichzeitig
`billing_status = budget_blocked`, `provider_status = available` und
`api_status = permission_denied`. `routing_status` nennt die für den Pfad ausschlaggebende
Diagnose; `evidence` dokumentiert alle Eingangssignale.

### 3.3 Positive Verwendbarkeit setzt positive Evidenz voraus

`copilot_usable = true` darf nur entstehen, wenn alle für den konkreten Kontext erforderlichen
Signale positiv und aktuell sind:

1. Abrechnungskontext ist belastbar bestimmt.
2. Usage-/Lizenzantwort ist syntaktisch und semantisch vollständig genug.
3. Keine explizite Quoten- oder Budgetblockade liegt vor.
4. Kein aktuelles Rate Limit oder Provider-Ausfall liegt vor.
5. Repository und Benutzer sind für Copilot Code Review berechtigt beziehungsweise konfiguriert,
   soweit dies über dokumentierte Schnittstellen prüfbar ist.

GitHub bietet nicht für jeden persönlichen Kontext einen read-only „Can review now“-Endpunkt.
Die CLI muss diese Evidenzgrenze im JSON nennen. Der nach Aufhebung des Billing-Locks geplante
reale Copilot-Review ist deshalb der abschließende Live-Positivnachweis, nicht Teil der Unit-Tests.

### 3.4 Keine automatische Kontext-Erfindung

Der Probe bestimmt den Kontext repo- und benutzerbezogen:

- persönlicher Kontext: User-Usage-Endpunkt;
- Organisationskontext: Organisation-Usage und, bei ausreichenden Rechten, Copilot-Sitzzuordnung;
- Enterprise-/Cost-Center-Kontext: nur bei explizit konfigurierter oder API-belegter Zuordnung;
- Legacy-Kontext: offizieller Premium-Request-Endpunkt als Kompatibilitätspfad.

Eine Organisationsmitgliedschaft allein beweist keine von dieser Organisation bezahlte
Copilot-Lizenz. Fehlen die Rechte zur Sitz- oder Billing-Prüfung, lautet die Diagnose
`permission_denied` beziehungsweise der Kontext `unknown`; die Route bleibt fail-closed.

### 3.5 Probe, Route und Dispatch bleiben getrennt

```text
probe     read-only: Evidenz sammeln und klassifizieren
route     read-only: reine Policy auf Probe + Diff-Metadaten anwenden
dispatch  extern wirkend: Copilot-/Rollenreview tatsächlich auslösen
```

Der Lieferumfang implementiert `probe` und `route`. Ein kostenpflichtiger Copilot-Dispatch ist
keine read-only Aktion und wird weder in Tests noch stillschweigend durch den Probe ausgelöst.
Harness-spezifische QA-/SEC-Auslösung verbleibt in den jeweiligen Adaptern.

## 4. Domänenvertrag

### 4.1 Reviewzweck

```text
checkpoint
final_exact_head
correction
```

- `checkpoint`: abgeschlossener Cluster/Schritt auf dem Haupt-PR-Branch.
- `final_exact_head`: Merge-Gate des Haupt-PRs gegen `main`.
- `correction`: erneutes Review nach einem oder mehreren behobenen Findings.

### 4.2 Risikoklasse

```text
low
medium
high
critical
```

Die Risikoklasse ist das Maximum aus:

1. Größenklasse anhand konfigurierbarer Diff-Schwellen;
2. Pfadmarkern für Governance-Kern, Verträge, Security, Authentifizierung, Secrets, CI,
   Datenmigrationen, Produktionsschreibpfade und kryptografische/protokollarische Logik;
3. expliziten maschinenlesbaren Risikomarkern des Vorgangs;
4. Abhängigkeits- und Blast-Radius-Merkmalen.

Manuelle Marker dürfen Risiko erhöhen, nie automatisch senken. Fehlen erforderliche Diff-Daten
oder ist die Klassifikation widersprüchlich, gilt `critical`, nicht `low`.

Die konkreten Globs und Schwellen stehen ausschließlich in `core/review-routing.toml`. Kern,
Adapter, Templates und Python-Code duplizieren die Werte nicht.

### 4.3 Reviewer-Routen

```text
local_checks
copilot
copilot_qa
copilot_qa_sec
qa
qa_sec
blocker
```

`local_checks` ist nur für einen risikoarmen Checkpoint zulässig und niemals eine Merge-Evidenz.
Jede andere erfolgreiche Route nennt die erforderliche unabhängige Reviewer-Menge.

## 5. Entscheidungsmatrix

Deterministische lokale Tests und statische Prüfungen laufen in jedem Fall.

### 5.1 Checkpoint

| Risiko | Copilot nutzbar | Route |
|---|---:|---|
| `low` | beliebig | `local_checks` |
| `medium` | `true` | `copilot` |
| `high` | `true` | `copilot_qa` |
| `critical` | `true` | `copilot_qa_sec` |
| `medium` oder `high` | `false` | `qa` |
| `critical` | `false` | `qa_sec` |

Damit entfällt die heutige pauschale QA nach jedem Cluster. Bei nutzbarem Copilot entscheidet das
Risiko, ob QA zusätzlich erforderlich ist. Bei nicht nutzbarem Copilot ist QA der einzige
Reviewpfad. Ein risikoarmer Checkpoint erzeugt keinen LLM-Review, weil die unabhängige finale
Exact-Head-Prüfung davon unberührt bleibt.

### 5.2 Finales Exact-Head-Review

| Risiko | Copilot nutzbar | Route |
|---|---:|---|
| `low` oder `medium` | `true` | `copilot` |
| `high` | `true` | `copilot_qa` |
| `critical` | `true` | `copilot_qa_sec` |
| `low`, `medium` oder `high` | `false` | `qa` |
| `critical` | `false` | `qa_sec` |

Ist ein erforderlicher QA- oder SEC-Kontext nicht verfügbar, wird aus der vorgesehenen Route
`blocker`. Es gibt keinen Merge mit reduzierter Reviewer-Menge.

### 5.3 Korrekturrunde

Die erforderliche Reviewer-Menge des vorausgehenden gültigen Reviews wird auf dem neuen Exact
Head erneut benötigt. Der Reviewumfang bleibt auf Korrekturdiff und direkte Auswirkungen begrenzt.

- War Copilot erforderlich und ist weiter nutzbar, bleibt Copilot erforderlich.
- Ist Copilot nun nicht nutzbar, ersetzt QA den Copilot-Anteil.
- Bereits risikobedingt erforderliche QA-/SEC-Anteile bleiben erhalten.
- Kein Copilot-Retry bei `copilot_usable = false`.
- Ein Review des alten Heads wird nie übernommen.

## 6. QA-Kosten

QA-Kosten werden getrennt dokumentiert:

```text
model
estimated_input_tokens
estimated_output_tokens
actual_input_tokens
actual_output_tokens
price_source
estimated_cost
actual_cost
```

Preise oder Tokenbudgets sind keine Kernkonstanten. Ein Harness kann bekannte Messwerte und eine
datierte Preisquelle liefern. Fehlen sie, bleiben Kostenfelder `unknown`.

Die Policy berücksichtigt Kosten strukturell:

- `local_checks` verhindert unnötige QA bei risikoarmen Checkpoints.
- `copilot` verhindert unnötige parallele QA bei niedrigem/mittlerem Risiko.
- Eine risikobedingt oder als Fallback erforderliche QA/SEC darf niemals wegen Kosten entfallen.
- Ist ein verpflichtender QA-/SEC-Kontext wegen eines harten Harness-Budgets nicht verfügbar,
  lautet die Route `blocker`, nicht `copilot` oder Merge.

## 7. Exact-Head-Evidenz

### 7.1 Allgemeine Invarianten

Gültige Merge-Evidenz setzt voraus:

- Base- und Head-SHA sind explizit;
- jedes Review bezieht sich auf genau diesen Head;
- erforderliche CI-Checks gehören zum selben Head und sind grün;
- null ungelöste Review-Threads;
- die laut Route erforderliche Reviewer-Menge ist vollständig;
- Folge-Reviews ersetzen ältere Freigaben nur für den neuen Head.

Lokale Tests sind Diagnose- und Entwicklungsevidenz, aber nach aktuellem Kern keine
CI-/Merge-Evidenz.

### 7.2 Copilot-`COMMENTED`

Copilot kann kein GitHub-`APPROVED` vergeben. Ein Copilot-Review erfüllt den technischen
Governance-Vertrag nur, wenn ein deterministischer Validator mindestens belegt:

- erwartete Copilot-Reviewer-Identität;
- Reviewzustand `COMMENTED`;
- `commit_id` entspricht dem Exact Head;
- Review wurde nach dem betreffenden Push abgeschlossen;
- kein Fehler-/Nicht-prüfbar-Ergebnis;
- kein ungelöstes Copilot-Finding;
- keine neuere Copilot-Anforderung ohne abgeschlossenes Review.

Der Validator bezeichnet dies als `valid_review_evidence`, nie als GitHub-`APPROVED`.
Serverseitige Erzwingung als Required Check ist Abhängigkeit von Issue #3 und nicht durch ein
lokales positives Ergebnis ersetzt.

## 8. Read-only GitHub-Adapter

Der Adapter verwendet nur dokumentierte Schnittstellen und die bestehende `gh`-Authentifizierung:

- `GET /user` für den authentifizierten Benutzer;
- User-/Organization-/Enterprise-Billing-Usage für AI Credits;
- User-/Organization-Legacy-Usage für Premium Requests;
- Organisationsbudgets, soweit offiziell verfügbar und berechtigt;
- Copilot-Sitzinformation für Organisationen, soweit berechtigt;
- GitHub-Status für Provider-Signale;
- Repository-, PR-, Review-, Thread- und Check-Metadaten für Eligibility/Exact-Head-Evidenz.

HTTP-Antworten werden typisiert klassifiziert:

- `401`/`403` beziehungsweise explizite Berechtigungsdiagnose → `permission_denied`;
- `429` oder belastbare Rate-Limit-Header → `rate_limited`;
- `500`/`502`/`503`/`504` beziehungsweise Status-Incident → `provider_unavailable`;
- leere, verzögerte, syntaktisch falsche oder semantisch unvollständige Antwort → `unknown`;
- `404` wird nur dann als fehlende Berechtigung klassifiziert, wenn die offizielle Schnittstelle
  oder `gh` dies belegt; andernfalls `unknown`.

Tokens, Headerwerte, Secret-Fragmente und Tokenlängen werden weder geloggt noch serialisiert.

## 9. CLI-Vertrag

### 9.1 Befehle

```text
python3 -m review_routing probe --repo OWNER/REPO --json
python3 -m review_routing route \
  --probe-file PROBE.json \
  --purpose final_exact_head \
  --base-sha BASE \
  --head-sha HEAD \
  --diff-file DIFF.json \
  --json
```

Der Composition Root instanziiert den GitHub-Adapter. Policy und Risikoklassifikation kennen
weder `gh` noch HTTP.

### 9.2 Probe-JSON

```json
{
  "schema_version": 1,
  "observed_at": "2026-07-26T00:00:00Z",
  "repository": "owner/repository",
  "billing_context": {
    "kind": "personal",
    "identity": "redacted-or-non-secret-name",
    "evidence": ["github_api"]
  },
  "billing_model": "ai_credits",
  "usage": {
    "used": 200,
    "limit": null,
    "remaining": null,
    "unit": "credits"
  },
  "signals": {
    "billing_status": "budget_blocked",
    "provider_status": "available",
    "api_status": "permission_denied"
  },
  "routing_status": "budget_blocked",
  "copilot_usable": false,
  "evidence": [],
  "warnings": []
}
```

`remaining` ist nur eine Zahl, wenn `used` und das tatsächlich geltende `limit` belastbar bekannt
sind. Das Feld beeinflusst `copilot_usable` und die Route nicht.

### 9.3 Route-JSON

```json
{
  "schema_version": 1,
  "purpose": "final_exact_head",
  "base_sha": "BASE",
  "head_sha": "HEAD",
  "risk": {
    "level": "high",
    "reasons": ["security_path"]
  },
  "copilot_usable": true,
  "required_reviewers": ["copilot", "qa"],
  "route": "copilot_qa",
  "merge_evidence_required": true,
  "dispatch_permitted": false
}
```

`dispatch_permitted` bleibt in diesem read-only Werkzeug immer `false`. Die Ausgabe ist ein Plan,
keine Freigabe zum Auslösen kostenpflichtiger Reviews.

### 9.4 Exitcodes

Probe:

| Code | Bedeutung |
|---:|---|
| `0` | Technisch vollständige Probe; fachlicher Status steht im JSON |
| `20` | `permission_denied` |
| `21` | `rate_limited` |
| `22` | `provider_unavailable` |
| `23` | Kontext oder Status `unknown` |
| `24` | Leere, unvollständige oder ungültige Antwort |

Eine explizit erkannte Quoten-/Budgetblockade ist eine erfolgreiche Probe und liefert `0`, obwohl
`copilot_usable = false` gilt.

Route:

| Code | Bedeutung |
|---:|---|
| `0` | Deterministische Route gewählt |
| `30` | Erforderlicher unabhängiger Reviewer nicht verfügbar (`blocker`) |
| `31` | Policy, Probe oder Eingabe ungültig |
| `32` | Exact-Head-Evidenz fehlt oder ist veraltet |

## 10. Architektur und SSOT

Vorgesehene Struktur:

```text
core/
  review-routing.toml
  interaction.toml
review_routing/
  __init__.py
  __main__.py
  contracts.py
  policy.py
  risk.py
  ports.py
  adapters/
    __init__.py
    github_gh.py
tests/
  fixtures/review-routing/
  test_review_routing_contracts.py
  test_review_routing_policy.py
  test_review_routing_risk.py
  test_review_routing_github.py
  test_review_routing_cli.py
```

- `contracts.py`: Enums und unveränderliche Datenträger.
- `ports.py`: Protokolle für Usage-/Availability-/Review-Evidenzquellen.
- `policy.py`: reine Routingfunktion.
- `risk.py`: reine Risikoklassifikation aus TOML und Diff-Metadaten.
- `github_gh.py`: einziger Ort für GitHub-Endpunkte, `gh` und HTTP-Klassifikation.
- `__main__.py`: Composition Root und CLI.
- `core/review-routing.toml`: einzige Quelle für Matrix, Schwellen und Risikomarker.
- `core/interaction.toml`: einzige Quelle für den Zwischenstatus-Schalter.

Keine Routingwerte werden in Kernprosa, Adaptern oder Templates kopiert. Diese Stellen benennen
nur Invarianten und verweisen auf die Policy.

Der bestehende Harness-Port `review.primary` bleibt zunächst erhalten. Neue Harness-Bindings
`review.fallback`, `review.usage_probe`, `review.availability_probe` oder
`review.routing_policy` sind nicht nötig:

- QA-/SEC-Auslösung erfolgt bereits über `roles.mechanism`;
- Usage/Availability sind Ports des gemeinsamen Python-Vertrags, nicht der Harnesse;
- die Routing-Policy ist ein Kernartefakt, kein Adapterwert.

## 11. Zentrale Ausgabepolitik

`core/interaction.toml`:

```toml
schema_version = 1

[output]
intermediate_status = false
```

Semantik:

- `false`: freiwillige Fortschritts-, Präsenz-, Planbestätigungs- und unveränderte
  Wartestatusmeldungen unterdrücken.
- `true`: normales Zwischenstatusverhalten des Harness unverändert lassen.

Unabhängig vom Wert müssen ausgegeben werden:

- entscheidungsnotwendige Rückfragen;
- Blocker;
- Einzelfreigabeanforderungen;
- Sicherheits- und Secret-Warnungen;
- Fehler, fehlgeschlagene Nachweise und Abweichungen;
- materielle neue Befunde, wenn sie eine Nutzerentscheidung oder Scope-Triage erfordern;
- das abschließende `ERGEBNIS` nach Kern §8.

Der Schalter darf keine Toolausgaben, Review-Findings, Auditnachweise oder Merge-Gates
wegdefinieren. Höher priorisierte Harness-/Systemvorgaben zu Statusmeldungen gelten weiterhin;
die Governance darf deren Unterdrückung nicht versprechen.

Damit der Wert vor der ersten freiwilligen Zwischenmeldung bekannt ist:

- Claude-Einstieg importiert `core/interaction.toml`;
- Codex-Einstieg weist dessen vollständiges Lesen als erste Sessionaktion an;
- Install-Prompt und Template-Zuordnung übernehmen die zusätzliche Datei;
- Drift-Tests erzwingen, dass alle Einstiegsvorlagen dieselbe SSOT laden.

## 12. Teststrategie

Alle GitHub-Antworten werden als lokale Fixtures oder Fake-Port-Antworten bereitgestellt. Kein Test
ruft GitHub auf oder löst ein Review aus.

Mindestens:

1. AI Credits mit bekanntem Limit/Budget; Restwert korrekt, aber ohne Routingeinfluss.
2. AI Credits ohne bekanntes Limit; `remaining = null`.
3. Legacy Premium Requests.
4. Explizit ausgeschöpftes Kontingent → `copilot_usable = false`.
5. Explizit blockiertes Budget → `false`.
6. `low_budget`, aber tatsächlich nutzbar → `true`, identische Route wie `available`.
7. Rate Limit → `false`, Exitcode `21`.
8. Provider-Ausfall → `false`, Exitcode `22`.
9. Fehlende Berechtigung → `false`, Exitcode `20`.
10. Leere Antwort → `unknown`, Exitcode `24`.
11. Unvollständige Antwort → `unknown`, Exitcode `24`.
12. Unbekannter Abrechnungskontext → `unknown`, Exitcode `23`.
13. Organisationsmitgliedschaft ohne Sitzbeleg erzeugt keinen Organisationskontext.
14. Checkpoint-Matrix für alle vier Risiken und beide Verwendbarkeitswerte.
15. Final-Matrix für alle vier Risiken und beide Verwendbarkeitswerte.
16. Korrekturrunde behält erforderliche Reviewer und ersetzt unbrauchbaren Copilot durch QA.
17. Kein Copilot-Retry bei `false`.
18. Fehlender verpflichtender QA-/SEC-Kontext → `blocker`.
19. QA-Kosten können verpflichtende Reviewer nicht entfernen.
20. Exact-Head-Mismatch → keine gültige Evidenz, Exitcode `32`.
21. Copilot-`COMMENTED` mit korrektem Head und null Findings → gültige technische Evidenz.
22. Copilot-`COMMENTED` auf altem Head oder mit offenem Finding → ungültig.
23. Kein Mergepfad ohne vollständige Exact-Head-Reviewer-Menge.
24. Secret-/Header-/Tokenwerte erscheinen nicht in JSON oder Fehlermeldungen.
25. `intermediate_status = false` ist der Repository-Default.
26. Ungültiger/nicht-boolescher Ausgabewert fällt fail-closed.
27. Kern, Policy, Adapter, Templates, README und Installationsanleitung bleiben driftfrei.
28. Bestehende 25 Governance-Tests bleiben grün.

## 13. Umsetzungsschnitt

1. Design-Spezifikation und Draft-Haupt-PR.
2. ADR, TOML-Verträge und zunächst fehlschlagende Vertrags-/Policytests.
3. Reiner Domänen-, Risiko- und Policy-Kern.
4. GitHub-Adapter mit Fake-/Fixture-Tests.
5. CLI, JSON und Exitcodes.
6. Ausgabepolitik und Harness-Verdrahtung.
7. Kern-, Rollen-, Adapter-, Template-, README-, INSTALL- und Katalogsynchronisierung.
8. Vollständige lokale Verifikation, Negativtest am aktuellen Billing-Lock und unabhängige QA/SEC.
9. Nach Nutzerhinweis zur Billing-Freigabe: GitHub-CI und realer Copilot-Positivtest am unveränderten
   Exact Head; bei jeder Korrektur neuer Head und neue Evidenz.

Jeder Schritt wird im Vorgang #4 mit Commit-SHA dokumentiert. Der Haupt-PR bleibt Draft, bis alle
lokal möglichen Nachweise und nach Aufhebung des Billing-Locks die Live-Nachweise vorliegen.

## 14. Sicherheits- und Betriebsgrenzen

- Keine Tokens in Repo, Logs, Fixtures, Issues oder JSON.
- Authentifizierung ausschließlich über bestehendes `gh`, Keychain oder Secret Manager.
- Probe und Route schreiben weder GitHub- noch lokale Konfigurationszustände.
- Keine Review-Anforderung in Tests.
- Keine Branch-Protection-/Ruleset-Mutation in diesem Vorgang.
- Kein Merge durch den Agenten; der Nutzer übernimmt ihn.
- External-State-Zeitstempel und SHA werden in jeder Evidenz mitgeführt.
- Caches sind nur mit expliziter kurzer Gültigkeit zulässig; ein negativer oder unbekannter Zustand
  darf nicht durch einen älteren positiven Cache überschrieben werden.

## 15. Vollständige Einsatzbereitschaft

Der PR kann die Governance erst dann als für diesen Funktionsumfang einsatzbereit ausweisen, wenn:

- alle lokalen Vertrags-, Unit-, Integrations-, CLI-, Drift- und Secret-Tests grün sind;
- Negativpfade inklusive aktuellem Billing-Lock nachgewiesen sind;
- nach Aufhebung des Billing-Locks der Live-Positivpfad erfolgreich ist;
- GitHub-CI am finalen Exact Head grün ist;
- die laut Matrix erforderlichen unabhängigen QA-/SEC-Reviews denselben Exact Head freigeben;
- keine ungelösten Threads bestehen;
- Dokumentation, ADR, Vorlagen und Installationsweg synchron sind.

„Vollständig und vollumfänglich einsatzbereit“ für das gesamte Repository bleibt zusätzlich von
Issue #3 abhängig: Ohne technisch erzwungenen Required Check beziehungsweise entschiedenen
CI-Unverfügbarkeitspfad ist das fail-closed Merge-Gate weiterhin nur organisatorisch, nicht
serverseitig erzwungen. Dieser PR darf diese externe Grenze nicht als erledigt darstellen.

## 16. Verworfene Alternativen

- Nur Markdown-/Promptmatrix: nicht hinreichend deterministisch oder testbar.
- Ein Shell-Skript mit eingebetteter Policy: vermischt GitHub-I/O, Statusklassifikation und
  Routing; schlecht mockbar.
- Restbudgetbasierte Reservierung: persönliche Limits sind nicht durchgehend belastbar und der
  Nutzer hat Restbudget ausdrücklich als Routing-Eingang verworfen.
- Copilot bei unbekanntem Zustand optimistisch versuchen: erzeugt Retries/Kosten und verletzt
  fail-closed.
- QA nach jedem Cluster: unnötiger Tokenverbrauch ohne risikobezogenen Qualitätsgewinn.
- `intermediate_status = false` unterdrückt alle Ausgaben: würde Blocker, Fehler, Freigaben und
  Auditnachweise verbergen.
- Neue Harness-Bindings für gemeinsame Probe/Policy: dupliziert harness-unabhängige Semantik.
- Routing-PR behebt gleichzeitig Branch Protection/Rulesets: vermischt Repository-Code mit einer
  separaten externen Schutzkonfiguration aus Issue #3.
