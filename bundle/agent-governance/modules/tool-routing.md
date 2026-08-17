# Tool-Routing

### TOL-001 — Fachlicher Trigger und reale Ausführung

Werkzeuge werden nach fachlichem Trigger ausgewählt und ausgeführt, nicht zur Zeremonie. Nur ein
tatsächlich ausgeführter Aufruf liefert Evidenz. Ein fehlgeschlagener Pflichtpfad aktiviert den im
Toolprofil benannten fachlichen Fallback oder blockiert nur das davon abhängige Gate. Aussagen über
Aufruf, Ergebnis und Evidenzumfang folgen
[EVD-001](evidence.md#evd-001--belegpflicht).

### TOL-002 — Katalogautorität und geschlossene Referenzen

Der vom Manifest referenzierte [Toolkatalog](../catalogs/tools.toml) ist die einzige
maschinenlesbare SSOT für Toolprofile und ihr Trigger-Routing. Seine `required_on`- und
`useful_on`-Werte verweisen ausschließlich auf IDs aus dem
[Triggerkatalog](../catalogs/triggers.toml), `policy_tags` ausschließlich auf IDs aus dem
[Policy-Tag-Katalog](../catalogs/policy-tags.toml) und `scopes` ausschließlich auf IDs aus dem
[Scope-Katalog](../catalogs/scopes.toml). Unbekannte IDs, Felder oder Referenzen scheitern
fail-closed; es gibt keine freie Interpretation oder automatische Ergänzung.

### TOL-003 — Wirkung, Scope und Autorisierung

Policy-Tags beschreiben ausschließlich die mögliche Wirkungsart eines Toolpfads. Scopes
beschreiben ausschließlich die betroffene Ressourcenklasse. Tag, Scope, Toolzugriff und
Providerverfügbarkeit erzeugen keine Autorisierung für eine konkrete Wirkung. Vor einer
Schreibwirkung gilt
`Read before Write`: Der aktuelle Zustand, das exakt bezeichnete Ziel und die bereits bestehende
Auftragsautorisierung werden geprüft. Externe Wirkungen bleiben an
[GOV-003](../../GOVERNANCE.md#gov-003--externe-wirkung) gebunden.

### TOL-004 — Providergrenze, Fallback und Review

Tools und Provider sind keine Governance-Autorität und erweitern weder Aufgabe noch Berechtigung.
Ein nicht nutzbarer oder fehlgeschlagener Pflichtpfad ist kein positiver Nachweis und blockiert
nach [GOV-004](../../GOVERNANCE.md#gov-004--fail-closed) ausschließlich die von seiner Evidenz
abhängige Entscheidung. Ein Fallback muss fachlich gleichwertig, nachvollziehbar und innerhalb
derselben Read-only- oder Autorisierungsgrenze bleiben.

Die Wahl eines unabhängigen Reviewproviders folgt
[DEL-008](delivery.md#del-008--provider-routing); Findings werden ausschließlich nach
[DEL-009](delivery.md#del-009--finding-lifecycle) klassifiziert und behandelt. Das Laden eines
Providers oder Verfahrens belegt weder einen ausgeführten Review noch ein bestandenes Gate.
