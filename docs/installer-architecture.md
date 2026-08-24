# Installerarchitektur 1.0

> Historische Evidenz - nicht normativ. Maßgeblich bleiben das Bundle und der getestete
> öffentliche CLI-Vertrag.

## Architektur

`GLOBAL_EXPLICIT_PATH_MANAGED_BLOCK` trennt drei Verantwortungen: Der Releaseverifier akzeptiert
nur ein geschlossenes, digestgebundenes Bundle; der Targetvalidator akzeptiert nur explizite
kanonische Pfade ohne Symlinks oder Escape; die Transaktion aktiviert Release-Metadaten und genau
einen generischen Markdown-Block. Keine Schicht kennt Harnessnamen oder produktspezifische Dateien.

Die aktive Installation verwendet `releases/<version>/bundle`, pro explizitem Ziel eine atomar
ersetzte `bindings/<binding-id>/current.json` und `backups/<binding-id>/<transaction-id>`. Der
symlinkfreie Current-Vertrag vermeidet eine
zweite Link-Vertrauensklasse. Der sicherheitskritische Entry-Detach verwendet einen
receipt-eindeutigen Sibling-Basename im bereits autoritativ identifizierten Entry-Parent. Die
repo-eigene Node-API-Primitive öffnet diesen Parent mit `O_DIRECTORY|O_NOFOLLOW`, gleicht den
Handle gegen die vorher erfasste Identität ab und führt ausschließlich validierte einzelne
Basenames aus: Linux verwendet
`renameat2(..., RENAME_NOREPLACE)`, Darwin `renameatx_np(..., RENAME_EXCL)`. Es existiert kein
pathname-basierter Fallback; fehlende Plattform-, Binary-, Syscall- oder Dateisystemfähigkeit
blockiert produktive Mutation fail-closed. Diese Primitive ist No-Clobber und parentgebunden,
aber kein Inode-Compare-and-Rename gegen einen bösartigen Same-UID-Final-Component-Swap im
letzten Kernel-Race-Fenster; die enge Grenze ist im
[Threat Model](installer-threat-model.md#out-of-atomic-guarantee) definiert. Vor jedem weiteren
produktiven Rename werden beobachtbare Identitäten erneut geprüft;
Backup, Staging, Aktivierung, Verifikation und Rollback haben geschlossene Zustände.
Current-, Local-Rules-, Receipt- und Lockdateien werden über native, identitätsgebundene Parent-
dirfds ersetzt oder entfernt. Eine rückstandsfreie Probe führt den exklusiven Rename auf jedem
betroffenen Dateisystem vor der ersten produktiven Mutation real aus.

## Managed Block und JSON

Der V1-Block enthält Version, kanonischen Installationsroot, normative Bootstrap-/Manifestpfade,
Governance-, Manifest- und vollständigen Bundledigest, die Pre-Response-Ladepflicht, die Trennung lokaler Regeln und
Fail-closed-Verhalten. JSON-Schema 1 nennt Architektur, Command, Outcome, Zustand, Phase,
Rollbackstatus, Capability-Liste und optional einen Ressourcenplan. Exitcodes sind 0 (Erfolg),
2 (ungültiger Aufruf), 4 (unsicherer Zustand), 5 (Fehler mit erfolgreichem Rollback), 6
(Rollbackfehler) sowie 130/143 für SIGINT/SIGTERM.

## Update, Uninstall und Recovery

Update ersetzt nur den eigenen Block und Current-Metadaten nach vollständig verifiziertem Staging.
Uninstall entfernt nur Block und aktive Metadaten; versionierte Releases und Backups bleiben für
Rollback erhalten. Rollback liest ausschließlich das geschlossene letzte Receipt und stellt
Entry- und Current-Bytes idempotent wieder her. Ein ownergebundener installationsrootweiter Lock schließt
parallele Mutationen fail-closed aus und kann bei Recovery nur für einen nachweislich nicht lebenden
Owner atomar übernommen werden. Digestgebundene Pre-/Postimages und vollständige Restore-Vorprüfung
verhindern Teilmutationen; aktive Fremdbindungen schützen gemeinsam referenzierte Releases und lokale
Regeln vor einem veralteten Rollback. Ein `PREPARED`-Receipt blockiert neue Mutationen,
bis Recovery ausgeführt wurde. Ein gemeinsamer Installationsroot verwaltet mehrere explizite
Target-/Entry-Bindings unabhängig. Top-Level- und Backup-Receipt sind im stabilen Zustand bytegleich;
write-order-konforme Zwischenzustände mit identischen unveränderlichen Feldern erzwingen Recovery und
werden durch den idempotenten Rollback geschlossen. Eine erst nach beiden Commit-Schreibvorgängen
erkannte gemeinsame Postimage-Abweichung demotiert zuerst das Backup- und danach das Top-Level-Receipt
crash-sicher auf `PREPARED`, bevor ein Rollback versucht wird.
Das Receipt bindet zusätzlich die erwarteten Identitäten von Entry-Parent, Installationsroot,
Binding-Root, Releases-Root sowie den gegebenenfalls vorhandenen Release- und Local-Rules-Parent.
Ein später beobachtbarer Austausch eines dieser Container blockiert Recovery vor dessen Mutation.
Ein neu aktivierter Release bleibt nach fehlgeschlagener Transaktion als vollständig verifiziertes,
unreferenziertes Recoveryartefakt erhalten, statt über einen rekursiv erneut aufgelösten Pathname
entfernt zu werden.
Die receipt-spezifische Sibling-Detach-Datei bleibt als Recoveryevidenz erhalten. Der Installer
entfernt sie nicht pathname-basiert und löscht dadurch bei einem späteren Namensaustausch keine
fremden Bytes. Auch die Wiederanlage des gewünschten Entry-Postimages erfolgt exklusiv über den
identitätsgebundenen Parent-dirfd.

## Grenzen und Migration

Der unveröffentlichte 0.6.0-Codex-Entwurf mit `--harness`, festen Homepfaden, `hooks.json` und
PreToolUse-Bridge ist entfernt. Fremdadapter wurden nach Supply-Chain- und Capability-Audit
verworfen. Die v0.5.0-Migration besteht aus explizitem Inventar und Backup, Installer-Dry-Run,
Managed-Block-Installation und Fresh-Session-Verifikation; sie erfolgt lokal erst aus öffentlichem
Stable. Dateisystemerfolg allein begründet niemals `HARNESS_E2E_VERIFIED`.
