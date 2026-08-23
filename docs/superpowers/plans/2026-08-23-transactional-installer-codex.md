# Transactional Installer and Codex Adapter Implementation Plan

> Historische Evidenz - nicht normativ.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a deterministic transactional installer CLI whose only productive harness adapter is Codex.

**Architecture:** A zero-runtime-dependency TypeScript package separates untrusted input validation, filesystem safety, release integrity, Codex planning, transaction execution, and CLI rendering. `Installation.bootstrap.prompt.md` remains the normative contract; the package is its controlled distribution consumer.

**Tech Stack:** Node.js 24, TypeScript strict mode, Node test runner, npm lockfile, existing Python unittest and GitHub Actions gates.

## Global Constraints

- Exact base is `c4fa1b20dcea87a7b74882d7621da5828634766e`; `VERSION` remains the single SemVer source.
- Runtime dependencies are forbidden for this slice; development dependencies are exact-pinned and lockfile-verified.
- Codex is the only supported harness; every other harness fails closed before mutation.
- Every filesystem target must be absolute, inside the explicit allowed root, non-symlink, and identity-rechecked before activation.
- No test may use a real user home, credentials, network mutation, MCP auto-approval, merge, tag, release, or registry publication.
- Every behavioral step follows red test, minimal implementation, focused green test, and relevant regression suite.

---

### Task 1: Package and contract skeleton

**Files:**
- Create: `package.json`, `package-lock.json`, `tsconfig.json`
- Create: `src/contracts.ts`, `src/errors.ts`
- Create: `tests/installer/contracts.test.ts`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `InstallState`, `Phase`, `InstallerRequest`, `InstallPlan`, `InstallResult`, `InstallerFailure`, and stable exit-code mapping.

- [ ] Write a failing test that imports the closed state/phase sets and validates stable exit-code mapping.
- [ ] Run `npm test -- --test-name-pattern='contract'`; expect module-not-found failure.
- [ ] Add exact-pinned TypeScript tooling, strict ESM build settings, public CLI/bin metadata, and closed typed contracts.
- [ ] Run `npm ci`, `npm run typecheck`, and the focused test; expect PASS.
- [ ] Run `npm audit --audit-level=high`; record dependency and advisory evidence.
- [ ] Commit as `chore(installer): add typed package contract`.

### Task 2: Filesystem safety and release integrity

**Files:**
- Create: `src/filesystem.ts`, `src/release.ts`
- Create: `tests/installer/filesystem.test.ts`, `tests/installer/release.test.ts`
- Create: `tests/fixtures/installer/release.ts`

**Interfaces:**
- Consumes: `InstallerFailure`, `Phase`.
- Produces: `validateAllowedPath(path, allowedRoot, expectation)`, `captureIdentity(path)`, `assertIdentity(path, identity)`, and `verifyRelease(releaseRoot)`.

- [ ] Add failing tests for relative/absolute traversal, root escape, source/target/intermediate symlinks, FIFO/unexpected types, missing required files, invalid manifest paths, manipulated files, and digest mismatch.
- [ ] Run focused tests; expect failures from missing implementations.
- [ ] Implement component-by-component `lstat` validation, realpath containment, regular-file reads with size limits, parent identity capture, manifest path validation, and deterministic release inventory verification.
- [ ] Run focused tests, typecheck, and existing Python catalog/bundle tests; expect PASS.
- [ ] Commit as `feat(installer): validate filesystem and release boundaries`.

### Task 3: Codex inspection, classification, and deterministic planning

**Files:**
- Create: `src/codex.ts`, `src/planner.ts`, `src/hooks.ts`
- Create: `tests/installer/codex.test.ts`, `tests/installer/planner.test.ts`, `tests/installer/hooks.test.ts`
- Create: `tests/fixtures/installer/homes.ts`

**Interfaces:**
- Consumes: filesystem/release validators and typed contracts.
- Produces: `inspectCodex(request)`, `classifyCodex(inventory)`, `planCodex(request, inventory)`, and lossless governance-hook merge/verification.

- [ ] Add failing fixtures/tests for FRESH, CURRENT, LEGACY, UNKNOWN, conflicting markers/roots, missing/corrupt manifest, unsupported harnesses, override instructions, inline hooks, duplicate hooks, known legacy imports, personal rules, non-parseable hook JSON, unrelated hook preservation, and stable plan ordering.
- [ ] Run focused tests; expect missing-module failures.
- [ ] Implement exact Codex home/config/instruction discovery from the official contract, closed legacy recognition, manifest-derived local-rules destination, and a planned single-tool PreToolUse binding.
- [ ] Explicitly return `mcpMutation: false` and `approvalExpansion: false`; never edit `config.toml` in this version.
- [ ] Run focused tests and typecheck; expect PASS.
- [ ] Commit as `feat(codex): add fail-closed inspection and planning`.

### Task 4: Backup, staging, activation, verification, and rollback state machine

**Files:**
- Create: `src/transaction.ts`, `src/backup.ts`, `src/staging.ts`, `src/receipt.ts`
- Create: `tests/installer/transaction.test.ts`, `tests/installer/rollback.test.ts`, `tests/installer/idempotency.test.ts`

**Interfaces:**
- Consumes: `InstallPlan`, filesystem identity guards, Codex adapter.
- Produces: `InstallerTransaction.inspect()`, `.plan()`, `.install()`, `.verify()`, `.rollback()`, `.status()`.

- [ ] Add failing tests for backup-before-write, byte/mode readback, backup failure with zero mutation, staging side-effect isolation, pre-activation identity change, atomic rename, and faults after inspect/backup/stage/binding/activation/readback/runtime verification.
- [ ] Assert every post-mutation failure restores prior bytes or explicit absence, emits phase/resource/rollback status, leaves no active orphan, and makes repeated rollback safe.
- [ ] Add failing idempotency tests for second install, no duplicate import/hook/rules, no unnecessary backup, and deterministic structured output.
- [ ] Implement the explicit state machine and smallest rollback journal needed to pass each test.
- [ ] Add best-effort signal registration that enters rollback only after verified backup and test injectable signal handling.
- [ ] Run transaction tests, all Node tests, typecheck, and existing Python bootstrap tests; expect PASS.
- [ ] Commit as `feat(installer): add transactional activation and rollback`.

#### Completion amendment: catchable process interruption

- [ ] Add RED tests for listener lifecycle, pre-mutation `SIGINT`/`SIGTERM`, interruption between
  activation renames, interruption before verification completion, repeated signals, signal during
  rollback, rollback failure, persistent `PREPARED` recovery, 130/143 exit mapping, and subsequent
  idempotent recovery.
- [ ] Implement a first-signal latch whose handlers never mutate the filesystem, cooperative
  checkpoints around atomic operations, and exactly one rollback path.
- [ ] Write and read back a schema-2 `PREPARED` receipt before activation; transition it to
  `COMMITTED` or `ROLLED_BACK` without weakening path and backup validation.
- [ ] Remove listeners in `finally`, document the `SIGKILL`/runtime-crash/power-loss boundary, and
  rerun transaction, CLI, package, repository, review, and CI gates on the resulting exact head.

### Task 5: CLI and isolated integration tests

**Files:**
- Create: `src/cli.ts`, `src/render.ts`, `tests/installer/cli.test.ts`, `tests/installer/integration.test.ts`
- Modify: `package.json`

**Interfaces:**
- Consumes: `InstallerTransaction` and typed result/error contracts.
- Produces: `agent-governance` commands `inspect`, `plan`, `install`, `verify`, `rollback`, `status` with stable JSON/human output and documented exit codes.

- [ ] Add failing subprocess tests for every command, `--dry-run`, `--json`, required explicit roots, harness auto-detection ambiguity, unsupported harness, invalid arguments, spaces in paths, and absence of secrets/private fingerprints in output.
- [ ] Implement a non-interactive argument parser with closed options and no shell interpolation.
- [ ] Build and run the CLI against isolated temp homes; assert dry-run has no filesystem changes and install/verify/rollback behave as planned.
- [ ] Run `npm test`, `npm run typecheck`, `npm run build`, and `npm pack --dry-run --json`; expect PASS and only intended package files.
- [ ] Commit as `feat(installer): expose noninteractive transactional CLI`.

### Task 6: Fresh-session and platform CI gates

**Files:**
- Create: `tests/e2e/run_installer_fixture.sh`, `tests/test_installer_distribution.py`
- Modify: `.github/workflows/ci.yml`, `tests/test_ci_workflow.py`, `tests/test_e2e_contract.py`

**Interfaces:**
- Consumes: built package and existing clean-Linux Codex harness.
- Produces: Linux/macOS isolated installer fixture matrix and a Codex-version-bound fresh-session contract.

- [ ] Add failing Python contract tests requiring Node 24, npm cache discipline, Linux/macOS fixture jobs, package/audit gates, no real home, and existing credential boundaries.
- [ ] Add the isolated shell runner and first verify it fails before build/install wiring exists.
- [ ] Extend CI minimally so package gates and fixture integration run on Ubuntu and macOS; retain existing Python and release jobs.
- [ ] Bind credentialed Codex E2E claims to the exact existing pinned CLI version and Linux runner; do not claim a local macOS Codex result.
- [ ] Run Python CI-contract tests and all local fixture gates; expect PASS.
- [ ] Commit as `ci(installer): add package and platform transaction gates`.

### Task 7: Documentation, provenance, and version 0.6.0

**Files:**
- Create: `docs/installer-architecture.md`, `docs/dependency-evidence.md`
- Modify: `README.md`, `INSTALL.md`, `Installation.bootstrap.prompt.md`, `CHANGELOG.md`, `VERSION`, `package.json`, `package-lock.json`, `tests/test_documentation.py`, `tests/test_release_check.py`, `tests/test_source_consolidation.py`

**Interfaces:**
- Produces: one consistent version contract, supported/unsupported matrix, migration/recovery instructions, dependency rejection evidence, and package usage without publication claims.

- [ ] Add failing documentation tests for CLI commands, Codex-only support, exact verified platform/version language, no auto-approval, prompt authority, rollback limits, and synchronized version metadata.
- [ ] Update docs and version sources to `0.6.0`; keep `VERSION` authoritative and make package validation derive/check against it.
- [ ] Document exact candidate package versions/integrity/license/source inspected, API and write behavior, transitives, advisory outcome, stability risk, and rejection rationale.
- [ ] Run documentation/release tests, `python3 tools/release_check.py tree`, package gates, and `git diff --check`; expect PASS.
- [ ] Commit as `docs(installer): document guarantees and limitations`, then `chore(release): prepare version 0.6.0` if the diff remains independently coherent.

### Task 8: Exact-head verification and independent reviews

**Files:**
- Modify only files required by valid findings.

**Interfaces:**
- Produces: exact-head local evidence, independent QA finding ledger, and independent SEC finding ledger.

- [ ] Run full Python tests, full Node tests, typecheck, format/lint, build, package content inspection, fixture integration, audit, release check, diff check, and a diff secret scan.
- [ ] Review the complete diff against `origin/main` for scope and generated artifacts.
- [ ] Load the manifest-selected QA and SEC roles; run separate fresh read-only review contexts against the same exact head.
- [ ] Classify every finding under DEL-009, fix valid blocking/significant findings with a red regression test, and rerun affected gates/reviews on the new head.
- [ ] Commit any fixes coherently; repeat until no blocking-valid or unclassified findings remain.

### Task 9: Push, pull request, and terminal CI

**Files:**
- Create a temporary PR body outside the repository only; do not commit secrets or raw logs.

**Interfaces:**
- Produces: remote branch, GitHub PR, head-SHA-equal checkpoint, and terminal required-check evidence.

- [ ] Confirm clean/explained worktree, exact base ancestry, coherent commits, and no tag/release/publish mutation.
- [ ] Push without force and verify local/remote head equality.
- [ ] Create the PR with `Relates to #15`, full architecture/security/test/version/limit evidence, and no auto-merge.
- [ ] Read PR head and required checks; wait to terminal state.
- [ ] For own CI failures, use systematic-debugging: reproduce, identify earliest cause, add red regression, minimally fix, rerun affected gates, commit, push, and re-observe.
- [ ] Report PASS only when every required check is terminal green; otherwise report the exact external blocker.

## Plan self-review

All design requirements map to a task. Interfaces and names are consistent across tasks, every
behavioral slice starts with an explicit failing test, and no step contains an implementation
placeholder. The plan preserves existing Python gates while adding the package rather than
rewriting unrelated governance internals.
