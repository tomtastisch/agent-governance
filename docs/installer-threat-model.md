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

- Das vollständige normative Bundle ist inventarisiert; Dateien, Digests, Größe, Typ und
  Manifestreferenzen werden vor Aktivierung geprüft.
- Target-, Entry-Parent-, Entry- und Installation-Identitäten werden erfasst und vor Mutation
  erneut geprüft. Symlinkbehaftete oder nichtkanonische Pfade scheitern fail-closed.
- Backup und Readback erfolgen vor der produktiven Entrymutation. Atomare Renames ersetzen nur
  reguläre Dateien im validierten Parent.
- Receipt-Schema, UUID, Backuproot, direkter SemVer-Releasepfad und Local-Rules-Containment sind
  geschlossen. Recovery revalidiert den expliziten Zielpfad.
- Private lokale Regeln werden nicht ausgegeben; Secret-Patterns werden im Tarball-Gate geprüft.

## Residual Risks

Node-Dateisystemaufrufe bieten keinen vollständigen offenen Handle-Vertrag über alle Plattformen;
ein privilegierter Angreifer kann zwischen Identity-Recheck und Rename weiterhin ein enges
TOCTOU-Fenster ausnutzen. `SIGKILL`, Stromausfall und Hardwarefehler sind nicht kooperativ
abfangbar. Das `PREPARED`-Receipt macht diese Zustände sichtbar und erzwingt Recovery, beweist aber
keine vollständige Crash-Atomarität. Die Markdownbindung beeinflusst Instruktionskontext und ist
kein universelles technisches Enforcement.
