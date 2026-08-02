# Agent Governance

> **Version:** [`0.1.0`](VERSION) &mdash; [Changelog](CHANGELOG.md)

Dieses Repository liefert ein kompaktes, harness- und providerneutrales Governance-Bundle.
Die installierbaren Inhalte liegen ausschließlich unter `bundle/`:

```text
bundle/
├── GOVERNANCE.md
└── agent-governance/
    ├── manifest.toml
    ├── modules/
    ├── roles/
    └── local/
        └── user-rules.example.md
```

`bundle/GOVERNANCE.md` enthält die kanonischen Bootstrap-Bytes. Das Manifest ist ein statischer,
fail-closed Index relativer Modul- und Rollenpfade. Lokale Nutzerregeln sind optional, bleiben
unversioniert und liegen später neben dem Beispiel unter
`bundle/agent-governance/local/user-rules.md`.

Harness-spezifische Bootstrap-Templates, Adapter, Rollenwrapper sowie die alten Core- und
Profilquellen gehören nicht mehr zum aktuellen Repositoryzustand. Repository-Dateien außerhalb
von `bundle/` werden vom Bundle nicht als Governance geladen.

## Cluster-4-Grenze

`project.toml` und `tools/` sind ein noch nicht konsolidierter operativer Bestand für Cluster 4.
Sie sind keine Governance-Quelle und werden vom Bootstrap oder Manifest nicht geladen. Ihre
Provider-, Runtime-, Tool- und Control-Plane-Inhalte sind mit Cluster 3 weder freigegeben noch
bereinigt worden.

Ein Installer und die Migration bestehender Nutzerdateien sind noch nicht implementiert. Der
aktuelle Status und die daraus folgende Installationsgrenze stehen in [INSTALL.md](INSTALL.md).

## Versionierung und lokale Prüfung

`VERSION` ist die SemVer-Quelle des Repositorys. `CHANGELOG.md` hält freigegebene und noch nicht
freigegebene Änderungen auseinander. Ein lokaler Entwicklungsstand ist kein Release.

Die mechanischen Prüfungen laufen ohne Fremdabhängigkeiten:

```text
python3 -m unittest discover -s tests -v
python3 tools/release_check.py tree
```

Die Tests prüfen insbesondere Bootstrap-Budget, Manifeststruktur, geschlossene Modul- und
Rollenauflösung, Regel-ID-Eindeutigkeit, relative Links, Quellkonsolidierung und die bewusste
Cluster-4-Grenze. `tests/check_links.py` bleibt eine netzabhängige, advisory Prüfung des in
Cluster 4 erhaltenen Werkzeugbestands.

## Historische Evidenz

Die Dateien unter `docs/decisions/` und `docs/audits/` dokumentieren frühere Zustände und
Migrationen. Sie sind keine laufzeitwirksamen Regelquellen und werden vom Bundle nicht importiert.
