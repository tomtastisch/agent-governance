# JSON-Schema-Vertrag

> Nicht normative JSON-Referenz. Maßgeblich ist das geschlossene TypeScript-Schema.

Erfolgsobjekte enthalten ausschließlich `schemaVersion`, `architecture`, `command`, `outcome`,
`state`, `phase`, `rollbackStatus`, `capabilities` und optional `plan`. `schemaVersion` ist `1`,
`architecture` ist `GLOBAL_EXPLICIT_PATH_MANAGED_BLOCK`, und `outcome` ist bei Erfolg `SUCCESS`.

Zulässige Zustände sind `FRESH`, `CURRENT`, `OUTDATED`, `DOWNGRADE_BLOCKED`, `ABSENT`, `TAMPERED`
und `RECOVERY_REQUIRED`. Phasen sind `inspect`, `plan`, `backup`, `stage`, `activate`, `verify`
und `rollback`. Capabilitywerte sind `FILESYSTEM_INSTALLED`, `BINDING_MATERIALIZED`,
`DIGEST_VERIFIED` und `ROLLBACK_AVAILABLE`; `HARNESS_E2E_VERIFIED` wird nicht aus dem
Dateisystem-CLI abgeleitet.

Ein Plan enthält Schema, Architektur, Command, Zustand, eine geordnete Ressourcenliste sowie die
festen Negativfelder `harnessSpecificMutation: false`, `mcpMutation: false`,
`hookMutation: false` und `approvalExpansion: false`. Ressourcen-IDs sind `release`,
`current-metadata`, `entry-file`, `backup`, `receipt` und optional `local-rules`.

Fehlerausgaben besitzen ebenfalls `schemaVersion` und einen geschlossenen Outcome; für
Transaktionsfehler kommen Phase, abstrakte Ressourcen-ID, Rollbackstatus und Fehlercode hinzu.
Entry- oder Regelinhalt und daraus abgeleitete Fingerprints erscheinen nie im Schema.

Init-Ergebnisse verwenden den eigenen typisierten `InitResult`-Vertrag. Bei Unterbrechung enthält
`targets` die bereits vollständig eingerichteten und verifizierten Ziele. Unterbrochene externe
Tool-Mutationen einschließlich ihres Read-backs ergänzen optional `externalEffect` mit
`state: "UNVERIFIED"`, `rollback: "NOT_ATTEMPTED"` und `guidance`. Die abstrakte `resourceId`
unterscheidet `github_cli:inspect`, `github_cli:install` und `github_cli:login`. Dieser optionale
Kontext führt keine persistente Tool-State-Authority und keine externe Rollbackzusage ein.

## Feldsemantik

- `schemaVersion` versioniert die Ausgabestruktur; Verbraucher dürfen nur Schema `1` als diesen
  Vertrag lesen.
- `architecture` identifiziert `GLOBAL_EXPLICIT_PATH_MANAGED_BLOCK`; `command` nennt den
  ausgeführten öffentlichen Command und `outcome` sein Ergebnis.
- `state` beschreibt den klassifizierten Bindungszustand, `phase` den erreichten
  Transaktionsschritt und `rollbackStatus` den Recoveryausgang.
- `capabilities` nennt ausschließlich belegte Installerfähigkeiten. Insbesondere ist
  `HARNESS_E2E_VERIFIED` keine durch die Dateisystem-CLI ableitbare Capability.
- `plan` ist nur bei geplanten Operationen vorhanden und beschreibt Ressourcen sowie die festen
  Negativfelder für Harness-, MCP-, Hook- und Approvalmutationen.

Das Exitverhalten der öffentlichen Commands steht in der
[Installer-CLI-Referenz](installer-cli-reference.md#exitverhalten).
