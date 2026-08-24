# JSON- und Exitcode-Vertrag

> Historische Evidenz - nicht normativ. Maßgeblich ist das geschlossene TypeScript-Schema.

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

## Exitcodes

- `0`: Erfolg
- `2`: `INVALID_INVOCATION`
- `4`: `UNSAFE_STATE`
- `5`: `VERIFICATION_ROLLED_BACK`
- `6`: `ROLLBACK_FAILED`
- `130`: Unterbrechung durch `SIGINT`
- `143`: Unterbrechung durch `SIGTERM`
