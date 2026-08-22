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

- Keine.

### Removed

- Keine.

**Breaking changes:** none

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
