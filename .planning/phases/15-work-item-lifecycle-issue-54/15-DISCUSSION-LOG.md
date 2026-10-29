# Phase 15: Work-Item Lifecycle (Issue #54) — Discussion Log

**Created:** 2026-10-29
**Mode:** auto (no user interaction — decisions derived from SPEC.md, Issue #54, Governance 1.9.4, Intel files)
**SPEC:** 15-SPEC.md — 13 requirements locked, ambiguity 0.09

## Discussion Summary

No interactive discussion was performed. All implementation decisions were derived directly from:

1. `15-SPEC.md` — locked requirements, acceptance criteria, edge coverage, prohibitions
2. Issue #54 — Work-Item Lifecycle specification (states, events, transitions, evidence, projections)
3. Governance 1.9.4 — GOV-001..006, EVD-001..004, WFL-001..005, TOL-001..004
4. `.planning/intel/SYNTHESIS.md` — consolidated overview (19 LOCKED ADRs, ~168 requirements, ~101 constraints)
5. `.planning/codebase/*` — codebase architecture, structure, conventions, concerns maps

## Decisions Captured

| Area | Decision |
|------|----------|
| Engine architecture | Pure TypeScript module, zero side effects, no GitHub writes |
| State machine | 4 states (ready/in_progress/blocked/completed), 4 transitions |
| Transition decision | Contains work item, event, source/target state, decision, evidence, reason, projection plan |
| Idempotency & ordering | Identical inputs → identical decisions; idempotent events; fail-closed on stale/drift |
| Managed in-progress projection | Engine produces plan; consumer applies via Issue #79 with read-back |
| Evidence | Audit evidence binds identity, states, event, decision, reference; no secrets (GOV-005) |
| Fail-closed | Invalid transitions rejected; missing GitHub/tools/auth block only dependent gates |
| Codebase patterns | TypeScript ESM, transactional installer, SignalCoordinator, custom errors, structured JSON |
| Slice isolation | Slice has own lifecycle; parent label only on own active work |
| No GitHub writes | Decision-only tests verify null GitHub write calls |

## Deferred Ideas

- GitHub label apply implementation → Issue #79
- Slice planning/materialization/aggregation → Issue #58
- Technical resume engine
- Management CLI
- Rulesets for lifecycle enforcement
- Automatic tool installation/authentication

## Next Step

`/gsd-plan-phase 15` — implementation planning (TDD: RED → GREEN → REFACTOR, test-first per WFL-005)
