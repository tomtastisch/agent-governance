# Lokale Verifikation

Dieses Modul gilt während lokaler Umsetzung und Prüfung. Scope und Bestandsschutz folgen
[INV-001](invariants.md#inv-001--scope-treue) und
[INV-002](invariants.md#inv-002--bestandsschutz).

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

### DEL-004 — Atomare Historie

Ein Commit enthält genau ein fachlich kohärentes, getestetes Ziel. Commitidentität,
Signaturanforderungen und vorhandene Repositorykonventionen werden vor der Veröffentlichung
geprüft. Veröffentliche Historie wird nicht ohne ausdrückliche, eng begrenzte Autorisierung
umgeschrieben. Sofern der Nutzer keinen anderen Lieferweg ausdrücklich autorisiert, entsteht
Arbeit auf einem abgegrenzten Branch vom aktuellen Remote-Ziel und wird über den vorgesehenen
Reviewweg geliefert; geschützte Branches, Force-Push und Schutzregeln werden nicht umgangen.

### DEL-006 — Dokumentation und Version

README, Betriebsgrenzendokumentation, Changelog und Versionsmetadaten beschreiben ausschließlich den
implementierten Stand. Verhaltens-, Kompatibilitäts- und Migrationsänderungen werden in der
für das Repository festgelegten Versionierung erfasst; Zukunftspläne erscheinen nicht als
bereits verfügbare Funktion.

## Grenze zur Lieferentscheidung

Lokale Evidence erlaubt ausschließlich die Aussage „lokal verifiziert“ im geprüften Scope.
Vor PR-/Review-Promotion, Integration, Release, Publishing oder einer Aussage wie „lieferbar“,
„merge-ready“ oder „release-ready“ wird der bestehende Trigger `release` angewendet und damit
`delivery` geladen. Ein anstehendes unabhängiges Qualitäts- oder Security-Gate aktiviert
`quality_review` beziehungsweise `security_review`; der passende Rollentrigger lädt die Rolle.
Kein lokaler Test ersetzt diese Gates. Bei unklarer Grenze gilt
[GOV-004](../../GOVERNANCE.md#gov-004--fail-closed).

