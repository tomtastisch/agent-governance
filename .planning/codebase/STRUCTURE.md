---
last_mapped_commit: 645068bfcb201fbd261dc8e8b37d57cd2eb25a70
last_mapped_at: 2026-10-29
---
# Codebase Structure — Agent Governance

**Analysis date:** 2026-10-29
**Repository:** `/Users/tomtastisch/Projects/github/agent-governance`
**Package:** `@tomtastisch/agent-governance` v1.9.4

---

## 1. Top-level layout

```
/Users/tomtastisch/Projects/github/agent-governance/
├── package.json                  # @tomtastisch/agent-governance 1.9.4, type: module, bin agent-governance -> dist/cli.js
├── package-lock.json
├── tsconfig.json                 # strict TS build, include src/**/*.ts + tests/installer/**/*.ts
├── tsconfig.build.json           # build configuration for tsc -> dist/
├── VERSION                       # 1.9.4
├── socket.yml                    # socket.dev supply-chain metadata
├── release.files.sha256          # release artifact digest list
├── CITATION.cff
├── LICENSE                       # Apache-2.0
├── THIRD_PARTY_NOTICES.md
├── CHANGELOG.md
├── README.md                     # German-language project README
├── .github/                      # GitHub CI/CD and repo configuration
│   ├── workflows/
│   │   ├── ci.yml                # native-platform, native-package, installer-package, consistency-tests, release-metadata, docs-remote, release-validate
│   │   ├── npm-publish.yml
│   │   ├── npm-bootstrap-publish.yml
│   │   ├── pages.yml
│   │   ├── release-tag-verify.yml
│   │   └── socket-freshness.yml
│   ├── dependabot.yml
│   ├── FUNDING.yml
│   ├── copilot-instructions.md
│   └── signing/                  # allowed_signers, legacy_allowed_signers
├── src/                          # TypeScript sources (53 files, ~5,534 LOC)
├── tests/                        # installer + node + python tests (72 files, ~6,444 LOC ts/mjs)
├── tools/                        # build/release/site/verify scripts (11 files)
├── bundle/                       # versioned governance bundle (installed into target roots)
├── docs/                         # documentation (German), decisions, superpowers plans/specs
├── contracts/                    # governance-contract.json
├── integrations/                 # upstream harness/toolkit vendored artifacts
├── native/                       # agent_governance_fs.c native filesystem primitive
├── site/                         # built GitHub Pages (HTML/CSS)
├── assets/                       # branding PNGs and architecture/overview diagrams
├── .planning/                    # planning artifacts
│   └── codebase/                 # this mapping: ARCHITECTURE.md, STRUCTURE.md
├── .superpowers/                 # superpowers session artifacts (sdd/)
├── .gitignore
└── .git/
```

## 2. `src/` — TypeScript sources (53 files)

**Root layer (entry, commands, contracts):**
- `src/cli.ts` — CLI entry point; `runCli(argv)`; bin mapping `agent-governance -> dist/cli.js`
- `src/public-commands.ts` — `PUBLIC_COMMAND_HANDLERS` (inspect/plan/install/verify/status/update/uninstall/rollback/init), `INIT_INVOCATION`, `parseInitInvocation`, help rendering
- `src/command-catalog.ts` — `loadCommandCatalog()` → public command definitions
- `src/contracts.ts` — shared types: `InstallerCommand`, `PublicCommandId`, `PublicCommandDefinition`, `InstallerRequest`, `PlannedResource`, `InstallPlan`, `InstallResult`, `InstallState`, `InstallPhase`, `TerminalOutcome`, `EXIT_CODES`
- `src/transaction.ts` — `InstallerTransaction` class: inspect/plan/verify/install/update/uninstall/rollback; phase checkpoints; receipt lifecycle; rollback/restore
- `src/errors.ts` — `InstallerFailure`, `InterruptedFailure`, `ConcurrentEntryChange`
- `src/signals.ts` — `SignalCoordinator`, `SignalInterruption`

**Installer domain (`src/installer/`):**
- `src/installer/context.ts` — `resolveContext`, `bindingIdFor`, `Context`
- `src/installer/contracts.ts` — `architecture` constant (`GLOBAL_EXPLICIT_PATH_MANAGED_BLOCK`), `TransactionCheckpoint`, `TransactionRequest`
- `src/installer/planner.ts` — `planInstallation`
- `src/installer/mutation.ts` — `atomicCreate`, `atomicWrite`, `atomicRemove`, `ensureDirectoryTree`
- `src/installer/release-staging.ts` — `prepareRelease`, `activateRelease`
- `src/installer/receipts.ts` — `Receipt`, `storeIdentity`
- `src/installer/recovery.ts` — `restore` (rollback from backup + receipt)
- `src/installer/snapshot.ts` — `digest`, `matchesSnapshot`, `optionalBytes`
- `src/installer/locking.ts` — `withInstallationLock`
- `src/installer/local-rules.ts` — local-rules mutation planning/read
- `src/installer/replacement-validation.ts` — replacement guard validation
- `src/installer/version.ts` — release version resolution helpers

**Orchestration / init wizard (`src/init/`):**
- `src/init/orchestrator.ts` — `runInit` (4 stages: inspect → plan → tools → setup+verify), `runInitTools`
- `src/init/harnesses.ts` — `createAgntnHarnessesAdapter` / harness discovery
- `src/init/harness-discovery.generated.ts` — generated harness discovery data
- `src/init/prompt.ts` — `createClackPrompt`
- `src/init/support.ts` — `resolveSupport` (harness support decision per environment)
- `src/init/types.ts` — `InitOptions`, `InitResult`, `InitSelection`, `InitTarget`, `InitPlannedTarget`, `InitTransaction`, etc.
- `src/init/bindings.ts` — `resolveTarget`
- `src/init/branding.ts` — `renderBranding`
- `src/init/theme.ts` — init color theme
- `src/init/tool-preparation/index.ts` — `runToolPreparation`
- `src/init/tool-preparation/gh.ts` — GitHub tool preparation
- `src/init/tool-preparation/types.ts` — `ToolPreparationResult`

**Catalogs / routing:**
- `src/routing-catalog.ts` — `parseRoutingCatalogs`, `RoutingCatalogs` (triggers, policy_tags, scopes, requiredToolTriggers)
- `src/ssot-manifest.ts` — SSOT manifest handling
- `src/discovery-catalog.ts`, `src/templates-catalog.ts`, `src/catalog-paths.ts` — catalog loading
- `src/closed-toml.ts` — closed TOML parser (`exact`, `table`, `text`, `ID`, `idList`)

**Governance data model:**
- `src/contract-fixture.ts` — `governanceContract` fixture (vocabulary fields, tool fields)
- `src/governance-contract.ts` — contract surface
- `src/work-items.ts` — work-item classification
- `src/resume-checkpoint.ts`, `src/resume-checkpoint-schema.ts`, `src/resume-resolve.ts`, `src/resume-toon.ts` — stateful resume / TOON derivation
- `src/replacement.ts` — forward-only replacement export

**Primitives:**
- `src/filesystem.ts` — `captureIdentity`, `assertIdentity`
- `src/native-filesystem.ts` — `probeNativeFilesystemCapability`, `secureCreateDirectory` (backed by native addon)
- `src/managed-block.ts` — `installManagedBlock`, `removeManagedBlock`, `verifyManagedBlock` (the managed Markdown block in entry files)
- `src/target.ts` — `inspectTarget`
- `src/release.ts` — `verifyRelease`, `resolveLatestRelease`
- `src/terminal/theme.ts` — terminal color theme

## 3. `tests/` — test suite

**TypeScript (node --test):**
- `tests/installer/*.test.ts` — per-module tests: `cli.test.ts`, `command-catalog.test.ts`, `contracts.test.ts`, `transaction-architecture.test.ts`, `transaction.test.ts`, `replacement.test.ts`, `resume-checkpoint.test.ts`, `resume-resolve.test.ts`, `resume-toon.test.ts`, `planner.test.ts`, `mutation`-adjacent (`filesystem.test.ts`, `native-filesystem.test.ts`), `managed-block.test.ts`, `signals.test.ts`, `ssot-manifest.test.ts`, `target.test.ts`, `work-items.test.ts`, `init-*` tests (`init-orchestrator`, `init-harnesses`, `init-prompt`, `init-support`, `init-theme`, `init-tool-preparation`, `init-branding`, `init-latest`, `init-dependency-boundary`), `catalog-oracles.test.ts`, `conformance.test.ts`, `public-commands-contract.test.ts`, `release.test.ts`, `pack-verifier.test.ts`, `gh-preparation-mocked.test.ts`, `cli-help.test.ts`
- `tests/node/dynamic_tool_client.test.mjs`, `tests/node/provider_bridge.test.mjs` — mjs bridge tests

**Python (`unittest discover -s tests`):**
- `tests/test_bundle.py`, `tests/test_bootstrap_contract.py`, `tests/test_catalogs.py`, `tests/test_ci_workflow.py`, `tests/test_conformance.py`, `tests/test_copilot_qa_binding.py`, `tests/test_documentation.py`, `tests/test_e2e_contract.py`, `tests/test_enforcement_contract.py`, `tests/test_governance.py`, `tests/test_installer_distribution.py`, `tests/test_local_rules_runtime.py`, `tests/test_microsoft_upstream.py`, `tests/test_neutral_harness.py`, `tests/test_npm_metrics.py`, `tests/test_offline_runtime.py`, `tests/test_prepare_release.py`, `tests/test_provider_bridge.py`, `tests/test_release_check.py`, `tests/test_resume.py`, `tests/test_routing_performance.py`, `tests/test_routing_shadow.py`, `tests/test_site.py`, `tests/test_socket_freshness.py`, `tests/test_source_consolidation.py`, `tests/test_sync_citation.py`, `tests/test_sync_version.py`, `tests/test_templates.py`

**Support / fixtures / e2e:**
- `tests/fixtures/bootstrap/{current,fresh,legacy}/` — bootstrap fixture trees (legacy includes `install/adapters/codex.md`, `install/core/core.md`, `install/profile/personal-rules.md`, `harness-config.json`)
- `tests/fixtures/installer/{release,replacement-*,workspace}.ts` — installer fixtures
- `tests/fixtures/provider/{invalid,unknown}-policy.json` — provider policy fixtures
- `tests/fixtures/resume/{effect,state,writer}.ts` — resume fixtures
- `tests/fixtures/routing/{baseline,corpus}.json` — routing test corpora
- `tests/fixtures/runtime/synthetic-local-rules.md` — local-rules runtime fixture
- `tests/contracts/{conformance-mutations,public-commands,routing,templates,work-items}.json` — expected contracts
- `tests/e2e/` — `Dockerfile`, `*.schema.json`, `run_*.sh`, `run_init_pty.mjs`, `codex_probes.md`, package-lock/package.json for consumer tests
- `tests/support/{bootstrap_reference,catalog_validator,neutral_harness,routing_measurement,routing_shadow}.py`

## 4. `tools/` — build / release / verify scripts

- `tools/build-native.mjs` — native addon build (`agent_governance_fs.node`)
- `tools/prepare_release.py` — release preparation
- `tools/release_check.py` — tree/docs-remote/release consistency (`tree`, `docs-remote`, `release` modes)
- `tools/release_manifest.py` — release manifest checks
- `tools/site_build.py` — GitHub Pages site build
- `tools/socket_freshness.py` — socket freshness check
- `tools/sync_citation.py`, `tools/sync_version.py` — CITATION/VERSION sync
- `tools/project-harness-discovery.ts` — `harnesses:check` / `harnesses:generate`
- `tools/verify-pack.mjs`, `tools/verify-licenses.mjs` — pack and license verification

## 5. `bundle/` — versioned governance bundle

```
bundle/
├── GOVERNANCE.md                                     # canonical bootstrap (126 lines, German)
├── contracts/governance-contract.json                # governance contract surface
├── agent-governance/
│   ├── manifest.toml                                 # schema_version 4; modules + roles; unknown/ambiguous = block; local_rules = "local/user-rules.md"; ssot = "ssot/manifest.toml"; templates = "templates/manifest.toml"
│   ├── modules/{invariants,enforcement,evidence,workflow,architecture,verification,delivery,security,tool_routing,templates,context,resume}.md
│   ├── roles/{architecture,triage,quality-assurance,security-review}.md
│   ├── ssot/
│   │   ├── manifest.toml
│   │   ├── routing/{triggers,policy_tags,scopes,tools,commands/commands}.toml   # triggers.toml: 49 triggers
│   │   ├── discovery/discovery-signals.toml
│   │   └── work-items/{classifications,projections/github-labels}.toml
│   └── templates/
│       ├── manifest.toml                             # atomic template registry
│       ├── communication/{completion,status,tool-error-blocker}.md
│       ├── context/handoff.md
│       ├── delivery/{pull-request,push-pr-checkpoint,release-checkpoint}.md
│       ├── external-effects/approval-checkpoint.md
│       ├── git/{branch,commit}.md
│       └── review/finding.md
```

## 6. `docs/` — documentation

`docs/installer-architecture.md`, `docs/installer-cli-reference.md`, `docs/installer-json-schemas.md`, `docs/installer-threat-model.md`, `docs/harness-recipes.md`, `docs/releasing.md`, `docs/resume-checkpoints.md`, `docs/work-items.md`, `docs/adapter-audit.md`, `docs/dependency-evidence.md`, `docs/github-pages.md`, `docs/issue-94-routing-evidence.md`, `docs/resume-checkpoints.md`, `docs/audits/2026-07-30-source-migration.md`, `docs/decisions/0001-…0007-*.md` (ADR-style decisions in German), `docs/superpowers/plans/*.md` and `docs/superpowers/specs/*.md` (design specs for past work items).

## 7. Remaining directories

- `integrations/agntn-harnesses/` — `README.md`, `upstream.lock.json`, `upstream/harnesses-0.3.0.tgz`
- `integrations/microsoft-agent-governance-toolkit/` — vendored toolkit v4.1.0 (`bridge/{action-bindings.json,build-provider.sh,codex-hook.mjs,extract-snapshot.py,policy.json,provider.mjs,runtime.files.sha256,verify-runtime.py}`, upstream tarball, LICENSE/NOTICE/TRADEMARKS)
- `native/agent_governance_fs.c` — C filesystem primitive (prebuilt per platform in `prebuilds/`)
- `site/` — built GitHub Pages (`index.html`, `ai-coding-agent-governance/`, `governance-as-code/`, `assets/site.css`)
- `assets/branding/` — `agent-governance-icon.png`, `agent-governance-terminal.png`
- `assets/diagrams/` — `governance-architecture.png`, `governance-overview.png`
- `.planning/codebase/` — this mapping (ARCHITECTURE.md, STRUCTURE.md)
- `.superpowers/sdd/` — superpowers session artifacts (e.g. `2026-08-26-issue-44-init-onboarding/`)

## 8. Naming conventions (quick reference)

| Concern | Convention | Example |
|---|---|---|
| TS source files | `kebab-case` | `release-staging.ts`, `local-rules.ts` |
| TS directories | lowercase, singular | `init/`, `installer/`, `tool-preparation/` |
| TS identifiers | `camelCase` functions/vars, `PascalCase` classes | `runInit`, `InstallerTransaction` |
| Test files | `tests/installer/<unit>.test.ts`, `tests/test_*.py`, `tests/node/<unit>.test.mjs` | `transaction.test.ts`, `test_bundle.py` |
| Test fixtures | `tests/fixtures/<domain>/<name>.*`, expected contracts `tests/contracts/*.json` | `tests/fixtures/routing/corpus.json` |
| Bundle documents | German prose, `bundle/agent-governance/{modules,roles,ssot,templates}/` | `modules/architecture.md` |
| Output artifacts | JSON, `schemaVersion: 1`, `Object.freeze` | `InstallResult`, `Receipt` |
