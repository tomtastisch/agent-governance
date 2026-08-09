# Tool-Routing

### TOL-001 — Trigger und Ausführung

Werkzeuge werden nach fachlichem Trigger ausgewählt und ausgeführt, nicht zur Zeremonie. Nur
eine tatsächlich ausgeführte Prüfung liefert Evidenz. Ein fehlgeschlagener Pflichtaufruf
aktiviert den benannten fachlichen Fallback oder blockiert nur das davon abhängige Gate.
Erfolgsaussagen folgen [EVD-001](evidence.md#evd-001--belegpflicht) und unterscheiden Aufruf,
Ergebnis und Evidenzumfang.

### TOL-002 — Standardkatalog

Die Einträge definieren Tool-Routing, keine Beschaffung. „Erforderlich“ bezeichnet den
fachlichen Auslöser; „nützlich“ erlaubt einen evidenzsteigernden Einsatz ohne Pflicht.

#### Lokale Git-CLI

**Name:** `git`.
**Zweck:** Repositoryzustand, Historie, Branches, Commits und Diffs aus der lokalen Source of Truth lesen und autorisierte Versionskontrollschritte ausführen.
**Trigger:** Jede Git-gestützte Analyse, Änderung oder Lieferung.
**Erforderlich:** Für Aussagen über lokalen Head, Arbeitsbaum, Base, Commitidentität oder Diff sowie für autorisierte lokale Git-Mutationen.
**Nützlich:** Für Blame-, Log- und Objektgraphanalysen.
**Evidenzgewinn:** Exakte Objekt-IDs, Status, Historie und maschinenprüfbare Diffs.
**Read-/Write-Grenze:** Lesen ist Standard; Commit, Branch und Push erfordern den bestätigten Lieferumfang, History-Rewrite eine eigene ausdrückliche Autorisierung.
**Fallback:** Scheitert die Git-Abfrage, ist eine Git-bezogene Identitäts- oder Lieferbehauptung blockiert; bereitgestellte unveränderliche Archive dürfen nur Inhaltsanalyse tragen.
**Keine Folgerung:** Lokale Git-Evidenz beweist weder Remotezustand noch CI- oder Reviewstatus.

#### Repositoryeigene Prüfungen

**Name:** Test-, Lint-, Build-, Drift- und Release-Checks des Repositorys.
**Zweck:** Den implementierten Vertrag mit seinen eigenen ausführbaren Akzeptanzkriterien prüfen.
**Trigger:** Änderung oder Abschlussaussage in einem Repository mit autoritativen Prüfkommandos.
**Erforderlich:** Für alle vom Diff oder Repositoryvertrag betroffenen Checks.
**Nützlich:** Für fokussierte Reproduktionen vor der Gesamtsuite.
**Evidenzgewinn:** Exitcodes, konkrete Findings und reproduzierbare Ergebnisprotokolle.
**Read-/Write-Grenze:** Prüfungen dürfen nur erwartete Build-/Testartefakte erzeugen; externe Wirkung oder produktive Veröffentlichung folgt nicht daraus.
**Fallback:** Nicht ausführbare Checks werden mit Ursache und fehlender Abdeckung gemeldet; gleichwertige vorhandene read-only Prüfungen dürfen ergänzen.
**Keine Folgerung:** Ein fokussierter oder lokal grüner Check belegt keine ausgelassene Gesamtsuite und keine Remote-CI.

#### GitHub CLI

**Name:** `gh`.
**Zweck:** GitHub-Repository, Pull Request, Review, Check und Actions-Zustand unmittelbar lesen und ausdrücklich autorisierte PR-Operationen ausführen.
**Trigger:** Ein GitHub-Remote oder eine GitHub-bezogene Zustands- oder Lieferbehauptung.
**Erforderlich:** Wenn GitHub-Zustand Teil des Gates ist; der Aufruf verwendet die dafür bestimmte Authentisierung ohne Authdaten offenzulegen.
**Nützlich:** Für auditierbare Reviewanforderungen und PR-Metadatenpflege.
**Evidenzgewinn:** Repository-, PR-, Reviewer-, Check- und Workflow-IDs mit Head-SHAs und Zeitpunkten.
**Read-/Write-Grenze:** Read-only vor Mutation; Schreibaktionen bleiben auf den einzeln autorisierten PR-/Reviewumfang begrenzt, Account- und Billingänderungen sind getrennte externe Wirkungen.
**Fallback:** GitHubs dokumentierte read-only API oder ein vorhandener Connector darf Leseevidenz liefern; eine erforderliche Mutation bleibt ohne autorisierten Pfad blockiert.
**Keine Folgerung:** GitHub-Zugriff autorisiert weder Merge noch Schutzregel-, Account- oder Abrechnungsänderungen.

#### GitHub-Connector

**Name:** GitHub-Connector oder GitHub-MCP.
**Zweck:** GitHub-Evidenz ergänzend strukturiert lesen, wenn sie den CLI-Nachweis verbessert.
**Trigger:** Unzureichend aufgelöste read-only GitHub-Metadaten oder ausdrückliche Connectorvorgabe.
**Erforderlich:** Nur wenn der Auftrag ihn verlangt oder die maßgebliche Evidenz über den primären GitHub-Pfad nicht auflösbar ist.
**Nützlich:** Für Reviewthreads, Beziehungen und strukturierte Metadaten.
**Evidenzgewinn:** Ergänzende Objektbezüge und nachvollziehbare Remote-Metadaten.
**Read-/Write-Grenze:** Standardmäßig read-only; Connector-Schreibrechte erweitern niemals die Nutzerautorisierung.
**Fallback:** `gh` und lokale Git-CLI bleiben für ihre jeweiligen Aussagen maßgeblich.
**Keine Folgerung:** Ein Connector ersetzt weder lokalen Git-Zustand noch eine fehlende GitHub-CLI-Laufzeitevidenz.

#### Autoritative Dokumentationsrecherche

**Name:** Primärquellenzugriff auf die aktuelle Hersteller- oder Projektdokumentation.
**Zweck:** Zeitvariable Toolsyntax, Fähigkeiten und Grenzen vor normativer Festschreibung verifizieren.
**Trigger:** Konkrete Toolregeln, deren Semantik oder Syntax sich geändert haben kann.
**Erforderlich:** Vor Aussagen, die von aktueller externer Tooldokumentation abhängen.
**Nützlich:** Für Quervergleich mit dem autoritativen Quellrepository.
**Evidenzgewinn:** Datierte, direkt zuordenbare Primärquellen statt Modellannahmen.
**Read-/Write-Grenze:** Recherche ist read-only; externe Beispiele erteilen keine lokale Ausführungsberechtigung.
**Fallback:** Gepinnte lokale Herstellerdokumentation darf verwendet werden, wenn Version und Herkunft belegt sind; sonst bleibt die zeitvariable Aussage offen.
**Keine Folgerung:** Dokumentierte Existenz beweist keinen lokalen Aufruf und keine erfolgreiche Verwendung.

#### Strukturierter Engineering-Workflow

**Name:** Vorhandene Skills oder gleichwertige Verfahren für Planung, TDD, systematisches Debugging, Review und Abschlussverifikation.
**Zweck:** Wiederholbare Arbeitsdisziplin an den tatsächlich ausgelösten Risikopunkten sicherstellen.
**Trigger:** Mehrschrittige Änderung, Verhaltensänderung, reproduzierbarer Fehler, Reviewgate oder Abschlussaussage.
**Erforderlich:** Wenn Auftrag oder aktiver Governance-Vertrag das jeweilige Verfahren verlangt.
**Nützlich:** Für explizite Hypothesen, kleine Testschleifen und nachvollziehbare Gatefolge.
**Evidenzgewinn:** Rote und grüne Tests, Ursachenbelege, Reviewreferenzen und frische Abschlusschecks.
**Read-/Write-Grenze:** Die Verfahren steuern Arbeit innerhalb des autorisierten Scopes und schaffen keine neuen externen Schreibrechte.
**Fallback:** Scheitert die konkrete Skill-Ausführung, darf ein fachlich gleichwertiger dokumentierter Ablauf dieselben Gates erfüllen.
**Keine Folgerung:** Das Laden eines Verfahrens belegt nicht, dass seine Gates ausgeführt oder bestanden wurden.

#### Unabhängiger Reviewprovider

**Name:** GitHub Copilot Code Review oder ein frischer unabhängiger read-only Reviewer.
**Zweck:** QA-Evidenz unabhängig vom implementierenden Kontext für einen exakt bezeichneten Stand erzeugen.
**Trigger:** Erforderliches unabhängiges QA-Gate.
**Erforderlich:** Wenn Risiko, Auftrag oder Liefervertrag unabhängige Prüfung verlangt.
**Nützlich:** Für zusätzliche Diffanalyse vor einer Abschlussentscheidung.
**Evidenzgewinn:** Revieweridentität, Reviewreferenz, Exact-Head-SHA, Zeitpunkt und klassifizierbare Findings.
**Read-/Write-Grenze:** Review ist read-only; Finding-Kommentare und Threadpflege bleiben auditierbare PR-Metadaten, Änderungen am Lieferstand erfolgen separat.
**Fallback:** Liefert der bevorzugte Provider kein eindeutig zuordenbares Review, übernimmt ein frischer unabhängiger read-only Reviewer dieselbe Rolle.
**Keine Folgerung:** Ein Reviewprovider ist nicht die Reviewerrolle selbst und sein Kommentar ist keine erfundene Plattformfreigabe.

#### Security-Diff-Prüfung

**Name:** Read-only Security-Diff-Scanner oder unabhängige SEC-Rolle.
**Zweck:** Sicherheitsrelevante Datenflüsse, Berechtigungen und Trust Boundaries im Exact-Head-Diff prüfen.
**Trigger:** Änderung an Security-Regeln, Authentisierung, Autorisierung, Secrets, Berechtigungen, Trust Boundaries, externer Schreibwirkung oder fail-closed Freigaben.
**Erforderlich:** Nur bei einem solchen Security-Trigger oder ausdrücklichem Auftrag.
**Nützlich:** Für die Kalibrierung plausibler Findings vor einer SEC-Entscheidung.
**Evidenzgewinn:** Risikobezogene Source-to-Sink- oder Regelpfade, Findingstatus und geprüfter SHA.
**Read-/Write-Grenze:** Prüfung bleibt read-only; Korrektur, Tracking oder Veröffentlichung sind eigene autorisierte Schritte.
**Fallback:** Ein frischer unabhängiger SEC-Reviewer prüft denselben Exact Head mit dokumentierter Abdeckung.
**Keine Folgerung:** Rein redaktionelle Änderungen lösen ohne Sicherheitswirkung kein formales SEC-Gate aus.

#### Microsoft APM

**Name:** Microsoft APM – Agent Package Manager.
**Zweck:** Deklarative Agent-Skills, Agent-Pakete und ihre Abhängigkeiten über vorhandene `apm.yml`- und `apm.lock.yaml`-Evidenz reproduzierbar beurteilen.
**Trigger:** Skills oder Agent-Pakete werden benötigt, geprüft, zusammengestellt oder versioniert; agentische Abhängigkeiten, reproduzierbare Konfiguration, Paketquelle, Lockzustand oder Drift sind relevant.
**Erforderlich:** Wenn der Trigger eintritt, ist APM der bevorzugte Prüfweg; deklarierte Manifeste und Locks werden gelesen und passende read-only Checks wie `apm audit --ci` berücksichtigt. Fehlt deklarierter APM-Zustand, wird diese Abwesenheit belegt, ohne Dateien anzulegen.
**Nützlich:** Für Provenienz-, Abhängigkeits-, Integritäts- und Driftbefunde in APM-verwalteten Agentpaketen.
**Evidenzgewinn:** Deklarierte Quellen, aufgelöster Lockzustand, Auditfindings und reproduzierbare Abweichungen.
**Read-/Write-Grenze:** Governance verwendet vorhandene APM-Evidenz und read-only Prüfpfade; sie verändert weder Paketquellen, Locks, Agentdateien noch Benutzer- oder Serverkonfiguration.
**Fallback:** Scheitert der APM-Prüfweg, darf nur ein fachlich gleichwertiger read-only Nachweis das betroffene Gate erfüllen; andernfalls bleibt es offen.
**Keine Folgerung:** Der Toolstandard begründet weder Paketverwaltung als Governance-Subsystem noch Runtime-, Deployment-, Server- oder Azure-Verantwortung.
