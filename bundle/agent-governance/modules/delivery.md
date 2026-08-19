# Lieferung und Qualität

### DEL-001 — Relevante Tests

Jede Änderung wird durch den kleinstmöglichen gezielten Test und den für ihr Risiko
relevanten Gesamtumfang geprüft. Testdaten und Fixtures müssen das behauptete Verhalten real
ausüben. Plattformabhängige Logik wird auf den unterstützten Plattformen oder in
nachweislich äquivalenten isolierten Umgebungen geprüft; fehlende Plattformnachweise werden
offen benannt.

### DEL-002 — Exakter Stand

Test-, CI-, Review- und Security-Evidenz gilt nur für den exakt bezeichneten Commit oder
Inhaltsstand. Ändert sich der Stand nach einer Prüfung, werden alle davon betroffenen Gates
erneut ausgeführt. Lokaler und entfernter Stand dürfen nicht ohne Hashvergleich gleichgesetzt
werden.

### DEL-003 — Unabhängige Prüfung

Jede Änderung an einem versionierten oder anderweitig persistenten Liefergegenstand benötigt
vor der Aussage „lieferbar“ sowie vor einer Integrations- oder Releaseentscheidung eine
unabhängige QA durch einen frischen read-only Kontext auf dem exakten Lieferstand. Zusätzlich
ausgelöste Rollen wie SEC oder ARCH ersetzen diese QA nicht. Die relevanten Checks müssen
erfolgreich sein; alle Reviewkommentare und Reviewthreads werden für diesen Stand frisch gelesen,
klassifiziert und behandelt. Kein `blocking-valid` Finding und kein unklassifizierter offener
Thread darf verbleiben. Eine Selbstprüfung darf zusätzliche Evidenz liefern, ersetzt aber kein
unabhängiges Rollenurteil.

### DEL-004 — Atomare Historie

Ein Commit enthält genau ein fachlich kohärentes, getestetes Ziel. Commitidentität,
Signaturanforderungen und vorhandene Repositorykonventionen werden vor der Veröffentlichung
geprüft. Veröffentliche Historie wird nicht ohne ausdrückliche, eng begrenzte Autorisierung
umgeschrieben. Sofern der Nutzer keinen anderen Lieferweg ausdrücklich autorisiert, entsteht
Arbeit auf einem abgegrenzten Branch vom aktuellen Remote-Ziel und wird über den vorgesehenen
Reviewweg geliefert; geschützte Branches, Force-Push und Schutzregeln werden nicht umgangen.

### DEL-005 — CI-Aussagekraft

CI-Ergebnisse werden nach Ursache und ausgeführten Schritten klassifiziert. Nur erfolgreich
ausgeführte relevante Jobs belegen die geprüfte Qualität. Infrastruktur-, Berechtigungs- oder
Accountfehler haben keine positive codebezogene Aussagekraft; ein ausführbarer Code-, Test-
oder Workflowfehler bleibt ein fachlicher Fehler.

### DEL-006 — Dokumentation und Version

README, Betriebsgrenzendokumentation, Changelog und Versionsmetadaten beschreiben ausschließlich den
implementierten Stand. Verhaltens-, Kompatibilitäts- und Migrationsänderungen werden in der
für das Repository festgelegten Versionierung erfasst; Zukunftspläne erscheinen nicht als
bereits verfügbare Funktion.

### DEL-007 — Reviewentscheidung

Vor einem unabhängigen Gate werden Prüfzweck, Exact Head, Risikoklasse und erforderliche
Rolle bestimmt. QA prüft Lieferqualität, SEC sicherheitsrelevante Auswirkungen und ARCH
Architekturgrenzen; Rolle und technischer Provider bleiben getrennt. Eine Selbstprüfung ist
kein unabhängiges Rollenurteil, und ein Providerkommentar wird nicht als Plattformfreigabe
umgedeutet.

### DEL-008 — Provider-Routing

Bei einem GitHub-Repository ist GitHub Copilot der bevorzugte QA-Provider, wenn der reale
PR-Reviewpfad einen Review mit Revieweridentität und Exact-Head-SHA liefert und auf demselben
Exact Head ein gültiges repository-natives Copilot-QA-Binding
(`.github/copilot-instructions.md`) mit auflösbaren kanonischen QA-/Delivery-Referenzen
vorhanden ist. Fehlt das Binding oder sind seine Referenzen nicht auflösbar, gilt der
Copilot-Pfad für dieses Gate fail-closed als nicht verwendbar. Ein frischer
unabhängiger read-only Reviewer ist der QA-Fallback, sobald der Providerzustand `no` oder
`unknown` lautet oder das Binding ungültig ist; Quoten-, Billing- oder Restbudgetzahlen werden
nicht erfunden und ein bestätigtes Negativergebnis wird nicht mit Retry-Spam verfolgt. Eine
SEC-Rolle bleibt bei ihrem Risikotrigger zusätzlich erforderlich und prüft denselben Exact Head.

### DEL-009 — Finding-Lifecycle

Jedes Finding wird als `blocking-valid`, `nonblocking-valid`, `invalid` oder
`not-applicable` klassifiziert. `blocking-valid` wird vor Fortsetzung korrigiert;
`nonblocking-valid` wird korrigiert oder mit technischer Begründung dokumentiert. Die beiden
anderen Klassen benötigen eine kurze überprüfbare Begründung. Nach jeder inhaltlichen
Korrektur werden betroffene Tests und Rollenprüfungen auf dem neuen Exact Head erneut
ausgeführt; offene valide Blocking-Findings verbieten eine Abschlussaussage.

### DEL-010 — Optionales Parallel-QA

Ein optionaler Parallel-QA-Modus wird nur aktiviert, wenn der Nutzer dies ausdrücklich verlangt
oder eine bestehende Governance-Risikoeinstufung/Qualitätsanforderung dies ausdrücklich auslöst;
er wird nicht standardmäßig für jedes Review ausgeführt. In diesem Modus prüfen zwei
unabhängige QA-Kontexte frisch und read-only denselben Exact Head. Ihre Findings bleiben bis zu
den jeweils eigenen Urteilen voneinander getrennt und werden anschließend nach
[DEL-009](delivery.md#del-009--finding-lifecycle) klassifiziert. Ein `blocking-valid` Finding
eines erforderlichen Reviewers blockiert die Abschlussaussage. Parallel-QA ersetzt SEC nicht;
ist SEC getriggert, läuft sie zusätzlich und kann parallel zu QA ausgeführt werden.

## Definition of Done

Der Liefergegenstand erfüllt seine Akzeptanzkriterien, relevante Tests und statische Prüfungen
sind grün, Diff und Arbeitsbaum sind abgegrenzt, Dokumentation stimmt und erforderliche
unabhängige Gates beziehen sich auf den exakten Stand. Der Nachweis folgt
[EVD-004](evidence.md#evd-004--abschlussnachweis).
