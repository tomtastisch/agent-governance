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

Wenn Risiko oder Auftrag eine unabhängige Prüfung verlangt, bewertet ein frischer read-only
Kontext den exakten Lieferstand. Findings werden behoben oder als Blocker behandelt. Eine
Selbstprüfung darf zusätzliche Evidenz liefern, ersetzt aber nicht die unabhängige Freigabe.

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

README, Installationsanleitung, Changelog und Versionsmetadaten beschreiben ausschließlich den
implementierten Stand. Verhaltens-, Kompatibilitäts- und Migrationsänderungen werden in der
für das Repository festgelegten Versionierung erfasst; Zukunftspläne erscheinen nicht als
bereits verfügbare Funktion.

## Definition of Done

Der Liefergegenstand erfüllt seine Akzeptanzkriterien, relevante Tests und statische Prüfungen
sind grün, Diff und Arbeitsbaum sind abgegrenzt, Dokumentation stimmt und erforderliche
unabhängige Gates beziehen sich auf den exakten Stand. Der Nachweis folgt
[EVD-004](evidence.md#evd-004--abschlussnachweis).
