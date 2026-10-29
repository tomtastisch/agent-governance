---
last_mapped_commit: 645068bfcb201fbd261dc8e8b37d57cd2eb25a70
last_mapped_at: 2026-10-29
---
# Codebase Stack Map — agent-governance

**Repository:** `/Users/tomtastisch/Projects/github/agent-governance`
**Package:** `@tomtastisch/agent-governance` v`1.9.4` (`VERSION`, `package.json`)
**Analysis date:** 2026-10-29
**License:** Apache-2.0 (`LICENSE`)
**Homepage:** https://github.com/tomtastisch/agent-governance#readme

---

## 1. Languages

| Language | Role | Key files / directories |
|---|---|---|
| TypeScript | Primary application language (ESM modules) | `src/**/*.ts` (~48 files), `tests/installer/**/*.ts`, `tools/project-harness-discovery.ts` |
| Python | CI/release gates, e2e support, root test suite | `tools/*.py` (`release_check.py`, `release_manifest.py`, `site_build.py`, `socket_freshness.py`, `sync_citation.py`, `sync_version.py`, `prepare_release.py`), `tests/support/*.py`, `tests/test_*.py` |
| C (C11, Node-API) | Native filesystem security addon | `native/agent_governance_fs.c` |
| Shell | E2E fixture / entrypoint scripts | `tests/e2e/*.sh`, `tests/e2e/container_entrypoint.sh` |
| JSON | Package manifest, lockfile, contracts, test schemas | `package.json`, `package-lock.json`, `contracts/governance-contract.json`, `tests/contracts/*.json`, `tests/e2e/*.schema.json` |
| TOML | Governance SSOT manifest, upstream lock | `bundle/agent-governance/manifest.toml`, `integrations/*/upstream.lock.toml` |
| YAML | GitHub Actions workflows, Socket.dev config | `.github/workflows/*.yml`, `socket.yml` |
| Markdown | Docs, decisions, third-party notices | `docs/**/*.md`, `README.md`, `CHANGELOG.md`, `THIRD_PARTY_NOTICES.md` |
| HTML/CSS | GitHub Pages site | `site/*.html`, `site/assets/site.css` |

---

## 2. Runtime & module system

- **Runtime:** Node.js, engine requirement `node >= 24` (`package.json` `engines.node`).
- **Module system:** ESM (`"type": "module"`), entry `dist/cli.js` exposed via the `agent-governance` bin.
- **Compiled output:** `dist/` (built by `tsc`; `tsconfig.json` for dev, `tsconfig.build.json` for release with `declaration`/`sourceMap`).
- **TS config highlights** (`tsconfig.json`): `target ES2022`, `module NodeNext`, `moduleResolution NodeNext`, `strict: true`, `noUncheckedIndexedAccess: true`, `exactOptionalPropertyTypes: true`, `allowImportingTsExtensions: true`, `rootDir .`, `outDir dist`, `skipLibCheck: true`, includes `src/**/*.ts` and `tests/installer/**/*.ts`.
- **Tests run with:** `node --experimental-strip-types --test tests/installer/*.test.ts` (Node test runner, type-stripped TS).

---

## 3. Build toolchain

| Tool | Purpose | Invocation |
|---|---|---|
| `tsc` (TypeScript 7.0.2) | Typecheck + emit | `node node_modules/typescript/bin/tsc -p tsconfig.json --noEmit`; release build `tsc -p tsconfig.build.json` |
| `cc`/`gcc` (C11) | Native Node-API addon compile | `tools/build-native.mjs` → `prebuilds/<platform>-<arch>/agent_governance_fs.node` |
| `npm` | Install, pack, audit, publish | `npm ci --ignore-scripts`, `npm pack --dry-run`, `npm audit ...`, `npm publish` |
| `python3` | Release gates, CI support | `tools/release_check.py`, `tools/release_manifest.py`, etc. |

Native addon targets (built in CI `native-platform` matrix): `darwin-arm64`, `darwin-x64`, `linux-arm64`, `linux-x64`, all on Node 24. Artifacts land in `prebuilds/` and ship inside the provenance-bound npm tarball.

---

## 4. Dependencies

### Runtime dependencies (exactly 3, exact pins)

| Package | Version | License | Purpose |
|---|---|---|---|
| `@clack/prompts` | `1.8.1` | MIT | Interactive prompt stack (`src/init/prompt.ts`, `createClackPrompt`) |
| `@toon-format/toon` | `4.4.0` | MIT | Deterministic Resume-TOON projection (`src/resume-toon.ts`) |
| `smol-toml` | `1.9.1` | BSD-3-Clause | TOML parsing for command and discovery catalogs (`src/closed-toml.ts`) |

`package-lock.json` resolves `34 = 1 root + 8 production (non-root) + 25 development` package records. Production-audit gate: moderate; full audit gate: high; signature/provenance attestation checked via `npm audit signatures --json --include-attestations`.

### Development dependencies (exact pins, not bundled in runtime package)

| Package | Version | License | Purpose |
|---|---|---|---|
| `typescript` | `7.0.2` | Apache-2.0 | Typecheck/build compiler |
| `@typescript/typescript6` | `6.0.2` | Apache-2.0 | TS6 compat shim for the discovery-parser AST API (TS7 removed the classic JS compiler API) |
| `@types/node` | `24.19.2` | — | Node type declarations (`types: ["node"]`) |

### Notable non-adopted candidates (reviewed, rejected)
- `@agntn/harnesses` — formerly a runtime dep; now a **passive discovery projection only**, tarball vendored at `integrations/agntn-harnesses/upstream/harnesses-0.3.0.tgz`, no runtime code loaded.
- `terminal-image@5.0.1`, `chalk`, `boxen`, `log-update` — excluded (no direct runtime import).
- `neon-solutions/add-mcp` (`add-mcp` 2.2.0) — rejected (no transactional backup/readback/rollback).
- `vercel-labs/skills` (`skills` 1.5.23) — rejected (no transactional governance interface).

### Native component
`native/agent_governance_fs.c` (323 lines) uses only OS and stable Node-API (`napi.h`) symbols. Exports: `secureRenameNoReplace`, `secureCreateNoReplace`, `secureCreateDirectory`, `secureWriteFile`, `secureRemoveFile`, `secureRemoveDirectory`, `secureRenameDirectoryNoReplace`. Directory-relative, identity-validated (`dev`/`ino` snapshot checks), `O_EXCL\|O_NOFOLLOW`, `fsync`, Linux `renameat2(RENAME_NOREPLACE)` / Darwin `renameatx_np(RENAME_EXCL)`. Built for Darwin/Linux on arm64/x64 only.

---

## 5. Configuration files

| File | Purpose |
|---|---|
| `package.json` | Manifest, bin, exports (`./replacement`, `./resume-checkpoint`, `./resume-toon`, `./work-items`), engines, scripts |
| `package-lock.json` | Exact dependency lock / SSOT for runtime dependency tree |
| `tsconfig.json` / `tsconfig.build.json` | TypeScript compiler config (dev / release emit) |
| `socket.yml` | Socket.dev GitHub App config; limits ingestion to root `package.json` + `package-lock.json` |
| `bundle/agent-governance/manifest.toml` | Governance SSOT: modules (invariants, enforcement, evidence, workflow, architecture, verification, delivery, security, tool_routing, templates, context, resume), roles (architecture, triage, quality_assurance, security_review), routing (`unknown = block`, `ambiguous = block`) |
| `VERSION` / `CHANGELOG.md` | Release version (`1.9.4`) and changelog |
| `release.files.sha256` | Release artifact integrity |
| `.github/dependabot.yml` | Daily dependency update checks |
| `.github/workflows/ci.yml` | CI pipeline (see §7) |
| `.github/copilot-instructions.md`, `FUNDING.yml`, `signing/` | Repo metadata, code-signing allow-lists |

---

## 6. Source layout (key entry points)

- `src/cli.ts` — CLI entry (`runCli`, command parsing, JSON/dry-run/non-interactive modes, exit codes).
- `src/command-catalog.ts`, `src/public-commands.ts` — public command definitions and handlers.
- `src/contracts.ts` / `src/governance-contract.ts` — command + governance contract types.
- `src/installer/*.ts` — installer core (context, contracts, latest release, local rules, locking, mutation, receipts, recovery, release staging, replacement guards/validation, snapshot, version).
- `src/init/*.ts` — init flow (bindings, branding, generated harness discovery, harnesses, orchestrator, prompt, support, theme, tool-preparation, types).
- `src/transaction.ts` — installer transaction with rollback.
- `src/work-items.ts`, `src/replacement.ts`, `src/resume-checkpoint.ts`, `src/resume-resolve.ts`, `src/resume-toon.ts`.
- `src/planner.ts`, `src/release.ts`, `src/target.ts`, `src/signals.ts`, `src/managed-block.ts`, `src/native-filesystem.ts`, `src/filesystem.ts`, `src/errors.ts`, `src/ssot-manifest.ts`, `src/routing-catalog.ts`, `src/templates-catalog.ts`, `src/catalog-paths.ts`, `src/terminal/theme.ts`.
- `src/init/harness-discovery.generated.ts` — generated discovery metadata (`HARNESS_DISCOVERY`), regenerated by `tools/project-harness-discovery.ts`.
- `tests/installer/*.test.ts` — installer unit tests (Node test runner).
- `tests/e2e/*.sh`, `tests/e2e/Dockerfile` — end-to-end fixtures (clean Linux, Codex local rules, init PTY, installer fixture, package consumers, release verifier, neutral harness, offline/materialized paths).
- `tests/support/*.py` + root `tests/test_*.py` — Python unittest suite (governance, routing, socket freshness, CI workflow, site, bundle, etc.).
- `tools/*.mjs` / `tools/*.py` — build-native, pack-verifier, license-verify, harness discovery, release checks/manifest, site build, sync tools.

---

## 7. CI/CD (`.github/workflows/`)

| Workflow | Purpose |
|---|---|
| `ci.yml` | Blocking consistency pipeline: native build on 4 platform/arch targets (Node 24), native package assembly, installer package tests (ubuntu/macos × Node 24/26: typecheck, test, build, `npm audit` moderate+high, signature attestation, license check, pack check, tarball consumer test, e2e fixtures), Python unittest consistency/drift tests, neutral-harness/offline path, release metadata, remote doc link checks, release validation on publish |
| `npm-publish.yml` / `npm-bootstrap-publish.yml` | npm publish with provenance |
| `pages.yml` | GitHub Pages site build/deploy |
| `release-tag-verify.yml` | Release tag verification |
| `socket-freshness.yml` | Socket.dev freshness check |

Key CI gates: `npm run typecheck`, `npm test`, `npm run build`, `python3 tools/release_manifest.py check`, `npm run harnesses:check`, `npm audit --omit=dev --audit-level=moderate`, `npm audit --audit-level=high`, `npm audit signatures --json --include-attestations`, `npm run license:check`, `npm run pack:check`, `npm run test:package`.

---

## 8. Testing

- **Installer unit tests:** `tests/installer/*.test.ts` (~40 files: cli, contracts, filesystem, transaction, replacement, resume, planner, harnesses, init-*, native-filesystem, pack-verifier, etc.), run with `node --experimental-strip-types --test`.
- **Typecheck:** `npm run typecheck` (`tsc --noEmit`).
- **Lint:** `npm run lint` (typecheck + `git diff --check`).
- **E2E fixtures:** `tests/e2e/*.sh` incl. `run_installer_fixture.sh`, `run_package_consumers.sh` (real tarball in fresh consumer), `run_release_verifier_fixture.sh`, `run_neutral_harness.sh`, `run_materialized_offline.sh`; fixture manifest `tests/e2e/package.json` pins `@openai/codex 0.147.0`.
- **Python test suite:** `python3 -m unittest discover -s tests` (root `tests/test_*.py` + `tests/support/` helpers).
- **Native addon tests:** `tests/installer/native-filesystem.test.ts`, exercised per CI platform matrix against built `.node` prebuilds.
