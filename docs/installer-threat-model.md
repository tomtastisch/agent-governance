# Threat Model des Explicit-Path-Installers

> Historische Evidenz - nicht normativ. Der ausführbare Vertrag liegt in Code, Tests und Bundle.

## Assets und Trust Boundaries

Geschützt werden Nutzerbytes der Entrydatei, das normative Bundle, persönliche lokale Regeln,
Backups, Aktivierungsmetadaten und Receipts. Vertrauensgrenzen liegen zwischen npm-Artefakt und
Staging, explizitem Zielroot und Installer, persistenter Transaktionsmetadatei und Recovery sowie
privater Regelquelle und veröffentlichbarer Evidenz. CLI-Argumente, bestehende Dateien und
persistente Metadaten werden nicht allein aufgrund ihrer Herkunft vertraut.

## In Scope

Der Vertrag umfasst den normalen unprivilegierten Benutzerbetrieb, unbeabsichtigte Parallelität
und externe Änderungen, die vor einer produktiven Mutation beobachtbar sind. Dazu gehören
manipulierte oder beschädigte Tarballs, Symlink- und Traversalumleitung, unerwartete Dateitypen,
Marker-Manipulation, beobachtbare TOCTOU-Abweichungen, Root- und Parent-Replacement, stale oder
manipulierte Receipts und Backups,
Kollisionen, Signale und partielle Dateisystemfehler. Auch Manipulationen durch einen Prozess mit
derselben UID bleiben in scope, soweit der Installer sie beobachten oder mit einer verfügbaren
atomaren Dateisystemprimitive sicher entscheiden kann.

## Out of Atomic Guarantee

Die einzige hier ausgegrenzte Klasse ist ein aktiv bösartiger
**Same-UID-Final-Component-Co-Writer** mit eigener Schreibberechtigung auf demselben
Directory-Namespace, der die finale Namenskomponente gezielt zwischen der letzten möglichen
Identitätsbeobachtung und dem folgenden Kernel-Namespace-Syscall austauscht. Linux
`renameat2(..., RENAME_NOREPLACE)` und Darwin `renameatx_np(..., RENAME_EXCL)` binden Parent-
Directories und erzwingen No-Clobber. Die Plattformgrenze lautet: **kein atomarer Inode-CAS-Vertrag**
nach dem Muster „mutiere diesen Namen nur, wenn er weiterhin Inode X bezeichnet“.

Die Architekturentscheidung lautet deshalb: **kein privilegierter Broker**. Ein solcher
Systemdienst oder privilegierter Installationsmechanismus wäre eine andere Produktarchitektur mit
neuer Privilege Boundary und größerer Angriffsfläche. Ein gleichprivilegierter Co-Writer könnte
Dateien zudem nach einem abgeschlossenen Installerlauf erneut verändern. Diese enge Grenze ist
keine allgemeine Ausnahme für Same-UID-Manipulationen und schwächt beobachtbare Identity-,
Symlink-, Traversal-, Receipt-, Backup-, Collision- oder Recovery-Prüfungen nicht ab.

## Kontrollen

- Das vollständige normative Bundle ist inventarisiert; Dateien, vollständiger Bundledigest,
  Größe und Typ sowie geschlossene Manifest-, Katalog- und Graphreferenzen werden vor Aktivierung geprüft.
- Target-, Entry-Parent-, Entry-, Installation-, Binding-Root-, Releases-Root-, Release- und
  Local-Rules-Parent-Identitäten werden erfasst, soweit vorhanden im Receipt persistiert und vor
  der jeweiligen Mutation erneut geprüft. Symlinkbehaftete oder nichtkanonische Pfade scheitern
  fail-closed.
- Backup und Readback erfolgen vor der produktiven Entrymutation. Atomare Renames ersetzen nur
  reguläre Dateien im validierten Parent.
- Der Rollback-Detach verwendet einen receipt-eindeutigen Sibling-Namen im bereits inspizierten
  Entry-Parent. Die schmale Node-API-C-Primitive bindet dessen vorher erfasste Identität an einen
  offenen `O_DIRECTORY|O_NOFOLLOW`-Handle und akzeptiert ausschließlich einzelne Basenames.
  Linux `RENAME_NOREPLACE` beziehungsweise Darwin `RENAME_EXCL` macht No-Clobber zum Bestandteil
  desselben dirfd-relativen Syscalls. Loader-, Plattform-, Handle-, Syscall- und Filesystemfehler
  haben keinen unsicheren JavaScript-Fallback. Auch die exklusive Wiederanlage läuft über den
  gebundenen Parent-dirfd. Nach einem partiellen exklusiven Create entfernt Fehlercleanup nur die
  weiterhin als regulär und identisch beobachtete eigene Datei dirfd-relativ und bewahrt den
  ursprünglichen I/O-Fehler. Die enge Final-Component-Grenze oben gilt auch für diesen letzten
  Vergleich. Die
  receipt-spezifische Detach-Evidenz wird nicht pathname-basiert entfernt.
- Receipt-Schema, targetgebundene Binding-ID, UUID, Backuproot, direkter SemVer-Releasepfad und
  der exakt manifestbestimmte Local-Rules-Pfad sind geschlossen. Recovery verlangt zwei im stabilen Zustand
  bytegleiche Receiptkopien; ausschließlich write-order-konforme Statussplits mit identischen unveränderlichen
  Feldern sind recoverbar. Der explizite Zielpfad und jede Restore-Ressource werden unmittelbar vor ihrer Mutation
  sowie über ihr erwartetes Postimage revalidiert.
- Ein kanonischer ownergebundener Lock pro Installationsroot verhindert überlappende Shared-State-
  Mutationen. Recovery übernimmt ihn nur nach geschlossen validierter Owner-Evidenz und negativem
  Prozess-Liveness-Check. Vor Rollback werden Backup-Ahnen, Typen, receiptgebundene Digests, sämtliche
  Pre-/Postimages und andere aktive Bindungen geprüft; gemeinsam referenzierte Releases und lokale
  Regeln bleiben erhalten, und veraltete Zustände blockieren vor der ersten Restore-Mutation.
- Private lokale Regeln werden nicht ausgegeben. Ihre explizite Quelle muss eine kanonische
  Markdown-Datei sein und wird ebenso wie bereits installierte Regeln fatal auf UTF-8 und auf den
  Kontrollzeichenvertrag geprüft. Quelle, Lesevorgang und Pfadidentität werden über einen
  `O_NOFOLLOW`-Filehandle mit Vor-/Nachprüfung gebunden; Carry-forward bindet Bytes und Existenz an
  den Inspektionssnapshot. Entry, Current und Shared Local Rules werden nach beiden Commit-Receipt-
  Schreibvorgängen gemeinsam revalidiert. Secret-Patterns werden im Tarball-Gate geprüft.
- Inventarisierte normative Markdown- und TOML-Quellen werden mit fataler UTF-8-Dekodierung geprüft;
  von den rohen C0-/DEL-Kontrollzeichen sind ausschließlich TAB, LF und CR zulässig. Manifestreferenzen
  akzeptieren nur `.toml` für Kataloge sowie `.md` für Module, Rollen und lokale Regeln; TOML wird
  zusätzlich gegen ein geschlossenes Syntax-Subset validiert. Parserdivergenzen und unbekannte
  normative Dateiformate werden fail-closed abgelehnt.

## Rollback-Sink-Analyse

- **Entry:** Der Parent ist receiptgebunden; Detach, Restore und exklusive Wiederanlage verwenden
  validierte einzelne Basenames und offene Parent-dirfds mit atomarem No-Clobber.
- **Current-Metadaten:** Installation- und Binding-Root-Identitäten sind receiptgebunden und werden
  vor Restore oder Entfernung erneut geprüft; der atomare Dateiersatz bleibt im validierten Parent.
- **Local Rules:** Der erwartete Local-Rules-Parent ist receiptgebunden und wird vor jeder
  Restore-Mutation erneut geprüft. Shared-State- und Postimage-Prüfungen bleiben zusätzlich aktiv.
- **Release-Cleanup:** Releases-Root und konkreter Release-Container sind receiptgebunden und werden
  vor rekursivem Cleanup erneut geprüft. Ein beobachtbarer Containeraustausch blockiert
  fail-closed; nur das oben beschriebene nicht atomar entscheidbare finale Kernelfenster bleibt
  außerhalb der Garantie.

## Residual Risks

Die handle-gebundene Native-Primitive wird nur für Darwin/Linux auf arm64/x64 ausgeliefert;
andere Plattformen können read-only inspizieren, aber nicht mutieren. Ein bereits privilegierter
Prozess kann offene Handles oder den Prozess selbst angreifen und liegt außerhalb dieses Vertrags.
Die ausdrücklich beschriebene Same-UID-Final-Component-Klasse besitzt keinen atomaren
Inode-Compare-and-Mutate-Schutz; alle davor beobachtbaren Abweichungen bleiben fail-closed.
`SIGKILL`, Stromausfall und Hardwarefehler sind nicht kooperativ
abfangbar. Das `PREPARED`-Receipt macht diese Zustände sichtbar und erzwingt Recovery, beweist aber
keine vollständige Crash-Atomarität. Die Markdownbindung beeinflusst Instruktionskontext und ist
kein universelles technisches Enforcement.
