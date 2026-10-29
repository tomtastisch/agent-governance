# Phase 15: Work-Item Lifecycle (Issue #54) — Context

**Created:** 2026-10-29
**Phase:** 15 — Work-Item Lifecycle (Issue #54)
**Spec:** `15-SPEC.md` — 13 requirements locked, ambiguity 0.09 (gate: ≤ 0.20)

## Domain

Agent Governance erhält eine kanonische, plattformneutrale Work-Item-Lifecycle-Semantik. Die Lifecycle-Engine ist eine reine Entscheidungs- und Validierungsebene: Sie nimmt einen aktuellen kanonischen Zustand + validiertes Event + Evidence entgegen, trifft eine Transition Decision und gibt einen kanonischen Folgezustand + Projection Plan aus. Die Engine selbst führt **keine** externen Schreibwirkungen durch (kein GitHub-Label-Apply, kein Issue-Close). Der Apply-Pfad wird separat über Issue #79 autorisiert und ausgeführt.

## Locked Requirements (from SPEC.md)

All 13 requirements from `15-SPEC.md` are locked and must not be re-discussed:

1. Lifecycle Authority — exactly one authority, separation of Classification/Display/Decision/Apply
2. work_started — work.ready → work.in_progress, authorized start after Current-State Resolution
3. work_blocked — work.in_progress → work.blocked, concrete blocker with scope/cause/evidence/resolution
4. work_resumed — work.blocked → work.in_progress, only with evidenced blocker resolution
5. work_completed — work.in_progress → work.completed, outcome met, tests/reviews passed, no blocking-valid findings
6. No false starts — materialization, planning, PR-existence, technical resume do not trigger work_started
7. Managed in-progress projection — start → `in-progress` label assignment; completion → removal; apply via #79
8. Slice isolation — slice start does not change parent lifecycle
9. No false completion — administrative closure, merge alone, missing evidence do not yield completion
10. Idempotency and ordering — identical inputs → identical decisions; idempotent events; fail-closed on stale/drift
11. Label from Projection-SSOT — label definition/color/aliases only from Projection-SSOT
12. No implicit tools/auth — missing tools/GitHub block only dependent gates; no implicit install/auth
13. Decision-only tests — null GitHub write calls; consumer integration verifies projection/auth/partial apply/read-back

## Canonical Refs

- `.planning/phases/15-work-item-lifecycle-issue-54/15-SPEC.md` — Locked requirements — MUST read before planning
- `/Users/tomtastisch/.agent-governance/releases/1.9.4/bundle/GOVERNANCE.md` — Canonical governance (GOV-001..006)
- `/Users/tomtastisch/.agent-governance/releases/1.9.4/bundle/agent-governance/manifest.toml` — Governance manifest (module routing)
- `/Users/tomtastisch/.agent-governance/releases/1.9.4/bundle/agent-governance/local/user-rules.md` — Local user rules (GSD, E2E, Hermes-Headless)
- `.planning/intel/SYNTHESIS.md` — Consolidated overview (19 LOCKED ADRs, ~168 requirements, ~101 constraints)
- `.planning/intel/decisions.md` — All 19 ADR decisions (LOCKED)
- `.planning/intel/constraints.md` — ~101 constraints by category
- `.planning/codebase/ARCHITECTURE.md` — Codebase architecture (8-layer, entry points, transactional installer)
- `.planning/codebase/STRUCTURE.md` — Codebase directory structure and naming conventions
- `.planning/codebase/CONVENTIONS.md` — Code style, naming, error handling, testing patterns

## Implementation Decisions

### 1. Lifecycle Engine Architecture

**Decision:** The lifecycle engine is a pure TypeScript module with no external side effects. It exposes a deterministic function:

```
transition(workItemId, event, currentState, evidence, eventId) → TransitionDecision
```

**Reasoning:** Issue #54 explicitly states "Lifecycle-Engine bleibt frei von GitHub-Schreibwirkungen" and "Transition Decision != externe Schreibfreigabe". The engine decides; the consumer (Issue #79) applies.

### 2. State Machine

**Decision:** Four states with explicit transitions:

| Event | From | To | Preconditions |
|-------|------|-----|---------------|
| work_started | work.ready | work.in_progress | authorized start, Current-State Resolution, unique identity, confirmed scope, start preconditions met |
| work_blocked | work.in_progress | work.blocked | concrete blocker with scope, cause, evidence, resolution |
| work_resumed | work.blocked | work.in_progress | evidenced blocker resolution only |
| work_completed | work.in_progress | work.completed | outcome met, acceptance criteria, tests/reviews passed, no blocking-valid findings, all effects verified |

**Reasoning:** Directly from Issue #54 transition contracts.

### 3. Transition Decision Structure

**Decision:** Every transition decision contains: work item ID, event, source state, target state, decision (approve/reject), present/missing evidence, reason, projection plan.

**Reasoning:** Issue #54: "Eine Transition Decision enthält mindestens Work Item, Event, Ausgangs-/Zielzustand, Entscheidung, vorhandene/fehlende Evidence, Grund und Projection Plan."

### 4. Idempotency & Ordering

**Decision:** Identical relevant inputs produce identical decisions. Already-applied identical events are idempotent. Expected source state and event ordering prevent lost updates and rollbacks from late events. Stale transitions and competing canonical authorities fail closed.

**Reasoning:** Issue #54 determinism/persistence requirements.

### 5. Managed in-progress Projection

**Decision:** The engine produces a deterministic projection plan (label `in-progress` assignment on start, removal on completion). The consumer applies it via Issue #79's shared Apply contract with read-back. Partial applies are tracked separately. No label writes happen inside the engine.

**Reasoning:** Issue #54: "Der operative Consumer wendet sie bei bestehender ziel- und wirkungsgebundener Autorisierung automatisch über den gemeinsamen Apply-Vertrag aus #79 an und liest sie zurück."

### 6. Evidence Requirements

**Decision:** Each transition requires documented evidence references. Audit evidence binds identity, previous/new state, event, decision, and secure evidence reference. No secrets, private prompt content, or derived fingerprints are stored (GOV-005).

**Reasoning:** Issue #54 evidence requirements + GOV-005.

### 7. Fail-Closed Behavior

**Decision:** Invalid transitions are rejected. Unknown or ambiguous classification blocks after GOV-004. Missing GitHub, tools, rights, or authentication block only the dependent gate — not the lifecycle semantics itself.

**Reasoning:** GOV-004 + Issue #54 ("Fehlendes GitHub, Pflichttool, Recht oder Authentifizierung blockiert ausschließlich die davon abhängige Wirkung beziehungsweise das Gate").

### 8. Codebase Integration Patterns

**Decision:** Follow existing codebase conventions:
- TypeScript ESM, Node >=24, entry via `src/cli.ts` → `dist/cli.js`
- Transactional installer pattern with phase checkpoints (inspect→plan→backup→stage→activate→verify→rollback)
- SignalCoordinator checkpoints with `try`/`catch`/`finally` and `coordinator.dispose()`
- Custom Error subclasses in `src/errors.ts`
- Structured JSON outcomes (`schemaVersion: 1`)
- `EXIT_CODES`/`exitCodeFor` from `src/contracts.ts`
- 2-space indent, semicolons, single quotes, `node:` built-in prefix, `.ts` extensions, `import type` for type-only
- Strict TS (`noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`)
- Tests via Node built-in `node:test` + `node:assert/strict`

**Reasoning:** Codebase conventions from `.planning/codebase/CONVENTIONS.md`, `ARCHITECTURE.md`, `STRUCTURE.md`.

### 9. Slice Isolation

**Decision:** A delivery slice has its own lifecycle. A parent receives the `in-progress` label only when the parent itself is actively worked on per its own work-start contract. An active child does not start the parent.

**Reasoning:** Issue #54 delivery-slices & parent section.

### 10. No GitHub Writes in Engine

**Decision:** The lifecycle engine performs zero GitHub API calls. Decision-only tests verify null GitHub write calls. Label projection is a separate consumer concern (Issue #79).

**Reasoning:** Issue #54: "Lifecycle-Engine bleibt frei von GitHub-Schreibwirkungen" and acceptance criterion 13.

## Deferred Ideas (for future phases)

- GitHub label apply implementation (Issue #79)
- Slice planning/materialization/aggregation (Issue #58)
- Technical resume engine
- Management CLI
- Rulesets for lifecycle enforcement
- Automatic tool installation/authentication

## Constraints

- `Lifecycle State != GitHub Label`
- `Lifecycle Event != Chatphrase`
- `Transition Decision != externe Schreibfreigabe`
- `work_started` consumed from Issue #55
- `resume_continuation` is NOT a lifecycle transition
- Materialization per Issue #57 or #79
- Planning per Issue #56
- `closed != completed`
- No GitHub write effect in Issue #54
- GitHub is not a general prerequisite for lifecycle semantics

## Acceptance Criteria (from SPEC.md, locked)

All 13 acceptance criteria from `15-SPEC.md` are locked and must be verified during execution.

---

*Phase: 15-work-item-lifecycle-issue-54*
*Context created: 2026-10-29*
*Next step: /gsd-plan-phase 15 — implementation planning (how to build what's specified above)*
