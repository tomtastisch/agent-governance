# Issue #39: Dokumentationsarchitektur für 1.0.1

> **Historische Evidenz - nicht normativ.** Diese Spezifikation dokumentiert den freigegebenen
> Zielvertrag des Issue-#39-Lieferstroms und ist keine aktuelle Governance- oder Versionsquelle.

## Ziel und Scope

Issue #39 liefert den nächsten Stable-Patch `1.0.1` als atomaren Dokumentations- und
Release-Stream. Die README wird zur knappen Einstiegsschicht, aktuelle Fachreferenzen erhalten
eindeutige Zuständigkeiten, `INSTALL.md` wird nach vollständiger Inhaltsmigration entfernt und die
drei vorhandenen Bilder werden semantisch eingeordnet. Prüf-, Packaging- und Releaseverträge
werden an diese Architektur angepasst; Runtime- und CLI-Semantik bleiben unverändert.

Nicht Teil des Patches sind Harness-Adapter oder -Erkennung, Hooks, MCP-Mutationen,
Approval-Automatik, neue Runtime-Abhängigkeiten, eine Docs-Site, eine Asset-Pipeline oder eine
Änderung der acht öffentlichen Installer-Commands.

## Source-of-Truth-Architektur

- `README.md` beantwortet ausschließlich: Was ist Agent Governance, warum ist es sinnvoll, wie
  startet man und wo liegen die Details. Sie enthält die H2-Abschnitte `Was ist Agent
  Governance?`, `Warum Agent Governance?`, `Schnellstart`, `Wie funktioniert es?`,
  `Dokumentation` und `Support und Lizenz`.
- `docs/installer-cli-reference.md` besitzt Commands, Optionen, Exit-Verhalten und den formalen
  CLI-Vertrag.
- `docs/harness-recipes.md` besitzt die belegten Codex-, Claude-Code-, OpenCode-V2- und
  OpenClaw-Beispiele. Es verwendet CLI-Syntax nur beispielhaft und verweist für deren Semantik auf
  die CLI-Referenz.
- `docs/installer-architecture.md` besitzt Komponenten, Datenfluss, Installation, Lifecycle,
  Transaktionen, Backups und Recovery.
- `docs/installer-threat-model.md` besitzt Trust Boundaries, Sicherheitsgarantien,
  Nicht-Garantien, die Same-UID-Grenze, Residual Risks und Schutzmaßnahmen.
- `docs/installer-json-schemas.md` besitzt JSON-Strukturen und Feldsemantik.
- `CHANGELOG.md` besitzt Versionen und Migrationshistorie.
- `bundle/` bleibt unverändert die einzige normative Governancequelle.
- Audits, Decisions und ältere Specs bleiben historische, nicht normative Evidenz. Die fünf
  aktuellen Installer-/Harness-Referenzen sind aktuelle, nicht normative Dokumentation und tragen
  keine irreführende historische Kennzeichnung.

Kurze Überblicke, Beispiele und Navigationsmetadaten dürfen verweisen; vollständige Command-,
Security-, Architektur-, Schema- oder Releaseverträge dürfen nicht parallel gepflegt werden.

## Semantische Migrationsmatrix

| Bestehender Inhalt aus README/INSTALL | Kanonisches Ziel | Entscheidung |
|---|---|---|
| Ein-Satz-Pitch, Problem/Nutzen, minimaler Stable-Start, knapper Ablauf | `README.md` | stark kürzen |
| Commands, Pflicht-/optionale Flags, Explicit-Path- und Exit-Vertrag | `docs/installer-cli-reference.md` | vollständig dort halten |
| Codex-, Claude-Code-, OpenCode- und OpenClaw-Zielpfade und Beispiele | `docs/harness-recipes.md` | aus README auslagern und mit Primärquellen belegen |
| Bundle-/Binding-Struktur, Managed-Block-Lifecycle, Backups, Read-back, Receipts, Statusübergänge, Signal-/Rollback- und Sibling-Restore-Verhalten | `docs/installer-architecture.md` | einzigartige langlebige Inhalte aus `INSTALL.md` ergänzen |
| Installationsgrenze, No-Clobber, Native-Grenze, Same-UID-Co-Writer, kein privilegierter Broker, Schutz vertraulicher Local Rules | `docs/installer-threat-model.md` | einzigartige langlebige Inhalte konsolidieren |
| JSON-State-/Status-/Receipt-Felder und Feldsemantik | `docs/installer-json-schemas.md` | nur Schemafragen dort halten |
| Release-/Binding-Identität als technischer Lifecycle | `docs/installer-architecture.md` | beschreibenden Vertrag konsolidieren |
| veröffentlichte Versionen und frühere Migrationen | `CHANGELOG.md` | historische Fakten dort belassen |
| alte `@next`, RC-, Fresh-Session- und HARNESS_E2E-Zwischenstände | kein aktuelles Dokument | als überholt entfernen; veröffentlichte Historie im Changelog bleibt |
| normative Governance-Regeln und Routing | `bundle/` | nicht in beschreibende Docs kopieren |
| vollständige lokale Test-/Releaseanleitung | vorhandene Scripts und Workflows | aus README entfernen; ausführbarer Repositoryvertrag bleibt SSOT |

`INSTALL.md` wird erst gelöscht, nachdem diese Ziele den weiterhin gültigen einzigartigen Inhalt
abdecken. Danach darf kein aktueller Repository-, Test-, Tool- oder Packagevertrag die Datei
voraussetzen.

## Harness-Rezepte und Primärquellen

Alle Rezepte verlangen `--scope global`, einen expliziten absoluten `--installation-root`, einen
verifizierten absoluten `--target-root` und eine relative Markdown-`--entry-file`. Sie behaupten
weder automatische Erkennung noch Adapter. Vor Mutation ist der tatsächlich aktive globale Zielpfad
des jeweiligen Harness zu prüfen.

Die am 25.08.2026 erneut gelesenen Primärquellen belegen:

- Codex: `${CODEX_HOME:-$HOME/.codex}/AGENTS.md`, sofern kein vorrangiges
  `AGENTS.override.md` aktiv ist; Quelle `https://developers.openai.com/codex/guides/agents-md`.
- Claude Code: `$HOME/.claude/CLAUDE.md` für persönliche, projektübergreifende Instruktionen;
  Quelle `https://code.claude.com/docs/en/memory`.
- OpenCode V2: `$XDG_CONFIG_HOME/opencode/AGENTS.md`, normalerweise
  `$HOME/.config/opencode/AGENTS.md`; Quelle `https://opencode.ai/v2/docs/instructions`.
- OpenClaw: `AGENTS.md` im tatsächlich aktiven Agent-Workspace. Der Default ist
  `$HOME/.openclaw/workspace`, kann aber durch Profile, State-Directory, Environment und
  Agentkonfiguration abweichen; Quelle `https://docs.openclaw.ai/agent-workspace`.

## Assets

Das vollständige Inventar enthält genau drei PNG-Dateien. Die visuelle Prüfung am 25.08.2026 ergab:

- Die quadratische Schloss-/Agent-Grafik wird
  `assets/branding/agent-governance-icon.png`.
- `Governance-ujjm885-44_44.png` erklärt auf hoher Ebene Problem, Wirkung, Nutzen und bewusste
  Nicht-Ziele und wird `assets/diagrams/governance-overview.png`.
- `Governance-dsfs652-20_44.png` zeigt detailliert Session, Binding, normative SSOT-Dateien,
  Routing und Laufzeitfluss und wird `assets/diagrams/governance-architecture.png`.

Die README verwendet Icon und genau die Overview-Grafik über absolute Raw-GitHub-URLs, damit die
npm-README funktioniert. Die Architekturreferenz verwendet das detaillierte Diagramm. `docs/images/`
wird entfernt; Duplikate und alte Referenzen sind unzulässig. `assets/` wird nicht paketiert.

## GitHub-Linkvertrag

Die README verlinkt aktuelle Fachreferenzen mit absoluten URLs der Form
`https://github.com/tomtastisch/agent-governance/blob/main/<repo-path>`. Der kanonische Satz umfasst
CLI Reference, Harness Recipes, Installer Architecture, Threat Model, JSON Schemas, Changelog und
den normativen Governance-Bestand. Support-, npm- und Badge-Ziele sind davon getrennte externe
Links.

`tools/release_check.py tree` prüft offline deterministisch Host, Owner/Repo, `main`-Ref, erlaubten
Zielpfad, lokale Existenz und verbotene Altpfade. Ein eigener Remote-Modus verwendet ohne neue
Abhängigkeit `gh api` gegen die GitHub Contents API. Im PR ist nur die lokale Prüfung blockierend;
auf `main` und vor Release ist der Remote-Modus blockierend, damit neue Dateien nicht vor dem Merge
fälschlich gegen `main` geprüft werden.

## Packaging- und Releasegrenze

Das npm-Paket behält `README.md`, `LICENSE`, `CHANGELOG.md`, `VERSION`, Releaseinventar, Bundle,
Buildartefakte, Native-Prebuilds und `docs/installer-cli-reference.md`. Es enthält weder
`INSTALL.md` noch `assets/`, `docs/harness-recipes.md` oder weitere Fachdocs. Packtests prüfen
erlaubte, erforderliche und ausdrücklich verbotene Pfade semantisch statt über eine feste
Gesamtzahl.

`VERSION` ist die einzige autoritative Quelle der aktuellen SemVer. `package.json#version` sowie
die Top-Level- und Root-Package-Version in `package-lock.json` sind kontrollierte technische
Projektionen daraus. Ein eng begrenztes, deterministisches und idempotentes Sync-Werkzeug setzt
ausschließlich diese drei Projektionsfelder; es verändert weder Dependencies noch Namen, Scripts,
Engines, Publish-Konfiguration, Changelog, Tags oder Releases. `tools/release_check.py` bleibt ein
davon unabhängiger read-only Validator und beweist die Gleichheit aller Projektionen fail-closed.

`CHANGELOG.md` bleibt das explizite historische Release-Ledger und keine dynamische
Current-Version-Projektion. Für diesen Ausführungssnapshot werden `VERSION` und ihre npm-Projektionen
auf `1.0.1` gesetzt; genau ein Abschnitt `## [1.0.1] — 2026-08-25` dokumentiert
Dokumentationsarchitektur, Harness Recipes, Asset-Reorganisation, `INSTALL.md`-Entfernung sowie
bereinigte Package-, Test- und Linkverträge und enthält `**Breaking changes:** none`. Produktive
Tools, Workflows, aktuelle Referenzdocs und Repository-Vertragstests dürfen die aktuelle
Patchversion nicht als zweite langlebige Quelle hartkodieren; historische Specs, Pläne, Fixtures
und Changelog-Einträge behalten ihre auditrelevanten Literale.

Der bestehende signierte Tag-/GitHub-Release-/npm-OIDC-Weg bleibt unverändert. Seine Nachweiskette
bindet `VERSION` an die npm-Projektionen, genau einen passenden Changelog-Abschnitt, den signierten
annotierten `v${VERSION}`-Tag auf dem exakten Releasecommit, das GitHub Release und das npm-Paket.
Stable-Versionen verwenden ausschließlich `latest`, genehmigte Prereleases ausschließlich `next`.
Signatur-, Provenance-, Integrity-, Tarball- und Consumer-Prüfungen bleiben eigenständige Gates.

## Liefer- und Verifikationsgrenze

Vor PR werden fokussierte rote/grüne Tests, vollständige Node- und Python-Suiten, Typecheck, Lint,
Build, Releasemanifest, Release-Check, Pack- und Package-Consumer-Gates, Installer-/Neutral-Harness-
Fixtures, Asset-/Altpfad-Suchen und `git diff --check` ausgeführt. Ein unabhängiger read-only QA- und
Security-Review bewertet den Exact Head. Erst nach grünen Required Checks und Review wird gemerged;
danach folgen Remote-Link-Gate, signierter Stable-Tag `v1.0.1`, GitHub Release, Trusted npm Publish,
Registry-/Tarball-/URL-/CI-Read-back und zuletzt das Schließen von Issue #39.
