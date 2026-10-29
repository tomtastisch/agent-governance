---
analysis_date: 2026-10-29
repository: https://github.com/tomtastisch/agent-governance
package: @tomtastisch/agent-governance
version: 1.9.4
scope: src/**/*.ts, tests/installer/**/*.test.ts, tools/*.{ts,mjs}
last_mapped_commit: 645068bfcb201fbd261dc8e8b37d57cd2eb25a70
last_mapped_at: 2026-10-29
---

# Code Conventions — agent-governance

**Analysis Date:** 2026-10-29

## 1. Language & Runtime

- Language: TypeScript, ESM (`"type": "module"` in `package.json`)
- Runtime: Node >=24 (`engines.node: ">=24"`)
- Entry point: `src/cli.ts` (shebang `#!/usr/bin/env node`, binary `dist/cli.js`)
- Build output: `dist/` via `tsc -p tsconfig.build.json` (declarations + sourcemaps, `rootDir: src`, excludes `tests`)
- Native component: `native/agent_governance_fs.c`, compiled by `tools/build-native.mjs`
- tsconfig (`tsconfig.json`): target ES2022, module `NodeNext`, moduleResolution `NodeNext`, `strict: true`, `noUncheckedIndexedAccess: true`, `exactOptionalPropertyTypes: true`, `allowImportingTsExtensions: true`, `rewriteRelativeImportExtensions: true`, `skipLibCheck: true`
- `tsconfig.json` include: `src/**/*.ts`, `tests/installer/**/*.ts` (typecheck covers installer tests)

## 2. Import & Module Style

- Built-ins always use the `node:` prefix: `import { lstat, realpath } from "node:fs/promises";` (`src/filesystem.ts`)
- Relative imports carry the `.ts` extension: `import { InstallerFailure } from "./errors.ts";` (`src/cli.ts`)
- Type-only imports use `import type`: `import type { InstallPhase } from "./contracts.ts";`
- Submodule directories under `src/`: `init/`, `installer/`, `terminal/`
- Package exports map in `package.json`: `./replacement`, `./resume-checkpoint`, `./resume-toon`, `./work-items`

## 3. Formatting

- 2-space indentation, semicolons, single-quoted strings
- Trailing commas in multi-line calls/objects (e.g. `createClackPrompt({ ..., environment: process.env, });` in `src/cli.ts`)
- Template literals for interpolation: `` `unknown option ${String(option)}` ``
- No ESLint/Prettier/EditorConfig found in repo. `lint` script = `tsc -p tsconfig.json --noEmit && git diff --check`, so type-cleanliness and git diff cleanliness are the only enforced checks
- Top-level executable guard in `src/cli.ts`: `if (process.argv[1] !== undefined && fileURLToPath(import.meta.url) === realpathSync(process.argv[1])) process.exitCode = await runCli(process.argv.slice(2));`

## 4. Naming

- Classes: PascalCase — `InstallerTransaction`, `InstallerFailure`, `InterruptedFailure`, `ConcurrentEntryChange`, `SignalCoordinator`
- Functions / methods: camelCase — `runCli`, `parse`, `validateAllowedPath`, `captureIdentity`, `assertIdentity`
- Variables / properties: camelCase — `transaction`, `helpTheme`, `releaseRoot`, `output`
- Constants: UPPER_SNAKE — `VALUE_OPTIONS`, `EXIT_CODES`
- Types / interfaces: PascalCase — `CliDependencies`, `PathIdentity`, `InstallerRequest`, `TerminalOutcome`
- Type aliases: PascalCase — `PathExpectation`, `InitSubcommand`, `Writer`
- Files: kebab-case — `cli.ts`, `resume-checkpoint.ts`, `gh-preparation-mocked.test.ts`, `project-harness-discovery.ts`
- Test files: `*.test.ts` under `tests/installer/`

## 5. Types

- Strict TypeScript throughout; prefer `interface` for object shapes (`CliDependencies`, `PathIdentity`, `InstallResult`), `type` for unions and primitives (`PathExpectation = "file" | "directory" | "missing" | "any"`)
- `readonly` properties preferred: `readonly code: string;`, `readonly phase: InstallPhase;`
- Constrained unions via `Exclude<...>`: `readonly outcome: Exclude<TerminalOutcome, "SUCCESS">;`
- Non-null assertion `!` used only where control flow guarantees presence (`values.get("--target-root")!`, `output.at(-1)!`)
- `void` return for procedures, `Promise<void>` for async procedures

## 6. Error Handling

- Custom `Error` subclasses in `src/errors.ts`:
  - `InstallerFailure` — carries `code`, `phase`, `resourceId`, `outcome` (non-SUCCESS), `rollbackStatus` (`NOT_REQUIRED | SUCCEEDED | FAILED`)
  - `InterruptedFailure extends InstallerFailure` — `signal: CatchableSignal`, `exitCode: 130 | 143` (SIGINT → 130, SIGTERM → 143), optional `externalEffect`
  - `ConcurrentEntryChange` — tamper-detection failure during mutation
- Structured error output: JSON with `schemaVersion: 1`, `outcome`, `phase`, `resourceId`, `rollbackStatus`, `code`, `error`, written through `out`/`error` `Writer` callbacks (`src/cli.ts` catch block)
- Exit codes from `EXIT_CODES` / `exitCodeFor` in `src/contracts.ts`
- Signal handling via `SignalCoordinator` + `SignalInterruption` in `src/signals.ts`; checkpoints with `coordinator.checkpoint("plan")`, disposed in `finally`
- `try` / `catch` / `finally`; `finally { coordinator.dispose(); }` pattern in `src/transaction.ts`
- Failures converted to structured outcomes rather than propagating to the CLI top level where possible
- Fault injection for testability: `private fault(phase): void { if (this.request.faultAfter === phase) throw new Error(\`injected failure after ${phase}\`); }` (`src/transaction.ts`)

## 7. Patterns

- Dependency injection via options object: `CliDependencies` passed to `runCli(argv, out, error, dependencies)`, falling back to real implementations with `??` (`src/cli.ts`)
- Writer callbacks: `type Writer = (value: string) => void;`, defaults `out = console.log`, `error = console.error`
- Result shape: `{ schemaVersion: 1, outcome, state, phase, rollbackStatus, capabilities }` — `InstallResult` (`src/contracts.ts`)
- Early guard clauses: unknown command throws, missing/duplicate required options throw, unknown options throw
- Atomic file operations: `atomicCreate`, `atomicWrite`, `atomicRemove` in `src/installer/mutation.ts`
- Tamper detection via identity capture: `captureIdentity` / `assertIdentity` in `src/filesystem.ts` (device/inode/mode with `bigint: true`)
- Backup-before-mutate with readback verification in `src/transaction.ts` `performMutation`

## 8. Not Enobserved (no config / convention found)

- No ESLint, no Prettier, no `.editorconfig`
- No barrel `index.ts` files
- No mandatory JSDoc requirement observed
