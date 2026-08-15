# Deterministischer Enforcement-Vertrag

Dieses Modul definiert ausschließlich die providerneutrale Grenze zwischen bereits erfolgter
semantischer Governance-Autorisierung und einer technischen Vor-Effekt-Prüfung. Die Governance
bleibt Autorität für Instruktionsgrenze, Klassifikation und Freigabe. Ein Provider setzt diese
Entscheidung technisch enger durch; er ist weder Instruktionsquelle noch Autorisierungsinstanz.

### ENF-001 — Trigger und minimale Action Envelope

Wenn die Governance einen geplanten externen oder toolbasierten Effekt als enforcement-pflichtig
klassifiziert, muss die Providerprüfung vor dem Effekt abgeschlossen sein. Ohne belegte
Vor-Effekt-Prüfung darf die Aktion nach
[GOV-004](../../GOVERNANCE.md#gov-004--fail-closed) nicht beginnen.

Der normalisierte Providerinput enthält ausschließlich:

- `action_id`: eindeutige Kennung der geplanten Aktion;
- `action`: kanonisch benannte Operation;
- `resource`: kanonisch benanntes Ziel;
- `effect`: erwartete Zustands- oder Außenwirkung;
- `semantic_authorization`: bereits bestehende Governanceentscheidung;
- `approval_context`: vorhandene, auf genau diese Aktion bezogene Approval-Evidenz;
- `risk_context`: für die Entscheidung erforderliche Risikoklassifikation;
- `evidence_id`: eindeutige Verbindung zur sicheren Entscheidungsevidenz.

Fehlt ein erforderliches Feld, ist ein Wert mehrdeutig oder enthält die Envelope mehr Daten als
für die Entscheidung notwendig, ist der Providerinput ungültig. Geschützte Informationen werden
nach [GOV-005](../../GOVERNANCE.md#gov-005--geschützte-informationen) weder als Providerinput noch
als Evidenzmaterial weitergegeben.

### ENF-002 — Geschlossene Providerentscheidung

Die normalisierte Providerentscheidung ist genau einer der Werte `allow`, `deny`,
`require_approval`, `error` oder `unknown`. Jeder andere, fehlende oder widersprüchliche Wert wird
als `unknown` behandelt. Providername, Implementierungsdetails und transportbezogene Daten sind
kein Bestandteil dieser normativen Entscheidungsmenge.

### ENF-003 — Einschränkende Providergrenze

Liegt von der Governance `deny` oder keine eindeutige semantische Autorisierung vor, darf ein
Provider die Aktion durch `allow` niemals freigeben. Ein Provider darf eine Autorisierung nur
weiter einschränken, niemals erweitern. Tool- oder Providerverfügbarkeit ist niemals selbst eine
Berechtigung. Die externe Wirkung bleibt zusätzlich an
[GOV-003](../../GOVERNANCE.md#gov-003--externe-wirkung) gebunden.

### ENF-004 — Entscheidungs- und Approval-Semantik

- Ein Providerentscheid `deny` blockiert die Aktion.
- Bei `require_approval` wird keine Approval erfunden oder aus allgemeinem Vertrauen abgeleitet.
  Nur bereits vorhandene, gültige und aktionsbezogene Approval-Evidenz darf erneut bewertet
  werden; fehlt sie, wird die Aktion sonst blockiert.
- Bei `error` oder `unknown` wird eine verpflichtende Enforcement-Prüfung fail-closed blockiert.
- Ausschließlich `allow` darf eine bereits semantisch autorisierte Aktion fortsetzen.

Eine nachträgliche Prüfung ist kein Enforcement. Der Effekt darf erst nach der normalisierten
Entscheidung und nur innerhalb des unverändert autorisierten Scopes beginnen.

### ENF-005 — Sichere Evidenz und Fehlergrenze

Die lokale Evidenz verbindet `action_id` und `evidence_id` mit der normalisierten Entscheidung,
dem geprüften Stand und dem Boolean-Status der Vor-Effekt-Prüfung. Sie enthält keine Secrets,
privaten Inhalte oder Fingerprints geschützter Informationen. Kann die Reihenfolge, Identität oder
Integrität dieser Evidenz nicht verifiziert werden, blockiert nur die betroffene Aktion nach
[GOV-004](../../GOVERNANCE.md#gov-004--fail-closed).
