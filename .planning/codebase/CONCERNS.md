---
last_mapped_commit: 645068bfcb201fbd261dc8e8b37d57cd2eb25a70
last_mapped_at: 2026-10-29
---
# Codebase Concerns Map

**Repository:** `https://github.com/tomtastisch/agent-governance` (`@tomtastisch/agent-governance`)
**Package version:** `1.9.4` (`VERSION`: `1.9.4`)
**Branch / state:** `main`, clean working tree, no local modifications
**Analysis date:** 2026-10-29
**Target:** `/Users/tomtastisch/Projects/github/agent-governance/.planning/codebase/CONCERNS.md`
**Workspace note:** `node_modules/` is absent in this checkout, so `npm run build`, `npm run lint`, `npm test`, and `npm run typecheck` were **not executed** in this session. All claims below are drawn from static reads of source, lockfile, docs, tests, CI scripts, and `git log`.

---

## 1. Executive summary / risk register

| Area | Severity | Primary locations | One-line assessment |
|---|---|---|---|
| Native addon & platform coverage | High | `native/agent_governance_fs.c`, `docs/installer-threat-model.md` | Node-API C addon ships prebuilds only for darwin/linux arm64+x64; all other platforms are read-only inspect, no mutation; documented residual same-UID final-component risk without atomic inode-CAS |
| TypeScript 7 toolchain migration | Medium | `package.json`, `tsconfig.json`, `tools/build-native.mjs`, `docs/dependency-evidence.md` | TS 7.0.2 dropped the classic JS compiler API; build relies on `@typescript/typescript6@6.0.2` (resolves `@typescript/old`→`typescript@6.0.3`) which can shadow the `tsc` bin name |
| Harness discovery incompatibility | Medium | `docs/dependency-evidence.md`, `tools/project-harness-discovery.ts`, `src/init/harness-discovery.generated.ts` | `@agntn/harnesses@0.4.2` requires Node >=26 and pins SDK 1.30.1 / TOML 1.8.0 — incompatible with the Node >=24 contract; upstream PR #97 still unpublished; custom data projection used instead |
| Test coverage scope | Medium | `package.json` `"test"` script | `npm test` runs only `tests/installer/*.test.ts` after `build:native`; contracts/e2e/node/python tests are not covered by the default test command |
| Static-analysis surface | Low | `package.json` `"lint"` script | Lint = `tsc --noEmit` + `git diff --check`; no ESLint/biome, no full-tree whitespace enforcement |
| TTY-gated onboarding | Low | `src/init/orchestrator.ts`, `src/cli.ts` | `runInit`/`runInitTools` return `INVALID_INVOCATION`/`NON_TTY` when `!isTTY`; CI/automation-driven init is constrained |
| Security design | Low–Medium | `docs/installer-threat-model.md`, `GOVERNANCE.md` (GOV-004/GOV-006) | Fail-closed root resolution, local-rule UTF-8/control-char contract, secret tarball gate, SRI+provenance in CI; out-of-scope: malicious same-UID final-component co-writer |
| TODO/FIXME markers | None | `src/**` | Zero actionable `TODO`/`FIXME`/`HACK`/`XXX`/`OPTIMIZE`/`WORKAROUND` markers in source (only a false positive on the word `review` in a type union) |

---

## 2. Technical debt

- **Minimal/custom TOML parser.** `src/closed-toml.ts` (117 lines) is a hand-rolled closed-subset TOML parser used for all manifest/catalog loading (`src/ssot-manifest.ts`, `src/routing-catalog.ts`). It supports integers, quoted strings with escapes, string arrays, and multiline strings; it rejects duplicate fields/tables and non-subset syntax fail-closed. Risk: divergence from full TOML for hand-edited manifests or future catalog extensions, and a custom parser is an implicit maintenance surface with no upstream security patching.
- **Documentation marked non-normative/historical.** `docs/adapter-audit.md` and `docs/dependency-evidence.md` carry "Historische Evidenz - nicht normativ" headers; several `docs/superpowers/specs/` and `docs/superpowers/plans/` files (2026-08 to 2026-10) describe implemented features. There is no explicit mechanism keeping these in sync with code, so stale-design drift is a latent debt.
- **Mixed test tooling.** Test tree contains both Node (`node:test` via `--experimental-strip-types`, `tests/installer/*.test.ts`, `tests/node/`, `tests/e2e/`) and Python (`tests/test_*.py`, `tests/contracts/`, `tests/support/`). No single command runs the full suite; `npm test` covers only installer tests.
- **Native test-injection macros in source.** `native/agent_governance_fs.c` contains `#ifdef AGENT_GOVERNANCE_TEST_FAIL_AFTER_CREATE`, `AGENT_GOVERNANCE_TEST_FAIL_CREATE_CLOSE`, `AGENT_GOVERNANCE_TEST_MUTATE_CREATE_CLOSE`, `AGENT_GOVERNANCE_TEST_SWAP_REPLACE_TEMP` (lines 180-256). These are test-only fault-injection paths living in the native source shipped with the package.
- **No `.planning/` artifacts besides empty `codebase/`.** `.planning/codebase/` exists but is empty; no `PROJECT.md`, `STATE.md`, `ROADMAP.md`, or `config.json`. This CONCERNS.md is the first planning artifact.

---

## 3. Known issues & resolved issue history (from `git log`)

These are fixed, but they indicate historical fragility clusters worth watching for regressions:

- **Release signing (1.9.4):** `74ee242 fix(release): aktiven SSH-Signierer für 1.9.4 ersetzen`; old key retained only for historical tags up to 1.9.3 (`645068b Merge pull request #168`).
- **Init/signal handling:** `7fde09a` feature `issue-154-tool-preparation`; `ee34ba9`/`fbc0da1`/`b0ad4c9`/`a8b32e4` fixes around init error results, early signal handling, completed/external effects on abort, real signals in read-only setup steps, SIGTERM results and release checks.
- **Cross-version / package inventory:** `fix/issue-89-cross-version-update`, `fix/issue-92/derived-package-inventory`, `fix/issue-93/same-sha-evidence-reuse`.
- **Metadata retry:** `fix/issue-103/immediate-metadata-retry`.
- **npm publish:** `fix/issue-115/npm-publish-verification`, `fix/release/npm-first-publish-bootstrap`, `fix/release/npm12-pack-schema`, `fix/release/npm12-readback`, `fix/release/npm-publish-expect-driver`, `fix/release/immutable-release-commit-binding`, `fix/release/annotated-tag-checkout`, `fix/release/ssh-signature-trust`.

---

## 4. Bugs & fragile areas

- **Native addon final-component race (documented residual risk).** `docs/installer-threat-model.md` lines 40-52: the only out-of-atomic-guarantee class is an actively malicious same-UID final-component co-writer that swaps the final name component between the last identity observation and the kernel syscall. Linux `renameat2(RENAME_NOREPLACE)` and Darwin `renameatx_np(RENAME_EXCL)` bind parent directories; no atomic inode compare-and-mutate exists. `native/agent_governance_fs.c` implements the validation loop (openat O_EXCL|O_NOFOLLOW, fstat identity snapshot, fsync, fstatat revalidation, renameat replace) in `secureWriteFile` (lines 241-261) and `secureCreateNoReplace` (lines 145-239).
- **Crash atomicity limits.** `docs/installer-threat-model.md` lines 122-130: `SIGKILL`, power loss, and hardware failure are not cooperatively catchable; the `PREPARED` receipt makes these states visible and forces recovery but does not prove full crash atomicity. A privileged process attacking open handles or the process itself is out of contract.
- **TTY-dependent init.** `src/init/orchestrator.ts` lines 174-183 and 84-98: `runInit` and `runInitTools` short-circuit with `INVALID_INVOCATION`/`NON_TTY` when `process.stdin.isTTY` is false; guidance points users to explicit transaction commands with `--non-interactive`. Automation-driven onboarding is therefore a constrained path.
- **Signal/interruption state machine.** `src/init/orchestrator.ts` uses `SignalCoordinator` (`src/signals.ts`) with `InterruptedFailure`, rollback statuses, resource IDs, and external effects across inspect/plan/verify phases (`readOnlyStage` lines 53-69). Signal is treated as authoritative even after subsequent read errors (line 60 comment). Complex failure/rollback interactions are a regression surface.
- **Atomic mutation helpers.** `src/installer/mutation.ts` (`atomicWrite`, `atomicRemove`, `atomicCreate`) compare preimage bytes before mutating, throw `ConcurrentEntryChange` on bound-snapshot write failures, and readback-verify after write/create. Fragility point: any caller that skips the snapshot/`requiredSnapshot` step loses the identity guard.
- **Closed-catalog routing.** `src/routing-catalog.ts` and `src/ssot-manifest.ts` enforce exact field sets, schema_version 1, non-empty catalogs, and unique IDs/paths; unknown references fail. Strictness is a feature but makes adding new trigger/policy/scope entries a coordinated change across catalog TOML, SSOT manifest, and code.
- **TS extension imports.** `tsconfig.json` sets `allowImportingTsExtensions: true` and `rewriteRelativeImportExtensions: true`; source imports `./contracts.ts` etc. with `.ts` extensions (NodeNext). Works under `tsc`/`node --experimental-strip-types` but is non-standard for plain Node consumption of built output.

---

## 5. Security

- **Fail-closed governance.** Bundle root resolution per GOV-004 (`GOVERNANCE.md` lines 9-34): exactly one validated root, manifest `agent-governance/manifest.toml` required, catalog paths must be non-symlink regular files within the manifest directory, no traversal/root escape, no relative bundle access.
- **Local user rules.** `local/user-rules.md` (German, global independent-agent-review rule) is resolved relative to the manifest directory, not logged or published; absent file leaves the bundle functional.
- **Dependency supply chain.** `docs/dependency-evidence.md`: 3 direct runtime deps exactly pinned with integrity values in `package-lock.json` (`@clack/prompts@1.8.1`, `@toon-format/toon@4.4.0`, `smol-toml@1.9.1`); 34 lock records; `npm audit --audit-level=high` reported null vulnerabilities at introduction; CI verifies registry signatures and provenance attestations (`npm audit signatures --json --include-attestations`).
- **Remediated advisories.** `smol-toml@1.9.0` → `1.9.1` fixed GHSA-r4xh-jqrq-34v2; a separate vulnerable TOML copy plus SDK affected by GHSA-6qxp-vccf-f47h were removed entirely from the runtime tree (1.9.2/1.9.3).
- **Excluded packages.** `terminal-image@5.0.1`, `chalk`, `boxen`, `log-update` deliberately not declared (no direct runtime import; decorator/license/audit surface not justified).
- **Native addon trust boundary.** `native/agent_governance_fs.c` uses only OS + stable Node-API symbols; prebuilds for darwin/linux arm64/x64 only; other platforms cannot mutate (read-only inspect).
- **Threat model out-of-scope items.** Malicious same-UID final-component co-writer, privileged process, SIGKILL/power loss/hardware failure, and markdown-binding influence on instruction context (not universal technical enforcement).
- **Secret handling.** Secret patterns checked in the tarball gate; local rules source must be a canonical Markdown file checked for UTF-8 and C0/DEL control characters (only TAB/LF/CR allowed).

No hard-coded secrets, tokens, or keys were found in the scanned source tree.

---

## 6. Performance

- No observed hot-spots in source; performance work exists historically: `perf/issue-94-governance-routing` branch and `docs/issue-94-routing-evidence.md`; `tests/test_routing_performance.py` exists.
- Native addon does fsync per write (`secureWriteFile` line 204) and identity revalidation (`fstatat` on both temporary and target before rename) — correct for durability but costlier than unsynchronized writes; acceptable for an installer/transactional tool, not for high-frequency I/O.
- Routing catalogs are parsed at CLI startup (`src/cli.ts` line 68 `loadCommandCatalog()`); no caching concern identified for an interactive CLI.

---

## 7. Build / toolchain / maintenance

- **Build:** `npm run build` = `harnesses:check` → `build:native` (`tools/build-native.mjs`) → wipe `dist` → `tsc -p tsconfig.build.json`. Native prebuilds shipped in npm tarball; `prebuilds/` is gitignored.
- **Toolchain drift risk:** TypeScript 7 build (`typescript@7.0.2`) vs TypeScript 6 AST compat shim (`@typescript/typescript6@6.0.2`, resolves `@typescript/old`→`typescript@6.0.3`) used by the passive discovery parser. The shim's transitive legacy compiler can occupy the `tsc` bin name; scripts call `node node_modules/typescript/bin/tsc` explicitly, and a regression test asserts the real compiler version.
- **Harness data projection:** `tools/project-harness-discovery.ts` reads `@agntn/harnesses@0.3.0` tarball as data via the TS6 AST API (no upstream code executed); generates `src/init/harness-discovery.generated.ts`; SRI/SHA-256 in `integrations/agntn-harnesses/upstream.lock.json`; `npm run harnesses:check` is part of build/CI/publish. `@agntn/harnesses@0.4.2` is unusable under the Node >=24 contract (requires Node >=26).
- **Version/citation sync:** `tools/sync_version.py`, `tools/sync_citation.py` keep `VERSION`/`CITATION.cff` in sync.
- **No ESLint/Prettier/biome.** `lint` = typecheck + `git diff --check` only.
- **Release artifacts:** `release.files.sha256`, `socket.yml`, `contracts/governance-contract.json`, `bundle/`, `site/` (docs site), `assets/`.

---

## 8. TODOs / FIXMEs / markers

A repo-wide case-insensitive scan for `TODO`, `FIXME`, `HACK`, `XXX`, `OPTIMIZE`, `WORKAROUND`, `TEMPORARY` found **zero actionable markers in `src/`**:

- `src/templates-catalog.ts:7` contains `"review"` inside a `TemplateCategory` type union — a false positive on the `REVIEW` alternation, not a marker.
- Remaining matches are incidental words (`temporary` in temp-dir usage across `tests/*.py`, `tools/sync_version.py`; `XXX-000` placeholder rule references in `docs/superpowers/specs/...` and `docs/superpowers/plans/...`; "keine TBD/TODO" placeholder statement in `docs/superpowers/plans/2026-09-20-issue-50-resume-fast-path.md:194`).

Tech debt in this repo is **implicit** (architecture, toolchain, test scope) rather than annotated in code.

---

## 9. Recommendations

1. Keep `smol-toml`, `@toon-format/toon`, `@clack/prompts` pins under Dependabot with the documented gate (signature + provenance + production audit) before any bump; re-verify `@agntn/harnesses` upstream PR #97 before considering a return to the library runtime.
2. Expand `npm test` (or add a CI step) to cover `tests/contracts/`, `tests/node/`, `tests/e2e/`, and the Python test files so the default command reflects the full suite.
3. Add ESLint (or biome) to `lint`; `git diff --check` only catches whitespace on changed lines.
4. Track native test-injection macros — confirm they are compiled out / inert in release prebuilds.
5. Periodically re-validate `docs/installer-threat-model.md` residual risks (SIGKILL, same-UID co-writer) against actual deployment platforms; prebuilds cover only darwin/linux arm64+x64.
6. Consider adding `.planning/` artifacts (`STATE.md`, `PROJECT.md`) now that `.planning/codebase/` exists; this CONCERNS.md is the seed.

---

## 10. Evidence & verification notes

- Files read: `package.json`, `package-lock.json` (via lock stats), `tsconfig.json`, `VERSION`, `CHANGELOG.md`, `GOVERNANCE.md` (canonical bundle + repo copy), `manifest.toml`, `local/user-rules.md`, `native/agent_governance_fs.c`, `src/cli.ts`, `src/filesystem.ts`, `src/planner.ts`, `src/closed-toml.ts`, `src/routing-catalog.ts`, `src/ssot-manifest.ts`, `src/installer/mutation.ts`, `src/init/orchestrator.ts`, `docs/installer-threat-model.md`, `docs/adapter-audit.md`, `docs/dependency-evidence.md`, `docs/issue-94-routing-evidence.md`, `.github/workflows/*`, `git log --oneline -25`.
- `node_modules/` absent → no build/lint/test execution in this session; claims about test/lint behavior are read from `package.json` scripts directly.
- No secrets, keys, or token material appear in this document; only content-independent metadata (paths, versions, severity ratings) is included, per GOV-005.
