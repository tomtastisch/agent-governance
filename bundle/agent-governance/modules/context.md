# Kontextkontinuität

### CTX-001 — Kanonische Arbeitswahrheit

Jede lange oder komplexe Aufgabe benennt ihre kanonische Source of Truth und deren
Prioritätsordnung. Versionierte Repositoryobjekte, explizit bezeichnete externe Datensätze
und bestätigte Trackerobjekte haben Vorrang vor Zusammenfassungen und Modellgedächtnis. Der
vollständige Chat ist Arbeitskontext, aber keine alleinige Source of Truth.

### CTX-002 — Sitzungsledger und Checkpoints

Ein kompaktes Sitzungsledger hält Ziel und Scope, kanonische Quellen, Exact State,
bestätigte und verworfene Entscheidungen, ausgeführte Evidenz, klassifizierte Findings und
den nächsten sicheren Schritt fest. Ein Checkpoint wird nach jeder Scopeentscheidung,
externen Wirkung, Commit-/Push-/Reviewgrenze, Findingkorrektur und vor einer Übergabe
aktualisiert. Die [Kontextübergabe](templates.md#kontextübergabe) ist die verbindliche Form.

### CTX-003 — Kontext neu laden

Der Agent muss Kontext neu laden, wenn eine Sitzung fortgesetzt oder komprimiert wurde,
Branch, Base, Head oder externe Referenz sich geändert haben, ein Checkpoint fehlt oder eine
behauptete Entscheidung nicht zur kanonischen Quelle passt. Vor weiterer Mutation werden
mindestens aktueller Scope, SSOT, Exact State, offene Findings und letzte Verifikation erneut
gelesen.

### CTX-004 — Verzweigung und Supersession

Jede fachliche Verzweigung erhält eine bezeichnete Basis und ein eigenes Ergebnis; sie darf
nicht still in den Hauptpfad zurückfließen. Eine veraltete Entscheidung bleibt nur als
supersedierte Evidenz erhalten und nennt ihren gültigen Nachfolger. Zusammenführung setzt
vereinbare Quellen, identische Objektbezüge und eine explizite Konfliktentscheidung voraus.

### CTX-005 — Quellenrouting, Widerspruch und Datenminimierung

Tool- und Wissensquellen werden nach ihrer Autorität und Aktualität geroutet; Repository,
Tracker, Knowledge Graph oder Memory dürfen Kontext liefern, aber keine höher priorisierte
SSOT still ersetzen. Ist der Zustand widersprüchlich, stoppt nur die Arbeit am betroffenen Schritt,
bis Quelle und Identität geklärt sind. Das Ledger speichert keine Secrets, Rohchats oder temporäre
Debugdaten und verweist auf große Evidenzobjekte, statt sie vollständig zu kopieren.
