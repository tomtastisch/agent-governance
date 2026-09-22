# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Keine.

### Changed

- Keine.

### Fixed

- Cross-Version-Updates validieren installierte ältere Releases gegen deren bekannte geschlossene
  Governance-Contract-Variante, während Paket-, Staging-, Digest-, Receipt- und Tamper-Prüfungen
  unverändert strikt bleiben. Dadurch wird ein unverändertes v1.3.0-Release unter einer neueren CLI
  als `OUTDATED` statt fälschlich als `TAMPERED` klassifiziert.

### Removed

- Keine.

**Breaking changes:** none

## [1.4.0] — 2026-09-20

### Added

- Kanonische, statische Work-Item-Klassifikations-SSOT
  `bundle/agent-governance/ssot/work-items/classifications.toml` als vierte Domain `work_items` im
  SSOT-Index. Stabile IDs der Form `dimension.value` (z. B. `type.refactor`, `semver.patch`) mit
  expliziter Cardinality je Dimension (`type`=one, `area`=many, `horizon`/`semver`=at_most_one).
  Die bestehende `policy_tags`-Domain (`read`, `write`) bleibt semantisch getrennt.
- Getrennte GitHub-Labelprojektion
  `bundle/agent-governance/ssot/work-items/projections/github-labels.toml` mit managed
  Projektionen, optionalen Legacy-Aliasen (`github-hardening`, `terminal-ux`) und dem einzigen
  formalisierten Titelmarker `[FUTURE]`. Ein deterministischer read-only Projection-Plan
  (`NOOP`, `CREATE`, `UPDATE`, `CONFLICT`, `UNMANAGED`, `CANDIDATE`) klassifiziert das
  GitHub-Inventar ohne Mutation.
- Öffentliche Auflösung über den Paketexport `@tomtastisch/agent-governance/work-items`
  (Loader, Validierung, Projektionsplan, Titelmarker- und Driftauflösung).

### Changed

- Keine.

### Fixed

- Keine.

### Removed

- Keine.

**Breaking changes:** none

## [1.3.0] — 2026-09-20

### Added

- Kanonische, geschlossene Template-Registry `bundle/agent-governance/templates/manifest.toml`, die
  jeden wiederverwendbaren generischen Formvertrag genau einmal mit stabiler Template-ID
  registriert. Zwei zuvor fehlende generische Verträge wurden ergänzt: `delivery/release-checkpoint`
  (Release-Nachweisform) und `external-effects/approval-checkpoint` (Freigabe-/Autorisierungsform).

### Changed

- Das Sammelmodul `modules/templates.md` ist auf eine rein erklärende Übersicht reduziert; die
  atomaren Formverträge liegen unter `templates/`. Die domain-spezifische Resume-Checkpoint-Form
  verbleibt beim Resume-Owner `modules/resume.md`. Das Root-Manifest (schema_version 4) referenziert
  zusätzlich die Template-Registry.
- `DEL-008` (Provider-Routing) präzisiert: ein Ausfall des bevorzugten Review-Providers
  (`fail-closed(provider)`) schließt nur diesen Providerpfad und erzwingt bei vorhandenem
  autorisiertem fachlich gleichwertigem Fallback dessen Ausführung; der gesamte Prüfworkflow
  blockiert erst, wenn kein gültiger Fallback verfügbar ist oder auch dieser keinen Nachweis liefert.

### Fixed

- Keine.

### Removed

- Keine.

**Breaking changes:** none

## [1.2.1] — 2026-09-20

### Added

- Deklarativer Governance-SSOT-Root `bundle/agent-governance/ssot/` mit genau einem geschlossenen
  Domain-Index (`ssot/manifest.toml`), der ausschließlich die real vorhandenen Domains `routing`,
  `commands` und `discovery` registriert.

### Changed

- Governance-Kataloge semantisch unverändert nach `ssot/routing/`, `ssot/commands/` und
  `ssot/discovery/` migriert. Das Root-Manifest (Schema 3) referenziert den SSOT-Index statt einer
  flachen `[catalogs]`-Liste; Resolver, Loader und Validatoren sind modular und domainbezogen.

### Fixed

- Keine.

### Removed

- Flacher `catalogs/`-Authority-Pfad entfernt; es verbleibt keine parallele Legacy-Authority.

**Breaking changes:** none

## [1.2.0] — 2026-09-20

### Added

- Zustandsgebundener Resume Fast-Path mit Trigger `resume_continuation`, Modul
  `modules/resume.md` (Regeln `RES-001`–`RES-015`) und strikter `Resume-Checkpoint`-Vorlage:
  Evidence-Reuse und -Invalidation an getrennten Identitäten/Fingerprints, strikte
  `INCOMPLETE`-/`PASS`-Trennung, Duplicate-Execution Guard, Dirty-Worktree-Identität,
  Fresh-Chat-Resume, TOON-Projektion (Token-Oriented Object Notation) und Progressive Context
  Loading ohne zweite State-/Checkpoint-/Evidence-Source of Truth.
- Reale, deterministische TOON-Verarbeitung als öffentlicher Modulpfad
  `@tomtastisch/agent-governance/resume-toon`: striktes Encode/Decode mit Domänenvalidierung
  (erlaubte Felder, Struktur, Checkpoint-Bindung, Freshness/Staleness, fail-closed, keine
  Secrets) über die offizielle Referenzimplementierung `@toon-format/toon` `4.1.1` (MIT).
- Live Release-/Registry-Verifikation (`python3 tools/release_check.py registry`) gegen die
  tatsächlich veröffentlichte npm-Version (`dist-tags.latest`), die veröffentlichte Versionsliste
  und das aktuelle GitHub Latest Release — die Zielversion wird nie aus dem lokalen `package.json`
  allein abgeleitet.

### Changed

- Keine.

### Fixed

- Keine.

### Removed

- Keine.

**Breaking changes:** none

## [1.1.0] — 2026-08-27

### Added

- Der interaktive `init`-Onboarding-Einstieg ist als einzige normale öffentliche Installation über
  `npm i @tomtastisch/agent-governance` und `npx agent-governance init` dokumentiert.
- Der npm-Tarball prüft nun explizit Command- und Discovery-Kataloge, Terminal-Branding und den
  tarball-only Init-Help-Pfad.

### Changed

- Direkte Runtime-Imports sind mit `@clack/prompts` 1.7.0 und `smol-toml` 1.8.0 exakt im Paket und
  Lockfile deklariert; Advanced-/Automation-/CI-Referenzen behalten die Low-Level-Commands.
- npm-Keywords beschreiben den vorhandenen AI-Governance-, Policy-as-Code-, Security-, CLI- und
  harness-neutralen Installerumfang ohne spätere Management-Funktionen vorwegzunehmen.

### Fixed

- `init` startet keinen Package Manager, keine Self-Install-, Repair- oder bedingte Nachladefunktion.
- `OUTDATED`-Ziele verwenden den Updatepfad; der gemeinsame Freigabeschritt zeigt vorher je Ziel
  Zustand, Mutation und Ressourcenoperationen, und Non-TTY-Aufrufe brechen vor Home-Kanonisierung ab.
- Strukturierte Discovery öffnet Live-Dateien nichtblockierend, verwirft FIFO-Austauschrennen und
  begrenzt Reads auch bei gleichzeitig wachsenden Dateien.
- plist-Evidence akzeptiert nur vollständig tokenisierte, begrenzte und wohlgeformte Hierarchien
  ohne kommentierte Signale, ungültige Entities, Attribute, Containertext oder übertiefe Strukturen.
  Die Standard-Apple-DOCTYPE wird ausschließlich als inerte Deklaration erkannt, ohne DTD-Zugriff.
- SQLite-Schema-Evidence erzwingt das Dateigrößenbudget und bleibt über einen nichtblockierend
  geöffneten Descriptor an die geprüfte reguläre Datei sowie `mode=ro&immutable=1` gebunden.
  Exakt ausgeschöpfte Schema-Grenzen bleiben vollständig; ein begrenzter zusätzlicher Datensatz
  unterscheidet sie von tatsächlichem Überlauf.
- Unabhängige Evidence-Quellen werden anhand der geöffneten Dateiidentität gezählt; Hardlinks
  desselben Objekts können keine hohe Konfidenz erzeugen.
- Das Discovery-Zeitbudget reserviert Analysezeit und verteilt die verbleibende Zeit auf Zonen
  und Kandidaten, damit eine frühe breite HOME-Struktur spätere XDG-Ziele nicht verdrängt.
- Der geführte Init-Prompt beendet seinen Fortschrittsindikator auch nach Discovery- oder
  Planungsfehlern, sodass der CLI-Prozess deterministisch zurückkehrt.
- Passive Discovery verteilt begrenzte Traversalbudgets auf Geschwister, toleriert erwartbare
  Dateisystem-Races, erhält App-Bundle-Grenzen und bevorzugt bei Score-Gleichstand vollständige
  Kandidaten.
- Strukturierte Evidence erzwingt die plist-Dict-Hierarchie und liest gleichzeitig wachsende Dateien
  nur bis zur konfigurierten Grenze plus einem Overflow-Byte; Manifestpfade lehnen Symlinks in jeder
  Zwischenkomponente ab.
- Der Linux-PTY-Treiber setzt für Expect ausdrücklich `C.UTF-8`, damit Suche, Multiselect und manueller
  Fallback auch mit `TERM=linux`, `NO_COLOR` und 60×24-Zellen zuverlässig bedienbar bleiben.
- Passive Discovery reserviert im Zonenbudget anteilig Traversalbudget, damit ein breiter Zonenroot
  entdeckte Kandidaten nicht auf ein Nullbudget setzt, und dedupliziert kandidatenklassenbewusst,
  damit sich DIRECTORY- und APP_BUNDLE-Sichten überlappender Zonen nicht gegenseitig verdecken.
- Die plist-Evidence zählt jeden Strukturknoten gegen das Entry-Limit statt nur Keys, und der
  Katalogwert `high_requires_runtime = false` wird korrekt beachtet, statt hohe Konfidenz
  unabhängig von der Konfiguration auszuschließen.

### Removed

- Der frühere normale Drei-Command-Quickstart mit expliziten Pfaden.

**Breaking changes:** none

## [1.0.1] — 2026-08-25

### Added

- Eine kompakte README mit klarer Dokumentationsarchitektur und eindeutigen Zuständigkeiten für
  aktuelle Referenzen.
- Harness Recipes für die verifizierten Harness-spezifischen Einstiegspfade sowie semantische Assets
  für Überblick, Architektur und Branding.

### Changed

- Package-, Test- und Linkbereinigung bindet die aktuelle Dokumentation, das schlanke npm-Artefakt
  und die Releaseverifikation konsistent zusammen.
- Öffentliche CLI-Commands und Runtime-Verhalten bleiben unverändert.

### Fixed

- Aktuelle Installationsbeispiele verwenden den stabilen `@latest`-Kanal statt einer hartkodierten
  Patchversion.

### Removed

- `INSTALL.md` nach vollständiger Migration seiner einzigartigen aktuellen Inhalte in die zuständigen
  Referenzen.

**Breaking changes:** none

## [1.0.0] — 2026-08-25

### Added

- Das globale Paket mit transaktionalem Explicit-Path-Installer und adapterlosem Kern sowie den Commands
  `inspect`, `plan`, `install`, `verify`, `status`, `update`, `uninstall` und `rollback`.
- Eine repo-eigene Node-API-C-Sicherheitsprimitive mit nativen Darwin-/Linux-Prebuilds für arm64
  und x64 sowie atomarem No-Clobber-Rename.
- Eine nicht normative Installer-CLI-Referenz für sämtliche öffentlichen Commands, Pfade und Optionen.

### Changed

- Die Architektur `GLOBAL_EXPLICIT_PATH_MANAGED_BLOCK` verlangt explizite globale Zielparameter
  und enthält keine Harnessadapter, Zielerkennung, Hooks, MCP-Mutationen oder Auto-Approvals.
- Mutierende Operationen prüfen Native-Capability, Releaseinventar, Receipts, Backups und
  Postimages fail-closed; ein unsicherer Pathname-Fallback existiert nicht.
- Der Sicherheitsvertrag grenzt ausschließlich den nicht atomar entscheidbaren bösartigen
  Same-UID-Final-Component-Swap aus und führt keinen privilegierten Broker ein.

### Fixed

- Recovery und Rollback binden Parent-, Release-, Binding-, Backup- und Local-Rules-Identitäten
  persistent und bewahren konkurrierend geänderte oder fremde Bytes.
- Native Replace-, Remove-, Create-, Detach- und Aktivierungsoperationen verwenden validierte
  Directory-Handles, kontrollierte Basenames und atomare Kollisionsgrenzen.
- Release-, Packaging- und Dokumentationsprüfungen binden alle vier Native-Prebuilds sowie die
  öffentliche CLI-Referenz deterministisch an das npm-Artefakt.
- macOS-Testfixtures kanonisieren temporäre Roots, ohne die produktive Symlinkgrenze zu lockern.

### Removed

- Den unveröffentlichten Codex-spezifischen Installerentwurf mit Harness-ID, festen Zielpfaden
  und Hookmutation.

**Breaking changes:** present

- **BREAKING:** Gegenüber dem manuellen v0.5.0-Bootstrap verlangt der Installer explizite globale
  Zielparameter und verwaltet ausschließlich seinen markierten Markdown-Block.

## [1.0.0-rc.3] — 2026-08-25

### Added

- Eine nicht normative Installer-CLI-Referenz für alle acht öffentlichen Commands und den
  expliziten globalen Pfad- und Optionsvertrag.

### Changed

- Das öffentliche npm-Paket enthält gezielt `docs/installer-cli-reference.md`; README und
  Installationsgrenze verlinken diese Bedienreferenz.
- Das Paket mit transaktionalem Explicit-Path-Installer und adapterlosem Kern behält die Architektur
  `GLOBAL_EXPLICIT_PATH_MANAGED_BLOCK` als globalen Auslieferungsvertrag bei: keine Harnessadapter,
  keine implizite Zielerkennung, unveränderte Rollback-Garantien und unveränderte
  macOS-Testfixtures.

### Fixed

- Dokumentations- und Pack-Drift-Tests binden die CLI-Referenz an die öffentliche Distribution,
  während alle anderen internen Dokumentationspfade aus dem Paket ausgeschlossen bleiben.

### Removed

- Keine.

**Breaking changes:** present

- **BREAKING:** Gegenüber dem manuellen v0.5.0-Bootstrap verlangt der Installer weiterhin
  explizite globale Zielparameter und verwaltet ausschließlich seinen markierten Markdown-Block.

## [1.0.0-rc.2] — 2026-08-24

### Added

- Das öffentliche Paket `@tomtastisch/agent-governance` mit globalem, adapterlosem,
  transaktionalem Explicit-Path-Installer und den Commands `inspect`, `plan`, `install`, `verify`,
  `status`, `update`, `uninstall` und `rollback`.
- Einen deterministischen Managed Block, geschlossene JSON-Schemas, verifizierte Backups,
  Releaseinventar, vollständige Bundle- und Manifestprüfung, Signal-Rollback und explizite lokale Regeln.
- Targetgebundene Binding-/Receipt-Metadaten für mehrere globale Einstiegsdateien unter einem
  gemeinsamen Installationsroot sowie einen OIDC-basierten npm-Publishworkflow.
- Eine repo-eigene Node-API-C-Primitive mit nativen Darwin-/Linux-Prebuilds für arm64 und x64.

### Changed

- Die Installationsarchitektur ist `GLOBAL_EXPLICIT_PATH_MANAGED_BLOCK`; Zielroot,
  Markdown-Einstieg und Installationsroot sind vollständig explizit.
- Das npm-Artefakt enthält keine Harnessadapter, Hooks, MCP-Mutationen, Auto-Approvals,
  Fremdadapter oder Runtime-Abhängigkeiten.
- Mutierende Installeroperationen prüfen die native Capability vor produktiver Mutation; ein
  fehlendes oder nicht unterstütztes Binary besitzt keinen unsicheren Pathname-Fallback.
- Der Sicherheitsvertrag grenzt ausschließlich den nicht atomar entscheidbaren bösartigen
  Same-UID-Final-Component-Swap aus; beobachtbare Container- und Persistenzabweichungen bleiben
  fail-closed, und es wird kein privilegierter Broker eingeführt.

### Fixed

- macOS-Testfixtures kanonisieren den temporären Root, ohne die produktive Symlinkgrenze
  abzuschwächen.
- Rollback bindet die Entry-Wiederherstellung per exklusiv reserviertem, recoveryfähigem
  Same-Filesystem-Detach an das validierte Postimage und behält dessen receipt-spezifische
  Evidenz bei; zwischenzeitlich geänderte Nutzerbytes werden nicht überschrieben oder gelöscht.
- Der Entry-Detach verwendet offene Directory-Handles und atomaren No-Replace-Rename
  (`renameat2/RENAME_NOREPLACE` beziehungsweise `renameatx_np/RENAME_EXCL`), sodass ein Austausch
  des sichtbaren Reservation-Pfads weder fremde Ersatzbytes beschreibt noch löscht.
- Der Detach liegt als receipt-eindeutiger Sibling im vorab identifizierten Entry-Parent; auch die
  Wiederanlage bindet sich nativ an diesen Parent, statt eine nach `mkdir` erneut aufgelöste
  Verzeichnisidentität zu autorisieren.
- Receipts persistieren die erwarteten Identitäten von Entry-Parent, Installation, Binding-Root,
  Releases-Root, Release und Local-Rules-Parent, damit später beobachtbare Containerwechsel vor
  Recovery- und Cleanup-Mutationen fail-closed blockieren.
- Ein partiell fehlgeschlagenes natives Exclusive-Create entfernt seine weiterhin identisch
  beobachtete eigene Datei dirfd-relativ und bewahrt den ursprünglichen I/O-Fehler.
- Current-, Local-Rules-, Receipt-, Lock- und Release-Aktivierungssinks mutieren ausschließlich
  relativ zu geöffneten identitätsgeprüften Parent-dirfds; Backup-Root-Identität ist receiptgebunden.
- Native Replace-/Remove-Operationen vergleichen zusätzlich die erwartete finale Objektidentität;
  Replace prüft auch den sichtbaren temporären Quellnamen unmittelbar vor dem Rename.
- Eine reale Rename-Capability-Probe läuft auf den betroffenen Dateisystemen vor der ersten
  produktiven Mutation. Neue verifizierte Releases bleiben bei Rollback als harmlose
  unreferenzierte Recoveryartefakte erhalten, statt rekursiv pathname-basiert gelöscht zu werden.
- Update-Pläne weisen die tatsächlich in ein neues Release übernommenen lokalen Regeln aus.
- Plan- und Dry-Run-Ausgaben benennen für explizite lokale Regeln die tatsächlich manifestgebundene
  Markdown-Datei statt nur deren übergeordnetes Verzeichnis.
- Die Tarball-Allowlist normalisiert sowohl das Arrayformat von npm 11 als auch das
  paketnamengebundene Objektformat von npm 12, bindet beide an den autorisierten Paketnamen und
  lockert keine Pfad-, Secret- oder Native-Prüfung.

### Removed

- Der unveröffentlichte Codex-only-Installerentwurf mit Harness-ID, festen Codexpfaden und
  Hookmutation wurde aus Runtime und öffentlichem Paket entfernt.

**Breaking changes:** present

- **BREAKING:** Gegenüber dem manuellen v0.5.0-Bootstrap verlangt der Installer explizite globale
  Zielparameter und verwaltet ausschließlich seinen markierten Markdown-Block.

## [1.0.0-rc.1] — 2026-08-24

### Added

- Das öffentliche Paket `@tomtastisch/agent-governance` mit globalem, adapterlosem,
  transaktionalem Explicit-Path-Installer und den Commands `inspect`, `plan`, `install`, `verify`,
  `status`, `update`, `uninstall` und `rollback`.
- Einen deterministischen Managed Block, geschlossene JSON-Schemas, verifizierte Backups,
  Releaseinventar, vollständige Bundle- und Manifestprüfung, Signal-Rollback und explizite lokale Regeln.
- Targetgebundene Binding-/Receipt-Metadaten für mehrere globale Einstiegsdateien unter einem
  gemeinsamen Installationsroot sowie einen OIDC-basierten npm-Publishworkflow.

### Changed

- Die Installationsarchitektur ist `GLOBAL_EXPLICIT_PATH_MANAGED_BLOCK`; Zielroot,
  Markdown-Einstieg und Installationsroot sind vollständig explizit.
- Das npm-Artefakt enthält keine Harnessadapter, Hooks, MCP-Mutationen, Auto-Approvals,
  Fremdadapter oder Runtime-Abhängigkeiten.

### Fixed

- macOS-Testfixtures kanonisieren den temporären Root, ohne die produktive Symlinkgrenze
  abzuschwächen.

### Removed

- Der unveröffentlichte Codex-only-Installerentwurf mit Harness-ID, festen Codexpfaden und
  Hookmutation wurde aus Runtime und öffentlichem Paket entfernt.

**Breaking changes:** present

- **BREAKING:** Gegenüber dem manuellen v0.5.0-Bootstrap verlangt der Installer explizite globale
  Zielparameter und verwaltet ausschließlich seinen markierten Markdown-Block.

## [0.5.0] — 2026-08-22

### Added

- Keine.

### Changed

- Die kanonische externe Governance-Tool-ID wurde von
  `mcp__agent_governance__execute` in `agent_governance__execute` geändert, weil Codex `mcp`
  und `mcp__*` für native MCP-Namensräume reserviert und die frühere Dynamic-Tool-ID vor dem
  Governance-Handler verwirft.
- Alle Provider verwenden weiterhin denselben Governance-Handler und dieselbe Governance-SSOT;
  die Entscheidungs-, Policy-, Scope-, Trigger- und Rollensemantik bleibt unverändert.
- Der Clean-Linux-Codex-Vertrag registriert die kanonische Oberfläche als einzelnes
  App-Server-Dynamic-Tool statt als MCP-Tool, damit Hook-Matcher und externer Identifier
  byte-identisch bleiben.
- **Migration:** Consumer, Policies, Adapter und Tests, die die frühere Tool-ID exakt
  referenzieren, müssen auf
  `agent_governance__execute` migrieren. Version `0.5.0` registriert keinen
  Kompatibilitätsalias für den alten Namen.

### Fixed

- Codex kann die kanonische Governance-Tooloberfläche als Dynamic Tool akzeptieren, ohne dass ein
  reservierter nativer MCP-Namensraum den Dispatch vor dem Governance-Handler blockiert.

### Removed

- **BREAKING:** Die externe Tool-ID `mcp__agent_governance__execute` ist keine aktive
  Runtime- oder Integrationsoberfläche mehr.

**Breaking changes:** present

## [0.4.1] — 2026-08-21

### Added

- Ein repository-natives Copilot-QA-Binding `.github/copilot-instructions.md` als dünner
  Consumer-Wrapper, der GitHub Copilot Code Review an die kanonische QA-Governance bindet.
- `DEL-010` (Optionales Parallel-QA) als ausdrücklich opt-in Vertrag.

### Changed

- `DEL-008` verlangt ein gültiges repository-natives Copilot-QA-Binding auf demselben Exact Head
  als Voraussetzung dafür, dass GitHub Copilot als bevorzugter QA-Provider gilt.
- Die nicht releasekritischen GitHub-Actions-Schritte verwenden die aktuelle Node-24-kompatible
  Action-Generation; der CI-Node-Runtimepfad wurde auf Node 24 LTS angehoben, während
  releasekritische Checkouts unverändert auf dem auditierten SHA-Pin bleiben.

### Fixed

- Der Copilot-QA-Binding-Validator lehnt Bundle-Referenzen mit Markdown-Fragment (`#…`) oder
  Query (`?…`) fail-closed ab und blockiert Backslash-/Windows-, Traversal-, absolute POSIX-,
  gerootete Laufwerkspfade (`C:/…`, `C:\…`), UNC- sowie sämtliche
  Groß-/Kleinschreibungsvarianten des `file:`-Schemas als nicht-repositorylokale Referenzen.

### Removed

- Keine.

**Breaking changes:** none

## [0.4.0] — 2026-08-18

### Added

- Vier geschlossene, maschinenvalidierbare Kataloge für Trigger, Policy-Tags, Scopes und Tools
  unter `catalogs/triggers.toml`, `catalogs/policy-tags.toml`, `catalogs/scopes.toml` und
  `catalogs/tools.toml`.
- Der zentrale Toolkatalog umfasst die weiterhin gültigen Standardtoolklassen sowie Linear,
  Supabase, Superpowers, Supermetrics, GitHub, Data Analytics, Canonical Memory Verifier und
  Microsoft APM.
- Zwei lokale, ausdrücklich nicht normative Erklärungsgrafiken zu Wirkung und Binding-Ablauf in
  der README.

### Changed

- Das Manifest verwendet Manifest-Schema 2, bleibt Root-Index und referenziert die vier Katalogpfade
  ausschließlich relativ zum kanonischen Manifestverzeichnis.
- Toolprofile und ihre geschlossenen Trigger-, Policy-Tag- und Scope-Referenzen liegen nur noch in
  `catalogs/tools.toml`; `modules/tool-routing.md` enthält ausschließlich allgemeine
  Routingsemantik und Autorisierungsgrenzen.
- Validatoren, Bootstrapmaterialisierung und produktneutraler Harness prüfen Katalogschema,
  Referenzintegrität und Pfadsicherheit deterministisch fail-closed.

### Fixed

- Keine.

### Removed

- `routing.known_triggers` und die vollständigen Markdown-Toolprofile als parallele
  maschinenlesbare beziehungsweise normative Katalogquellen.

- **BREAKING:** Consumer des Manifest-Schemas 1 müssen `routing.known_triggers` durch den vom
  Manifest referenzierten Triggerkatalog ersetzen und die vier Kataloge vor dem Modulrouting
  validieren.

**Breaking changes:** present

## [0.3.2] — 2026-08-15

### Added

- Ein versionierter, auf einen einzelnen genehmigten ED25519-Release-Signer und den
  Git-Namespace begrenzter SSH-Allowed-Signers-Trust-Anchor für reproduzierbare
  Release-Verifikation.

### Changed

- Die Release-Verifikation verwendet ihren repositorygebundenen SSH-Trust-Anchor direkt und
  hängt nicht mehr von benutzerspezifischer oder GitHub-Runner-Gitkonfiguration ab.
- Die Tag- und Published-Release-Jobs laden Verifier und Signer-Policy vom geschützten
  `main`-Ref und prüfen das Kandidaten-Tag separat, sodass das Tag seinen eigenen Trust Anchor
  nicht ersetzen kann.
- Der GitHub-Release-Check validiert nun zusätzlich die kryptografische Signatur des
  zugehörigen Release-Tags.
- `v0.3.0` und `v0.3.1` bleiben unveränderte signierte Git-Tags ohne GitHub Release;
  `v0.3.2` ist der nächste produktive Releasekandidat.

### Fixed

- Clean GitHub-hosted Runner können signierte SSH-Release-Tags deterministisch mit
  `git tag -v` verifizieren, weil `release_check` den fingerprint-gepinnten
  `allowedSignersFile` explizit pro Git-Aufruf bereitstellt.

### Removed

- Keine.

**Breaking changes:** none

## [0.3.1] — 2026-08-15

### Added

- Keine.

### Changed

- Die releasekritischen GitHub-Actions-Checkout-Schritte für Tag- und
  Published-Release-Validierung verwenden den exakt gepinnten, reparierten
  `actions/checkout`-Stand `de0fac2e4500dabe0009e67214ff5f5447ce83dd` (`v6.0.2`).
- Der öffentliche signierte Tag `v0.3.0` bleibt unverändert bestehen; wegen des
  fehlgeschlagenen Tag-CI-Laufs wurde dafür kein GitHub Release veröffentlicht.
- `v0.3.1` enthält den vollständigen `0.3.0`-Produktstand unverändert plus ausschließlich
  diesen Release-Pipeline-Hotfix. Sein Tag-CI scheiterte weiterhin, weil kein SSH-Trust-Anchor
  bereitgestellt war; daher wurde kein GitHub Release `v0.3.1` veröffentlicht.

### Fixed

- Signierte annotierte Release-Tags bleiben in Tag- und Published-Release-CI als echte
  Tagobjekte erhalten. Die vollständige Signaturprüfung auf einem cleanen Runner funktionierte
  in `v0.3.1` jedoch noch nicht, weil dort der SSH-Trust-Anchor fehlte.

### Removed

- Keine.

**Breaking changes:** none

## [0.3.0] — 2026-08-12

### Added

- Einmaliger harness- und providerneutraler `Installation.bootstrap.prompt.md` mit sicherer
  Harness-Erkennung, Backup, Staging, Rollback und frischer Runtime-Verifikation.
- Automatisierte Fresh-, Current- und Legacy-Pfade einschließlich idempotenter Current-Prüfung,
  gezielter Binding-Reparatur, verpflichtender Legacyfixture und verlustfreier synthetischer
  Regelmigration.
- Providerneutraler Enforcement Contract mit geschlossener Action Envelope, den Entscheidungen
  `allow`, `deny`, `require_approval`, `error` und `unknown` sowie verbindlicher
  fail-closed-Semantik vor dem Effekt.
- Microsoft Agent Governance Toolkit als gepinnter Enforcement-Provider: offizielles stabiles
  Release `v4.1.0`, exakter Commit, byte-identisches Releasearchiv, neu berechneter SHA-256,
  vollständiges Dateimanifest, MIT-Lizenz, NOTICE und Trademark-Hinweis.
- Kleine Bridge zum realen Microsoft-PolicyEngine und Codex-PreToolUse-Hook für einen explizit
  operationsgebundenen Toolpfad mit vertrauenswürdig abgeleiteter Action Envelope.
- Produktneutraler synthetischer Harness für Routing, Rollen, `local_rules`, Offlinebetrieb,
  lokalen Audit und alle Providerentscheidungen ohne produktspezifische Pfadvorgabe.
- Clean-Linux-E2E mit Codex CLI 0.147.0, echter frischer Runtime, real blockierten
  Providerentscheidungen, materialisiertem Offline-Provider, zustandsspezifischen Fixtures,
  immutable Buildinputs, Exact-Commit-Prüfung, Hostile-Matrix sowie Secret- und Auth-Isolation.
- Sicherheits- und Regressionstests für Archivextraktion, Instruction Boundary,
  Pfad-/Symlink-Traversal, Rootkonflikte, Backup/Rollback und private Evidenzgrenzen.

### Changed

- README führt Mitarbeiter über einen kurzen Release- und Bootstrapfluss und trennt Governance,
  Enforcement und Microsoft-Provider ausdrücklich.
- INSTALL bleibt Boundary- und Verantwortungsdokument; der ausführbare Installationsvertrag liegt
  ausschließlich in `Installation.bootstrap.prompt.md`.
- Die Bootstrap-Root-Auflösung verwendet begrenzte, manifestvalidierte Harness-Kandidaten wie
  `CODEX_HOME` und `AGENT_GOVERNANCE_ROOT`, akzeptiert gesetzte Umgebungskandidaten nur als
  nichtleere absolute Pfade und behandelt das aktuelle Arbeitsverzeichnis nicht implizit als
  Bundle-Root.

### Fixed

- Caller-kontrollierte Effect-, Autorisierungs-, Risiko-, Approval- und Evidence-Attestierungen
  werden nicht mehr als technische Enforcement-Eingabe vertraut; Hook und synthetisches Effekttool
  binden dieselbe kanonische Operation unabhängig an die tatsächliche Wirkung.
- Bereits materialisierte Provider-Runtimes, Policy und Operationsvertrag werden vor Verwendung
  vollständig und releasegebunden auf Byteintegrität geprüft.
- Ein interner Rollbackfehler bewahrt das verifizierte Recovery-Backup und einen recoverbaren
  Altzustand; eine umgeleitete interne Backupwurzel wird vor privaten Kopien blockiert.
- Clean-Linux-Statuszeilen unterscheiden realen Codex-Fresh-Lauf, Current-/Legacy-Fixtures und
  materialisierten Offline-Provider und behaupten keine nicht ausgeführten Zustände mehr.

- Folgezugriffe behalten den absoluten Governance-Root und das daraus abgeleitete
  Manifestverzeichnis bei; eine zusätzliche projektlokale `AGENTS.md` wird nicht mit dem
  kanonischen Einstiegspunkt verwechselt.
- Der Statusvertrag verlangt ein ausdrücklich benanntes Feld für verbleibende Risiken und
  schreibt bei leerem Restbestand `Verbleibende Risiken: keine` vor.
- Der Legacy-Regressionspfad stellt sicher, dass bestehende aktive Verdrahtung und synthetische
  persönliche Regeln nicht nur durch einen sauberen Fresh-Test verdeckt werden.

### Removed

- Keine.

**Breaking changes:** none

## [0.2.0] — 2026-08-09

### Added

- Triggerbasiertes Tool-Routing mit Microsoft APM als Standard für deklarative Agent-Skill- und
  Agent-Paket-Evidenz.
- Exact-Head-Verträge für unabhängige QA- und risikobasierte Security-Prüfungen.
- Zentrale strikte Templates für driftanfällige Delivery-, Review- und Kontextübergaben.
- Sitzungsledger- und Checkpoint-Regeln für nachvollziehbare lange Aufgaben.
- Regressionstests für Scope, SSOT, Manifest, Tool-Routing, Review, Templates, Kontext und
  hostunabhängige Git-Fixtures.

### Changed

- Governance ist auf Regeln, Rollen, Templates, Source-of-Truth-Verträge, Tool-Routing und
  Verifikation begrenzt.
- Die kanonische Einstiegskette führt ausschließlich vom Bootstrap über das statische Manifest
  zu triggergerecht geladenen Modulen und Rollen.
- Reviewerrollen und Reviewprovider sind getrennt; GitHub Copilot ist ein bevorzugter
  QA-Provider mit unabhängigem Fallback.
- APM- und andere Toolregeln beschreiben fachliche Trigger und Evidenzgrenzen, jedoch weder
  Installations- noch Verfügbarkeitszustände.

### Fixed

- Git-Test-Fixtures verwenden deterministisch `main`, repository-lokale Identität und geprüfte
  Rückgabecodes ohne globale Git-Konfiguration.
- Security-Trigger sind vor dem Modulrouting sichtbar, versionierte Lieferungen benötigen immer
  unabhängige Exact-Head-QA, und Secret-Nachweise schließen inhaltsabgeleitete Metadaten aus.

### Removed

- Alte Harness-Adapter, Bootstrap-Templates, Rollenwrapper, Core-/Rollenquellen, Branch-Tags und
  die Profilvorlage als konkurrierende Governance-Autorität.
- **BREAKING:** Operative Projekt-, Werkzeug-, Provider- und Runtimeverträge sowie Verweise auf
  entfernte Legacy-Quellen gehören nicht mehr zum öffentlichen Governance-Vertrag.

**Breaking changes:** present

## [0.1.0] — 2026-07-27

### Added

- Harness-agnostisches Kernregelwerk (`core/core.md`) mit 20 Abschnitten:
  Rolle, Kommunikation, Goldene Regeln, Evidenz & Hypothesen, Arbeitsweise,
  Rollen & Routing, Blocker-Protokoll, Abschlussformat, Architektur/SSOT,
  Code-Standards, Tests, Dokumentation & Versionierung, CI-Pipeline,
  Definition of Done, Branch-/Commit-/PR-Disziplin, Review- & Merge-Gate,
  Sicherheit & Instruktionsgrenze, Issue-Dokumentationspflicht, Werkzeuge &
  Manifest, Selbstprüfung
- Hexagonale Architektur: Kern — Ports (`[BINDING:*]`/`[PROFILE:*]`) — Adapter
  — genau eine Verdrahtungsstelle je Harness
- Claude-Code-Adapter mit Subagenten-Routing (AK/ST/QA/SEC)
- Codex-Adapter mit separatem Rollenkontext
- Rollenerweiterungen `core/roles/{ak,st,qa,sec}.md`
- Branch-/PR-Tag-Schema (`core/branch-tags.toml`): geschlossene Tag-Liste nach
  Conventional-Commit-Typen, SSOT für Branch, PR-Titel und Commit-Präfix
- Werkzeug-Katalog (`tools/tools.md`) mit Freigabe-Ebenen und
  deterministischer CLI-Installation (`tools/Brewfile`)
- CI-Pipeline (`.github/workflows/ci.yml`): blockierende Konsistenz-/
  Drift-Tests, advisory Link-Check
- Konsistenz-Testsuite (`tests/test_governance.py`): Port-Vertrag, Profil,
  Referenzen, Rollen, Pfadfreiheit, Katalog, Templates, Branch-Tags
- ADRs für strukturelle Entscheidungen (`docs/decisions/`)
- Kopierfertige Verdrahtungs-Templates (`templates/`)
- Gehärteter Installations-Prompt (`INSTALL.md`)
- Profilvorlage (`profile/profile.example.md`)
- Autoritative SemVer-Quelle (`VERSION`)
- Deterministische Release-Metadaten-Validierung (`tools/release_check.py`)
- Dieser CHANGELOG

### Changed

- Keine.

### Fixed

- Keine.

### Removed

- Keine.

**Breaking changes:** none
