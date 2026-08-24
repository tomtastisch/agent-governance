# Installerarchitektur 1.0

> Historische Evidenz - nicht normativ. Maßgeblich bleiben das Bundle und der getestete
> öffentliche CLI-Vertrag.

## Architektur

`GLOBAL_EXPLICIT_PATH_MANAGED_BLOCK` trennt drei Verantwortungen: Der Releaseverifier akzeptiert
nur ein geschlossenes, digestgebundenes Bundle; der Targetvalidator akzeptiert nur explizite
kanonische Pfade ohne Symlinks oder Escape; die Transaktion aktiviert Release-Metadaten und genau
einen generischen Markdown-Block. Keine Schicht kennt Harnessnamen oder produktspezifische Dateien.

Die aktive Installation verwendet `releases/<version>/bundle`, eine atomar ersetzte
`current.json` und `backups/<transaction-id>`. Der symlinkfreie Current-Vertrag vermeidet eine
zweite Link-Vertrauensklasse. Vor jedem produktiven Rename werden Identitäten erneut geprüft;
Backup, Staging, Aktivierung, Verifikation und Rollback haben geschlossene Zustände.

## Managed Block und JSON

Der V1-Block enthält Version, kanonischen Installationsroot, normative Bootstrap-/Manifestpfade,
beide erwarteten SHA-256-Digests, die Pre-Response-Ladepflicht, die Trennung lokaler Regeln und
Fail-closed-Verhalten. JSON-Schema 1 nennt Architektur, Command, Outcome, Zustand, Phase,
Rollbackstatus, Capability-Liste und optional einen Ressourcenplan. Exitcodes sind 0 (Erfolg),
2 (ungültiger Aufruf), 4 (unsicherer Zustand), 5 (Fehler mit erfolgreichem Rollback), 6
(Rollbackfehler) sowie 130/143 für SIGINT/SIGTERM.

## Update, Uninstall und Recovery

Update ersetzt nur den eigenen Block und Current-Metadaten nach vollständig verifiziertem Staging.
Uninstall entfernt nur Block und aktive Metadaten; versionierte Releases und Backups bleiben für
Rollback erhalten. Rollback liest ausschließlich das geschlossene letzte Receipt und stellt
Entry- und Current-Bytes idempotent wieder her. Ein `PREPARED`-Receipt blockiert neue Mutationen,
bis Recovery ausgeführt wurde.

## Grenzen und Migration

Der unveröffentlichte 0.6.0-Codex-Entwurf mit `--harness`, festen Homepfaden, `hooks.json` und
PreToolUse-Bridge ist entfernt. Fremdadapter wurden nach Supply-Chain- und Capability-Audit
verworfen. Die v0.5.0-Migration besteht aus explizitem Inventar und Backup, Installer-Dry-Run,
Managed-Block-Installation und Fresh-Session-Verifikation; sie erfolgt lokal erst aus öffentlichem
Stable. Dateisystemerfolg allein begründet niemals `HARNESS_E2E_VERIFIED`.
