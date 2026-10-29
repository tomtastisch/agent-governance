# Requirements: Agent Governance

**Definiert:** 2026-10-29  
**Core Value:** Ein einzelnes, unveränderliches, harness-agnostisches Governance-Bundle als einzige Bootstrap-Quelle für KI-Agent-Installationen — fail-closed, SSOT-konform und ohne Harness-spezifische Adapter.

## v1 Requirements

Requirements für die aktuelle Release-Linie. Jedes Requirement mapped auf Roadmap-Phasen.

### Architektur / Dokumentation (DOC-ARCH)

- [ ] **DOC-ARCH-01**: README.md als Einstiegsschicht — Was ist Agent Governance, warum sinnvoll, wie startet man, wo liegen Details
- [ ] **DOC-ARCH-02**: docs/installer-cli-reference.md — Commands, Optionen, Exit-Verhalten, formaler CLI-Vertrag
- [ ] **DOC-ARCH-03**: docs/harness-recipes.md — Belegte Codex-, Claude-Code-, OpenCode-V2- und OpenClaw-Beispiele
- [ ] **DOC-ARCH-04**: docs/installer-architecture.md — Komponenten, Datenfluss, Installation, Lifecycle, Transaktionen, Backups, Recovery
- [ ] **DOC-ARCH-05**: docs/installer-threat-model.md — Trust Boundaries, Sicherheitsgarantien, Nicht-Garantien, Same-UID-Grenze, Residual Risks
- [ ] **DOC-ARCH-06**: docs/installer-json-schemas.md — JSON-Strukturen und Feldsemantik
- [ ] **DOC-ARCH-07**: CHANGELOG.md — Versionen und Migrationshistorie
- [ ] **DOC-ARCH-08**: bundle/ als einzige normative Governancequelle
- [ ] **DOC-ARCH-09**: Audits, Decisions, ältere Specs als historische, nicht normative Evidenz
- [ ] **DOC-ARCH-10**: INSTALL.md erst löschen, nachdem Migrationsziele den weiterhin gültigen einzigartigen Inhalt abdecken
- [ ] **DOC-ARCH-11**: Alle Harness-Rezepte verlangen `--scope global`, expliziten absoluten `--installation-root`, verifizierten absoluten `--target-root`, relative Markdown-`--entry-file`
- [ ] **DOC-ARCH-12**: Vor Mutation ist der tatsächlich aktive globale Zielpfad des jeweiligen Harness zu prüfen
- [ ] **DOC-ARCH-13**: Drei PNG-Dateien unter assets/ (Branding-Icon, Overview, Architektur-Diagramm)
- [ ] **DOC-ARCH-14**: Release-Check `tools/release_check.py tree` prüft offline deterministisch Host, Owner/Repo, main-Ref, erlaubten Zielpfad

### Copilot-QA-Binding (COP-BIND)

- [ ] **COP-BIND-01**: Genau eine Datei `.github/copilot-instructions.md` — bewusst klein, keine vollständige Kopie der QA-Rolle
- [ ] **COP-BIND-02**: Copilot liest `bundle/agent-governance/roles/quality-assurance.md` und `bundle/agent-governance/modules/delivery.md` (DEL-002, DEL-003, DEL-007, DEL-008, DEL-009)
- [ ] **COP-BIND-03**: Keine GitHub-URL-Includes und keine `$HOME`-Dateien; ausschließlich Repositorypfade des PR-Heads
- [ ] **COP-BIND-04**: Kein eigener Materializer — keine `materialize(...)`-Funktion, keine SHA-256-Provenienz
- [ ] **COP-BIND-05**: Mechanischer Binding-Test verifiziert Datei-Existenz, Nichtnormativität, Referenzintegrität, Rule-ID-Eindeutigkeit
- [ ] **COP-BIND-06**: DEL-008: GitHub-Copilot-PR-Review erfüllt bevorzugte QA-Provider-Rolle nur bei belegter Revieweridentität und auflösbaren kanonischen Referenzen
- [ ] **COP-BIND-07**: DEL-010 als neue Regel für optionales Parallel-QA — nicht standardmäßig aktiv

### Globaler explizit-Pfad-Installer (GLO-INST)

- [ ] **GLO-INST-01**: Package liefert globalen, non-interaktiven Node.js CLI ohne third-party Runtime-Dependencies
- [ ] **GLO-INST-02**: Repository-owned Node-API C Primitive für handle-bound exclusive rename auf unterstützten Platformen
- [ ] **GLO-INST-03**: Jedes Target explizit: absoluter canonical `--target-root`, relative Markdown `--entry-file`, globaler `--scope`, absoluter canonical `--installation-root`
- [ ] **GLO-INST-04**: Runtime enthält keine Harness-Namen, Presets, Detection, Adapter, Hooks, MCP Mutation, Approval-Logik
- [ ] **GLO-INST-05**: Unterstützte Commands: `inspect`, `plan`, `install`, `verify`, `status`, `update`, `uninstall`, `rollback`
- [ ] **GLO-INST-06**: Unknown options, duplicate values, relative roots, root escape, symlinks, non-Markdown entries, ambiguous markers, inventory drift, Identity changes fail closed vor produktiver Mutation
- [ ] **GLO-INST-07**: Verification rejected missing inventory entries, additional normative files, traversal, links, non-regular payload files, oversized files, duplicate paths, unsupported manifest shape, digest mismatch
- [ ] **GLO-INST-08**: Staging auf destination filesystem; Activation mit write-with-exclusive-create, readback, atomic rename, directory identity revalidation, durable receipt
- [ ] **GLO-INST-09**: `<installation-root>/releases/<version>/bundle` contains verified release bundle
- [ ] **GLO-INST-10**: `<installation-root>/bindings/<binding-id>/current.json` identifiziert aktiv version und digests für ein explizites target/entry Paar
- [ ] **GLO-INST-11**: `<installation-root>/backups` contains immutable per-transaction backups and receipts
- [ ] **GLO-INST-12**: Entry enthält höchstens einen Managed Block (`<!-- BEGIN AGENT_GOVERNANCE_MANAGED_V1 -->` / `<!-- END AGENT_GOVERNANCE_MANAGED_V1 -->`)
- [ ] **GLO-INST-13**: Generated body identifiziert sich als Projektion, dokumentiert Governance-Version, canonical installation root, normative Bootstrap- und Manifest-Pfade, SHA-256-Digests, pre-response Load Order
- [ ] **GLO-INST-14**: Bytes außerhalb des Blocks werden exakt preserved; LF oder CRLF beibehalten; neue Datei UTF-8 ohne BOM mit LF
- [ ] **GLO-INST-15**: `--local-rules` optional und explizit; absolute canonical reguläre nicht-Symlink Markdown-Datei; nie geloggt oder in Output-Fingerprints enthalten

### Init-Onboarding (INIT-ONB)

- [ ] **INIT-ONB-01**: Einzige normale öffentliche Installations- und Erstkonfigurationswahrheit ist `npm i @tomtastisch/agent-governance` gefolgt von `npx agent-governance init`
- [ ] **INIT-ONB-02**: `init` ist interaktive Orchestrierung über der vorhandenen `InstallerTransaction`; einzige mutierende Engine bleibt `plan -> install -> verify`
- [ ] **INIT-ONB-03**: `bundle/agent-governance/catalogs/commands.toml` ist einzige Command-Level-SSOT für alle Commands inkl. `init`
- [ ] **INIT-ONB-04**: Jeder Command-Eintrag enthält stabile ID, namespacefähigen Pfad, kanonische Kurzbeschreibung, Capability, Wirkungsklasse und Orchestrierungs-/Interaktivitätsmetadaten
- [ ] **INIT-ONB-05**: Strikt validierender Loader auf Basis von `smol-toml` lehnt unbekannte Felder, Typen, doppelte Pfade und semantisch ungültige Kataloge fail-closed ab
- [ ] **INIT-ONB-06**: Drei-Schritt-Wizard: (1) Umgebung prüfen, (2) AI-/LLM-Ziele auswählen, (3) Prüfen und einrichten
- [ ] **INIT-ONB-07**: Ohne interaktives TTY bricht `init` deterministisch ab und verweist auf expliziten nicht-interaktiven Installerweg
- [ ] **INIT-ONB-08**: `@clack/prompts@1.7.0` ist einziger Prompt-Stack; `smol-toml@1.8.0` ist TOML-Parser
- [ ] **INIT-ONB-09**: `init` startet weder npm, pnpm, yarn noch bun; fehlende deklarierte Runtime-Dependency ist fehlerhaftes Package, wird fail-closed gemeldet

### Forward-only Replacement (FWD-REPL)

- [ ] **FWD-REPL-01**: Narrow public package export `./replacement` mit `replaceInstallation`; kein neuer CLI-Command
- [ ] **FWD-REPL-02**: Additive Package-Capability ist SemVer minor; kein Release-Bump in dieser Implementierung
- [ ] **FWD-REPL-03**: Request liefert explizit source installation root, new absent installation root, release root, target root und relative Markdown entry file
- [ ] **FWD-REPL-04**: Source und destination installation roots müssen disjoint sein; entry/target muss outside both sein
- [ ] **FWD-REPL-05**: Alte Receipts, Bindings, Release-Schemas oder alte Local Rules werden nicht gelesen, übersetzt, trusted, mutiert, kopiert oder regeneriert
- [ ] **FWD-REPL-06**: Six transaction steps: Validate → Bind → Reserve → Recreate → Verify → Restore-on-failure
- [ ] **FWD-REPL-07**: Keine globale Dateisystem-Suche, keine neue Runtime-Dependency, kein legacy-Branch, kein weakened Device-Check

### Resume-Materialisierung (RES-MAT)

- [ ] **RES-MAT-01**: Neuer Package-Subpfad `resume-checkpoint` materialisiert bestätigte, minimierte Resume-Metadaten
- [ ] **RES-MAT-02**: Vollständige Checkpoint-Generationen mit vorhandener exklusiver nativen Rename-Primitive veröffentlicht; keine Datenbank oder Hintergrunddienst
- [ ] **RES-MAT-03**: Expliziter, privater Speicherordner enthält fortlaufende Generationen; Writer bindet sich an erwartete Generation und deren Fingerprint
- [ ] **RES-MAT-04**: Vor und nach Veröffentlichung werden Schema, Payload, Vorgängerbindung und Verzeichnisidentität geprüft
- [ ] **RES-MAT-05**: Abbruch hinterlässt entweder alten oder vollständig validierbaren neuen Zustand
- [ ] **RES-MAT-06**: Inhalt erweitert bestehenden ResumeProjection-Inhalt um granulare Identitäten, priorisierte Authority-Referenzen, aktiven Task/Status
- [ ] **RES-MAT-07**: Schemafelder geschlossen, Größen begrenzt; keine generischen Payloads, Toolausgaben, Chats, Credentials oder Credential-Derivate
- [ ] **RES-MAT-08**: Keine Netzwerkzugriffe; External Effects werden vor Callback mit Operation-ID, Ziel, Aktion und sicheren Input-Bindungen PREPARED persistiert

### Cross-Language Conformance (CONF-LANG)

- [ ] **CONF-LANG-01**: `contracts/governance-contract.json` ist reine, sprachneutrale Deklaration aller strukturellen Definitionen
- [ ] **CONF-LANG-02**: Fixture liegt unter `contracts/governance-contract.json` im Repository-Root und wird in `package.json` `files` aufgenommen
- [ ] **CONF-LANG-03**: TypeScript konsumiert Fixture über typisierten Loader `src/contract-fixture.ts` (fail-closed, geschlossenes Schema)
- [ ] **CONF-LANG-04**: Python konsumiert dieselbe Fixture über `tests/support/catalog_validator.py` (`load_contract_fixture`)
- [ ] **CONF-LANG-05**: Beide Validatoren werden gegen gleiche Fixture-Menge geprüft und müssen identische Accept/Reject-Verdicts liefern
- [ ] **CONF-LANG-06**: Conformance-Gate: jede Abweichung im Verdict lässt Gate fehlschlagen
- [ ] **CONF-LANG-07**: Fixture liegt außerhalb `bundle/` und beeinflusst geschlossenes Release-Inventar (`release.files.sha256`) nicht

### Resume-Candidate-Resolution (RES-CAND)

- [ ] **RES-CAND-01**: Interner Modul `src/resume-resolve.ts`, nicht in `package.json` `exports` aufgenommen (SemVer-patch-kompatibel)
- [ ] **RES-CAND-02**: `resolveResumeCandidates(candidates, context)` erhält Candidate-Scope als `readonly string[]` kanonischer Store-Verzeichnispfade; keine Dateisystem-Suche
- [ ] **RES-CAND-03**: Matching ist exakter Identitätsvergleich, keine Heuristik; `exactHead`/`HEAD` ist nie Matching-Schlüssel
- [ ] **RES-CAND-04**: Ergebnis-Vorrang: INVALID > AMBIGUOUS > RESUME > NO_MATCH
- [ ] **RES-CAND-05**: Rein lesend; ruft weder `executeEffect` noch `recoverEffect` auf; kein Netzwerkzugriff, kein PR-Readback

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

(Keine v2-Requirements definiert — alle bekannten Anforderungen sind in v1 erfasst.)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Harness-CLI-Ausführung | Keine neue Support-/Binding-Authority (CON-SEC-001) |
| Eigener Materializer / Synchronisations-Engine | Kein eigener Materializer (CON-DEP-003) |
| Socket.dev als Release-Authority | Nicht-autoritativ (CON-DEP-002) |
| Privilegierter Broker / Daemon / setuid | Sicherheitsvertrag (CON-PLT-004) |
| cwd-Fallback / automatische Erkennung | Explicit-over-implicit (CON-INS-003) |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DOC-ARCH-01 bis DOC-ARCH-14 | Phase 1 (Dokumentation) | Pending |
| COP-BIND-01 bis COP-BIND-07 | Phase 2 (Copilot-QA-Binding) | Pending |
| GLO-INST-01 bis GLO-INST-15 | Phase 3 (Installer-Hardening) | Pending |
| INIT-ONB-01 bis INIT-ONB-09 | Phase 4 (Init-Onboarding) | Pending |
| FWD-REPL-01 bis FWD-REPL-07 | Phase 5 (Forward-only Replacement) | Pending |
| RES-MAT-01 bis RES-MAT-08 | Phase 6 (Resume-Materialisierung) | Pending |
| CONF-LANG-01 bis CONF-LANG-07 | Phase 7 (Cross-Language Conformance) | Pending |
| RES-CAND-01 bis RES-CAND-05 | Phase 8 (Resume-Candidate-Resolution) | Pending |

**Coverage:**  
- v1 requirements: ~168 total (aus 9 SPEC-Dokumenten)  
- Mapped to phases: 8  
- Unmapped: 0 ✓

---\
*Requirements definiert: 2026-10-29*  
*Letzte Aktualisierung: 2026-10-29 nach Intel-Synthese aus .planning/intel/*
