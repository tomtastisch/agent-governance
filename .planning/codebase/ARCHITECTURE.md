---
last_mapped_commit: 645068bfcb201fbd261dc8e8b37d57cd2eb25a70
last_mapped_at: 2026-10-29
---
# Codebase Architecture — Agent Governance

**Analysis date:** 2026-10-29
**Repository:** `/Users/tomtastisch/Projects/github/agent-governance`
**Package:** `@tomtastisch/agent-governance` v1.9.4
**Scope:** read-only mapping of the existing codebase; no behavior changed.

---

## 1. System summary

Agent Governance is an interactive, transactional CLI (with programmatic package exports) that installs a closed, versioned governance bundle into coding-agent harnesses. Mutations happen only at explicit paths (`--target-root`, `--entry-file`, `--installation-root`, `--scope global`) and only after explicit confirmation; discovery is passive and never mutating. Core concerns: stateful resume, work-item classification, forward-only replacement, and deterministic SOSS (Source-of-Truth) module routing. The repository is itself a governance bundle (`bundle/GOVERNANCE.md`, schema_version 4 manifest) that the CLI installs into target roots.

## 2. Tech stack

| Layer | Choice |
|---|---|
| Runtime | Node.js `>=24`, ESM (`"type": "module"`) |
| Language | TypeScript 7.0.2, `@types/node` 24.19.2, `NodeNext` module/moduleResolution, strict (`noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`) |
| Build | `tsc -p tsconfig.build.json` → `dist/`; native C addon via `tools/build-native.mjs`, artifacts in `prebuilds/<target>/` |
| Dependencies | `@clack/prompts` 1.8.1 (prompts), `@toon-format/toon` 4.4.0 (TOON), `smol-toml` 1.9.1 (closed TOML) |
| Tests | `node --experimental-strip-types --test tests/installer/*.test.ts`; Python `unittest` suite under `tests/` |
| CI (`.github/workflows/ci.yml`) | `native-platform` (linux-arm64/x64, darwin-arm64/x64, node 24), `native-package`, `installer-package` (ubuntu/macos × node 24/26), `consistency-tests`, `release-metadata`, `docs-remote`, `release-validate`. Blocks on typecheck, test, build, `pack:check`, npm audit incl. signatures, `license:check`, `harnesses:check`, `release_manifest.py check`, `git diff --check`. |
| Publishing | npm pack with provenance + signature attestations (`npm audit signatures --json --include-attestations`), `tools/verify-pack.mjs` |

## 3. Entry points

| Entry | Path | Role |
|---|---|---|
| CLI bin | `src/cli.ts` → bin `agent-governance` → `dist/cli.js` | `runCli(argv)`: argv parsing, catalog load, command dispatch, JSON/text output, exit codes (`EXIT_CODES`: 0/2/4/5/6/130) |
| Public commands | `src/public-commands.ts` | `PUBLIC_COMMAND_HANDLERS`: `inspect`, `plan`, `install`, `verify`, `status`, `update`, `uninstall`, `rollback` (transactional), `init` (orchestration) |
| Command catalog | `src/command-catalog.ts` | `loadCommandCatalog()` → `PublicCommandDefinition[]` (id, path, description, capability, effect, interactive) |
| Package exports | `package.json` `exports` | `./replacement`, `./resume-checkpoint`, `./resume-toon`, `./work-items` (`dist/*.js` + `.d.ts`) |
| Native primitive | `native/agent_governance_fs.c` → `prebuilds/<target>/agent_governance_fs.node` | filesystem identity/capability primitives used by mutations |

All non-init commands require `--target-root`, `--entry-file`, `--scope global`, `--installation-root`; optional `--local-rules`, `--dry-run`, `--non-interactive`, `--json`, `-h/--help`.

## 4. Layered architecture

**Layer 1 — CLI / presentation:** `src/cli.ts`, `src/terminal/theme.ts`, `src/init/prompt.ts`. Raw argv → parsed `InstallerRequest`; structured JSON or `outcome: state (phase)` text; clack interactive prompts; branding rendering.

**Layer 2 — Command / public API:** `src/public-commands.ts`, `src/command-catalog.ts`. `PUBLIC_COMMAND_HANDLERS[commandId]({ transaction, init })`; each transactional command delegates to `InstallerTransaction`, `init` delegates to `runInit`.

**Layer 3 — Orchestration (init wizard):** `src/init/orchestrator.ts` + `src/init/*`. Four stages: `inspect` (discover harnesses via `src/init/harnesses.ts`, resolve latest release via `src/installer/latest.ts`, build rows incl. transaction `status()`/`localVersion()`), `plan` (target selection), `tools` (tool preparation, `src/init/tool-preparation/` incl. `gh.ts`), `setup`/`verify` (per-target plan → confirm → install/update → verify → `CURRENT`). Every stage is wrapped in `readOnlyStage` with a `SignalCoordinator`; `SIGINT`/`SIGTERM` → `INTERRUPTED`.

**Layer 4 — Transaction:** `src/transaction.ts`. `InstallerTransaction` exposes `inspect`/`status`/`localVersion`/`plan`/`verify`/`install`/`update`/`uninstall`/`rollback`. Phases (`src/contracts.ts:15`): inspect → plan → backup → stage → activate → verify → (rollback). Checkpoints via `SignalCoordinator`; fault-injection seams (`faultAfter`) for failure-path tests; receipt lifecycle `PREPARED` → `COMMITTED` / `ROLLED_BACK`.

**Layer 5 — Installer domain:** `src/installer/*`. `planner.ts` (`planInstallation`), `mutation.ts` (`atomicCreate`/`atomicWrite`/`atomicRemove`/`ensureDirectoryTree`), `release-staging.ts` (`prepareRelease`/`activateRelease`), `receipts.ts` (`Receipt`, `storeIdentity`), `recovery.ts` (`restore`), `snapshot.ts` (`digest`/`matchesSnapshot`/`optionalBytes`), `locking.ts` (`withInstallationLock`), `local-rules.ts`, `context.ts` (`resolveContext`/`bindingIdFor`/`Context`), `contracts.ts` (`TransactionCheckpoint`/`TransactionRequest`/`architecture` constant).

**Layer 6 — Primitives:** `src/filesystem.ts` (`captureIdentity`/`assertIdentity`), `src/native-filesystem.ts` + C addon (`probeNativeFilesystemCapability`/`secureCreateDirectory`), `src/managed-block.ts` (`installManagedBlock`/`removeManagedBlock`/`verifyManagedBlock`), `src/signals.ts` (`SignalCoordinator`/`SignalInterruption`), `src/errors.ts` (`InstallerFailure`/`InterruptedFailure`/`ConcurrentEntryChange`), `src/target.ts` (`inspectTarget`), `src/release.ts` (`verifyRelease`/`resolveLatestRelease`).

**Layer 7 — Catalogs & routing:** `src/routing-catalog.ts` (`RoutingCatalogs` from triggers/policy_tags/scopes/tools TOML), `src/ssot-manifest.ts`, `src/command-catalog.ts`, `src/discovery-catalog.ts`, `src/templates-catalog.ts`, `src/catalog-paths.ts`, `src/closed-toml.ts` (`exact`/`table`/`text`/`ID`/`idList` closed-TOML validation). Vocabularies live in `bundle/agent-governance/ssot/routing/` (`triggers.toml` = 49 triggers, `policy_tags.toml`, `scopes.toml`, `tools.toml`, `commands/commands.toml`, `discovery/`, `work-items/`). Manifest rule: `unknown = "block"`, `ambiguous = "block"`.

**Layer 8 — Contracts & fixtures:** `src/contracts.ts` (shared types), `src/contract-fixture.ts` (`governanceContract` fixture used by routing validation).

## 5. Key abstractions (defined in `src/contracts.ts` unless noted)

- `InstallerRequest` — `targetRoot`, `entryFile`, `scope: "global"`, `installationRoot`, `localRules?`, `dryRun`, `nonInteractive`, `releaseRoot`
- `InstallState` — `FRESH`, `CURRENT`, `OUTDATED`, `DOWNGRADE_BLOCKED`, `ABSENT`, `TAMPERED`, `RECOVERY_REQUIRED`
- `TerminalOutcome` — `SUCCESS`, `INVALID_INVOCATION`, `UNSAFE_STATE`, `VERIFICATION_ROLLED_BACK`, `ROLLBACK_FAILED`, `INTERRUPTED`
- `InstallPlan` — `architecture: "GLOBAL_EXPLICIT_PATH_MANAGED_BLOCK"`, `resources: PlannedResource[]` where each resource id ∈ {`release`, `current-metadata`, `entry-file`, `backup`, `receipt`, `local-rules`} with operation ∈ {`create`, `replace`, `remove`, `preserve`, `verify`}
- `InstallResult` — `outcome`, `state`, `phase`, `rollbackStatus`, `capabilities[]` (`FILESYSTEM_INSTALLED`, `BINDING_MATERIALIZED`, `DIGEST_VERIFIED`, `ROLLBACK_AVAILABLE`)
- `TransactionRequest` / `TransactionCheckpoint` — `src/installer/contracts.ts`
- `Context` — resolved target + release + binding context, `src/installer/context.ts`
- `Receipt` — id, bindingId, status, backupRoot, filesystem identities, entry/current/local-rules digests, `src/installer/receipts.ts`
- `RoutingCatalogs` — triggers/policyTags/scopes/requiredToolTriggers sets, `src/routing-catalog.ts`

## 6. Data flow — `install` command (canonical path)

1. `src/cli.ts` `runCli` parses argv (validates required options, rejects unsafe values), loads the command catalog, and routes to `PUBLIC_COMMAND_HANDLERS.install`.
2. Handler calls `transaction().install()` → `InstallerTransaction.mutate("install")` with an `InstallerRequest`.
3. `resolveContext` + state guard: only `FRESH`/`CURRENT`/`OUTDATED` are installable; `TAMPERED`/`RECOVERY_REQUIRED`/`DOWNGRADE_BLOCKED` are rejected outright (fail-closed, GOV-004).
4. `planInstallation` produces the `InstallPlan`; `--dry-run` short-circuits here with the plan and no mutation.
5. `withInstallationLock` serializes per installation root; `performMutation`:
   - captures filesystem identities (`captureIdentity`), ensures directory trees (`backups/`, `releases/`, `bindings/`);
   - backs up entry file + `current.json` into `backups/<bindingId>/<uuid>/`, then **readback-verifies** every backup;
   - prepares the release stage (`prepareRelease`), writes receipt `PREPARED` with digests;
   - checkpoints `backup` → `stage` (activate release, atomic-write `current.json` + local rules) → `activate` (atomic-write entry file as managed block) → `verify` (postimage snapshot comparison of entry / current / local-rules) → receipt `COMMITTED`.
6. Any post-backup failure → `restore()` from backup; outcome `VERIFICATION_ROLLED_BACK` if restore succeeded, `ROLLBACK_FAILED` if restore itself failed.
7. Output: structured JSON or `outcome: state (phase)`; exit code mapped from `TerminalOutcome`.

## 7. Routing model (this repo is its own governance bundle)

`bundle/agent-governance/manifest.toml` (schema_version 4) declares 12 modules (`invariants`, `enforcement`, `evidence`, `workflow`, `architecture`, `verification`, `delivery`, `security`, `tool_routing`, `templates`, `context`, `resume`) and 4 roles (`architecture`, `triage`, `quality_assurance`, `security_review`), each with `triggers` and `dependencies`; modules load topologically only when their trigger fires. `ssot/routing/triggers.toml` defines 49 named triggers (e.g. `analysis`, `architecture`, `external_effect`, `security_sensitive_change`, `tool_selection`, `resume_continuation`). Parsed at runtime by `src/routing-catalog.ts` / `src/ssot-manifest.ts` / `src/command-catalog.ts` with strict closed-TOML validation (`src/closed-toml.ts`); unknown/ambiguous references block (GOV-004).

## 8. Security posture

GOV-001 (authority), GOV-002 (instruction boundary), GOV-003 (external effect), GOV-004 (fail-closed), GOV-005 (secrets), GOV-006 (security pre-classification) are enforced via `bundle/GOVERNANCE.md` and module/runtime triggers. Concrete mechanisms: no silent harness mutations, no implicit paths, explicit `--scope global`, dry-run mode, backup+readback before mutation, atomic writes, postimage verification, rollback on verification failure, native-FS identity assertions (`assertIdentity`), installation lock, signature/provenance checks on publish, `local/user-rules.md` opt-in local rules.

## 9. Metrics (approximate, `wc -l`, excludes `node_modules`/`.git`)

- `src/`: 53 TypeScript files, ~5,534 LOC
- `tests/`: 72 test files (`.test.ts`, `.test.mjs`, `.py`), ~6,444 LOC for TS/mjs tests
- `tools/`: 11 scripts (TS/Python/mjs)
- `bundle/`: `GOVERNANCE.md` + `agent-governance/` manifest, 12 module docs, 4 role docs, `ssot/` catalogs, `templates/` registry

## 10. Naming conventions

- TypeScript files: `kebab-case` (`release-staging.ts`, `local-rules.ts`); directories lowercase (`init/`, `installer/`, `tool-preparation/`)
- Identifiers: `camelCase` functions/variables, `PascalCase` classes (`InstallerTransaction`, `SignalCoordinator`, `InstallerFailure`)
- Tests: `tests/installer/<unit>.test.ts`, `tests/node/<unit>.test.mjs`, `tests/test_*.py`; fixtures under `tests/fixtures/` and expected contracts under `tests/contracts/*.json`
- Bundle artifacts: German prose; tree `bundle/agent-governance/{modules,roles,ssot/{routing,commands,discovery,work-items},templates}/`
- Outputs: JSON `schemaVersion: 1`, deeply frozen (`Object.freeze`), deterministic key order

## 11. Locations of interest

- Entry: `src/cli.ts`
- Command handlers: `src/public-commands.ts`
- Transaction engine: `src/transaction.ts`
- Contract types: `src/contracts.ts`, `src/installer/contracts.ts`
- Installer domain: `src/installer/{planner,mutation,release-staging,receipts,recovery,snapshot,locking,local-rules,context,snapshot,version}.ts`
- Primitives: `src/{filesystem,native-filesystem,managed-block,signals,errors,target,release}.ts`
- Native addon: `native/agent_governance_fs.c`, `tools/build-native.mjs`
- Catalogs: `src/{routing-catalog,ssot-manifest,command-catalog,discovery-catalog,templates-catalog,catalog-paths,closed-toml}.ts`
- Init wizard: `src/init/orchestrator.ts` + `src/init/{harnesses,prompt,support,types,tool-preparation}.ts`
- Governance bundle: `bundle/GOVERNANCE.md`, `bundle/agent-governance/manifest.toml`, `bundle/agent-governance/ssot/routing/triggers.toml`
- Tests: `tests/installer/*.test.ts`, `tests/*.py`, `tests/e2e/*.sh`
- CI: `.github/workflows/ci.yml`, `npm-publish.yml`, `pages.yml`, `release-tag-verify.yml`, `socket-freshness.yml`, `npm-bootstrap-publish.yml`
- Planning output (this mapping): `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STRUCTURE.md`
