# Agent Governance

> **Version:** [`0.1.0`](VERSION) &mdash; [Changelog](CHANGELOG.md)

Dieses Repository liefert ein kompaktes, harness- und providerneutrales Governance-Regelwerk.
Sein Vertrag ist auf Regeln, Rollen, Templates, Source-of-Truth-Verträge, Tool-Routing und
Verifikation begrenzt. Die kanonischen Inhalte liegen ausschließlich unter `bundle/`:

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

`bundle/GOVERNANCE.md` ist der einzige kanonische Einstieg. Von dort führt die Einstiegskette
ausschließlich zum statischen, fail-closed Manifest-Index und triggergerecht weiter zu den dort
deklarierten Modulen und Rollen. Jede Regel und jedes strikte Template besitzt genau eine
normative Quelle im Bundle; README, Betriebsgrenzendokumentation und historische Evidenz
beschreiben diesen Vertrag nur. Der optionale lokale Regelpfad ist im Manifest deklariert und
bleibt unversioniert.

Harness-spezifische Bootstrap-Templates, Adapter, Rollenwrapper sowie die alten Core- und
Profilquellen gehören nicht mehr zum aktuellen Repositoryzustand. Repository-Dateien außerhalb
von `bundle/` werden vom Bundle nicht als Governance geladen.

## Betriebsgrenze

Installation, Provisionierung, Migration, Backup, Restore, Deployment, Runtimebetrieb und
Control-Plane-Funktionen gehören nicht zum Repositoryvertrag. [INSTALL.md](INSTALL.md) beschreibt
ausschließlich diese Grenze und enthält weder Setup-Anleitung noch Zukunftsplanung.

## Versionierung und lokale Prüfung

`VERSION` ist die SemVer-Quelle des Repositorys. `CHANGELOG.md` hält freigegebene und noch nicht
freigegebene Änderungen auseinander. Ein lokaler Entwicklungsstand ist kein Release.

Die mechanischen Prüfungen laufen ohne Fremdabhängigkeiten:

```text
python3 -m unittest discover -s tests -v
python3 tools/release_check.py tree
```

Die Tests prüfen insbesondere Bootstrap-Budget, Manifeststruktur, geschlossene Modul- und
Rollenauflösung, Regel- und Template-SSOTs, relative Links, Quellkonsolidierung, Tool-Routing,
Review-/Kontextverträge und die operative Scope-Grenze.

## Historische Evidenz

Die Dateien unter `docs/decisions/` und `docs/audits/` dokumentieren frühere Zustände und
Migrationen. Sie sind keine laufzeitwirksamen Regelquellen und werden vom Bundle nicht importiert.
