# Threat Model des Explicit-Path-Installers

> Historische Evidenz - nicht normativ. Der ausführbare Vertrag liegt in Code, Tests und Bundle.

## Assets und Trust Boundaries

Geschützt werden Nutzerbytes der Entrydatei, das normative Bundle, persönliche lokale Regeln,
Backups, Aktivierungsmetadaten und Receipts. Vertrauensgrenzen liegen zwischen npm-Artefakt und
Staging, explizitem Zielroot und Installer, persistenter Transaktionsmetadatei und Recovery sowie
privater Regelquelle und veröffentlichbarer Evidenz. CLI-Argumente, bestehende Dateien und
persistente Metadaten werden nicht allein aufgrund ihrer Herkunft vertraut.

## Angreifer und Risiken

Berücksichtigt werden lokale unprivilegierte Konkurrenzprozesse, manipulierte oder beschädigte
Tarballs, Symlink- und Traversalumleitung, unerwartete Dateitypen, Marker-Manipulation,
TOCTOU-Austausch von Root, Entry oder Elternverzeichnis, manipulierte Receipt-Pfade, Signale und
partielle Dateisystemfehler. Ein bereits privilegierter Hostangreifer außerhalb der gewählten
Dateisystemgrenzen ist nicht vollständig beherrschbar.

## Kontrollen

- Das vollständige normative Bundle ist inventarisiert; Dateien, vollständiger Bundledigest,
  Größe und Typ sowie geschlossene Manifest-, Katalog- und Graphreferenzen werden vor Aktivierung geprüft.
- Target-, Entry-Parent-, Entry- und Installation-Identitäten werden erfasst und vor Mutation
  erneut geprüft. Symlinkbehaftete oder nichtkanonische Pfade scheitern fail-closed.
- Backup und Readback erfolgen vor der produktiven Entrymutation. Atomare Renames ersetzen nur
  reguläre Dateien im validierten Parent.
- Der Rollback-Detach verwendet einen receipt-eindeutigen Sibling-Namen im bereits inspizierten
  Entry-Parent. Die schmale Node-API-C-Primitive bindet dessen vorher erfasste Identität an einen
  offenen `O_DIRECTORY|O_NOFOLLOW`-Handle und akzeptiert ausschließlich einzelne Basenames.
  Linux `RENAME_NOREPLACE` beziehungsweise Darwin `RENAME_EXCL` macht No-Clobber zum Bestandteil
  desselben dirfd-relativen Syscalls. Loader-, Plattform-, Handle-, Syscall- und Filesystemfehler
  haben keinen unsicheren JavaScript-Fallback. Auch die exklusive Wiederanlage läuft über den
  gebundenen Parent-dirfd; Fehlercleanup löscht keinen erneut aufgelösten Namen. Die
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

## Residual Risks

Die handle-gebundene Native-Primitive wird nur für Darwin/Linux auf arm64/x64 ausgeliefert;
andere Plattformen können read-only inspizieren, aber nicht mutieren. Ein bereits privilegierter
Prozess kann offene Handles oder den Prozess selbst angreifen und liegt außerhalb dieses Vertrags.
`SIGKILL`, Stromausfall und Hardwarefehler sind nicht kooperativ
abfangbar. Das `PREPARED`-Receipt macht diese Zustände sichtbar und erzwingt Recovery, beweist aber
keine vollständige Crash-Atomarität. Die Markdownbindung beeinflusst Instruktionskontext und ist
kein universelles technisches Enforcement.
