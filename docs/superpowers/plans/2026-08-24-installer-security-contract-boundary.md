# Installer Security Contract Boundary Implementation Plan

> Historische Evidenz - nicht normativ. Maßgeblich sind der getestete Installervertrag und das Bundle.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve every implementable installer filesystem control while narrowly excluding only malicious same-UID final-component swaps that the supported unprivileged kernels cannot atomically compare-and-mutate.

**Architecture:** Closed receipts persist the directory and container identities needed by later recovery, and rollback validates those identities before touching Entry, Current, Local Rules, or a newly activated Release. The existing Node-API primitive retains dirfd binding and atomic no-clobber; documentation and executable contract tests state that its basename syscall is not an inode-CAS primitive.

**Tech Stack:** TypeScript, Node.js 24+, Node-API C, node:test, Python unittest, Darwin `renameatx_np`, Linux `renameat2`, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-24-global-explicit-path-installer-design.md`

## Global Constraints

- No privileged broker, daemon, root helper, setuid binary, service, FUSE layer, or unsafe pathname fallback.
- The exception covers only a malicious same-UID co-writer with write access to the same namespace swapping a final component inside the kernel-unavoidable observation-to-syscall window.
- Observable parent/root replacement, symlinks, traversal, collisions, stale state, receipt/backup manipulation, and unsupported native capability remain fail-closed.
- All behavior changes use witnessed RED/GREEN tests; every new Exact Head receives full gates plus separate read-only QA and Security reviews.

---

### Task 1: Persist recovery identities

**Files:** Modify `src/transaction.ts`; modify `tests/installer/transaction.test.ts`.

**Interfaces:** Receipt schema stores decimal device/inode plus numeric mode for Entry Parent, Binding Root, Local-Rules Parent when applicable, and the exact newly activated Release directory when cleanup authority is needed.

- [ ] Keep and run `recovery never trusts a replacement parent containing copied detach evidence`; confirm it fails because recovery accepts the replacement parent.
- [ ] Add focused RED cases replacing the Binding Root, Local-Rules Parent, and newly activated Release container before rollback sinks.
- [ ] Add closed receipt fields and strict scalar/path consistency validation; derive runtime `PathIdentity` values only from those fields.
- [ ] Validate every persisted identity before the corresponding restore or cleanup and run the focused recovery suite GREEN.

### Task 2: Recover exclusive-create I/O failures

**Files:** Modify `native/agent_governance_fs.c`; modify `tests/installer/native-filesystem.test.ts` and the native CI test harness if injection requires Linux interposition.

**Interfaces:** `secureCreateNoReplace` removes only the exclusively created basename after a failed write/fsync, via its already bound parent dirfd, and preserves the original I/O error; the documented final-component limitation still applies to an actively malicious same-UID swap.

- [ ] Add a deterministic RED native test that injects write failure and proves the created partial target prevents retry.
- [ ] Implement minimal dirfd-relative failure cleanup with type/identity revalidation and no absolute/pathname fallback.
- [ ] Run the failure/retry, collision, parent-swap, Native-load, and normal restore tests GREEN.

### Task 3: Materialize the narrow security contract

**Files:** Modify `docs/installer-threat-model.md`, `docs/installer-architecture.md`, `README.md`, `INSTALL.md`, `CHANGELOG.md`, `docs/superpowers/specs/2026-08-24-global-explicit-path-installer-design.md`, and `tests/test_documentation.py`; reclassify the existing final-component characterization in `tests/installer/native-filesystem.test.ts` without deleting it.

**Interfaces:** `docs/installer-threat-model.md` is the repository security-contract source for the installer; public summaries link to it and never claim universal race freedom or inode-CAS semantics.

- [ ] Add RED documentation assertions for the exact in-scope/out-of-atomic-guarantee boundary, no privileged component, retained no-clobber/native packaging, and forbidden absolute claims.
- [ ] Convert the final-component reproducer into an explicit non-gating platform-characterization test that positively demonstrates and labels the kernel limitation.
- [ ] Update every stronger README/architecture/spec statement and document the per-sink Finding-C analysis.
- [ ] Run documentation, Native, transaction, packaging, and release-contract tests GREEN.

### Task 4: Exact-head delivery

**Files:** No additional production files unless a validated finding receives its own RED test.

- [ ] Run Node standard, isolated temp, Node 24.19, Python, typecheck, lint, build, actionlint, manifest/tree, audit, license, pack, npm/npx/pnpm consumers, installer fixture, neutral harness, binary inspection, and diff checks.
- [ ] Review the full diff, create coherent SSH-signed commit(s), verify signatures and clean worktree, and fast-forward push the existing branch.
- [ ] Obtain separate read-only QA and Security verdicts on the new Exact Head under the updated contract; require `BLOCKING_VALID_FINDINGS=0`.
- [ ] Observe all CI/native jobs, Greptile, annotations, and review threads terminal before applying the repository landing workflow.

## Plan self-review

The plan covers Findings A, B, and each Finding-C resource class without treating the approved final-component exception as a general Same-UID exclusion. It adds no privilege boundary or runtime dependency, preserves the two existing reproductions, and keeps release work behind fresh exact-head evidence.
