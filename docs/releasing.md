# Release-Metadaten vorbereiten

`VERSION` ist die einzige Versionsauthority. Das Release-Datum stammt ausschließlich
vom eindeutigen, ersten versionierten Abschnitt in `CHANGELOG.md`, dessen Version
`VERSION` entspricht. Der Abschnitt trägt ein gültiges Datum in der Form
`## [<VERSION>] — YYYY-MM-DD`.

## Vorbereitung im bestehenden Liefer-/Release-PR

Fachliche Changelog-Einträge werden während der Umsetzung unter `[Unreleased]` gepflegt.
Der Release Owner bestimmt Bump-Intent oder Zielversion und ein bewusstes Release-Datum.
Das Repositorytool materialisiert daraus die Metadaten im **selben bereits autorisierten
Liefer-/Release-PR** vor dessen finalem Exact-Head-Gate:

```sh
python3 tools/prepare_release.py --bump minor --date YYYY-MM-DD
# Alternativ ein explizites SemVer-Ziel:
python3 tools/prepare_release.py --target X.Y.Z --date YYYY-MM-DD
```

`--bump` akzeptiert `patch`, `minor` oder `major` aus einer stabilen `VERSION` ohne
Buildmetadaten; für Prereleases/Buildmetadaten ist ein explizites Ziel erforderlich.
`--target` verlangt strikt gültiges SemVer mit höherer Präzedenz. Derselbe explizite Zielwert
ist idempotent, sofern Release-Datum und kanonisch leerer Unreleased-Bereich übereinstimmen.
Ein Downgrade oder nur geänderte Buildmetadaten bei gleicher Präzedenz scheitern geschlossen.
Das obligatorische Datum hat keinen Uhr-Fallback; nach dem Cut bleibt allein der datierte
CHANGELOG-Abschnitt seine Authority. Ein Issue darf das fachliche Releaseziel ausdrücken,
ersetzt aber niemals `VERSION` als technische Versionsauthority.

Der Cut übernimmt den vorhandenen Unreleased-Inhalt bytegleich in den neuen Releaseabschnitt
und setzt dessen bisherige Kategorien in derselben Reihenfolge auf `- Keine.` sowie den
Breaking-Marker auf `none` zurück. Das Repositoryformat ist UTF-8/LF. Mehrdeutige Überschriften,
doppelte Kategorien/Marker, ungültige Versionen und inkonsistente Historie werden abgewiesen.

Prepare prüft einen isolierten Kandidaten mit den bestehenden Version-, Citation-, Manifest-
und Tree-Primitiven. Erst danach übernimmt die vorhandene transaktionale Sync-/Rollback-Primitive
die sechs Metadatendateien gemeinsam. Reguläre Eingaben werden an ihre Dateiidentitäten gebunden;
beobachtbare Änderungen während der Vorbereitung, Symlinks und unsichere Dateitypen blockieren
die Übernahme. Fehler vor Übernahme verändern keine Release-Metadaten; abfangbare Schreibfehler
werden zurückgerollt. SIGKILL/Stromausfall oder ein fehlgeschlagener Rollback sind keine zugesagte
Mehrdatei-Crash-Atomarität: erhaltene `.sync-version-*`-Backups erfordern Prüfung vor Wiederholung.
Concurrent Writer während der finalen Rename-Sequenz sind wie bei der bestehenden Sync-Primitive
außerhalb einer atomaren Inode-CAS-Garantie; Prepare nur im exklusiv verwendeten Worktree ausführen.

Für Agent Governance gilt: **kein separater Version-only-PR als normaler Release-Schritt**
und kein ungeprüfter Post-Merge-Versionscommit auf `main`. Reihenfolge:

```text
Implementierung → Prepare Release → finaler Exact Head → relevante CI → QA/SEC → Merge
```

Metadatenänderungen invalidieren die davon betroffene Evidence gemäß DEL-002/DEL-006.
Die vorhandene CI prüft den neuen Head: Release-Metadaten, Konsistenz-/Drift-Tests,
Installer-/Package-/Plattformgates und Prepare-Contracts in der Python-Suite.
Historische Pläne dokumentieren ihren damaligen Stand und sind keine aktuelle Release-Authority.

## Bestehende Projektionen und Diagnose

Prepare orchestriert diese bestehenden Primitiven; sie bleiben einzeln für Diagnose und
gezielten Projektionsabgleich verfügbar, sind aber kein zweiter normaler Bump-Pfad:

```sh
python3 tools/sync_version.py
python3 tools/sync_citation.py
python3 tools/release_manifest.py generate
python3 tools/release_check.py tree
python3 tools/release_manifest.py check
```

Der Citation-Sync schreibt nur `CITATION.cff.version` und `date-released` und entfernt
`commit`. Andere CFF-Inhalte bleiben bytegleich. Eine erneute Ausführung ist
idempotent. Die CFF verwendet eindeutige, unquotierte Root-Schlüssel und einfache,
einzeilige Releasewerte. Die unterstützte YAML-Teilmenge umfasst einfache
Root-Skalare, eingerückte Textblöcke, Autorenlisten aus einfachen Mappings und
Keyword-Listen. Andere Strukturen, mehrdeutige Formen, fehlende Releasefelder,
Steuerzeichen oder Symlink-Eingaben werden abgewiesen. LF-, CRLF- und CR-Zeilenenden
bleiben erhalten. Das ist eine Layoutprüfung, keine vollständige CFF-Schemaprüfung. Es gibt keine Datumsoption und keinen Zeitstempel aus der Uhr.

Das bestehende Release-Metadaten-Gate prüft die CFF-Projektionen unabhängig vom
Schreibvorgang. Fehlender Sync, Versions-/Datumsdrift und ein `commit`-Feld blockieren
die Tree-Prüfung sowie die Metadatenprüfung vor Tag/Release/Registry-Aktionen.
Tag- und Release-Checks lesen CFF und CHANGELOG zusätzlich aus regulären Blobs des
aufgelösten Tag-Commits; eine spätere Korrektur auf `main` verdeckt keinen Tag-Drift.

## Veröffentlichung und Read-back

Prepare erzeugt keinen Commit, Tag oder zusätzlichen PR und führt keine GitHub-/npm-Mutation aus.
**Prepare ist keine Veröffentlichung und keine Merge-/Publishing-Freigabe.**
Anschließend gelten unverändert die Repository-Gates und unabhängigen Reviews,
der geschützte PR-/Merge-Weg, der signierte `v<VERSION>`-Tag und der Workflow
`Trusted Release Tag Gate`. Nach Veröffentlichung des GitHub-Releases wird
`Trusted npm Publish` auf `main` mit dem signierten Tag und dem für die Version
vorgesehenen Dist-Tag ausgeführt. Veröffentlichung und Provenance benötigen
Remote-Readbacks. Ein Zenodo-Record oder DOI gilt erst nach öffentlicher
Verifikation als vorhanden; die CFF allein belegt keine abgeschlossene Archivierung.
