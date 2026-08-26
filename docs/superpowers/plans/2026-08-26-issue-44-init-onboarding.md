# Issue 44 Init-Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Einen produktneutralen, passiven und professionellen `agent-governance init`-Pfad mit gemeinsamer Command-SSOT, bestehender Installer-Engine und veröffentlichbarem npm-Minor liefern.

**Architecture:** Command-Katalog und Discovery-Signalkatalog sind strikt validierte Bundle-SSOTs. Kleine TypeScript-Module trennen öffentliche Commands, bounded Discovery, Confidence/Boundary/Duplicate-Aufbereitung, Prompt-UI, Branding und Init-Orchestrierung; alle Mutationen laufen weiterhin ausschließlich durch `InstallerTransaction`.

**Tech Stack:** Node.js >=24, TypeScript/ESM, `node:sqlite`, `smol-toml@1.8.0`, `@clack/prompts@1.7.0`, Node test runner, Python unittest, npm/gh.

**Spec:** `docs/superpowers/specs/2026-08-26-issue-44-init-onboarding-design.md`

## Global Constraints

- Keine Produktnamen, Produktpfade oder Binary-Namen als Discovery-Classifier; keine Candidate-Ausführung, AI/LLM, Login, Netzwerkklassifikation oder Symlinkfolge.
- `InstallerCommand` bleibt die acht Transaktionscommands; `init` ist ausschließlich Public-/Orchestrierungscommand.
- Jeder öffentliche Command steht genau einmal in `bundle/agent-governance/catalogs/commands.toml`, besitzt einen realen Handler und verwendet die katalogisierte Beschreibung für Help.
- `HIGH_CONFIDENCE` verlangt unabhängige starke Runtime- und korroborierende Evidence; Unsicherheit und nicht unterscheidbare Copies werden konservativ `UNCERTAIN`.
- Externe Daten werden bounded, streng typisiert, control-character-sanitized und fail-closed verarbeitet; SQLite wird nur read-only geöffnet und garantiert geschlossen.
- Genau drei Wizard-Hauptschritte; keine Mutation vor expliziter Bestätigung und kein Erfolg vor erfolgreichem Verify.
- `@clack/prompts` ist der einzige Prompt-Stack; keine undeclared transitive Dependency wird importiert.
- Tests verwenden ausschließlich synthetische isolierte HOME-/XDG-/Application-Support-Roots.
- #42-Management-Namespaces und #37-Readiness-Zustandsmaschine bleiben außerhalb des Scopes.
- TDD: Für jede Verhaltensänderung zuerst ein spezifischer roter Test, beobachtetes erwartetes Scheitern, minimale Implementierung, grüner relevanter Umfang, Refactor bei weiter grünem Stand.

---

### Task 1: Command-SSOT, Loader, Registry und Help

**Files:**
- Create: `bundle/agent-governance/catalogs/commands.toml`
- Create: `src/catalog-paths.ts`
- Create: `src/command-catalog.ts`
- Create: `src/public-commands.ts`
- Modify: `bundle/agent-governance/manifest.toml`
- Modify: `src/contracts.ts`
- Modify: `src/cli.ts`
- Modify: `package.json`
- Modify: `package-lock.json`
- Modify: `tests/support/catalog_validator.py`
- Modify: `tests/test_catalogs.py`
- Modify: `tests/installer/cli.test.ts`
- Create: `tests/installer/command-catalog.test.ts`

**Interfaces:**
- Produces: `InstallerCommand`, `PublicCommandId`, `PublicCommandDefinition`, `loadCommandCatalog(releaseRoot?: string)`, `PUBLIC_COMMAND_HANDLERS`, `renderGlobalHelp()`, `renderCommandHelp(id)`.
- Consumes: existing `InstallerTransaction` methods and package-relative release root.

- [ ] **Step 1: Write failing catalog and CLI tests** that assert the nine exact paths/IDs, closed schema, strict semantic rejection, handler ↔ SSOT equality, descriptions in global help, `--help`/`-h`, `init --help`, `install --help`, help Exit 0/no transaction/discovery, unknown-command Exit 2, and `init` exclusion from `InstallerCommand`.
- [ ] **Step 2: Run** `node --experimental-strip-types --test tests/installer/command-catalog.test.ts tests/installer/cli.test.ts` and `python3 -m unittest tests.test_catalogs -v`; record failures caused by missing catalog/help.
- [ ] **Step 3: Install and implement the minimal closed command catalog and loader** by pinning `smol-toml@1.8.0` as a direct runtime dependency and using `smol-toml.parse` with exact field/type/ID/path/effect/capability validation and duplicate rejection; introduce public-command routing without widening the transaction union.
- [ ] **Step 4: Implement help before required-option parsing** and dispatch the eight transaction handlers through one registry; reserve an injected init handler for the later orchestrator.
- [ ] **Step 5: Re-run targeted tests and `npm run typecheck`**, refactor only while green, then commit `feat(cli): add command catalog and help registry`.

### Task 2: Discovery catalog, bounded enumeration and structured evidence

**Files:**
- Create: `bundle/agent-governance/catalogs/discovery-signals.toml`
- Create: `src/discovery/types.ts`
- Create: `src/discovery/catalog.ts`
- Create: `src/discovery/zones.ts`
- Create: `src/discovery/filesystem.ts`
- Create: `src/discovery/structured.ts`
- Create: `src/discovery/sqlite.ts`
- Create: `src/discovery/package-metadata.ts`
- Create: `tests/installer/discovery-catalog.test.ts`
- Create: `tests/installer/discovery-filesystem.test.ts`
- Create: `tests/installer/discovery-evidence.test.ts`
- Modify: `bundle/agent-governance/manifest.toml`
- Modify: `tests/support/catalog_validator.py`
- Modify: `tests/test_catalogs.py`

**Interfaces:**
- Produces: `DiscoveryCatalog`, `DiscoveryLimits`, `EvidenceFamily`, `EvidenceRecord`, `CandidateClass`, `discoverZones(environment)`, `enumerateCandidates(zones, limits, clock)`, `analyzeStructuredFile(path, limits)`, `analyzeSqliteSchema(path, limits)`, `analyzePackageMetadata(path, limits)`.
- Consumes: `smol-toml`, `node:sqlite` `DatabaseSync(path,{readOnly:true})`, canonical non-symlink paths.

- [ ] **Step 1: Add red tests** for catalog closed validation and generic signals plus direct HOME/XDG/macOS/App-Bundle zones; symlink, permission, oversize, file/depth/entry/SQLite/time budgets and malformed structured inputs.
- [ ] **Step 2: Add red evidence tests** proving bounded key/schema-only JSON/TOML/plist-like inspection, local package metadata limits, read-only SQLite schema access, no row query, defensive close, and malformed SQLite failure.
- [ ] **Step 3: Run the three new test files and Python catalog tests**; verify failures identify missing discovery contracts.
- [ ] **Step 4: Implement catalog validation, platform zone enumeration and no-follow bounded traversal** with explicit counters/deadline and incomplete-candidate status.
- [ ] **Step 5: Implement structured/package/SQLite evidence extraction** without persisting values or secrets; sanitize every displayable string and close databases in `finally`.
- [ ] **Step 6: Re-run targeted tests plus typecheck**, refactor while green, then commit `feat(discovery): add bounded passive evidence collection`.

### Task 3: Classifier, boundary refinement, duplicates and identity

**Files:**
- Create: `src/discovery/classifier.ts`
- Create: `src/discovery/boundary.ts`
- Create: `src/discovery/duplicates.ts`
- Create: `src/discovery/identity.ts`
- Create: `src/discovery/index.ts`
- Create: `tests/installer/discovery-classifier.test.ts`
- Create: `tests/installer/discovery-boundary.test.ts`
- Create: `tests/installer/discovery-duplicates.test.ts`
- Create: `tests/installer/discovery-regression.test.ts`

**Interfaces:**
- Produces: `classifyEvidence(records,catalog): Candidate`, `refineCandidateRoots(candidates): Candidate[]`, `resolveDuplicateCandidates(candidates): Candidate[]`, `resolveCandidateIdentity(candidate): CandidateDisplay`, `discoverCandidates(options): Promise<Candidate[]>`.
- Consumes: Task-2 EvidenceRecords and declarative confidence thresholds; identity is invoked only after positive generic classification.

- [ ] **Step 1: Write red classifier tests** for multi-source Runtime/State/Tooling/AI metadata High, package-only/App-bundle/plausible Uncertain, and all required negative overlay/single-document/message/`AI agent` cases.
- [ ] **Step 2: Write red boundary and duplicate tests** for one strong child, multiple child clusters, active plus near-copy, indistinguishable copies, and mtime-only secondary tie-break behavior.
- [ ] **Step 3: Write the synthetic 6/7 labeled regression fixture** whose labels may name known targets but whose classifier inputs contain only generic evidence; require conservative coverage and no obvious false-positive High.
- [ ] **Step 4: Run the four test files** and record expected classifier/boundary/duplicate absence failures.
- [ ] **Step 5: Implement minimal independent-source scoring, conservative High rules, root refinement, normalized-structure duplicate resolution, ambiguity demotion and post-classification display identity**.
- [ ] **Step 6: Re-run discovery tests and full installer tests**, refactor while green, then commit `feat(discovery): classify and deduplicate candidate roots`.

### Task 4: Three-step init orchestration over InstallerTransaction

**Files:**
- Create: `src/init/types.ts`
- Create: `src/init/orchestrator.ts`
- Create: `src/init/bindings.ts`
- Modify: `src/public-commands.ts`
- Modify: `src/cli.ts`
- Create: `tests/installer/init-orchestrator.test.ts`
- Modify: `tests/installer/cli.test.ts`

**Interfaces:**
- Produces: `InitTarget`, `InitDependencies`, `runInit(options,deps): Promise<InitResult>`, `resolveBinding(candidate,manualInput): InitTarget`.
- Consumes: `discoverCandidates`, prompt abstraction from Task 5 via an interface, and a transaction factory exposing real `plan()`, `install()`, `verify()`, `status()`.

- [ ] **Step 1: Write red orchestration tests** for exact 1/3→2/3→3/3 order, multiple deterministic targets, manual custom root/entry, no TTY, cancel, no mutation before confirm, real plan call before install, mandatory verify, verify failure, no false aggregate success, CURRENT idempotency and optional installation root.
- [ ] **Step 2: Run init and CLI tests**; verify failures are from the absent orchestration boundary.
- [ ] **Step 3: Implement binding resolution using existing explicit target/entry contracts**; ambiguous native entry resolution stays in the step-2 custom flow and never becomes a preset matrix.
- [ ] **Step 4: Implement runInit with dependency injection, one explicit approval, sequential deterministic transactions and verify-gated result**; connect it as a public handler without adding `init` to `InstallPlan.command`.
- [ ] **Step 5: Re-run targeted tests and installer suite**, refactor while green, then commit `feat(init): orchestrate plan install and verify`.

### Task 5: Prompt UI, accessibility and terminal branding

**Files:**
- Create: `src/init/prompt.ts`
- Create: `src/init/theme.ts`
- Create: `src/init/branding.ts`
- Create: `assets/branding/agent-governance-terminal.png`
- Create: `tests/installer/init-prompt.test.ts`
- Create: `tests/installer/init-theme.test.ts`
- Create: `tests/installer/init-branding.test.ts`
- Create: `tests/e2e/run_init_pty.mjs`
- Modify: `package.json`
- Modify: `package-lock.json`
- Modify: `tools/verify-pack.mjs`

**Interfaces:**
- Produces: `createClackPrompt(io): InitPrompt`, `renderCandidate(candidate,state,theme)`, `renderLegend(theme)`, `renderBranding(io): Promise<void>`.
- Consumes: `@clack/prompts` multiselect/path/confirm/spinner/cancel and the selected packaged terminal asset; no other prompt/color stack.

- [ ] **Step 1: Write red UI tests** for high preselection, uncertain differentiation without forced label text, separate confidence/focus/selection markers, permanent custom option/footer legend, keyboard/cancel semantics, 60-column wrapping, NO_COLOR/monochrome and sanitized local labels.
- [ ] **Step 2: Write red branding tests** for bounded icon dimensions, deterministic fallback, rendering failure continuation and package path; add a PTY driver that uses only synthetic HOME/XDG roots.
- [ ] **Step 3: Run targeted UI tests** and record expected missing-renderer failures.
- [ ] **Step 4: Pin `@clack/prompts@1.7.0` and derive the small PNG deterministically at development time**, implement Clack prompt/theme/spinner and decorative branding fallback; do not add `terminal-image` unless its measured tree remains proportionate.
- [ ] **Step 5: Run UI tests, typecheck and PTY smoke**, inspect 60/80/120 columns and NO_COLOR, iterate only via new failing regression tests, then commit `feat(init): add accessible branded terminal wizard`.

### Task 6: Metadata, packaging, documentation and version 1.1.0

**Files:**
- Modify: `package.json`
- Modify: `package-lock.json`
- Modify: `VERSION`
- Modify: `CHANGELOG.md`
- Modify: `README.md`
- Modify: `docs/installer-cli-reference.md`
- Modify: `docs/installer-architecture.md`
- Modify: `docs/installer-threat-model.md`
- Modify: `docs/dependency-evidence.md`
- Modify: `release.files.sha256`
- Modify: `tools/verify-licenses.mjs`
- Modify: `tools/verify-pack.mjs`
- Modify: `tests/test_documentation.py`
- Modify: `tests/test_installer_distribution.py`
- Modify: `tests/test_source_consolidation.py`
- Modify: `tests/installer/pack-verifier.test.ts`
- Modify: `tests/e2e/run_package_consumers.sh`

**Interfaces:**
- Produces: npm package metadata, allowlisted dependency/license contract, packed command/discovery catalogs and terminal asset, registry-ready 1.1.0 projections.
- Consumes: runtime imports and decisions from Tasks 1–5.

- [ ] **Step 1: Re-read npm registry and release state**, then write red metadata/pack/docs tests for exact dependencies, truthful description/keywords, runtime assets, init-first quickstart, advanced explicit commands, threat boundaries and tarball-only help/init smokes.
- [ ] **Step 2: Run targeted Python/pack/package tests** and verify they fail for the old zero-dependency/asset/quickstart contracts.
- [ ] **Step 3: Update package metadata and lockfile without force**, document direct/transitive counts, licenses, install/tarball sizes, maintenance, integrity, audit and the explicit `terminal-image` decision.
- [ ] **Step 4: Update README, CLI reference, architecture and threat model** without creating a second command truth or reversing the no-adapter decision.
- [ ] **Step 5: Set `VERSION` to `1.1.0`**, run the repository sync/version and release-manifest tools, add the dated changelog section, and avoid historical replacements.
- [ ] **Step 6: Run targeted docs, distribution, pack and consumer tests**, then commit `feat(release): prepare npm init onboarding 1.1.0`.

### Task 7: Full local gates and real visual QA

**Files:**
- Modify only test/code/docs files required by a reproduced gate failure, always through a new red regression first.
- Record: `.superpowers/sdd/2026-08-26-issue-44-init-onboarding/visual-qa.md` (git-ignored evidence).

**Interfaces:**
- Produces: exact-head local verification and visual-QA evidence.
- Consumes: complete branch from Tasks 1–6.

- [ ] **Step 1: Run** `npm ci`, `npm run typecheck`, `npm run lint`, `npm test`, `python3 -m unittest discover -s tests -v`, `npm audit --audit-level=high`, `npm run license:check`, `npm run pack:check`, `npm run test:package`, `tests/e2e/run_installer_fixture.sh`, `tests/e2e/run_neutral_harness.sh`, `git diff --check`, release/manifest checks and a fresh real-tarball consumer smoke.
- [ ] **Step 2: On any failure invoke systematic-debugging**, reproduce, trace root cause, add a focused red test, implement the smallest fix, rerun affected and full gates, and commit an atomic `fix(...)` change.
- [ ] **Step 3: Run the actual init wizard in a PTY** with isolated synthetic HOME at 60, 80 and 120 columns, `NO_COLOR`, ANSI fallback, available image protocol, cancel and error paths; use terminal screenshots/captures for visual inspection and record exact observations.
- [ ] **Step 4: Re-run every affected gate after visual corrections**, then commit any evidence-backed corrections.

### Task 8: Independent exact-head review, PR, CI and authorized release path

**Files:**
- Review artifacts only in the plan-specific ignored SDD workspace; repository changes only for validated findings.

**Interfaces:**
- Produces: independent QA and SEC verdicts on exact Head, PR and CI evidence, then merge/tag/release/npm readback only when protection and authorization gates permit.
- Consumes: governance QA/SEC roles, Superpowers requesting-code-review and verification-before-completion.

- [ ] **Step 1: Build one exact-head review package and dispatch fresh read-only QA and SEC contexts** covering security, false positives, paths/symlinks, SSOT drift, help/parser, TTY/ANSI, supply chain, packaging and compatibility.
- [ ] **Step 2: Classify every finding**, fix Critical/Important and valid blocking findings via TDD, rerun affected/full gates and repeat both required reviews on the new exact Head.
- [ ] **Step 3: Run fresh verification-before-completion gates**, commit coherent residual changes, push `feat/issue-44/init-onboarding`, open a PR to `main` referencing #44, and verify local/remote/PR Head equality.
- [ ] **Step 4: Observe all required CI/review threads**, systematically debug failures without disabling checks, update the PR and re-review exact changed Heads.
- [ ] **Step 5: If protection permits, merge through the repository path**; otherwise emit the exact `USER:` action and pause without weakening rules.
- [ ] **Step 6: On merged exact main**, re-read registry/version, rerun release gates, create the required signed `v1.1.0` tag, await tag verification, create GitHub Release, use existing OIDC Trusted Publishing, read back registry/provenance/integrity and smoke a fresh registry consumer; stop with `USER:` at any real signature/review/publishing permission boundary.
- [ ] **Step 7: Only after all applicable readbacks**, post the compact closure comment to #44 and close it; otherwise leave it open with the precise external blocker.
