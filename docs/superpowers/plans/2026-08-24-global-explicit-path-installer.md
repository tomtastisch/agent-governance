# Global Explicit-Path Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver and release a deterministic transactional global explicit-path governance installer.

**Architecture:** A zero-runtime-dependency TypeScript CLI validates an explicit target and a closed release bundle, stages a versioned installation, and atomically maintains one Markdown managed block. Closed receipts and verified byte backups provide rollback without any harness-specific runtime knowledge.

**Tech Stack:** Node.js 24+, TypeScript 5.9, node:test, Python unittest release checks, GitHub Actions, npm public registry.

**Spec:** `docs/superpowers/specs/2026-08-24-global-explicit-path-installer-design.md`

## Global Constraints

- Architecture identifier: `GLOBAL_EXPLICIT_PATH_MANAGED_BLOCK`.
- Package: `@tomtastisch/agent-governance`; first candidate `1.0.0-rc.1` under `next`.
- No runtime dependencies, harness IDs, adapters, hooks, MCP mutation, approvals, implicit target, or cwd fallback.
- Production symlink and containment boundaries remain fail-closed on macOS and Linux.
- Every behavior change follows a witnessed RED/GREEN cycle and every release claim uses fresh exact-head evidence.

---

### Task 1: Canonical test workspace

**Files:** Modify `tests/installer/filesystem.test.ts`; create `tests/fixtures/installer/workspace.ts`; migrate `tests/installer/*.test.ts`.

**Interfaces:** Produces `createTestRoot(prefix: string): Promise<string>` returning a canonical symlink-free temporary root.

- [ ] Add a test asserting the fixture root equals its own `realpath`; run it under the default macOS environment and observe failure caused by `/var` versus `/private/var`.
- [ ] Implement the helper by resolving `tmpdir()` before `mkdtemp`, migrate fixtures, and run standard plus `TMPDIR=/private/tmp` Node suites.
- [ ] Confirm the production `validateAllowedPath` implementation is unchanged.

### Task 2: Closed generic contracts and argument parser

**Files:** Modify `src/contracts.ts`, `src/errors.ts`, `src/cli.ts`; modify `tests/installer/contracts.test.ts`, `tests/installer/cli.test.ts`.

**Interfaces:** `InstallerRequest` contains `targetRoot`, `entryFile`, `scope`, `installationRoot`, optional `localRules`, `dryRun`, and `nonInteractive`; JSON schemas expose generic resources and capability states.

- [ ] Add RED tables for all eight commands, required and optional flags, duplicate/unknown options, absolute/canonical roots, relative Markdown entry, no cwd fallback, and stable exit codes.
- [ ] Replace Codex routing with generic dispatch and deterministic human/JSON rendering; run focused CLI and contract tests GREEN.

### Task 3: Target and managed-block model

**Files:** Create `src/managed-block.ts`, `src/target.ts`; create `tests/installer/managed-block.test.ts`, `tests/installer/target.test.ts`; remove `src/codex.ts`, `src/hooks.ts`, and their tests after neutral extraction.

**Interfaces:** `inspectManagedEntry(bytes)` returns closed state and line-ending metadata; `renderManagedBlock(release, installationRoot, eol)` returns deterministic bytes; target inspection binds parent and entry identities.

- [ ] Add RED cases for new/empty/user-owned LF/CRLF/UTF-8 files, surrounding bytes, duplicate/incomplete/foreign markers, tampering, update, uninstall, and reinstall.
- [ ] Add RED path cases for relative root, traversal, root/parent/entry symlinks, missing root, wrong type, identity race, outside entry, and non-Markdown extension.
- [ ] Implement the smallest generic parser/renderer and target validator; run focused suites GREEN.

### Task 4: Closed release staging and active metadata

**Files:** Modify `src/release.ts`, `src/filesystem.ts`, `tools/release_manifest.py`; create or modify release/filesystem tests.

**Interfaces:** `verifyRelease(root)` returns version and bootstrap/manifest/bundle digests plus inventory; `stageRelease` creates `releases/<version>/bundle`; `current.json` is the atomic active pointer.

- [ ] Add RED cases for absent/extra normative files, digest/manifest manipulation, traversal, links, types, size, local rules, update, and explicit downgrade policy.
- [ ] Implement closed inventory enumeration, manifest reference validation, bounded reads, staging readback, and atomic metadata activation; run focused suites GREEN.

### Task 5: Generic transaction lifecycle

**Files:** Rewrite `src/planner.ts`, `src/transaction.ts`; retain neutral `src/signals.ts`; rewrite planner/transaction/signal tests.

**Interfaces:** Commands implement inspect, plan, install, verify, status, update, uninstall, and rollback over the versioned installation, current metadata, entry file, backups, and closed receipt.

- [ ] Add RED tests for dry-run, backup/readback, staging, every injected phase fault, signals before/during mutation and rollback, repeated signals, rollback failure/recovery, root identity races, and idempotence.
- [ ] Implement verified pre-mutation backups, same-filesystem staging, atomic renames, serialized rollback, recovery, and exact postcondition verification; run focused and complete Node suites GREEN.

### Task 6: Package and exclusion gates

**Files:** Modify `package.json`, `package-lock.json`, `tsconfig*.json`, `.github/workflows/ci.yml`, package/release tests and E2E fixtures.

**Interfaces:** Published tarball contains only CLI runtime, governance bundle, license/readme/version, and closed inventory.

- [ ] Add RED checks rejecting harness IDs/paths, adapters, integrations, hooks, MCP, approvals, runtime dependencies, unexpected tar entries, and package metadata drift.
- [ ] Set scoped RC metadata, remove excluded runtime artifacts from the package, add build/pack/local-tarball/npx/pnpm-dlx/Node-matrix/macOS/Linux/audit/license/secret gates, and run them GREEN.

### Task 7: Documentation and recipes

**Files:** Rewrite `README.md`, `INSTALL.md`, `docs/installer-architecture.md`, `docs/dependency-evidence.md`, `CHANGELOG.md`; add threat model, JSON schemas, migration and release documentation.

**Interfaces:** Documentation describes only implemented behavior and marks each harness capability from real evidence.

- [ ] Define executable documentation assertions for CLI, exits, schemas, managed block, recovery, local rules, limitations, v0.5.0 migration, removed Codex draft, adapter audit, and RC/stable flow.
- [ ] Verify official global entry documentation before adding recipes; keep unverified harnesses explicitly unverified.

### Task 8: Exact-head local verification and independent reviews

**Files:** No production changes unless a validated finding receives a RED regression test.

- [ ] Run Python, Node standard and alternate-temp suites, typecheck, lint/format, build, E2E, release checks, pack allowlist, tarball install, npx, pnpm dlx, audit, license, secret and runtime-exclusion scans.
- [ ] Dispatch fresh read-only QA and Security roles on the same exact head, classify all findings, fix valid findings test-first, and repeat all affected gates and both reviews.

### Task 9: PR completion and RC release

**Files:** Versioned source and release metadata only.

- [ ] Create coherent signed commits without rewriting the twelve existing commits, push normally, create the specified PR, and observe exact-head CI/reviews through the repository PR-completion watcher.
- [ ] At verified readiness, produce the canonical landing plan and request the required fresh per-PR exact-head confirmation.
- [ ] After merge authorization, verify merge commit, create and verify signed `v1.0.0-rc.1`, publish GitHub prerelease and npm `next` with provenance, then perform registry metadata/digest/dist-tag/provenance and fresh-install readback.

### Task 10: Public RC matrix, stable promotion, and migration

**Files:** Capability evidence, changelog, release metadata, and follow-up fixes only through new RC/PR cycles.

- [ ] Test each locally available harness in a fresh session with exact version, official entry, dry-run/install/verify/update/uninstall/rollback/reinstall, synthetic local rule, legacy absence, and tamper fail-closed evidence.
- [ ] If any public contract changes, issue the next RC through a new PR; otherwise prepare and land the `1.0.0` promotion with fresh gates and reviews.
- [ ] Publish signed stable GitHub/npm releases with provenance and readback, migrate active local governance only from public stable with verified backups, test used harness sessions plus `codex-work` and `codex-private`, and close Issue #15 only after all evidence is complete.

## Plan self-review

The tasks cover every specification boundary, use one public interface vocabulary throughout, and contain no deferred implementation placeholders. Release, landing, publication, migration, and issue closure remain gated by their exact external evidence and required confirmations.
