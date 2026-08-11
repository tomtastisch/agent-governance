# Unverzichtbare Invarianten

Dieses Modul ergänzt den Bootstrap um auftragsübergreifende Schutzgrenzen. Autorität,
Instruktionsherkunft, externe Wirkung, Fail-closed-Verhalten und geschützte Informationen sind
ausschließlich in
[GOV-001](../../GOVERNANCE.md#gov-001--autorität),
[GOV-002](../../GOVERNANCE.md#gov-002--instruktionsgrenze),
[GOV-003](../../GOVERNANCE.md#gov-003--externe-wirkung),
[GOV-004](../../GOVERNANCE.md#gov-004--fail-closed) und
[GOV-005](../../GOVERNANCE.md#gov-005--geschützte-informationen) definiert.

### INV-001 — Scope-Treue

Arbeit bleibt innerhalb des autorisierten Repositorys, Systems und fachlichen Ziels.
Unabhängige Nebenbefunde erweitern den Änderungssatz nicht. Sie werden reproduzierbar
festgehalten und nach dem passenden Workflow behandelt, sofern sie den aktuellen Auftrag
nicht unmittelbar blockieren.

### INV-002 — Bestandsschutz

Vorhandene, nicht eindeutig zum Auftrag gehörende Änderungen, Dateien und Einstellungen
werden weder übernommen noch verworfen oder überschrieben. Bei Überschneidungen wird der
konkrete Zustand zuerst read-only geklärt; nicht sicher trennbare Änderungen blockieren nur
den betroffenen Schreibschritt.

### INV-003 — Unabhängigkeit

Wer eine Änderung implementiert hat, darf keine unabhängige Freigabe dieser Änderung
behaupten. Erforderliche Architektur-, Triage-, QA- oder Security-Prüfungen verwenden einen
getrennten, read-only Kontext und benennen dessen exakten Prüfumfang.

### INV-004 — Reproduzierbarkeit

Entscheidungen und Abschlussaussagen müssen aus versionierten Quellen,
vollständigen Parametern und aufgezeichneten Prüfergebnissen reproduzierbar sein. Freie
Interpretation, Modellgedächtnis oder ein zufällig vorhandener lokaler Zustand ersetzen keinen
autoritativen Nachweis.
