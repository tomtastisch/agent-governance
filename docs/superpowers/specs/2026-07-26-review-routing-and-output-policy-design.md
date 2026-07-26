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

Verbrauch, Limit, Budget und Restwert bleiben Diagnosefelder. Die Usage-Antwort beschreibt
ausschließlich Verbrauch; weder freie `status`-Felder noch ein dort auftauchendes `limit` gelten
als Blockade-, Capability- oder Budgetevidenz. Eine Blockade oder Erschöpfung darf nur ein
separater Verifier aus einem extern digest-gepinnten Operator-Artefakt rekonstruieren. GitHub
Actions-Billing-Annotationen und allgemeine Provider-/API-Antworten sind keine
Copilot-Blockade. Ein berechnetes oder geschätztes Restbudget entscheidet nicht, welcher Reviewer
verwendet wird.

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
| `quota_exhausted` | `false` | Nur mit extern gepinnter Operator-Evidenz |
| `budget_blocked` | `false` | Separat verifizierte aktuelle Budgetblockade |
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

1. Reviewmodus (`manual` oder `automatic`), Requester, PR-Autor und der daraus folgende
   Billing-Principal sind belastbar bestimmt.
2. Abrechnungskontext und Billing-Modell dieses Principals sind belastbar bestimmt.
3. Usage-/Lizenzantwort ist syntaktisch und semantisch vollständig genug; gemessen wird
   `grossQuantity`, während `limit` und `remaining` ohne eigene autoritative Budgetquelle
   unbekannt bleiben.
4. Keine gleich alte oder neuere, separat verifizierte Quoten-, Account- oder Budgetblockade
   liegt vor.
5. Kein aktuelles Rate Limit oder Provider-Ausfall liegt vor.
6. Es liegt eine zeitlich gültige positive Capability-Evidenz für Repository, Principal und
   Reviewmodus vor.

GitHub bietet nicht für jeden persönlichen Kontext einen read-only „Can review now“-Endpunkt.
Historische Usage ohne Blockade und ein abgeschlossenes GitHub-Review allein sind deshalb
**keine** positive Capability-Evidenz. Zulässig ist ausschließlich ein versioniertes
Operator-Artefakt, dessen kanonischer SHA-256-Digest außerhalb des CLI durch die Publisher-App
oder installierte Konfiguration fest gepinnt ist. Sein geschlossener Typ ist:

- `operator_setting`: eine direkt an Repository, Principal und Reviewmodus gebundene, zeitlich
  begrenzte Operator-Freigabe; oder
- `completed_review_context`: eine Bindung an Repository, stabile Principal-Identität,
  Reviewmodus, PR, Review-ID, Review-Commit, Zeitpunkt und Ablauf.

Bei `completed_review_context` wird das referenzierte Review erst **nach** erfolgreicher
Pin-Prüfung read-only über GitHub erneut geladen. Es muss Copilot, `COMMENTED`, Review-ID,
Review-Commit und Zeitpunkt exakt bestätigen. Das API-Review kann Principal und Reviewmodus nicht
selbst binden und darf daher niemals allein oder für einen anderen Principal/Modus Capability
erzeugen. Die API-Review-ID wird nur akzeptiert, wenn ihr konkreter Typ `int` ist; `bool`, Float,
String, `null` und andere Formen werden abgelehnt.

`ProbeRequest` transportiert dafür nur eine nicht vertrauenswürdige Referenz. Er kann weder
`trust`, erwarteten Digest noch Issuer setzen. `OperatorEvidenceTrustPort` liefert den externen
Digest-Pin ausschließlich programmatisch; sein erforderliches `pin_source` ist geschlossen auf
`publisher_app` oder `installed_config`. `CapabilityEvidenceVerifierPort` und
`BlockEvidenceVerifierPort` rekonstruieren routingfähige Evidenz samt geschlossener Provenienz.
`ABSENT`, `INVALID` und `EXPIRED` bleiben ausnahmslos `unverified`.
Eine gleich alte oder neuere verifizierte Blockade schlägt die Capability; ein danach
abgeschlossenes Review schlägt eine ältere Blockade. Technische Permission-, Rate- oder
Providerfehler einschließlich entsprechender Verifierfehler schlagen beide Caches, abgelaufene
Evidenz wird ignoriert.

Fehlt sie, bleibt die Diagnose `unknown` und `copilot_usable = false`. Der nach Aufhebung des
Billing-Locks vom Nutzer ausdrücklich freizugebende einmalige Dispatch ist der Bootstrap- und
Live-Positivnachweis. Er gehört nicht zum read-only Probe und nicht zu Unit-Tests. Sein Ergebnis
kann anschließend als zeitlich begrenzte Capability-Evidenz verwendet werden.

### 3.4 Keine automatische Kontext-Erfindung

Der Probe bestimmt den Kontext review- und principalbezogen:

- manueller Review: anfordernder Benutzer ist der zunächst zu prüfende Billing-Principal;
- automatischer Review: PR-Autor ist der zunächst zu prüfende Billing-Principal;
- persönlicher Kontext: User-Usage-Endpunkt des Principals;
- Organisationskontext: Organisation-Usage und, bei ausreichenden Rechten, Sitz- oder
  Policy-Zuordnung;
- Enterprise-/Cost-Center-Kontext: nur bei explizit konfigurierter oder API-belegter Zuordnung;
- Legacy-Kontext: offizieller Premium-Request-Endpunkt als Kompatibilitätspfad.

Eine Organisationsmitgliedschaft und auch ein Seat-`404` beweisen weder persönlichen noch
organisatorischen Billing-Kontext. Eine Organisationsmitgliedschaft allein beweist keine
von dieser Organisation bezahlte
Copilot-Lizenz. Für Mitglieder ohne eigene Copilot-Sitzzuordnung kann Code Review je nach
Organisations-/Enterprise-Policy trotzdem der Organisation, dem Enterprise oder einem Cost Center
zugerechnet werden. Ist mehr als ein Principal möglich oder fehlen die Rechte zur Sitz-, Policy-
oder Billing-Prüfung, lautet der Principal `unknown`; die Route bleibt fail-closed.

Der typisierte `BillingPrincipal` enthält `kind`, `identifier`, `review_mode`, `requester`,
`pull_request_author`, `source`, `observed_at` und `expires_at`. Eine implizite Ableitung allein aus
dem Repository-Eigentümer ist unzulässig.

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
3. expliziten maschinenlesbaren Risikomarkern des Vorgangs.

Manuelle Marker dürfen Risiko erhöhen, nie automatisch senken. Fehlen erforderliche Diff-Daten
oder ist die Klassifikation widersprüchlich, gilt `critical`, nicht `low`.

Security-Relevanz ist zusätzlich ein eigenes boolesches Ergebnis
`security_relevant = true | false`. Jeder kritische Security-/Auth-/Secret-/Krypto-/
Protokollmarker setzt es auf `true`; ein expliziter Vorgangsmarker kann es nur einschalten, nie
ausschalten. `security_relevant = true` erzwingt SEC unabhängig von der numerischen Risikoklasse.
Damit kann eine kleine, aber sicherheitskritische Änderung nicht als bloßes `high` ohne SEC laufen.

Die konkreten Globs und Schwellen stehen ausschließlich in `core/review-routing.toml`. Kern,
Adapter, Templates und Python-Code duplizieren die Werte nicht.

Die Risikoeingabe ist ein geschlossenes `DiffSnapshot`-Schema Version 1:

```text
schema_version
repository
api_base_sha
merge_base_sha
head_sha
diff_mode = merge_base_to_head
rename_detection = disabled
copy_detection = disabled
files[]:
  path
  status = added | modified | deleted | renamed | copied
  previous_path          Pflicht bei renamed/copied, sonst verboten
  additions
  deletions
  binary
explicit_risk          optional, kann nur erhöhen
security_relevant     optional, true kann nur erhöhen
risk_reasons[]         optional, reine Evidenztexte ohne Steuerwirkung
```

Pflichtfelder sind Schema, Repository, alle drei SHAs, die drei Diffmodusfelder und für jede Datei
alle aufgeführten
Dateifelder. Pfade sind normalisierte relative POSIX-Pfade in Unicode-NFC: kein führender Slash,
kein `.`/`..`, kein Backslash, kein NUL und keine doppelte Darstellung desselben Pfads.
`additions`/`deletions` sind nichtnegative Ganzzahlen; Binärdateien tragen jeweils `0`.
Bei `renamed` und `copied` werden sowohl `previous_path` als auch `path` gegen alle Pfadmarker
klassifiziert; das Maximum beider Pfade gilt.

Abhängigkeits- und Blast-Radius-Metadaten gehören nicht zu Schema Version 1 und dürfen nicht
implizit erwartet werden. Sollen sie später die Route steuern, erfordert dies eine neue
Schema-Version mit vollständig geschlossenen Feldern. Fehlen in Version 1 **erforderliche**
Felder, wird der Snapshot als ungültig abgelehnt; die aufrufende Policy behandelt ihn fail-closed
wie `critical`. Optionale Felder werden nicht als heimliches `false` interpretiert.
Issue-/PR-Freitext ist keine vertrauenswürdige Risikoeingabe.

Jeder Pfadmarker in `core/review-routing.toml` ist ein geschlossenes Objekt aus `glob`, `level`
und `security_relevant`. Ein Marker ohne eines dieser Felder, mit einem unbekannten Feld oder
einem ungültigen Level macht die Policy ungültig. Damit sind Risikostufe und SEC-Auslösung
explizit, ohne im Klassifikator aus Dateinamen abgeleitet zu werden.

Ein geschlossenes Schema beweist noch keine Vollständigkeit. Deshalb akzeptiert `route` keine frei
gelieferte Diff-Datei als autoritative Eingabe. Ein `DiffSourcePort` liest den vollständigen
PR-Diff read-only aus dem lokalen Git-Objektbestand. Er übernimmt den `api_base_sha` und `head_sha`
aus dem `PullRequestStatePort`, berechnet `merge_base_sha = git merge-base api_base_sha head_sha`
und diffiert ausschließlich `merge_base_sha..head_sha`.

Der lokale Git-Adapter bindet `repo_path` an `repository`, indem er das kanonische Toplevel und
die normalisierte `origin`-URL gegen `OWNER/REPO` prüft. Fehlender/fremder Origin, abweichendes
Toplevel oder nicht vorhandene Commitobjekte sind für ein Gate ein Fehler. Er verwendet
`--no-ext-diff`, `--no-textconv`, `--no-renames` und NUL-delimitierte Raw-/Numstat-Ausgaben.
Heuristische Rename-/Copy-Erkennung ist damit bewusst deaktiviert: auch mehrdeutige oder
inhaltlich veränderte Verschiebungen erscheinen deterministisch als Delete+Add und beide Pfade
werden klassifiziert. Das Schema unterstützt `renamed`/`copied` für künftige verifizierte Quellen,
der Git-v1-Adapter emittiert diese Stati jedoch nicht.

`DiffSnapshot` und sein Digest enthalten `api_base_sha`, `merge_base_sha`, `head_sha`,
`diff_mode = merge_base_to_head`, `rename_detection = disabled`,
`copy_detection = disabled` und die normalisierte Repository-ID. Tests decken vorgerückte und
divergierte Base-Zweige sowie mehrdeutige Rename-/Copy-Kandidaten ab. Tests verwenden ansonsten
Fake-Ports; reale Tests lösen keine GitHub-Anfrage aus.

Der kanonische SHA-256-`diff_digest` des vollständigen `DiffSnapshot` wird in jede
`RouteDecision` übernommen. `validate` erhebt denselben Diff über den vertrauenswürdigen Port
erneut und nutzt injizierte `RiskClassifierPort`- und `RoutingPolicyPort`-Verträge zur erneuten
Klassifikation und Entscheidung. Es vergleicht Repository, SHAs, Digest, Risiko und
`security_relevant`. Route und Reviewer-Menge werden erstmals gate-fähig aus der erneut
erhobenen Probe sowie der tatsächlichen Coverage und dem tatsächlichen Reviewmodus berechnet,
nicht blind mit der vorläufigen Task-5-Menge verglichen. Eine ausgelassene Datei, ein versteckter
alter Rename-/Copy-Pfad, eine abweichende Klassifikation oder das unzulässige Entfernen
risiko-/security-/fallback-/correction-bedingter Reviewer macht das Gate ungültig.

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

Die folgenden Tabellen sind eine **nicht normative Designansicht**. Nach der Implementierung ist
`core/review-routing.toml` die einzige normative Matrix; jede menschenlesbare Darstellung wird aus
ihr generiert oder ausdrücklich als historischer Entscheidungsstand gekennzeichnet.

## 5. Entscheidungsmatrix

Deterministische lokale Tests und statische Prüfungen laufen in jedem Fall.

### 5.1 Checkpoint

| Risiko | Copilot nutzbar | Route |
|---|---:|---|
| `low` | `true` | `local_checks` |
| `medium` | `true` | `copilot` |
| `high` | `true` | `copilot_qa` |
| `critical` | `true` | `copilot_qa_sec` |
| `low`, `medium` oder `high` | `false` | `qa` |
| `critical` | `false` | `qa_sec` |

Damit entfällt die heutige pauschale QA nach jedem Cluster. Bei nutzbarem Copilot entscheidet das
Risiko, ob QA zusätzlich erforderlich ist. Bei nicht nutzbarem Copilot ist QA der einzige
Reviewpfad. `local_checks` ist ausschließlich bei `low` **und** positiv belegtem Copilot-Kontext
zulässig; bei `false/unknown` verlangt auch ein kleiner Checkpoint mindestens QA.

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

Für beide Tabellen gilt als überlagernde Invariante:

- `security_relevant = true` ergänzt SEC;
- nachweislich ausgeschlossene oder nicht verifizierbare Copilot-Dateiabdeckung ergänzt QA;
- ein degradierter oder unbekannter Copilot-Reviewmodus ergänzt QA;
- bei `copilot_usable = false` wird Copilot vollständig entfernt, niemals erneut versucht.

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
- Reviewmodus `full` statt `degraded`/`unknown`;
- vollständige Zuordnung aller Diff-Dateien zu `reviewed`, `excluded` oder `unverified`;
- keine Datei in `excluded` oder `unverified`, sofern die Route nicht zusätzlich QA verlangt;
- bei zusätzlich erforderlicher QA: QA deckt alle ausgeschlossenen/nicht verifizierbaren Dateien
  und ihre direkten Auswirkungen auf demselben Exact Head ab.

Der Validator bezeichnet dies als `valid_review_evidence`, nie als GitHub-`APPROVED`.
Serverseitige Erzwingung als Required Check ist Abhängigkeit von Issue #3 und nicht durch ein
lokales positives Ergebnis ersetzt.

GitHub schließt bestimmte Dateitypen von Copilot Code Review aus und kann bei nicht verfügbaren
Actions-Fähigkeiten degradiert prüfen. `COMMENTED + Exact Head + null Findings` beweist deshalb
allein keine vollständige Abdeckung. Kann der Validator die Abdeckung oder den Modus nicht positiv
belegen, wird Copilot-Evidenz nur als teilweise gewertet und die erforderliche Route um QA
erweitert. Fehlt anschließend die QA-Evidenz, bleibt das Gate rot.

Der Evidenzvertrag enthält pro Diff-Datei:

```text
path
status
coverage = reviewed | excluded | unverified
coverage_source = github_api | harness_runtime | unavailable
reviewer
```

sowie `copilot_review_mode = full | degraded | unknown` und
`review_mode_source = github_api | harness_runtime | unavailable`. Jede positive
`coverage_source` und `review_mode_source` ist an Repository, PR, Exact Head,
Beobachtungszeitpunkt und ihre konkrete maschinenlesbare Quellkennung gebunden. `unavailable`,
fehlende, fremde oder stale Quellen können weder `coverage_complete=true` noch `full` belegen.
Freitextkommentare werden nicht als Abdeckungs- oder Modusbeweis interpretiert.

### 7.3 Stabiler Gate-Vertrag

`validate` verarbeitet einen vollständigen `GateSnapshot`:

```text
repository
pull_request_number
base_sha
head_sha
check_runs
review_requests
reviews
review_file_coverage
copilot_review_mode
review_mode_source
threads
observed_at
valid_until
```

`GateSnapshot` ist die einzige autoritative Eingabe für per-Datei-Coverage und den tatsächlich
beobachteten Copilot-Reviewmodus. Der Validator leitet `coverage_complete` selbst ab: Jeder
Pfad/Status aus dem erneut erhobenen `trusted_diff` muss genau einmal im Snapshot erscheinen und
eine aktuelle, Exact-Head-gebundene `coverage_source` besitzen. Excluded oder unverified bleibt
für Copilot unvollständig und ergänzt QA; eine spätere QA-Validierung ersetzt nicht rückwirkend die
Copilot-Coverage. Der Validator leitet den Modus ausschließlich aus `copilot_review_mode` und
`review_mode_source` ab. Route-/Probe-Dateien dürfen weder Coverage noch Modus behaupten.
Repository/PR/Head des Snapshots müssen dem aktuellen PR-State entsprechen und
`observed_at <= evaluated_at < valid_until` gelten; damit sind auch seine Coverage-/Modusquellen
zeitlich und kontextuell gebunden.

Die Task-5-Datei wird in ein geschlossenes `PreliminaryRoutePlan` dekodiert:

```text
repository
pull_request_number
purpose
base_ref
base_sha
merge_base_sha
head_sha
pr_state_source
risk
security_relevant
policy_source_ref
policy_source_path
policy_digest
runtime_digest
runtime_trust
diff_digest
copilot_usable             untrusted preliminary
copilot_coverage_complete  untrusted preliminary
copilot_review_mode        untrusted preliminary
route                      untrusted preliminary
required_reviewers         untrusted preliminary
gate_status                untrusted preliminary
gate_eligible              untrusted preliminary
```

Fehlende oder unbekannte Felder machen die Datei ungültig. Die als `untrusted preliminary`
markierten Felder werden nur zur vollständigen Schema-/Auditdarstellung dekodiert und niemals in
den finalen `ReviewRequest` übernommen.

Die finale Auswertung erhält einen geschlossenen Kontext:

```text
GateEvaluationContext:
  preliminary_plan: PreliminaryRoutePlan
  current_pr_state: PullRequestState
  probe_request: ProbeRequest
  fresh_probe: ProbeReport
  reviewer_availability: ReviewerAvailabilitySnapshot
  evaluated_at: datetime
```

`validate` lädt zuerst den aktuellen PR-State, rekonstruiert aus den CLI-Kontextfeldern eine neue
`probe_request`, führt `ProbePort.probe()` genau einmal frisch aus und prüft `fresh_probe` gegen
Request-Digest, PR, Principal, Modus und `observed_at <= evaluated_at < valid_until`. Danach lädt
es die programmatic-only `reviewer_availability` genau einmal für Repository/PR/Head/Purpose.
Fremde oder stale Probe-/Availability-Evidenz erzeugt ein rotes Gate. Der in Task 5
serialisierte `probe_request_digest` allein ist nicht rekonstruierbar und keine Autorität.

Der formale Validator-Vertrag lautet:

```text
EvidenceValidatorPort.validate(
  context: GateEvaluationContext,
  evidence: GateSnapshot,
  runtime: RuntimeProvenance,
  trusted_config: RoutingConfig,
  trusted_diff: DiffSnapshot,
  risk_classifier: RiskClassifierPort,
  routing_policy: RoutingPolicyPort,
) -> GateResult
```

`validate_exact_head(...)` besitzt dieselben Parameter. Der Validator baut den finalen
`ReviewRequest` ausschließlich aus neu klassifiziertem Risiko, `fresh_probe.copilot_usable`,
abgeleitetem `coverage_complete`, abgeleitetem `copilot_review_mode` und aktueller
Reviewer-Verfügbarkeit und ruft die Policy erneut auf.

Die Namen und erwarteten Quellen aller Pflichtchecks stammen ausschließlich aus der geladenen
Basispolicy `core/review-routing.toml` am vollständigen `base_sha`. Für ein gate-fähiges Ergebnis
wird dieses SHA zusammen mit Base-Ref und Head-SHA read-only über einen `PullRequestStatePort` aus
der GitHub-PR-Metadatenquelle erhoben; der Aufrufer darf es nicht frei wählen. Sie sind kein Feld
externer Evidenz und werden niemals aus dem PR-Head geladen.
Jeder Policy-Eintrag bindet `name` und `source_app_slug`; ein gleichnamiger Check aus einer anderen
Quelle erfüllt die Pflicht nicht. Der Validator lehnt eine leere Pflichtcheckliste sowie unbekannte
oder doppelte Einträge bereits beim Laden der Policy ab.

Seine Ausgabe ist ein stabiles, publizierbares `GateResult`:

```text
check_name = agent-governance/review-gate
conclusion = success | failure
repository
pull_request_number
base_sha
head_sha
base_ref
pr_state_source
policy_source_ref
policy_source_path
policy_digest
runtime_digest
runtime_trust = installed | development
diff_digest
evidence_digest
required_reviewers
validated_reviewers
unresolved_thread_count
reasons
observed_at
```

Nur `success` ist positiv; `neutral`, `skipped`, `cancelled`, fehlend und unbekannt werden nicht
erzeugt beziehungsweise fail-closed als `failure` abgebildet. `policy_digest` bindet das Ergebnis
an die konkrete TOML-Policy, `evidence_digest` an den kanonisch serialisierten Snapshot.

`RoutingConfig.policy_digest` ist der SHA-256-Digest der kanonisch serialisierten, vollständig
validierten Policy. Für gate-fähige Routen lädt ein `PolicySourcePort` diese Policy read-only mit
`git show <api-erhobenes-base_sha>:core/review-routing.toml`; Arbeitsbaum, frei übergebene SHAs
und PR-Head sind keine Vertrauensquelle. Jede `RouteDecision` übernimmt Digest, vollständigen
Source-Commit, Base-Ref, PR-State-Quelle und Pfad.
`validate` lädt dieselbe Basispolicy erneut und verwirft abweichende oder fehlende Provenienz.
Dadurch kann weder der PR selbst noch ein Route-/Evidence-JSON Pflichtchecks, Quellen oder
Routingregeln abschwächen.

Ändert ein PR die Policy, bleibt für sein Gate die Basispolicy maßgeblich; die Kandidatenpolicy
wird zusätzlich streng geparst und getestet, aber erst nach Merge zur Basispolicy eines
Folge-PRs. Für den einmaligen Bootstrap dieses PRs existiert am Base-SHA noch keine Policy.
Deshalb darf das neue Werkzeug für PR #5 selbst keinen positiven publizierbaren `GateResult`
behaupten und liefert `trusted_base_policy_missing`. Die Bootstrap-Freigabe erfolgt nach dem
bisherigen Kernvertrag durch unabhängige Exact-Head-Reviews und die explizite Mergeentscheidung
des Nutzers. Erst ein späterer PR kann den neuen Gate-Vertrag vollständig gegen eine geschützte
Basispolicy ausführen.

Solange Issue #3 Base-Branch-Schutz, erwarteten Base-Ref und Publisher-App noch nicht technisch
erzwingt, ist auch ein API-erhobener Base-SHA nur lokale Validierungsevidenz, kein veröffentlichter
Required Check. Der spätere Publisher muss Base-Ref und Protection/Ruleset gegen seine
außerhalb des PR-Heads verwaltete App-Konfiguration prüfen. Ein Offline-Aufruf mit expliziten SHAs
ist ausschließlich diagnostisch und trägt `gate_eligible = false`.

`PreliminaryRoutePlan` wird aus Task 5 nur als Provenienzvergleich eingelesen. Verglichen werden
Repository/PR/Purpose, Base-/Head-/Merge-Base-SHAs, Policy-/Runtime-/Diff-Provenienz und -Digests
sowie Risiko/Security. Seine Werte für Usability, Coverage, Reviewmodus, Route, Reviewer,
Gate-Status und Gate-Fähigkeit sind ausdrücklich keine Validierungsautorität und dürfen die finale
Policyentscheidung nicht beeinflussen. Der externe `GateSnapshot` enthält keine zweite,
potenziell abweichende Routingentscheidung.

Der read-only Lieferumfang gibt dieses Ergebnis nur als JSON aus. Ein typisierter
`GatePublisherPort` legt den späteren Übergabevertrag fest:

```text
publish(result: GateResult) -> PublicationReceipt
```

`PublicationReceipt` enthält Repository, PR, Head-SHA, Checkname, Publisher-App-Slug,
Publication-ID, Idempotenzschlüssel und Veröffentlichungszeit. Der Idempotenzschlüssel ist der
SHA-256-Digest aus Repository, PR, Head-SHA, `runtime_digest`, `policy_digest` und
`evidence_digest`. Vor jedem
Schreibvorgang muss der spätere Publisher den aktuellen PR-Head erneut read-only abfragen und
bei Abweichung ohne Veröffentlichung abbrechen. Als vertrauenswürdige Publisher-Quelle ist eine
dedizierte, in der Policy festgelegte GitHub-App vorgesehen; ein lokaler Benutzer-Token oder
beliebiger Workflow gilt nicht automatisch als gleichwertig.

Dieser PR definiert Port und Receipt, besitzt aber bewusst keine schreibende Implementierung.
Issue #3 verantwortet GitHub-App, Installation, Required-Check-Regel und Publication-Receipt-
Persistenz. Das lokale Ergebnis wird niemals als bereits veröffentlichter Required Check
bezeichnet.

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
python3 -m review_routing probe \
  --repo OWNER/REPO \
  --review-mode manual \
  --requester USER \
  --capability-reference CAPABILITY-REFERENCE.json \
  --json
python3 -m review_routing probe \
  --repo OWNER/REPO \
  --review-mode automatic \
  --pull-request NUMBER \
  --capability-reference CAPABILITY-REFERENCE.json \
  --json
python3 -m review_routing route \
  --repo OWNER/REPO \
  --pull-request NUMBER \
  --review-mode manual \
  --requester USER \
  --capability-reference CAPABILITY-REFERENCE.json \
  --purpose final_exact_head \
  --repo-path /absolute/path/to/checkout \
  --json
python3 -m review_routing validate \
  --route-file ROUTE.json \
  --evidence-file EVIDENCE.json \
  --repo OWNER/REPO \
  --pull-request NUMBER \
  --review-mode manual \
  --requester USER \
  --organization ORG \
  --enterprise ENTERPRISE \
  --cost-center COST_CENTER \
  --capability-reference CAPABILITY-REFERENCE.json \
  --repo-path /absolute/path/to/checkout \
  --json
python3 -m review_routing validate \
  --route-file ROUTE.json \
  --evidence-file EVIDENCE.json \
  --repo OWNER/REPO \
  --pull-request NUMBER \
  --review-mode automatic \
  --capability-reference CAPABILITY-REFERENCE.json \
  --repo-path /absolute/path/to/checkout \
  --json
python3 -m review_routing output-policy --json
```

Bei `manual` ist `--requester` Pflicht; bei `automatic` wird der PR-Autor read-only aus dem
angegebenen PR ermittelt. Eine Capability-Referenz ist ausschließlich ein nicht
vertrauenswürdiges Operator-Artefakt. Der CLI besitzt keine Flags für Quelle, Trust, Issuer,
Pin-Quelle oder erwartete Digests. `OperatorEvidenceTrustPort` wird ausschließlich programmatisch
über `CliDependencies` injiziert. `RuntimeRegistry.bootstrap` übernimmt exakt diese Instanz und
verdrahtet sie in Capability-Verifier, Block-Verifier und Probe; kein Adapter-Fallback darf sie
ersetzen. Die normale Source-Checkout-CLI besitzt keine Pins. Fehlt die Referenz, scheitert ihre
Verifikation oder passt Principal/Repository/Reviewmodus nicht, bleibt `copilot_usable = false`.

`route` akzeptiert kein zuvor geschriebenes Probe-JSON als Autorität. Der Befehl lädt zuerst den
aktuellen PR-State, bindet daraus Repository und PR an eine neue `ProbeRequest`, ruft
`ProbePort.probe()` genau einmal auf und akzeptiert den Report nur bei identischem
`request_digest`, PR, Principal, Reviewmodus und aktueller Gültigkeitszeit. `--probe-file`,
`--qa-available` und `--sec-available` sind ungültig. QA-/SEC-Verfügbarkeit stammt ausschließlich
aus einem programmatisch injizierten `ReviewerAvailabilityPort`; fehlende, abgelaufene, fremde,
`unavailable`- oder `unknown`-Evidenz gilt als nicht verfügbar.

`validate` verlangt denselben vollständigen aktuellen Probe-Kontext wie `route`. Es lädt erneut
den aktuellen PR-State, baut daraus eine neue `ProbeRequest`, führt `ProbePort` genau einmal
frisch aus, prüft Request-Digest, PR, Principal, Modus und TTL und lädt anschließend
`ReviewerAvailabilityPort` programmatic-only für den aktuellen Exact Head und Purpose. Die
Task-6-`CliDependencies` nennen deshalb ausdrücklich `ProbePort`, `PullRequestStatePort`,
`ReviewerAvailabilityPort` und `ClockPort` neben den bereits benötigten Trust-/Policy-/Diff-Ports.
Die Route-Datei und ihr `probe_request_digest` können diesen Kontext weder rekonstruieren noch
autorisieren.

Der Composition Root löst Ports ausschließlich über die generische Runtime-Registry auf. Policy
und Risikoklassifikation kennen weder `gh` noch HTTP; `__main__.py` importiert keine
Adapterimplementierung.

### 9.2 Probe-JSON

```json
{
  "schema_version": 1,
  "observed_at": "2026-07-26T00:00:00Z",
  "repository": "owner/repository",
  "pull_request_number": null,
  "request_digest": "sha256:...",
  "valid_until": "2026-07-26T00:05:00Z",
  "review_mode": "manual",
  "requester": "requester",
  "pull_request_author": null,
  "billing_principal": {
    "kind": "personal",
    "identifier": "requester",
    "source": "github_api",
    "observed_at": "2026-07-26T00:00:00Z",
    "expires_at": "2026-07-26T00:15:00Z"
  },
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
    "billing_status": null,
    "usage_status": "available",
    "provider_status": "available",
    "api_status": "available"
  },
  "routing_status": "unknown",
  "copilot_usable": false,
  "capability_evidence": {
    "status": "absent",
    "artifact_kind": null,
    "expires_at": null,
    "source": null,
    "source_reference": null,
    "artifact_digest": null,
    "trust": "unverified",
    "pin_source": null
  },
  "block_evidence": {
    "status": "absent",
    "kind": null,
    "source": null,
    "source_reference": null,
    "artifact_digest": null,
    "trust": "unverified",
    "pin_source": null
  },
  "evidence": [],
  "warnings": []
}
```

`remaining` ist nur eine Zahl, wenn `used` und das tatsächlich geltende `limit` belastbar bekannt
sind. Das Feld beeinflusst `copilot_usable` und die Route nicht.
`capability_evidence.status` wird ausschließlich aus der geschlossenen
`CapabilityVerification` abgeleitet. Es existiert kein zweites setzbares Statusfeld; Trust,
Evidenzpräsenz und ein positiver `copilot_usable`-Wert müssen konstruktiv zur Verification passen.

### 9.3 Route-JSON

```json
{
  "schema_version": 1,
  "purpose": "final_exact_head",
  "pull_request_number": 5,
  "base_ref": "main",
  "base_sha": "BASE",
  "merge_base_sha": "MERGE_BASE",
  "head_sha": "HEAD",
  "risk": {
    "level": "high",
    "security_relevant": false,
    "reasons": ["high_changed_lines"]
  },
  "copilot_usable": true,
  "copilot_coverage_complete": null,
  "copilot_review_mode": "unknown",
  "probe_request_digest": "sha256:...",
  "probe_observed_at": "2026-07-26T00:00:00Z",
  "probe_valid_until": "2026-07-26T00:05:00Z",
  "required_reviewers": ["copilot", "qa"],
  "route": "copilot_qa",
  "policy_source_ref": "BASE",
  "policy_source_path": "core/review-routing.toml",
  "policy_digest": "sha256:...",
  "runtime_digest": "sha256:...",
  "runtime_trust": "installed",
  "diff_digest": "sha256:...",
  "diff_mode": "merge_base_to_head",
  "rename_detection": "disabled",
  "copy_detection": "disabled",
  "decision_stage": "preliminary",
  "gate_status": "evidence_validation_pending",
  "gate_eligible": false,
  "merge_evidence_required": true,
  "dispatch_permitted": false
}
```

Task 5 kennt weder Exact-Head-Dateiabdeckung noch den tatsächlich erreichten Copilot-Reviewmodus.
Deshalb bleiben `copilot_coverage_complete = null`, `copilot_review_mode = unknown`,
`decision_stage = preliminary`, `gate_status = evidence_validation_pending`,
`gate_eligible = false` und `dispatch_permitted = false`. Die Ausgabe ist ein konservativer Plan,
keine Freigabe zum Auslösen kostenpflichtiger Reviews und kein Gate-Ergebnis.

Task 6 erhebt PR-State, Basispolicy, vollständigen Diff, Risiko, frische Probe, Dateiabdeckung und
Reviewmodus erneut und trifft damit die erste gate-fähige Policyentscheidung. Sie vergleicht die
gebundene Provenienz, SHAs, Digests und das neu berechnete Risiko, übernimmt aber nicht blind die
vorläufige Task-5-Reviewer-Menge. QA darf nur entfallen, wenn sie dort ausschließlich wegen
unbekannter Coverage beziehungsweise unbekanntem Modus hinzukam und Task 6
`coverage_complete=true` sowie `full` belegt; Risiko-, Security-, Fallback- und Correction-QA
bleibt erhalten.

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

Eine separat verifizierte Quoten-/Budgetblockade ist eine erfolgreiche Probe und liefert `0`, obwohl
`copilot_usable = false` gilt. Das setzt voraus, dass die Blockade von einer erfolgreich
abgerufenen autoritativen Quelle stammt. Liegt zusätzlich oder stattdessen nur Operator-Evidenz
vor, während eine erforderliche API wegen fehlender Rechte nicht geprüft werden konnte,
überschreibt der technische Fehler die Cacheentscheidung: `routing_status = permission_denied`,
`copilot_usable = false` und Exitcode `20`. Die verifizierte Blockevidenz bleibt separat im JSON
nachvollziehbar.

Route:

| Code | Bedeutung |
|---:|---|
| `0` | Deterministische Route gewählt |
| `30` | Erforderlicher unabhängiger Reviewer nicht verfügbar (`blocker`) |
| `31` | Policy, Probe, Diffquelle oder Eingabe ungültig; schließt fehlende Basispolicy ein |
| `32` | Exact-Head-Evidenz fehlt oder ist veraltet |

`validate` ist die read-only Brücke zwischen gewählter Route und Merge-Gate-Evidenz. Der Befehl
lädt frische Probe und Reviewer-Verfügbarkeit, die Policy vom Base-Commit, erhebt und
klassifiziert den Git-Diff erneut und leitet Coverage/Modus aus `GateSnapshot` samt ihrer
gebundenen Quellen ab. Er berechnet die finale Route neu und validiert erst danach erforderliche
Reviewer, CI-Checks, Threads, SHAs und Digests. Task-5-Usability, -Route und -Reviewer-Menge
bleiben untrusted Vorplanfelder. Der Befehl schreibt keinen Check-Run und erteilt keine
GitHub-Freigabe. `output-policy` liest ausschließlich `core/interaction.toml`.

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
  runtime.toml
  registry.py
  policy.py
  risk.py
  evidence.py
  adapters/
    __init__.py
    git_cli.py
    github_gh.py
    toml_config.py
tests/
  fixtures/review-routing/
  test_review_routing_contracts.py
  test_review_routing_policy.py
  test_review_routing_risk.py
  test_review_routing_github.py
  test_review_routing_cli.py
```

- `contracts.py`: **einziges Vertragsmodul** für sämtliche Ports, Domänen-, Konfigurations-,
  Evidenz- und Fehlertypen; ohne Import aus einem anderen Projektmodul.
- `runtime.toml`: separate, installations-/publisherseitig gebundene Bootstrap-SSOT für die
  unveränderliche Port→Factory-Auswahl; enthält keine Routingwerte.
- `registry.py`: generische Laufzeitregistrierung und Factory-Auflösung; kennt nur das
  Vertragsmodul sowie die aus der installierten Bootstrap-SSOT geladenen Modulnamen.
- `policy.py`: reine Routingfunktion.
- `risk.py`: reine Risikoklassifikation aus TOML und Diff-Metadaten.
- `evidence.py`: reine Exact-Head-/Reviewer-/Check-/Thread-Validierung.
- `git_cli.py`: vollständige read-only Diff- und Policy-Erhebung aus Commitobjekten.
- `github_gh.py`: einziger Ort für GitHub-Endpunkte, `gh` und HTTP-Klassifikation.
- `toml_config.py`: strikte TOML-Implementierung des Konfigurationsports.
- `__main__.py`: Composition Root und CLI; importiert keine Adapterimplementierung.
- `core/review-routing.toml`: einzige Quelle für Matrix, Schwellen und Risikomarker.
- `core/interaction.toml`: einzige Quelle für den Zwischenstatus-Schalter.

`RiskClassifierPort` und `RoutingPolicyPort` liegen wie alle anderen Ports in `contracts.py`.
`evidence.py` importiert weder `risk.py` noch `policy.py`, sondern erhält beide Implementierungen
injiziert. Damit bleibt die erneute Gate-Klassifikation real, ohne die Importblindheit der
Architektur zu brechen.

Analog bieten `evidence.py` und `output_policy.py` ihre Funktionen über
`EvidenceValidatorPort.validate(...)` beziehungsweise `OutputPolicyPort.decide(...)` an. Nur
dadurch dürfen ihre Factories in der Runtime-SSOT erscheinen.

Keine Routingwerte werden in Kernprosa, Adaptern oder Templates kopiert. Diese Stellen benennen
nur Invarianten und verweisen auf die Policy.

`review_routing/runtime.toml` enthält die geschlossene Liste registrierbarer Adaptermodule und die
Priorität je Port. `registry.py` lädt sie als Paketressource über `importlib.resources` und lädt die
Factories danach über `importlib`; jedes Adaptermodul meldet benötigte/angebotene Ports an. Die
Composition Root ruft nur die generische Registry auf und nennt `GitHubGhProbe` oder `TomlConfig`
nirgends.

Die Routing-Policy darf keinen `[runtime]`-Abschnitt enthalten. Eine Head-Änderung der
Routing-Policy kann daher niemals Policy-/Diff-Quellen austauschen. Gate-fähige Ausführung setzt
eine installierte, publisherseitig digest-gebundene Runtime-Ressource voraus. Ein externer
`RuntimeTrustPort` liefert dafür:

```text
RuntimeTrustConfig:
  expected_runtime_digest
  source = publisher_app | installed_config | development
  observed_at
```

`runtime_trust = installed` entsteht ausschließlich, wenn der berechnete Manifest-Digest mit dem
externen `expected_runtime_digest` übereinstimmt und die Quelle `publisher_app` oder
`installed_config` ist. Ein fehlender Pin ergibt `development`; ein vorhandener, aber abweichender
Pin ist ein harter Konfigurationsfehler. Dieser PR liefert bewusst keine vertrauenswürdige
Publisher-Implementierung des Ports. Tests injizieren Fake-Trust-Konfigurationen; der spätere
Publisher aus Issue #3 stellt den echten Port außerhalb des PR-Artefakts bereit.

Für die reale lokale CLI existiert ein zirkelfreier Default: `RuntimeRegistry.bootstrap(None)`
erzeugt intern ausschließlich `RuntimeTrustConfig(source=development,
expected_runtime_digest=None)`. Diese Development-Quelle ist keine Factory und kein externer
Adapter; sie kann niemals `installed` oder `gate_eligible=true` erzeugen. Ein Publisher darf einen
vertrauenswürdigen `RuntimeTrustPort` ausschließlich über die programmatische
`CliDependencies`-Grenze injizieren; es gibt bewusst keinen CLI-Schalter, mit dem ein Benutzer
`installed` behaupten kann.

Ausführung direkt aus einem PR-Checkout wird als `runtime_trust = development` und
`gate_eligible = false`
gekennzeichnet. Issue #3/#7 verantworten später signiertes/publiziertes Artefakt und Publisher-
Digest; PR #5 liefert lokale Funktionalität und die vollständigen Verträge, behauptet aber keine
Selbstbeglaubigung seines eigenen Codes.

Ein AST-basierter Architekturtest erzwingt:

- außer `contracts.py` importiert kein Fach-/Adaptermodul ein anderes Fach-/Adaptermodul;
- `policy.py`, `risk.py`, `evidence.py` und Adapter importieren projektintern ausschließlich
  `review_routing.contracts`;
- `__main__.py` kennt nur `contracts` und `registry`, keine Adapter;
- alle Factory-Module stammen aus `review_routing/runtime.toml`;
- `core/review-routing.toml` mit einem injizierten `[runtime]`-Abschnitt wird abgelehnt;
- fehlende, konkurrierende oder zyklisch abhängige Provider werden typisiert und fail-closed
  gemeldet.

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

Mechanisch beweisbar sind Schema, Defaultwert, Parser, fail-closed Validierung sowie die
Verdrahtung in Kern, Adaptern und Einstiegsvorlagen. Ob ein fremder Harness freiwillige
Zwischenmeldungen tatsächlich vollständig unterdrückt, bleibt eine Harness-Fähigkeit und wird
nicht durch einen Python-Unit-Test vorgetäuscht. Ein nicht durchsetzender Harness muss die
Abweichung offen melden.

Damit der Wert vor der ersten freiwilligen Zwischenmeldung bekannt ist:

- Claude-Einstieg importiert `core/interaction.toml`;
- Codex-Einstieg weist dessen vollständiges Lesen als erste Sessionaktion an;
- Install-Prompt und Template-Zuordnung übernehmen die zusätzliche Datei;
- Drift-Tests erzwingen, dass alle Einstiegsvorlagen dieselbe SSOT laden.

### 11.1 Harness-Fähigkeiten und Abnahme

| Harness | Ladepfad | Durchsetzung | Ehrliche Zusage |
|---|---|---|---|
| Claude Code | `@`-Import der TOML plus Adapterregel | promptbasiert/best-effort | freiwillige Meldungen unterdrücken; native/systemische Ausgaben bleiben möglich |
| Codex | verpflichtende erste Leseaktion plus Adapterregel | promptbasiert/best-effort | freiwillige Meldungen unterdrücken; App-/System-Updates bleiben möglich |
| MCP-Orchestrator | explizite Übergabe des validierten Werts an den gestarteten Agenten | abhängig vom Zielharness | Fähigkeit muss gemeldet werden; unbekannt ist nicht „greift“ |
| anderer Harness | neuer Adapter nach Port-Vertrag | zunächst unbekannt | bis zum positiven Harness-Test nur advisory |

Messbare Akzeptanzfälle je unterstütztem Harness:

1. `false`, triviale toolgestützte Aufgabe ohne Blocker: keine freiwillige Fortschrittsmeldung,
   genau ein Abschluss.
2. `false`, fehlende notwendige Entscheidung: genau die erforderliche Rückfrage bleibt sichtbar.
3. `false`, Fehler/Sicherheitsbefund: Befund und Abschluss bleiben sichtbar.
4. `true`, gleiche triviale Aufgabe: normales Harness-Zwischenverhalten ist zulässig.
5. ungültige/fehlende TOML: fail-closed kein freiwilliger Status; Konfigurationsfehler wird an einer
   verpflichtenden Ausgabegrenze gemeldet.

Parser, Default, Template-Wiring und ein simulierter Message-Policy-Entscheider werden automatisiert
getestet. Die echten Claude-/Codex-Fälle sind nach Installation als Harness-Akzeptanztests zu
protokollieren. Bis dahin lautet der Status `best_effort`, nicht „vollständig nativ erzwungen“.
Issue #4 und die PR-Beschreibung verwenden dieselbe Abgrenzung.

## 12. Teststrategie

Alle GitHub-Antworten werden als lokale Fixtures oder Fake-Port-Antworten bereitgestellt. Kein Test
ruft GitHub auf oder löst ein Review aus.

Mindestens:

1. AI-Credit-Usage verwendet `grossQuantity`; freie Usage-Felder `status`/`limit` werden nicht
   als Routing- oder Budgetevidenz übernommen.
2. AI Credits ohne separate autoritative Budgetquelle; `limit = remaining = null`.
3. Legacy Premium Requests.
4. Extern gepinntes Operator-Artefakt für ausgeschöpftes Kontingent →
   `copilot_usable = false`.
5. Extern gepinntes Operator-Artefakt für blockiertes Budget → `false`.
6. `low_budget`, aber tatsächlich nutzbar → `true`, identische Route wie `available`.
7. Rate Limit → `false`, Exitcode `21`.
8. Provider-Ausfall → `false`, Exitcode `22`.
9. Fehlende Berechtigung → `false`, Exitcode `20`.
10. Leere Antwort → `unknown`, Exitcode `24`.
11. Unvollständige Antwort → `unknown`, Exitcode `24`.
12. Unbekannter Abrechnungskontext → `unknown`, Exitcode `23`.
13. Organisationsmitgliedschaft oder Seat-`404` ohne Sitzbeleg erzeugt weder Organisations- noch
    persönlichen Fallbackkontext.
14. Manuell versus automatisch bestimmt Requester beziehungsweise PR-Autor als Principal.
15. Mehrdeutiger oder nicht belegbarer Billing-Principal → `unknown`.
16. Abgelaufene, fremde, ungepinnte oder fehlende Capability-Referenz → nicht nutzbar und niemals
    `trust=verified`.
17. Von einem Verifier aus `operator_setting` oder `completed_review_context` rekonstruierte
    Capability mit geschlossenem Source-/Digest-/`pin_source`-Nachweis und passendem
    Principal/Repo/Modus → nutzbar.
18. Ein GitHub-Review allein ist keine Capability; `completed_review_context` wird erst nach
    erfolgreichem externem Pin gegen Bot, `COMMENTED`, PR, Review-ID, Commit und Zeitpunkt
    revalidiert.
19. Dasselbe API-Review kann nicht für einen anderen Principal oder Reviewmodus positiv werden.
20. Capability- und Block-Verifierfehler besitzen dieselbe Routing-Priorität wie übrige
    Permission-, Rate-, Provider-, Timeout- und Malformed/Incomplete-Fehler.
21. API-/Provider-Blockquellen und `bool` als Schema- oder PR-ID werden fail-closed abgelehnt;
    eine API-Review-ID ist nur bei `type(id) is int` gültig; eine Actions-Billing-Lock-Annotation
    ist kein Copilot-Block.
22. Checkpoint-Matrix für alle vier Risiken und beide Verwendbarkeitswerte; `false` verlangt
    ausnahmslos QA.
23. Final-Matrix für alle vier Risiken und beide Verwendbarkeitswerte.
24. Security-Relevanz erzwingt SEC unabhängig von Diff-Größe/Risikoklasse.
25. Ausgeschlossene, unverified oder degradierte Copilot-Abdeckung erzwingt QA.
26. Korrekturrunde behält erforderliche Reviewer und ersetzt unbrauchbaren Copilot durch QA.
27. Kein Copilot-Retry bei `false`.
28. Fehlender verpflichtender QA-/SEC-Kontext → `blocker`.
29. QA-Kosten können verpflichtende Reviewer nicht entfernen.
30. Exact-Head-Mismatch → keine gültige Evidenz, Exitcode `32`.
31. Copilot-`COMMENTED` mit korrektem Head, voller Abdeckung und null Findings → gültige
    technische Evidenz.
32. Copilot-`COMMENTED` auf altem Head, mit offenem Finding oder ohne Abdeckungsbeleg → ungültig.
33. GateResult enthält stabilen Checknamen, Runtime-/Basispolicy-Quelle,
    Runtime-/Policy-/Diff-/Evidenzdigest und vollständige Provenienz.
34. Kein Mergepfad ohne vollständige Exact-Head-Reviewer-Menge.
35. Versioniertes Diff-Schema, Pfadnormalisierung, Rename-/Copy-Quellpfad und fehlende
    Pflichtfelder fail-closed.
36. Registry löst Provider aus SSOT auf; Composition Root bleibt importblind.
37. Secret-/Header-/Tokenwerte erscheinen nicht in JSON oder Fehlermeldungen.
38. `intermediate_status = false` ist der Repository-Default.
39. Ungültiger/nicht-boolescher Ausgabewert fällt fail-closed.
40. Simulierter Message-Policy-Entscheider erhält Rückfragen/Blocker/Fehler/Abschluss.
41. Kern, Policy, Adapter, Templates, README und Installationsanleitung bleiben driftfrei.
42. Bestehende 25 Governance-Tests bleiben grün.
43. Policyänderung nur am PR-Head schwächt die Basispolicy nicht ab.
44. Fehlende Basispolicy im Bootstrap erzeugt keinen positiven GateResult.
45. Vollständiger Git-Diff enthält Add/Modify/Delete; vorgerückte/divergierte Base-Zweige nutzen
    Merge-Base→Head, mehrdeutige Rename-/Copy-Kandidaten werden als Delete+Add klassifiziert.
46. Fehlende/zusätzliche/veränderte Diff-Datei oder abweichender `diff_digest` macht das Gate
    ungültig.
47. Validate klassifiziert den vertrauenswürdig erhobenen Diff erneut, vergleicht Risiko und
    Security-Flag exakt und berechnet Route/Reviewer mit echter Coverage und echtem Reviewmodus
    neu; nur ausschließlich vorläufige Coverage-/Mode-QA darf bei positivem Vollbeleg entfallen.
48. Gate-fähige Route übernimmt Base-Ref/Base-SHA/Head-SHA aus PR-Metadaten und verwirft
    caller-selektierte SHAs.
49. Wechsel von Base-Ref oder Head zwischen Route und Validate macht die Evidenz ungültig;
    Offline-SHAs bleiben ausdrücklich `gate_eligible = false`.
50. Eine `[runtime]`-Injection in der PR-Head-Policy wird abgelehnt und kann Policy-/Diff-Adapter
    nicht austauschen; nur die installierte Runtime-Bootstrap-SSOT bestimmt Factories.
51. Fehlender externer Runtime-Pin bleibt `development`; passender publisher-/installationsseitiger
    Pin wird `installed`; abweichender Pin ist ein harter Fehler.
52. Nach jedem Factory-Slice löst die inkrementell aktualisierte Runtime-SSOT alle bis dahin
    angebotenen/benötigten Ports vollständig und zyklusfrei auf.
53. Lokale CLI ohne injizierten Trust-Port bleibt deterministisch `development`; kein CLI-Argument
    kann `installed` vortäuschen.
54. Evidence-Validator und Output-Policy werden über ihre typisierten Ports aufgelöst; GitHub-
    Command/Status/Clock/Probe/PR-State-Fakes erfüllen exakt die geschlossenen Signaturen.
55. Registry-Bootstrap erhält die Identität eines injizierten `OperatorEvidenceTrustPort` bis in
    beide Verifier und einen positiven, vollständig gefakten Registry-Level-Probe.
56. `ProbeReport` leitet Capability-Status aus der Verification ab und lehnt
    `dataclasses.replace`-Mismatchfälle für Status, Trust, Evidenz, Präsenz und Verwendbarkeit ab.

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

Die unabhängige ST-Bereitschaftsprüfung hat außerdem zwei getrennte Bestandsdefekte bestätigt:

- Issue #6: CI-Testumfang, Pflichtstages und Nachweisartefakte erfüllen Kern §11/§13 noch nicht.
- Issue #7: SemVer-Quelle, CHANGELOG, Tags/Releases erfüllen Kern §12 noch nicht.

Beide bleiben außerhalb von Issue #4/PR #5. Dieser PR kann seinen eigenen Funktionsumfang
vollständig liefern, darf aber die gesamte Agent-Governance erst nach Abschluss von #3, #6 und #7
als vollumfänglich einsatzbereit bezeichnen.

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
