# Issue #39 Documentation Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver Issue #39 as the stable SemVer patch `1.0.1`, from compact README and separated documentation through verified PR, merge, GitHub Release, npm publication, read-back, and issue closure.

**Architecture:** Human-facing content has one owner per domain; README is navigation, current reference docs are non-normative but not historical, and `bundle/` remains the normative SSOT. Offline link validation is part of the PR tree gate, while remote `main` validation runs only after merge and before release; packaging remains intentionally narrower than repository documentation.

**Tech Stack:** Markdown, Python 3.11 standard library, Node.js >=24/npm repository lockfile, TypeScript node:test, Git/GitHub CLI, existing GitHub Actions and npm Trusted Publishing.

**Spec:** `docs/superpowers/specs/2026-08-25-issue-39-documentation-architecture-design.md`

## Global Constraints

- Target version is exactly `1.0.1`; release tag is `v1.0.1`; npm package is `@tomtastisch/agent-governance@1.0.1`.
- Public CLI commands and runtime behavior do not change.
- No runtime dependency, docs platform, docs site, asset pipeline, harness adapter, harness detection, hook, MCP mutation, or approval automation is added.
- `bundle/` remains the sole normative governance source and is not changed.
- `INSTALL.md` is removed only after all unique current information is migrated.
- Current docs use absolute `https://github.com/tomtastisch/agent-governance/blob/main/<repo-path>` links from README.
- PR tests are offline; remote `main` URL checks are post-merge/pre-release only.
- The npm tarball contains `docs/installer-cli-reference.md` but excludes `INSTALL.md`, `assets/`, `docs/harness-recipes.md`, and the other current reference docs.
- The visually verified mapping is `ujjm...` to `governance-overview.png` and `dsfs...` to `governance-architecture.png`.
- Every behavior change in verification, packaging, or release logic follows red-green-refactor.

---

### Task 1: Materialize migration ownership and current-reference classification

**Files:**
- Modify: `tests/test_documentation.py`
- Modify: `tests/test_source_consolidation.py`
- Modify: `docs/installer-cli-reference.md`
- Create: `docs/harness-recipes.md`
- Modify: `docs/installer-architecture.md`
- Modify: `docs/installer-threat-model.md`
- Modify: `docs/installer-json-schemas.md`

**Interfaces:**
- Consumes: current README/INSTALL inventory and the ownership matrix in the spec.
- Produces: five active, non-normative reference documents with one domain owner each and four source-backed harness recipes.

- [ ] **Step 1: Write failing documentation/source-consolidation tests**

  Add tests that require the five current references, reject the historical marker in their first ten lines, require the four recipe headings and official source URLs, and make `ACTIVE_REFERENCE_FILES` omit `INSTALL.md`. Name each test for the stale architecture it catches.

- [ ] **Step 2: Verify RED**

  Run `python3 -m unittest tests.test_documentation tests.test_source_consolidation -v` and confirm failures are caused by the missing recipes/current-reference split.

- [ ] **Step 3: Migrate unique content**

  Create `docs/harness-recipes.md` from the four verified primary-source contracts. Consolidate CLI, lifecycle/recovery, security boundary, and JSON field content into their owning references without duplicating a full neighboring contract. Remove the historical marker only from current references.

- [ ] **Step 4: Verify GREEN and review the semantic matrix**

  Run `python3 -m unittest tests.test_documentation tests.test_source_consolidation -v`; then compare every row in the spec migration matrix against the resulting files and record any missing unique content before continuing.

- [ ] **Step 5: Commit**

  Commit as `docs: separate current installer and harness references`.

### Task 2: Move assets and reduce README to the entry layer

**Files:**
- Modify: `tests/test_documentation.py`
- Modify: `README.md`
- Modify: `docs/installer-architecture.md`
- Move: `docs/images/82b014a1-7278-4be4-a665-37dae365c850.png` -> `assets/branding/agent-governance-icon.png`
- Move: `docs/images/Governance-ujjm885-44_44.png` -> `assets/diagrams/governance-overview.png`
- Move: `docs/images/Governance-dsfs652-20_44.png` -> `assets/diagrams/governance-architecture.png`

**Interfaces:**
- Consumes: Task 1 reference destinations and the visually verified asset mapping.
- Produces: compact README with exactly six H2 sections, one overview image, three durable badges, Stable quickstart, and intent-oriented absolute GitHub navigation.

- [ ] **Step 1: Write failing README and asset-contract tests**

  Require the exact H2 structure, npm/CI/Apache badges derived from package/workflow metadata, absolute current-doc links, one `governance-overview` reference, the architecture image in architecture docs, semantic asset paths, and absence of `@next`, RC guidance, `INSTALL.md`, `docs/images/`, and old filenames.

- [ ] **Step 2: Verify RED**

  Run `python3 -m unittest tests.test_documentation -v` and confirm the old 325-line README and old asset paths fail the new invariants.

- [ ] **Step 3: Move assets and author the compact README**

  Move the three exact files, remove an empty `docs/images/`, add the architecture image to its owner, and rewrite README with icon, pitch, npm/CI/license badges, Was/Warum/Schnellstart/Wie/Dokumentation/Support sections. Use Stable `npx @tomtastisch/agent-governance@latest` commands for `plan`, `install`, and `verify`, explicit paths, and absolute Raw-GitHub image URLs.

- [ ] **Step 4: Verify GREEN and asset uniqueness**

  Run `python3 -m unittest tests.test_documentation -v`; run `find assets docs/images -type f` as applicable and content-digest comparison to prove there are three intended image files, no duplicates, and no stale directory.

- [ ] **Step 5: Commit**

  Commit as `docs: simplify readme and organize visual assets`.

### Task 3: Replace INSTALL and README drift checks with canonical link validation

**Files:**
- Modify: `tests/test_release_check.py`
- Modify: `tools/release_check.py`
- Modify: `.github/workflows/ci.yml`
- Delete: `INSTALL.md`

**Interfaces:**
- Consumes: README canonical current-doc URL set from Task 2.
- Produces: `_check_document_links(root)` for deterministic tree validation and a `docs-remote` CLI mode that validates the same paths through `gh api` after merge.

- [ ] **Step 1: Write failing local-link and remote-mode tests**

  Add fixture tests for wrong host, wrong owner/repo, non-`main` current ref, unexpected/missing path, deleted `INSTALL.md`, stale `docs/images`, and missing local target. Add subprocess-injected `gh` tests proving `docs-remote` checks every canonical path and fails closed on missing CLI/API errors without making normal tree tests network-dependent.

- [ ] **Step 2: Verify RED**

  Run the new focused `tests.test_release_check` cases and confirm failures come from the absent link checker/remote mode and retained INSTALL requirement.

- [ ] **Step 3: Implement minimal local and remote checks**

  Parse Markdown links with the standard library, compare against the exact canonical path map, resolve local paths beneath the repository, and add `docs-remote` using `gh api repos/tomtastisch/agent-governance/contents/<path>?ref=main`. Remove `_check_install_links`; make missing `INSTALL.md` required rather than erroneous.

- [ ] **Step 4: Wire CI by event boundary**

  Keep `release-metadata` local and blocking for pull requests. Add a separate remote-doc job gated to `push` on `main` and `release: published`, with read-only contents permission and no PR network dependency; update stale workflow step names that mention INSTALL.

- [ ] **Step 5: Verify GREEN**

  Run `python3 -m unittest tests.test_release_check -v`, `python3 tools/release_check.py tree`, and the complete Python suite.

- [ ] **Step 6: Commit**

  Commit as `test: enforce canonical documentation links`.

### Task 4: Tighten npm packaging and release Stable-patch contracts

**Files:**
- Modify: `tests/installer/pack-verifier.test.ts`
- Modify: `tools/verify-pack.mjs`
- Modify: `package.json`
- Modify: `package-lock.json`
- Modify: `tests/test_ci_workflow.py`
- Modify: `.github/workflows/npm-publish.yml`

**Interfaces:**
- Consumes: deleted INSTALL and the package boundary from the spec.
- Produces: semantic required/forbidden package-path checks and Trusted Publishing admission for stable `1.0.1` without changing the OIDC path.

- [ ] **Step 1: Write failing pack and publish-contract tests**

  Update the allowed fixture to omit `INSTALL.md`; add explicit tests that reject `INSTALL.md`, any `assets/` path, `docs/harness-recipes.md`, and non-CLI docs while requiring README/LICENSE/CHANGELOG/CLI reference. Add a workflow contract that accepts the repository VERSION with `latest` and rejects prerelease/Stable dist-tag mismatches without hardcoding only `1.0.0`.

- [ ] **Step 2: Verify RED**

  Run `node --experimental-strip-types --test tests/installer/pack-verifier.test.ts` and the focused CI workflow unittest; confirm old allowlists and publish case fail.

- [ ] **Step 3: Implement minimal packaging/release changes**

  Remove `INSTALL.md` from `package.json#files` and `tools/verify-pack.mjs`, introduce explicit forbidden prefixes/files, and generalize the existing main-controlled OIDC workflow's stable `latest` admission to the exact VERSION/tag while retaining RC-to-`next` validation.

- [ ] **Step 4: Update lockfile with repository npm**

  Run `npm install --package-lock-only --ignore-scripts` and inspect that only root package version metadata changes; no dependency version changes are allowed.

- [ ] **Step 5: Verify GREEN**

  Run the focused pack/CI tests, `npm run build`, `npm run pack:check`, and inspect `npm pack --dry-run --json` for required and forbidden paths.

- [ ] **Step 6: Commit**

  Commit as `build: keep the 1.0.1 package boundary slim`.

### Task 5: Version and changelog the complete patch

**Files:**
- Modify: `VERSION`
- Modify: `package.json`
- Modify: `package-lock.json`
- Modify: `CHANGELOG.md`
- Modify: `tests/test_documentation.py`
- Modify: `tests/test_source_consolidation.py`
- Modify: `tests/test_release_check.py`

**Interfaces:**
- Consumes: all delivered Issue #39 behavior and repository version SSOT.
- Produces: internally consistent release metadata for `1.0.1` with no breaking change.

- [ ] **Step 1: Write failing version-derived tests**

  Replace stale exact-`1.0.0` current-release assertions with VERSION-derived assertions, require the `1.0.1` changelog section to name documentation architecture, Harness Recipes, asset migration, INSTALL removal, package/link/test cleanup, and `**Breaking changes:** none`.

- [ ] **Step 2: Verify RED**

  Run the focused documentation, source-consolidation, and release-check tests and confirm failures identify the old metadata.

- [ ] **Step 3: Update release metadata**

  Set VERSION/package/lock root metadata to `1.0.1`, add the dated changelog section, and leave Unreleased reset with no breaking changes. Do not embed `1.0.1` in README prose or recipes.

- [ ] **Step 4: Verify GREEN**

  Run focused tests, `python3 tools/release_check.py tree`, and `python3 tools/release_manifest.py check`.

- [ ] **Step 5: Commit**

  Commit as `chore: prepare release 1.0.1`.

### Task 6: Full local verification and semantic redundancy audit

**Files:**
- Modify only files required to correct in-scope failures found by the gates; every logic correction starts with a reproducing test.

**Interfaces:**
- Consumes: exact branch head after Tasks 1-5.
- Produces: complete local release evidence for one immutable candidate head.

- [ ] **Step 1: Run focused and full repository gates**

  Run `npm ci --ignore-scripts`, `npm run typecheck`, `npm run lint`, `npm run build`, `npm test`, `python3 -m unittest discover -s tests -v`, `python3 tools/release_manifest.py check`, `python3 tools/release_check.py tree`, `npm audit --audit-level=high`, `npm run license:check`, `npm run pack:check`, `npm run test:package`, `tests/e2e/run_installer_fixture.sh`, `tests/e2e/run_neutral_harness.sh`, and `git diff --check`.

- [ ] **Step 2: Run explicit repository invariants**

  Search tracked/current user docs for `INSTALL.md`, `docs/images/`, old image names, `@next`, current RC instructions, stale package entries, duplicate asset digests, and unexpected bundle changes. Inspect the generated tarball inventory semantically.

- [ ] **Step 3: Perform the semantic redundancy audit**

  Compare README against CLI, Harness, Architecture and Threat Model; Architecture against Threat Model; Harness against CLI; and all docs against `bundle/`. Record each domain owner and correct any parallel full contract.

- [ ] **Step 4: Commit gate-driven corrections, if any**

  Commit each coherent correction with its covering test and rerun every affected gate.

### Task 7: Independent exact-head reviews and PR delivery

**Files:**
- No planned product edits; review findings may produce scoped tested commits.

**Interfaces:**
- Consumes: exact verified head and full `origin/main..HEAD` review package.
- Produces: independent QA and Security verdicts, pushed branch, Issue-#39 PR, and green Required Checks.

- [ ] **Step 1: Run independent read-only reviews**

  Dispatch fresh reviewers for QA and the GOV-006 security-sensitive diff. Require exact head SHA and assess information loss, ownership duplication, links, packaging, versions, release checks, image mapping, RC remnants, runtime/CLI drift, tests, and network flakiness. Classify and fix all blocking-valid findings, then rerun affected gates and both reviews on the new head.

- [ ] **Step 2: Commit and push the reviewed head**

  Verify clean status and signatures, push `docs/issue-39-readme-architecture-1.0.1`, and create a PR against `main` referencing Issue #39 and the no-breaking-change/release-follow-up contract.

- [ ] **Step 3: Read back PR review and CI**

  Verify PR head SHA, read every review/thread, and wait for at least `Release-Metadaten (blockierend)` and `Konsistenz- & Drift-Tests (blockierend)` plus all current checks to finish successfully. Fix only in-scope findings through tested commits and repeat exact-head review.

### Task 8: Merge, remote link gate, release, publication, and issue closure

**Files:**
- No local product edits unless an in-scope post-merge defect requires a new reviewed PR.

**Interfaces:**
- Consumes: merge-ready reviewed PR and repository's existing signed-tag/OIDC release workflow.
- Produces: main merge, remote-valid docs, GitHub `v1.0.1`, npm `1.0.1`/`latest`, verified tarball, and closed Issue #39.

- [ ] **Step 1: Merge normally and verify main ancestry**

  Merge through the protected PR process, record merge SHA, fetch `origin/main`, and prove the merge SHA is contained in the current remote main.

- [ ] **Step 2: Run blocking post-merge document read-back**

  Run `python3 tools/release_check.py docs-remote` from the merged main and directly read all canonical GitHub blob URLs, especially `docs/harness-recipes.md`. Stop release on any mismatch.

- [ ] **Step 3: Execute the existing signed Stable release path**

  Follow repository release instructions to create the signed annotated `v1.0.1` tag and non-draft/non-prerelease GitHub Release targeting the merged main, then dispatch `.github/workflows/npm-publish.yml` with `tag=v1.0.1` and `dist_tag=latest`. Do not use a personal npm token.

- [ ] **Step 4: Read back CI, GitHub Release, npm, and tarball**

  Verify workflow conclusion and exact SHA; GitHub tag/release target, signature, notes, draft/prerelease flags; `npm view @tomtastisch/agent-governance@1.0.1 version dist-tags dist --json`; provenance/signature metadata; downloaded tarball contents; README links; required files; and absence of INSTALL/assets/non-package docs.

- [ ] **Step 5: Close Issue #39 only after every gate is evidenced**

  Add a concise comment containing PR, release, npm version, delivered doc/package changes and verified gates, then close Issue #39 and read back its closed state.

