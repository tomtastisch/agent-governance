# Arbeitsablauf

### WFL-001 — Abgegrenzter Arbeitsplan

Vor einer Änderung werden ein fachlich kohärentes Ziel, Scope, Nicht-Ziele, Risiken,
objektive Akzeptanzkriterien, Prüfweg und atomarer Liefergegenstand festgelegt. Es ist nur ein
Änderungscluster aktiv; ein Folgecluster beginnt erst nach erfolgreicher Prüfung und
gesichertem Abschluss des aktuellen Clusters.

### WFL-002 — Enger Blocker

Ein Blocker wird auf genau die Entscheidung oder Wirkung begrenzt, für die notwendige
Evidenz, Autorisierung oder ein auflösbarer Zustand fehlt. Davon unabhängige read-only oder
bereits autorisierte Arbeit läuft weiter. Der Blockerbericht enthält Ursache, Nachweis,
betroffenen Scope und den kleinsten Auflösungsschritt.

### WFL-003 — Neue Befunde

Ein neu entdeckter Defekt wird vor einer scope-erweiternden Behebung unabhängig reproduziert,
ursächlich eingegrenzt und gegen bestehende Vorgänge dedupliziert. Nicht blockierende,
eigenständige Befunde werden nicht still in denselben Änderungssatz aufgenommen.

### WFL-004 — Systematisches Debugging

Bei einem realen Test- oder Laufzeitfehler wird zuerst die Reproduktion stabilisiert, dann die
früheste belegte Ursache bestimmt und anschließend die kleinste ursächliche Korrektur
umgesetzt. Symptomatische Umgehungen, Abschalten von Prüfungen und spekulative Mehrfachfixes
sind keine Fehlerbehebung.

### WFL-005 — Testgetriebene Änderung

Änderbares Verhalten erhält zunächst einen reproduzierbaren fehlschlagenden Test, danach die
kleinste Implementierung und schließlich einen grünen relevanten Gesamtumfang. Reine
Dokumentations- oder mechanische Datenänderungen verwenden stattdessen einen vorab definierten
prüfbaren Vertrag.

## Clusterabschluss

Der Diff wird auf Scope-Überschreitung, temporäre Dateien und nicht belegte
Dokumentationsaussagen geprüft. Der Abschluss folgt
[EVD-004](evidence.md#evd-004--abschlussnachweis); ein fehlgeschlagener relevanter Test
verhindert den Abschluss des betroffenen Clusters.
