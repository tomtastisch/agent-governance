# Installationsgrenze

> **Version:** siehe [`VERSION`](VERSION)

Dieses Boundary- und Verantwortungsdokument ist keine zweite Governancequelle. Die normative
Governance liegt ausschließlich unter `bundle/`; die öffentliche CLI materialisiert nur eine
daraus reproduzierbare globale Bindung.

Die Architektur `GLOBAL_EXPLICIT_PATH_MANAGED_BLOCK` verlangt `--scope global`, einen absoluten
kanonischen `--installation-root`, einen absoluten kanonischen `--target-root` und einen relativen
Markdownpfad in `--entry-file`. Es gibt kein Defaultziel, keinen cwd-Fallback, keine Harnesserkennung,
keinen Adapter, keine Hook-/MCP-/Approvalmutation und keine Projektinstallation.

Die Commands `inspect`, `plan`, `install`, `verify`, `status`, `update`, `uninstall` und `rollback`
verwenden denselben expliziten Vertrag. `--dry-run` mutiert nichts, `--json` liefert Schema 1 und
`--non-interactive` erlaubt vollständige Automation. `--local-rules` bezeichnet optional eine
absolute kanonische reguläre Markdown-Datei. Sie muss gültiges UTF-8 enthalten; von rohen
C0-/DEL-Kontrollzeichen sind nur TAB, LF und CR zulässig. Ihr Inhalt erscheint weder in Ausgabe
noch Evidenzfingerprints.

Die atomare Garantie hat eine enge Plattformgrenze: Linux und Darwin bieten keinen atomaren
Inode-CAS-Vertrag gegen einen bösartigen Same-UID-Final-Component-Co-Writer, der mit eigener
Schreibberechtigung die finale Namenskomponente genau zwischen Beobachtung und Namespace-Syscall
austauscht. Die Architekturentscheidung lautet: kein privilegierter Broker. Beobachtbare Root-,
Parent-, Symlink-, Receipt-, Backup- und Collision-Abweichungen bleiben fail-closed Bestandteil
des Sicherheitsvertrags.

Vor der Entry-Mutation erzeugt der Installer ein Backup und verifiziert es per Readback. Releases
werden unter `<installation-root>/releases/<version>/bundle` vollständig inventar- und
digestgeprüft; `bindings/<binding-id>/current.json` wird atomar ersetzt, und
`backups/<binding-id>/<transaction-id>` enthält eine zweite gebundene Receiptkopie. Im stabilen Zustand sind beide
Kopien bytegleich; ein Abbruch zwischen Statuswrites ist ausschließlich für die erwartete Write-Reihenfolge und
identische unveränderliche Receiptfelder recoverbar.
`PREPARED`, `COMMITTED` und `ROLLED_BACK` unterscheiden Recoveryzustände. `SIGINT` und `SIGTERM`
werden serialisiert behandelt (Exit 130 beziehungsweise 143); `SIGKILL`, Stromausfall und
Dateisystemdefekte können nur durch den verifizierten Recoveryvertrag, nicht durch eine falsche
Atomaritätsbehauptung adressiert werden.
Vor der ersten produktiven Mutation führt der Installer auf Entry- und Installationsdateisystem
eine rückstandsfreie native No-Clobber-Probe aus. Current-, Local-Rules-, Receipt-, Lock- und
Release-Aktivierungsmutationen bleiben danach an identitätsgeprüfte Parent-dirfds gebunden.

Der Managed Block beginnt mit `<!-- BEGIN AGENT_GOVERNANCE_MANAGED_V1 -->` und endet mit
`<!-- END AGENT_GOVERNANCE_MANAGED_V1 -->`. Außenbytes und vorhandene LF-/CRLF-Zeilenenden bleiben
erhalten; doppelte, unvollständige, fremde oder manipulierte Marker scheitern fail-closed. Update
ersetzt, Uninstall entfernt ausschließlich diesen Block; Rollback stellt die vollständige vorherige
Datei wieder her. Zur crash-sicheren, konkurrenzfesten Entry-Wiederherstellung reserviert Rollback
neben der Entry-Datei ein receipt-spezifisches `.<entry>.agent-governance-<transaction-id>.restore/`
mit Modus `0700`. Dessen identitätsgebundene `entry.bin` bleibt nach erfolgreichem Rollback als
Recovery-Evidenz erhalten; sie wird weder von Uninstall noch durch spätere Transaktionen implizit gelöscht.

Veröffentlichung erfolgt zuerst als `1.0.0-rc.N` unter `next`, nach öffentlichem Readback,
Provenance- und Fresh-Install-Prüfung separat als `1.0.0` unter `latest`. Eine lokale produktive
Migration darf ausschließlich aus dem vollständig geprüften öffentlichen Stable-Paket erfolgen.
