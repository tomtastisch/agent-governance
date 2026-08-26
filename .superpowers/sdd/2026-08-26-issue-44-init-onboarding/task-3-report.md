# Task 3 Report — Classifier, boundary refinement, duplicates and identity

## Scope and starting state

- Worktree: `/Users/tomwerner/agent-governance/.worktrees/issue-44-init-onboarding`
- Branch: `feat/issue-44/init-onboarding`
- Starting HEAD: `e8e3d17d7a3f24a16e5cf24b8c1fbeb0063758bd`
- Preserved and excluded from staging: the pre-existing changes to the Issue-44 plan and design documents.
- All fixtures use synthetic absolute roots and synthetic HOME/XDG state. No real user data, candidate process, network resource, product binary, or package manager was accessed.

## TDD evidence

### Initial RED

Command:

```text
node --experimental-strip-types --test tests/installer/discovery-classifier.test.ts tests/installer/discovery-boundary.test.ts tests/installer/discovery-duplicates.test.ts tests/installer/discovery-regression.test.ts
```

Observed result: exit 1; all four test files failed because the classifier, boundary, duplicate, and discovery-index modules did not exist.

Additional focused RED cycles:

- The synthetic end-to-end discovery test returned no candidate because Task-2 display truncation collapsed three long canonical source paths to one source identity. A diagnostic run reproduced three paths of 130–132 characters becoming one 96-character source string. The index now restores the already enumerated canonical file path only for internal classification; bounded structural metadata remains unchanged.
- Boundary refinement silently reloaded the default catalog and upgraded a child that was `UNCERTAIN` under a supplied stricter catalog. The focused test failed with actual `HIGH_CONFIDENCE`; refinement now receives and preserves the originating catalog.
- The post-classification display-identity test failed while the public resolver was absent; the minimal resolver was then restored with an explicit `REJECTED` guard and control-character sanitization.

### GREEN and refactor

- Four focused files: 14/14 passed, exit 0.
- TypeScript typecheck and lint/`git diff --check`: exit 0.
- Refactoring occurred only after focused green runs and retained the declarative catalog thresholds through root splitting.

## Implemented contracts

- `classifyEvidence(records, catalog, context?)` validates records against declared signals and scores unique evidence families, not repeated records. A high result requires the configured score, family and independent-source gates, complete evidence, strong Runtime evidence and strong/corroborating non-Runtime evidence.
- Package-only evidence remains `UNCERTAIN`; App bundles cannot become high; overlay-only, document-only, single-source broad documents, message-like metadata and label phrases are rejected.
- `refineCandidateRoots(candidates, catalog?)` eliminates broad ancestors and replaces a broad container with all smallest coherent child clusters while retaining the classifier catalog.
- `resolveDuplicateCandidates(candidates)` first requires generic normalized identity plus structural similarity. It uses bounded evidence digests, normalized relative structure, density/coherence and only then passive activity. A unique stronger/active near-copy wins; indistinguishable copies remain present and are both demoted to `UNCERTAIN`; unrelated newer roots are not merged.
- `resolveCandidateIdentity(candidate)` is unavailable for rejected candidates and derives only a sanitized post-classification display label. No label participates in classification.
- `discoverCandidates(options)` composes bounded zones, no-follow enumeration, passive structural/package/SQLite evidence, classification, boundary refinement and duplicate resolution. It does not import or invoke child-process, network, login, package-manager or candidate-execution APIs.
- The synthetic seven-label regression fixture recognizes six positive candidates conservatively (four high, two uncertain) and rejects one overlay; fixture labels never enter evidence or classifier rules.
- Static scans found no product/provider names, protocol overlay name, candidate binary name, child-process import, conflict marker, debug marker, common secret marker or console debugging in the Task-3 production files.

## Verification before commit

- Focused Task-3 tests: 14/14 passed, exit 0.
- Full Node installer suite (`npm test`): 186/186 passed, exit 0.
- TypeScript typecheck: exit 0.
- Production build: exit 0.
- Lint and `git diff --check`: exit 0.
- Release manifest: current, exit 0.
- Full Python suite: 419 tests ran; 418 passed and only the pre-authorized Task-6 zero-runtime-dependency gate failed.
- License check: failed only on the same pre-authorized zero-runtime-dependency contract; it was not changed or weakened.

## Delivery boundary and remaining gates

- Intended Task-3 paths are staged explicitly for one signed commit with message `feat(discovery): classify and deduplicate candidate roots`.
- Independent QA and SEC were not run because the task explicitly prohibits subagents. The parent workflow must run both on the exact integrated head before any integration- or release-readiness claim.
- The known zero-runtime-dependency and license gate remains exclusively routed to Task 6.

## Review fix round 1/5

### Finding 1 — basename-dependent duplicate classification

- Root cause: `duplicatePair()` required `normalizedCandidateIdentity(left) === normalizedCandidateIdentity(right)` before comparing generic evidence. The basename therefore decided whether structurally indistinguishable roots entered ambiguity handling.
- RED: `node --experimental-strip-types --test tests/installer/discovery-duplicates.test.ts` exited 1. Synthetic `/synthetic/alpha` and `/synthetic/beta` candidates had identical normalized Evidence structure, digest, density and activity, but remained `HIGH_CONFIDENCE`.
- GREEN: removed the identity import and basename gate from duplicate resolution. Exact generic structural matches with indistinguishable quality/activity are both retained as `UNCERTAIN`. A separate test proves differing activity alone cannot group structurally dissimilar roots.
- Refactor: removed the now-dead basename copy/snapshot normalization from `identity.ts`; `basename()` remains only in the guarded post-classification display resolver.

### Finding 2 — High confidence without State anchor

- Root cause: the High predicate treated State, Tooling and AI metadata as interchangeable corroborating families. Runtime + Tooling + AI metadata reached score 8, three families and three independent sources without persistent State evidence.
- RED: `node --experimental-strip-types --test tests/installer/discovery-classifier.test.ts` exited 1; the synthetic no-State candidate was actual `HIGH_CONFIDENCE`, expected `UNCERTAIN`.
- GREEN: High now requires the declarative Runtime gate, actual strong Runtime evidence, a strong/corroborating State anchor and additional strong/corroborating Tooling or AI metadata, while retaining all score/family/independent-source/completeness gates. The no-State overlay-shaped candidate remains positive but is demoted to `UNCERTAIN`.

### Fix-round verification before commit

- Focused Task-3 suite: 16/16 passed, exit 0.
- Full Node installer suite: 188/188 passed, exit 0.
- TypeScript typecheck: exit 0.
- Lint and `git diff --check`: exit 0.
- The pre-existing Issue-44 plan/design changes remain excluded. The known Task-6 zero-runtime-dependency/license gate is unchanged.
