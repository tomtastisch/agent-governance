# Release-Metadaten vorbereiten

`VERSION` ist die einzige Versionsauthority. Das Release-Datum stammt ausschließlich
vom eindeutigen, ersten versionierten Abschnitt in `CHANGELOG.md`, dessen Version
`VERSION` entspricht. Der Abschnitt trägt ein gültiges Datum in der Form
`## [<VERSION>] — YYYY-MM-DD`.

Nach Änderung dieser beiden Quellen werden die bestehenden npm-Projektionen,
Zitiermetadaten und das Payload-Manifest deterministisch aktualisiert:

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
einzeilige Releasewerte; mehrdeutige Formen, fehlende Felder oder Symlink-Eingaben
werden abgewiesen. Es gibt keine Datumsoption und keinen Zeitstempel aus der Uhr.

Das bestehende Release-Metadaten-Gate prüft die CFF-Projektionen unabhängig vom
Schreibvorgang. Fehlender Sync, Versions-/Datumsdrift und ein `commit`-Feld blockieren
die Tree-Prüfung sowie die Metadatenprüfung vor Tag/Release/Registry-Aktionen.

Anschließend gelten unverändert die Repository-Gates und unabhängigen Reviews,
der geschützte PR-/Merge-Weg, der signierte `v<VERSION>`-Tag und der Workflow
`Trusted Release Tag Gate`. Nach Veröffentlichung des GitHub-Releases wird
`Trusted npm Publish` auf `main` mit dem signierten Tag und dem für die Version
vorgesehenen Dist-Tag ausgeführt. Veröffentlichung und Provenance benötigen
Remote-Readbacks. Ein Zenodo-Record oder DOI gilt erst nach öffentlicher
Verifikation als vorhanden; die CFF allein belegt keine abgeschlossene Archivierung.
