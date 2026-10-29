---
phase: 15
name: Work-Item Lifecycle (Issue #54)
slug: work-item-lifecycle-issue-54
status: planned
wave: 1
depends_on: []
files_modified:
  - src/lifecycle/state.ts
  - src/lifecycle/events.ts
  - src/lifecycle/transition.ts
  - src/lifecycle/projection.ts
  - src/lifecycle/evidence.ts
  - src/lifecycle/index.ts
  - tests/lifecycle/state.test.ts
  - tests/lifecycle/transition.test.ts
  - tests/lifecycle/projection.test.ts
autonomous: true
granularity: standard
tracer_mode: true
---

# Phase 15: Work-Item Lifecycle (Issue #54) — Plan

## Phase Goal

Implementiere eine kanonische, plattformneutrale Work-Item-Lifecycle-Semantik als reine TypeScript-Entscheidungsebene ohne externe Schreibwirkungen. Zustände: work.ready, work.in_progress, work.blocked, work.completed. Ereignisse: work_started, work_blocked, work_resumed, work_completed. Transition-Validierung mit Preconditions, Required Evidence, Idempotenz und Ordering. Managed in-progress Projektion als separate Consumer-Sorge (Issue #79).

## Tracer Slice (Wave 1)

Ein end-to-end fähiger Durchlauf: `transition()` akzeptiert `work_started` mit valider Evidence, produziert `TransitionDecision` mit Zielzustand `work.in_progress` und Projection Plan (`in-progress` Label-Zuordnung). Keine GitHub-Schreibwirkung. Serialisierbare Entscheidung.

## Requirements Coverage

Alle 13 Anforderungen aus `15-SPEC.md` werden durch die folgenden Tasks abgedeckt:
- R1 (Lifecycle Authority): Task L1, L2
- R2 (work_started): Task L3
- R3 (work_blocked): Task L4
- R4 (work_resumed): Task L5
- R5 (work_completed): Task L6
- R6 (No false starts): Task L3, L7
- R7 (Managed in-progress projection): Task L8
- R8 (Slice isolation): Task L4, L9
- R9 (No false completion): Task L6, L7
- R10 (Idempotency & ordering): Task L7
- R11 (Label from Projection-SSOT): Task L8
- R12 (No implicit tools/auth): Task L10
- R13 (Decision-only tests): Task L11

## Constraints (locked)

- Lifecycle State != GitHub Label
- Lifecycle Event != Chatphrase
- Transition Decision != externe Schreibfreigabe
- work_started consumed from Issue #55
- resume_continuation is NOT a lifecycle transition
- Materialization per Issue #57 or #79
- Planning per Issue #56
- closed != completed
- No GitHub write effect in Issue #54
- GitHub is not a general prerequisite for lifecycle semantics

## Edge Coverage (from SPEC.md, lifted into must_haves)

| Edge | Requirement | Verification |
|------|-------------|--------------|
| Stale Transition / Lost Updates | R10 | fail-closed on stale source state; event ordering prevents lost updates |
| Concurrent authorities | R10 | competing canonical authorities fail closed |
| Idempotent events | R10 | identical already-applied events are idempotent |
| Late events | R10 | late events rejected via source state validation |

## Prohibitions (from SPEC.md, lifted into must_haves.prohibitions)

| Prohibition | Requirement | Verification |
|-------------|-------------|--------------|
| MUST NOT perform GitHub writes in decision-only tests | R13 | decision-only tests verify null GitHub write calls |
| MUST NOT treat administrative Closure as completion | R9 | closed != completed; closure alone yields no work.completed |
| MUST NOT start work from materialization, planning, PR-existence or technical resume | R6 | these actions produce no work_started and no in-progress projection |

## must_haves.truths (goal-backward verification)

1. Transition function `transition(workItemId, event, currentState, evidence, eventId)` returns `TransitionDecision` with work item, event, source/target state, decision, evidence, reason, projection plan.
2. `work_started` transitions `work.ready → work.in_progress` only when authorized start, Current-State Resolution, unique identity, confirmed scope, and start preconditions are met.
3. `work_blocked` transitions `work.in_progress → work.blocked` only with concrete blocker (scope, cause, evidence, resolution).
4. `work_resumed` transitions `work.blocked → work.in_progress` only with evidenced blocker resolution.
5. `work_completed` transitions `work.in_progress → work.completed` only when outcome met, acceptance criteria fulfilled, tests/reviews passed, no blocking-valid findings, all effects verified.
6. Invalid transitions are rejected with reason.
7. Identical relevant inputs produce identical decisions (idempotency).
8. Already-applied identical events are idempotent (no re-application).
9. Expected source state and event ordering prevent lost updates and rollbacks from late events.
10. Stale transitions fail closed.
11. Competing canonical authorities fail closed.
12. Projection plan from valid `work_started` includes `in-progress` label assignment; from `work_completed` includes removal.
13. Engine performs zero GitHub API calls (decision-only tests verify null writes).
14. No secrets, private prompt content, or derived fingerprints in audit evidence (GOV-005).
15. Missing GitHub/tools/auth blocks only dependent gates, not lifecycle semantics.

## must_haves.prohibitions

1. statement: "Engine performs no GitHub API calls", status: resolved, verification: test
2. statement: "Administrative closure alone yields no work.completed", status: resolved, verification: test
3. statement: "Materialization/planning/PR-existence/technical resume produce no work_started", status: resolved, verification: test

## Tasks

<task id="L1" name="Define lifecycle state and event types">
<read_first>
- .planning/phases/15-work-item-lifecycle-issue-54/15-SPEC.md
- .planning/phases/15-work-item-lifecycle-issue-54/15-CONTEXT.md
- .planning/codebase/CONVENTIONS.md
- .planning/codebase/ARCHITECTURE.md
</read_first>
<action>
Create `src/lifecycle/state.ts` with:
- `WorkItemState` type: `"work.ready" | "work.in_progress" | "work.blocked" | "work.completed"`
- `LifecycleEvent` type: `"work_started" | "work_blocked" | "work_resumed" | "work_completed"`
- `Evidence` interface with `references: string[]` and `secureReference: string`
- `ProjectionPlan` interface with `labelAssignment: "in-progress" | "remove" | "none"` and `target: string`
- `TransitionDecision` interface with `workItemId`, `event`, `sourceState`, `targetState`, `decision: "approve" | "reject"`, `evidence: { present: string[]; missing: string[] }`, `reason: string`, `projection: ProjectionPlan`
- All types exported, strict TS (`noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`)
</action>
<acceptance_criteria>
- `src/lifecycle/state.ts` compiles with `tsc --noEmit` (0 errors)
- All types are exported and importable from `src/lifecycle/index.ts`
- `WorkItemState` has exactly 4 literal values; `LifecycleEvent` has exactly 4 literal values
</acceptance_criteria>
</task>

<task id="L2" name="Create lifecycle module index">
<read_first>
- src/lifecycle/state.ts
- .planning/codebase/CONVENTIONS.md
</read_first>
<action>
Create `src/lifecycle/index.ts` that re-exports all types from `src/lifecycle/state.ts`. Follow codebase conventions: 2-space indent, semicolons, single quotes, `node:` built-in prefix, `.ts` extensions on relative imports, `import type` for type-only imports.
</action>
<acceptance_criteria>
- `src/lifecycle/index.ts` compiles with `tsc --noEmit` (0 errors)
- All types from `state.ts` are re-exported
- File follows codebase conventions (2-space, semicolons, single quotes, `node:` prefix, `import type` for types)
</acceptance_criteria>
</task>

<task id="L3" name="Implement work_started transition validation">
<read_first>
- src/lifecycle/state.ts
- src/lifecycle/index.ts
- 15-SPEC.md (Requirement R2, R6)
</read_first>
<action>
Create `src/lifecycle/transition.ts` with:
- `validateStart(workItemId: string, evidence: Evidence, eventId: string): TransitionDecision` — approves only when currentState is `work.ready`, authorized start confirmed, unique identity, confirmed scope, start preconditions met
- `work_started` event produces target state `work.in_progress` with projection plan (`labelAssignment: "in-progress"`, `target: workItemId`)
- Rejects with reason if any precondition missing (materialization, planning, PR-existence, technical resume do not qualify)
</action>
<acceptance_criteria>
- `validateStart` with `work.ready` + valid evidence returns `decision: "approve"`, `targetState: "work.in_progress"`, `projection.labelAssignment: "in-progress"`
- `validateStart` with non-`work.ready` state returns `decision: "reject"` with reason
- `validateStart` without authorized start returns `decision: "reject"` with reason
</acceptance_criteria>
</task>

<task id="L4" name="Implement work_blocked transition validation">
<read_first>
- src/lifecycle/state.ts
- src/lifecycle/transition.ts
- 15-SPEC.md (Requirement R3, R8)
</read_first>
<action>
Extend `src/lifecycle/transition.ts` with:
- `validateBlock(workItemId: string, blocker: { scope: string; cause: string; evidence: string[]; resolution: string }, eventId: string): TransitionDecision` — approves only when currentState is `work.in_progress` and blocker has scope, cause, evidence, resolution
- `work_blocked` produces target state `work.blocked`
- Rejects if blocker evidence incomplete
</action>
<acceptance_criteria>
- `validateBlock` with `work.in_progress` + complete blocker returns `decision: "approve"`, `targetState: "work.blocked"`
- `validateBlock` with non-`work.in_progress` state returns `decision: "reject"`
- `validateBlock` with incomplete blocker returns `decision: "reject"` with reason
</acceptance_criteria>
</task>

<task id="L5" name="Implement work_resumed transition validation">
<read_first>
- src/lifecycle/state.ts
- src/lifecycle/transition.ts
- 15-SPEC.md (Requirement R4)
</read_first>
<action>
Extend `src/lifecycle/transition.ts` with:
- `validateResume(workItemId: string, resolutionEvidence: string[], eventId: string): TransitionDecision` — approves only when currentState is `work.blocked` AND resolutionEvidence is non-empty (evidenced blocker resolution)
- `work_resumed` produces target state `work.in_progress`
- Rejects if currentState is not `work.blocked` or resolutionEvidence is empty
</action>
<acceptance_criteria>
- `validateResume` with `work.blocked` + resolution evidence returns `decision: "approve"`, `targetState: "work.in_progress"`
- `validateResume` with non-`work.blocked` state returns `decision: "reject"`
- `validateResume` with empty resolution evidence returns `decision: "reject"`
</acceptance_criteria>
</task>

<task id="L6" name="Implement work_completed transition validation">
<read_first>
- src/lifecycle/state.ts
- src/lifecycle/transition.ts
- 15-SPEC.md (Requirement R5, R9)
</read_first>
<action>
Extend `src/lifecycle/transition.ts` with:
- `validateComplete(workItemId: string, outcomeMet: boolean, reviewsPassed: boolean, blockingFindings: number, effectsVerified: boolean, eventId: string): TransitionDecision` — approves only when currentState is `work.in_progress` AND outcomeMet AND reviewsPassed AND blockingFindings === 0 AND effectsVerified
- `work_completed` produces target state `work.completed` with projection plan (`labelAssignment: "remove"`, `target: workItemId`)
- Rejects if any precondition missing
</action>
<acceptance_criteria>
- `validateComplete` with `work.in_progress` + all preconditions met returns `decision: "approve"`, `targetState: "work.completed"`, `projection.labelAssignment: "remove"`
- `validateComplete` with blockingFindings > 0 returns `decision: "reject"`
- `validateComplete` with effectsVerified = false returns `decision: "reject"`
</acceptance_criteria>
</task>

<task id="L7" name="Implement idempotency, ordering, and fail-closed logic">
<read_first>
- src/lifecycle/transition.ts
- 15-SPEC.md (Requirement R10)
- .planning/codebase/ARCHITECTURE.md (transactional installer pattern)
</read_first>
<action>
Extend `src/lifecycle/transition.ts` with:
- `processEvent(workItemId: string, event: LifecycleEvent, currentState: WorkItemState, evidence: Evidence, eventId: string, appliedEvents: string[]): TransitionDecision` — main entry point
- Idempotency: if `eventId` already in `appliedEvents`, return same decision as before (idempotent)
- Ordering: reject if `currentState` does not match expected source state for the event
- Fail-closed: unknown event, ambiguous state, or missing evidence → `decision: "reject"` with reason
- Stale transitions: event with outdated source state fails closed
</action>
<acceptance_criteria>
- `processEvent` with duplicate `eventId` in `appliedEvents` returns identical decision (idempotent)
- `processEvent` with mismatched `currentState` returns `decision: "reject"`
- `processEvent` with unknown event type returns `decision: "reject"` with reason
- `processEvent` with missing evidence returns `decision: "reject"` with reason
</acceptance_criteria>
</task>

<task id="L8" name="Implement managed in-progress projection">
<read_first>
- src/lifecycle/state.ts
- src/lifecycle/transition.ts
- 15-SPEC.md (Requirement R7, R11)
- .planning/codebase/CONVENTIONS.md
</read_first>
<action>
Create `src/lifecycle/projection.ts` with:
- `buildProjection(decision: TransitionDecision): ProjectionPlan` — derives `labelAssignment` and `target` from transition decision
- `work_started` approve → `labelAssignment: "in-progress"`, `target: workItemId`
- `work_completed` approve → `labelAssignment: "remove"`, `target: workItemId`
- All other decisions → `labelAssignment: "none"`
- No GitHub API calls; pure function returning projection data only
</action>
<acceptance_criteria>
- `buildProjection` for approved `work_started` returns `{ labelAssignment: "in-progress", target: workItemId }`
- `buildProjection` for approved `work_completed` returns `{ labelAssignment: "remove", target: workItemId }`
- `buildProjection` for rejected decision returns `{ labelAssignment: "none" }`
- No `fetch`, `http`, or GitHub API imports in `projection.ts`
</acceptance_criteria>
</task>

<task id="L9" name="Implement slice isolation check">
<read_first>
- src/lifecycle/transition.ts
- 15-SPEC.md (Requirement R8)
</read_first>
<action>
Extend `src/lifecycle/transition.ts` with:
- `isSliceActive(workItemId: string, parentId: string): boolean` — checks if a slice (child) is independently active without affecting parent lifecycle
- Parent receives `in-progress` label only when parent itself is actively worked on per its own work-start contract
- Active child does not start parent
</action>
<acceptance_criteria>
- `isSliceActive` returns true when slice has its own active work-start, independent of parent state
- Parent lifecycle is not modified by child slice activity
</acceptance_criteria>
</task>

<task id="L10" name="Implement no-implicit-tools/auth guard">
<read_first>
- src/lifecycle/transition.ts
- 15-SPEC.md (Requirement R12)
</read_first>
<action>
Extend `src/lifecycle/transition.ts` with:
- `checkDependencies(available: { github: boolean; tools: boolean; auth: boolean }): { blocked: string[]; allowed: string[] }` — returns which gates are blocked due to missing dependencies
- Missing GitHub blocks only label projection (Issue #79 consumer), not lifecycle decision
- Missing tools block only dependent gates
- Missing auth blocks only dependent gates
- No automatic installation or authentication attempted
</action>
<acceptance_criteria>
- `checkDependencies` with all false returns `blocked` containing label-projection gate, `allowed` containing lifecycle decision
- `checkDependencies` with all true returns empty `blocked`
- No `npm install`, `npm auth`, or similar commands invoked
</acceptance_criteria>
</task>

<task id="L11" name="Write lifecycle tests (node:test + node:assert/strict)">
<read_first>
- src/lifecycle/state.ts
- src/lifecycle/transition.ts
- src/lifecycle/projection.ts
- .planning/codebase/TESTING.md
- .planning/codebase/CONVENTIONS.md
</read_first>
<action>
Create test files:
- `tests/lifecycle/state.test.ts` — type exports, strict TS compilation
- `tests/lifecycle/transition.test.ts` — all 4 transitions, idempotency, ordering, fail-closed, invalid transitions
- `tests/lifecycle/projection.test.ts` — projection derivation, no GitHub writes
Run with `node --experimental-strip-types --test tests/lifecycle/*.test.ts`
</action>
<acceptance_criteria>
- All 3 test files pass (`exit code 0`)
- Decision-only tests verify null GitHub write calls (no `fetch`, `http`, GitHub imports in test files)
- Tests cover all 13 requirements from SPEC.md
- Tests follow codebase conventions: `node:test` + `node:assert/strict`, manual mocking via dependency-injected fakes
</acceptance_criteria>
</task>

## Verification

- `tsc --noEmit` — 0 errors across all new/modified files
- `node --experimental-strip-types --test tests/lifecycle/*.test.ts` — all tests pass, exit code 0
- `git diff --check` — no whitespace errors
- Decision-only tests: null GitHub write calls verified

## Artifacts this phase produces

- `src/lifecycle/state.ts` — `WorkItemState`, `LifecycleEvent`, `Evidence`, `ProjectionPlan`, `TransitionDecision` types
- `src/lifecycle/index.ts` — module re-exports
- `src/lifecycle/transition.ts` — `validateStart`, `validateBlock`, `validateResume`, `validateComplete`, `processEvent`, `checkDependencies`, `isSliceActive`
- `src/lifecycle/projection.ts` — `buildProjection`
- `tests/lifecycle/state.test.ts`, `tests/lifecycle/transition.test.ts`, `tests/lifecycle/projection.test.ts`

## Dependencies

- No new runtime dependencies (exactly 3 existing: `@clack/prompts`, `@toon-format/toon`, `smol-toml`)
- Dev dependencies: `typescript 7.0.2`, `@types/node 24.19.2`
- Node.js >=24, ESM (`"type": "module"`)

## Reversibility

All decisions are reversible within this phase (no published contracts, no migrations). No one-way-door decisions.
