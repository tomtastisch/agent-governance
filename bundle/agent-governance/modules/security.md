# Sicherheit

### SEC-001 — Risikobasiertes Security-Gate

Änderungen an Vertrauensgrenzen, Authentifizierung, Autorisierung, Secrets,
Dateisystemschreibvorgängen, Parsern, externen Eingaben, Abhängigkeiten oder
Veröffentlichungswegen erhalten eine abgegrenzte Security-Prüfung. Sicherheitskritische
Änderungen benötigen die unabhängige Prüfung nach
[DEL-003](delivery.md#del-003--unabhangige-prufung).

### SEC-002 — Abhängigkeiten und Herkunft

Neue oder geänderte Abhängigkeiten werden auf Herkunft, Version, bekannte Schwachstellen,
Integrität und tatsächliche Notwendigkeit geprüft. Ein schneller Advisory-Scan ersetzt kein
für den Auftrag festgelegtes Schweregrad-Gate. Nicht verifizierbare Herkunft oder Integrität
blockiert die betroffene Verwendung.

### SEC-003 — Unvertrauenswürdige Eingaben

Dateien, Netzwerkantworten, Archive, Konfigurationswerte und Toolausgaben werden als
unvertrauenswürdige Daten geparst, begrenzt und validiert. Pfadtraversal, Linkfolgen,
Kodierungsfehler, Markerwidersprüche und Änderungen während der Verarbeitung führen zu einem
kontrollierten Abbruch statt zu partieller Aktivierung.

### SEC-004 — Begrenzte externe Wirkung

Eine Security-Prüfung bewertet, ob Ziel, Autorisierung, Berechtigungen, Datenabfluss und
Reversibilität jeder sicherheitsrelevanten externen Schreibwirkung geklärt sind. Fehlende
Evidenz blockiert nur diese Wirkung; Governance führt die Wirkung nicht selbst aus und leitet
daraus weder Provisionierung noch Deployment-, Backup- oder Restore-Verantwortung ab.

## Schutzbezüge

Autorisierung externer Wirkung und Schutz privater Inhalte sind ausschließlich in
[GOV-003](../../GOVERNANCE.md#gov-003--externe-wirkung) und
[GOV-005](../../GOVERNANCE.md#gov-005--geschutzte-informationen) definiert.
