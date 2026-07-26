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
bleibt `unverified`. Eine gleich alte oder neuere verifizierte Blockade schlägt eine Capability;
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
