# Forward-only Replacement Implementation Plan

> **For agentic workers:** Use subagent-driven-development to implement this plan task-by-task. Read the linked specification before implementation.

**Goal:** Provide a safe forward-only replacement for an installation whose persisted identity no longer verifies, without interpreting historical contracts.

**Architecture:** A narrow `./replacement` package capability isolates the selected old entry and delegates fresh materialization to the existing installer in a disjoint new root. All old managed state remains intact; no existing CLI or recovery validator is relaxed.

**Tech Stack:** TypeScript, Node.js built-ins, existing native filesystem primitives and Node test runner.

**Spec:** `docs/superpowers/specs/2026-09-25-issue-123-forward-replacement-design.md`

## Global Constraints

- Node.js >=24; Darwin/Linux arm64/x64 support remains unchanged.
- No new runtime dependencies, no legacy validators or version branches.
- Never access the Socket secret or mutate the active installation during development.
- Source/destination roots disjoint; destination absent; retain original private entry and all old managed state.
- Fail closed on unsafe input and observable concurrent changes.
- New package API is minor; no release bump, merge or publish in this implementation task.

### Task 1: Replacement capability and distributable contract

**Files:** create `src/replacement.ts`, `tests/installer/replacement.test.ts`;
modify `package.json`, packaging/consumer tests and directly relevant installer documentation,
`CHANGELOG.md`, and regenerate `release.files.sha256` if inventoried documentation changes.
Use internal `src/installer/replacement-*.ts` modules only when responsibilities require them.

**Interfaces:** consumes `InstallerTransaction`, `inspectTarget`, managed-block parsing,
current local-rules validation and native identity-bound filesystem operations;
produces exported `replaceInstallation(request)` with typed request/result and safe
quarantine/plan references. Existing public commands and exports remain unchanged.

- [ ] Write and run the first failing lifecycle test through the proposed module:

  ```ts
  const replacement = await import('../../src/replacement.ts');
  assert.equal(typeof replacement.replaceInstallation, 'function');
  const result = await replacement.replaceInstallation(request);
  assert.equal(result.outcome, 'SUCCESS');
  assert.equal((await new InstallerTransaction(newRequest).verify()).state, 'CURRENT');
  assert.deepEqual(await readFile(quarantinedEntry), originalEntry);
  assert.deepEqual(await readFile(oldReceipt), originalReceipt);
  ```

  Fixtures use the existing release/workspace helpers and synthetic private bytes.
  Establish RED because the capability is absent, not because fixture setup is invalid.
- [ ] Implement the smallest transaction from the specification, using fresh resource
  identities and existing no-clobber primitives. Run the focused test to GREEN.
- [ ] Extend RED/GREEN coverage for each rejected input and failure boundary named
  in the specification. Assert actual preservation/non-mutation rather than mock calls.
  Use test-runner mocks or subprocess barriers for fault/race injection rather than
  exposing test-only controls in the public API.
- [ ] Register `./replacement` types/default export and exercise it from the built
  tarball in `tests/e2e/run_package_consumers.sh`. Document explicit new-root usage,
  local-rules opt-in, quarantine retention, failure recovery and minor SemVer.
- [ ] Run `npm run typecheck`, `npm test`, `npm run lint`, `npm run build`,
  `npm run pack:check`, `npm run test:package`, `npm run license:check`,
  `npm audit --audit-level=high`, `python3 -m unittest discover -s tests`,
  `python3 tools/release_manifest.py check`, `python3 tools/release_check.py tree`,
  and applicable installer/neutral-harness E2E scripts. Record real outcomes.
- [ ] Inspect status/diff/log, self-review scope/security, then commit only intended
  changes with a conventional `feat(installer): ...` message. Do not push.

### Task 2: Independent review and delivery

**Files:** no preplanned production changes; corrections must be finding-driven.

- [ ] Independent read-only SEC reviews the exact diff and trust/race/recovery boundaries.
- [ ] Independent QA reviews specification coverage, package consumption and evidence.
- [ ] Correct findings with regression tests; rerun affected gates on each new head.
- [ ] Push the exact verified branch, create the PR with canonical governance template,
  request Copilot if available and inspect every check/review/thread until resolved.
- [ ] Report exact head, CI, QA and SEC. Ask once for merge/release authorization when
  required to supply a published fix; keep #122 paused and active installation intact.
