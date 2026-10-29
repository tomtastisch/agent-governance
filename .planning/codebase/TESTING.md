---
analysis_date: 2026-10-29
repository: https://github.com/tomtastisch/agent-governance
package: @tomtastisch/agent-governance
version: 1.9.4
scope: tests/installer/**/*.test.ts, tests/*.py, tests/fixtures/
last_mapped_commit: 645068bfcb201fbd261dc8e8b37d57cd2eb25a70
last_mapped_at: 2026-10-29
---

# Testing Conventions — agent-governance

**Analysis Date:** 2026-10-29

## 1. Test Framework

- Runner: Node built-in `node:test`
- Assertion library: `node:assert/strict` (`assert.equal`, `assert.deepEqual`, `assert.ok`)
- Invocation: `node --experimental-strip-types --test tests/installer/*.test.ts`
- npm script: `npm test` (runs `build:native` first, then the test glob)
- TypeScript tests run with type stripping — no separate compile step for tests
- Typecheck: `npm run typecheck` = `tsc -p tsconfig.json --noEmit`; `tsconfig.json` include covers `tests/installer/**/*.ts`
- Test file glob: `tests/installer/*.test.ts` (suffix `.test.ts`)

## 2. Test Structure & Placement

- Unit tests live in `tests/installer/`, one file per source module:
  - `cli.test.ts` → `src/cli.ts`
  - `transaction.test.ts` → `src/transaction.ts`
  - `native-filesystem.test.ts` → `src/native-filesystem.ts`
  - `release.test.ts`, `replacement.test.ts`, `resume-checkpoint.test.ts`, `work-items.test.ts`, `ssot-manifest.test.ts`, `signals.test.ts`, `target.test.ts`, `planner.test.ts`, `command-catalog.test.ts`, `contracts.test.ts`, `conformance.test.ts`, `filesystem.test.ts`, `managed-block.test.ts`, `public-commands-contract.test.ts`, `resume-resolve.test.ts`, `resume-toon.test.ts`, `templates-catalog.test.ts`, `tool-preparation-review.test.ts`, `transaction-architecture.test.ts`, `init-*.test.ts`, `harness-projection.test.ts`, `pack-verifier.test.ts`, `build-toolchain.test.ts`, `catalog-oracles.test.ts`, `init-branding.test.ts`
- Each `test("description", async () => { ... })` is a top-level registration in `node:test`
- Arrange-act-assert inside test bodies
- Fixture for isolated roots: `createTestRoot(prefix)` from `tests/fixtures/installer/workspace.ts` (e.g. `createTestRoot("agent-governance-cli-")`)
- Python suite under `tests/*.py` (e.g. `test_governance.py`, `test_bundle.py`, `test_catalogs.py`, `test_release_check.py`, `test_ci_workflow.py`, `test_documentation.py`, `test_sync_version.py`) — separate runner, not part of `npm test`
- E2E script: `tests/e2e/run_package_consumers.sh` (run via `npm run test:package`)

## 3. Mocking & Test Doubles

- No mocking library — no vitest/jest/sinon, no `vi.mock`; mocking is manual
- Primary technique: dependency injection. Modules accept `dependencies` / `deps` objects; tests pass fakes
  - Example: `createMockDeps(overrides)` builds `GhPreparationDependencies` with stub functions (`tests/installer/gh-preparation-mocked.test.ts`)
  - CLI tests inject `CliDependencies` (`createTransaction`, `init`, `initPrompt`, `prepareTools`, `initOptions`) into `runCli` (`tests/installer/cli.test.ts`)
- Prototype monkey-patching for method stubs, restored in `finally`:
  - `InstallerTransaction.prototype[command] = async () => result(command) as never;` then `Object.assign(InstallerTransaction.prototype, { [command]: original })`
  - `as never` casts used when replacing prototype methods
- Spies via closure counters: `let transactionCalls = 0;` / `initCalls += 1;`, asserted with `assert.equal`
- Captured output via Writer callbacks: `const output: string[] = []; ... (value) => output.push(value)`; errors via `(value) => errors.push(value)`
- Deterministic CLI invocation: `--non-interactive --json` flags; synthetic environments (`environment: { home: "/synthetic/home", platform: "linux" }`, `isTTY: true/false`)
- Env override with restore in `finally`: `process.env.HOME = ...; finally { ... process.env.HOME = previousHome; }`

## 4. Coverage

- No coverage tool configured — no c8, nyc, vitest coverage, or jest
- `npm test` reports pass/fail only; no coverage threshold enforced
- `lint` does not measure tests; `typecheck` is the static gate

## 5. Test Writing Rules

- Use `assert.equal` (strict equality), `assert.deepEqual` for objects, `assert.ok` for truthiness
- Restore all mutated prototypes / globals in `finally`
- Non-TTY and TTY paths both exercised (e.g. CLI default init tests)
- Failure-path tests assert exit codes (`2`, `4`, `5`, `130`, `143`) and structured JSON outcomes (`INVALID_INVOCATION`, `UNSAFE_STATE`, `VERIFICATION_ROLLED_BACK`, `INTERRUPTED`)
- Assert no secret content leaks in errors (e.g. `errors.some((value) => /token|secret/i.test(value))` is `false`)
