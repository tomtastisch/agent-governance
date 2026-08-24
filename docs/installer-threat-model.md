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
- Private lokale Regeln werden nicht ausgegeben; Secret-Patterns werden im Tarball-Gate geprüft.
- Normative TOML-Quellen werden mit fataler UTF-8-Dekodierung und einem geschlossenen, kontrollzeichenfreien
  Syntax-Subset geprüft; Parserdivergenzen werden fail-closed abgelehnt.

## Residual Risks

Node-Dateisystemaufrufe bieten keinen vollständigen offenen Handle-Vertrag über alle Plattformen;
ein privilegierter Angreifer kann zwischen Identity-Recheck und Rename weiterhin ein enges
TOCTOU-Fenster ausnutzen. `SIGKILL`, Stromausfall und Hardwarefehler sind nicht kooperativ
abfangbar. Das `PREPARED`-Receipt macht diese Zustände sichtbar und erzwingt Recovery, beweist aber
keine vollständige Crash-Atomarität. Die Markdownbindung beeinflusst Instruktionskontext und ist
kein universelles technisches Enforcement.
