# JSON- und Exitcode-Vertrag

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

## Exitcodes

- `0`: Erfolg
- `2`: `INVALID_INVOCATION`
- `4`: `UNSAFE_STATE`
- `5`: `VERIFICATION_ROLLED_BACK`
- `6`: `ROLLBACK_FAILED`
- `130`: Unterbrechung durch `SIGINT`
- `143`: Unterbrechung durch `SIGTERM`
