# ADR 0003: Deterministisches Review-Routing aus zentraler Policy

Status: angenommen · Datum: 2026-07-26

## Kontext

Review-Routen müssen aus Reviewzweck, Risikoklasse und einer belastbar festgestellten binären
Copilot-Verwendbarkeit entstehen. Verbrauchs- und Billinginformationen sind diagnostisch wichtig,
dürfen aber keine Route aus einem geschätzten Restbudget ableiten. Gleichzeitig muss ein
Copilot-`COMMENTED`-Review als technische Evidenz prüfbar sein, ohne ihn fälschlich als
GitHub-`APPROVED` zu bezeichnen.

## Entscheidung

`core/review-routing.toml` ist die einzige normative Quelle für Diff-Schwellen, Pfadmarker,
Routingmatrix und Gate-Check-Identitäten. Die Policy nimmt ausschließlich `copilot_usable` als
binäre Routing-Eingabe an. Diagnosestatus wie `low_budget`, `budget_blocked` oder
`permission_denied` bleiben als getrennte Evidenz erhalten. Es gibt weder eine `remaining`-
Berechnung als Routing-Eingabe noch eine Budgetreservierung.

Usage ist ausschließlich eine Verbrauchsmessung (`grossQuantity`). Freie Felder wie `status`
oder `limit` in einer Usage-Antwort sind weder Capability- noch Blockadeevidenz. Routingfähige
Capability entsteht nur durch `CapabilityEvidenceVerifierPort` aus einem Operator-Artefakt,
dessen kanonischer Digest extern durch Publisher-App beziehungsweise installierte Konfiguration
gepinnt ist. Der geschlossene Artefakttyp ist `operator_setting` oder
`completed_review_context`. Ein abgeschlossenes GitHub-Review allein bindet weder Principal noch
Reviewmodus und ist keine Capability. Nur ein zuvor gepinntes `completed_review_context` darf das
Review anschließend read-only gegen Bot, `COMMENTED`, PR, Review-ID, Commit und Zeitpunkt
revalidieren. Der Caller liefert nur eine nicht vertrauenswürdige Referenz und kann Quelle, Trust,
Issuer, `pin_source` oder den erwarteten Digest nicht setzen.

`BlockEvidenceVerifierPort` rekonstruiert Quoten-, Account- oder Budgetblockaden getrennt aus
ausschließlich extern gepinnter Operator-Evidenz. Provider-/API-Antworten und
Actions-Billing-Lock-Annotationen sind keine Copilot-Blockadeevidenz. `OperatorEvidenceTrustPort`
liefert den Pin ausschließlich programmatisch über `CliDependencies`; die Source-Checkout-CLI
kennt keine Pins und besitzt keine Trust-/Digest-Override-Flags. Verifizierte Evidenz trägt
zwingend `pin_source=publisher_app|installed_config`; abwesende, ungültige und abgelaufene Evidenz
bleibt `unverified`. `RuntimeRegistry.bootstrap` verdrahtet exakt die injizierte Trust-Port-Instanz
in beide Verifier und den daraus gebauten Probe. Der öffentliche Capability-Status wird
ausschließlich aus `CapabilityVerification` abgeleitet und ist kein unabhängig setzbares Feld.
Eine gleich alte oder neuere verifizierte Blockade schlägt eine Capability;
ein danach abgeschlossenes Review schlägt die ältere Blockade. Technische Permission-, Rate- und
Providerfehler, auch aus den beiden Verifiern, haben Vorrang vor beiden Caches. Abgelaufene Evidenz
bleibt ohne Routingwirkung.

Ein Copilot-Review kann ausschließlich als `valid_review_evidence` gelten, wenn es als
`COMMENTED` auf dem Exact Head vollständig und ohne offene Findings belegt ist; es ist keine
GitHub-Freigabe. Unklare, degradierte oder ausgeschlossene Abdeckung ergänzt unabhängig von der
Risikoklasse den erforderlichen QA-Anteil.

Probe und Route bleiben read-only. Sie fordern keine Reviews an, veröffentlichen keinen
Check-Run und ändern weder GitHub- noch lokale Konfigurationszustände. Die paketierte
`review_routing/runtime.toml` ist getrennt von der Policy die einzige Bootstrap-Quelle für
Adaptermodule. Eine externe, passende Publisher-/Installations-Pinbindung kann diese Runtime als
`installed` ausweisen; ein Source-Checkout bleibt `development` und damit nicht gate-fähig.
Ein Organisations-Seat-`404` oder eine bloße Mitgliedschaft erzeugt keinen persönlichen
Fallbackkontext, sondern `unknown`.

Eine gespeicherte Probe-Ausgabe ist Diagnose und niemals Routingautorität. `route` lädt zuerst den
aktuellen PR-State, erzeugt daraus eine vollständig digest-gebundene `ProbeRequest`, führt den
Probe-Port genau einmal frisch aus und prüft den Report gegen Request, PR, Principal, Reviewmodus
und Gültigkeitszeit. Reviewer-Verfügbarkeit für QA und SEC wird ausschließlich über aktuelle,
Exact-Head- und Purpose-gebundene `ReviewerAvailabilityPort`-Evidenz aus dem Harness bestimmt;
CLI-Flags oder Umgebungsvariablen dürfen sie nicht behaupten.

Die Task-5-Route ist ausdrücklich `preliminary`: Coverage ist unbekannt, der Copilot-Reviewmodus
ist `unknown`, und `gate_eligible` sowie `dispatch_permitted` bleiben falsch. Erst Task 6 erhebt
Coverage und Modus erneut und trifft die erste gate-fähige Policyentscheidung. Dabei wird die
vorläufige Reviewer-Menge nicht blind konserviert; QA darf nur entfallen, wenn sie ausschließlich
wegen der zuvor unbekannten Coverage beziehungsweise des unbekannten Modus hinzukam und nun
vollständige Abdeckung im Modus `full` positiv belegt ist.

Task 6 erhält dafür einen geschlossenen `GateEvaluationContext` mit rekonstruierter
`probe_request`, genau einmal erhobenem `fresh_probe`, aktueller programmatic-only
`reviewer_availability` und `evaluated_at`. `validate` verlangt denselben vollständigen
Probe-Kontext wie `route`; der serialisierte `probe_request_digest` allein ist nicht
rekonstruierbar und keine Autorität. Coverage und tatsächlicher Reviewmodus stammen ausschließlich
aus dem Exact-Head-gebundenen `GateSnapshot` mit `coverage_source` beziehungsweise
`review_mode_source`. Der Validator baut daraus und aus der frischen Usability/Availability einen
neuen finalen `ReviewRequest` und ruft die Policy erneut auf.

Vom Task-5-Vorplan werden ausschließlich Repository/PR/Purpose, Base-/Head-/Merge-Base-SHAs,
Policy-/Runtime-/Diff-Provenienz und -Digests sowie Risiko/Security verglichen. Vorläufige
Usability, Coverage, Modus, Route, Reviewer-Menge und Gatefelder besitzen keine finale
Steuerwirkung. Manipulation dieser Felder darf daher das Gate weder positiv noch negativ
beeinflussen; fremde oder stale Probe-, Reviewer-, Coverage- oder Modusevidenz macht es
fail-closed rot.

Jedes Review-/Request-Ereignis trägt eine über beide Collections eindeutige `event_id`. Pro
Reviewer und Exact Head werden zunächst alle autoritativ kontextgebundenen Ereignisse gesammelt,
danach gewinnt ausschließlich das eindeutig neueste. Ein neueres `ERROR`, `PENDING`,
`CHANGES_REQUESTED` oder `DISMISSED` entwertet ältere positive Copilot-, QA- oder SEC-Evidenz;
unterschiedliche Latest Events mit identischem Zeitpunkt bleiben fail-closed. Die
Eingabereihenfolge ändert weder Ergebnis noch Digest. Für Review, Request und Check gilt:

```text
event_at <= source.observed_at <= snapshot.observed_at <= evaluated_at < source.valid_until
evaluated_at < snapshot.valid_until
```

`GateResult` bindet seinen Purpose und den vollständigen kanonischen Ergebnisvertrag in
`gate_result_digest`: Checkname, Conclusion, Repository/PR/Purpose, Base-Ref/Base-/Head-SHA/
PR-State-Quelle, Policy-/Runtime-/Diff-/Evidence-Digests, sortierte Required-/Validated-Reviewer,
Threadzahl, Reasons und Beobachtungszeit. Der `idempotency_key` bindet mindestens
Repository/PR/Head/Checkname/Result-Digest. `PublicationReceipt` bindet denselben
`gate_result_digest` neben Repository/PR/Head/Check, Publisher-App, Publication-ID, Idempotenz,
`head_revalidated_at` und `published_at`.

Korrekturrunden dürfen ihre vorausgehende Reviewer-Menge ausschließlich aus
`PriorGateEvidence` beziehen. `PriorGateEvidencePort.load_immediate(repository,
pull_request_number, current_head_sha)` ist nur programmatisch über `CliDependencies`
injizierbar; alte Reviewzeilen, Dateien, CLI-Flags und Umgebungsvariablen sind keine Autorität.
Ohne Port/Ergebnis gilt `correction_prior_gate_unavailable`. Positive Evidenz verlangt exakte
Repository-/PR-/Current-Head-, Publisher-/Publication-, Digest-, Idempotenz- und Zeitbindung,
Prior-Conclusion `success`, Purpose ungleich `checkpoint`, nichtleeres
`required_reviewers == validated_reviewers`, null Reasons und null Threads:

```text
prior_result.observed_at
<= receipt.head_revalidated_at
<= receipt.published_at
<= prior_evidence.observed_at
<= current_evaluated_at
< prior_evidence.valid_until
```

Bis Issue #3 ein autoritatives Publisher-Ledger einschließlich unmittelbarer
Latest-/Ancestry-Auswahl bereitstellt, bleibt die produktive positive Korrektur deaktiviert; nur
ein synthetischer, injizierter Fake-Port belegt den Vertragspositivfall. Die allgemeine
Findings-Correction bleibt fachlich ungelöst, weil ein zuvor fehlgeschlagenes Gate die
verlangte Prior-Conclusion-`success` nicht erfüllt. Für `GatePublisherPort` und
`PriorGateEvidencePort` existiert in diesem read-only Lieferumfang keine Factory.

## Konsequenzen

Die Routingentscheidung ist reproduzierbar und fail-closed. Kandidatenpolicy kann keine
Laufzeitadapter austauschen. Für die spätere Veröffentlichung eines Required Checks bleiben die
dedizierte Publisher-App, deren Installation und die serverseitige Durchsetzung getrennte
Aufgaben.

## Verworfene Alternativen

- Markdown- oder Prompt-Matrix: nicht deterministisch ausführbar und nicht ausreichend testbar.
- Shell-Skript mit eingebetteter Policy: vermischt I/O, Klassifikation und Routing.
- Restbudget-Routing: Limits und Verbrauch sind nicht verlässlich genug und wurden als
  Routing-Eingang verworfen.
- Optimistischer Copilot-Retry bei unbekanntem Zustand: verletzt fail-closed und kann Kosten
  auslösen.
- Pauschale QA nach jedem Cluster: vermeidet keine unnötigen Kosten risikobasiert.
