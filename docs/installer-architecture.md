# Installerarchitektur 1.0

> Nicht normative Architekturreferenz. Maßgeblich bleiben das Bundle und der getestete öffentliche
> CLI-Vertrag.

## Init-Onboarding und Dependency-Grenze

Der normale öffentliche Einstieg ist exakt `npm i @tomtastisch/agent-governance` gefolgt von
`npx agent-governance init`. `init` orchestriert ausschließlich die vorhandene Transaktion
`status -> plan -> [Bestätigung] -> install|update -> verify`; Runtime-Abhängigkeiten werden vorab
durch die deklarativen
`package.json.dependencies` und das Lockfile geliefert. Der Init-Pfad startet weder npm, pnpm,
yarn oder bun noch einen Package-Manager-Bootstrap und enthält keinen Self-Install-, Repair- oder
bedingten Nachladepfad. Fehlt eine direkte Runtime-Abhängigkeit, schlägt das Paket fail-closed fehl.

Vor der Transaktion nutzt `init` eine begrenzte, passive und nicht mutierende Discovery als
Auswahlunterstützung. Sie trifft keine automatische Zielannahme, mutiert keinen Harness und besitzt
keine fachliche Authority. Die bewusste Auswahl erzeugt explizite Transaktionsziele; Status und
Pläne werden für alle Ziele vor einer gemeinsamen Bestätigung ermittelt. Erst diese Bestätigung
autorisiert die Mutation.

Die Installed-Harness-Erkennung des `init`-Screens ist auf einen einzelnen Adapter hinter
`@agntn/harnesses` beschränkt, der ausschließlich `getAllHarnesses()` und `isInstalled()` nutzt und
keine erkannte Harness-CLI startet. Welcher erkannte Harness automatisch unterstützt wird und
welches Binding-/Entry-Ziel zulässig ist, entscheidet allein die Agent-Governance-Support-/Binding-SSOT;
Daten oder Pfade aus der Dependency werden niemals automatisch als Binding-Ziel übernommen.

## Architektur

`GLOBAL_EXPLICIT_PATH_MANAGED_BLOCK` trennt drei Verantwortungen: Der Releaseverifier akzeptiert
nur ein geschlossenes, digestgebundenes Bundle; der Targetvalidator akzeptiert nur explizite
kanonische Pfade ohne Symlinks oder Escape; die Transaktion aktiviert Release-Metadaten und genau
einen generischen Markdown-Block. Der generische Installer-/Runtime-/Release-Verifier-Core besitzt
kein ad-hoc Harnesswissen; konkrete Harnessidentitäten existieren nur in ausdrücklich autorisierten
Support-, Binding- und Kompatibilitätsflächen, insbesondere der Init-Support-/Binding-SSOT.
Der Paket- und Stagingpfad validiert ausschließlich den aktuellen semantischen Governance-Contract.
Bereits installierte Releases verwenden denselben Byte-, Inventar-, Pfad- und Digestverifier, aber
eine explizite geschlossene Liste historisch veröffentlichter Contract-Varianten. Unbekannte
zukünftige Varianten und jede Inhaltsabweichung bleiben fail-closed.

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

![Detaillierte Übersicht über Bindings, normative Dateien, Routing und Laufzeitfluss.](../assets/diagrams/governance-architecture.png)

## Installation und Lifecycle

Eine Transaktion materialisiert ausschließlich eine globale, explizit gewählte Bindung:
`--scope global`, ein absoluter kanonischer `--installation-root`, ein absoluter kanonischer
`--target-root` und ein relativer Markdownpfad in `--entry-file`. Es gibt kein Defaultziel, keinen
cwd-Fallback, keine aus Produktidentität abgeleitete Zielannahme und keine Projektinstallation. Die
[Harness-Rezepte](harness-recipes.md) helfen allein bei der manuellen Auswahl eines verifizierten
Ziels; sie verändern diesen Pfadvertrag nicht.

Vor der Entry-Mutation erstellt der Installer ein Backup und verifiziert es per Read-back. Das
Release unter `releases/<version>/bundle` wird vollständig gegen Inventar und Digests geprüft. Im
stabilen Zustand sind `bindings/<binding-id>/current.json` und die gebundene Receiptkopie unter
`backups/<binding-id>/<transaction-id>` bytegleich. `PREPARED`, `COMMITTED` und `ROLLED_BACK`
klassifizieren Recoveryzustände. `SIGINT` und `SIGTERM` werden serialisiert behandelt; bei
`SIGKILL`, Stromausfall oder Dateisystemdefekten entscheidet allein der verifizierte
Recoveryvertrag. Das zugehörige Exitverhalten gehört zur
[Installer-CLI-Referenz](installer-cli-reference.md#exitverhalten).

## Managed Block

Der V1-Block enthält Version, kanonischen Installationsroot, normative Bootstrap-/Manifestpfade,
Governance-, Manifest- und vollständigen Bundledigest, die Pre-Response-Ladepflicht, die Trennung
lokaler Regeln und Fail-closed-Verhalten. Er beginnt mit
`<!-- BEGIN AGENT_GOVERNANCE_MANAGED_V1 -->` und endet mit
`<!-- END AGENT_GOVERNANCE_MANAGED_V1 -->`. Außenbytes und vorhandene LF-/CRLF-Zeilenenden bleiben
erhalten; doppelte, unvollständige, fremde oder manipulierte Marker scheitern fail-closed. Update
ersetzt und Uninstall entfernt ausschließlich den verwalteten Block; Rollback stellt die
vollständige vorherige Datei wieder her.

Für die crash-sichere, konkurrenzfeste Entry-Wiederherstellung reserviert Rollback neben der
Entry-Datei ein receipt-spezifisches `.<entry>.agent-governance-<transaction-id>.restore/` mit
Modus `0700`. Dessen identitätsgebundene `entry.bin` bleibt nach erfolgreichem Rollback als
Recovery-Evidenz erhalten und wird weder von Uninstall noch durch spätere Transaktionen implizit
gelöscht. JSON-Strukturen und Feldsemantik gehören ausschließlich zu den
[JSON-Schemas](installer-json-schemas.md).

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
