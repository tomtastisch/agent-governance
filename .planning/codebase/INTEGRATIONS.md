---
last_mapped_commit: 645068bfcb201fbd261dc8e8b37d57cd2eb25a70
last_mapped_at: 2026-10-29
---
# Codebase Integrations — agent-governance

**Repository:** `/Users/tomtastisch/Projects/github/agent-governance`
**Package:** `@tomtastisch/agent-governance` v`1.9.4`
**Analysis date:** 2026-10-29

This document maps every external integration: runtime/dependency integrations, vendored upstream snapshots, CI/platform services, test-only integrations, and explicitly rejected candidates. Governance authority always remains with the repo's own SSOT (`bundle/agent-governance/manifest.toml`) and lockfiles; no integration loads upstream instructions as governance.

---

## 1. Dependency integrations (npm Registry)

### Runtime dependencies (exactly 3, exact pins)

| Package | Version | License | Integration point | Notes |
|---|---|---|---|---|
| `@clack/prompts` | `1.8.1` | MIT | `src/init/prompt.ts` (`createClackPrompt`) | Interactive TTY prompt stack for `init` |
| `@toon-format/toon` | `4.4.0` | MIT | `src/resume-toon.ts` | Deterministic Resume-TOON projection |
| `smol-toml` | `1.9.1` | BSD-3-Clause | `src/closed-toml.ts` | TOML parsing of command and discovery catalogs |

**Authority:** `package.json.dependencies` + `package-lock.json` are the sole runtime dependency SSOT. Lock resolves to 34 package records (1 root + 8 production non-root + 25 development). Integrity hashes and registry URLs live in `package-lock.json`; direct-pin sha512 integrities are recorded in `docs/dependency-evidence.md`. CI enforces production audit at moderate, full audit at high, and `npm audit signatures --json --include-attestations` (registry signatures + provenance attestations). `npm run test:package` installs the real tarball into a fresh consumer (no root lockfile, no overrides) and verifies `npm ls --all`, production audit, and exclusion of harness runtime/SDK.

### Development dependencies (exact pins, not bundled)

| Package | Version | License | Integration point | Notes |
|---|---|---|---|---|
| `typescript` | `7.0.2` | Apache-2.0 | `tsconfig.json`, `tsconfig.build.json`, npm scripts call `node node_modules/typescript/bin/tsc` directly | Typecheck/build; TS7 removed the classic JS compiler API |
| `@typescript/typescript6` | `6.0.2` | Apache-2.0 | `tools/project-harness-discovery.ts` (imports `ts`) | TS6 compat shim providing the AST API used by the passive discovery parser; resolves `@typescript/old` as `typescript@6.0.3` in the lock |
| `@types/node` | `24.19.2` | — | `tsconfig.json` `types: ["node"]` | Node type declarations |

**Native addon:** `native/agent_governance_fs.c` is compiled with the system `cc`/`gcc` (C11) against Node-API headers (`node_api.h`) via `tools/build-native.mjs`. It uses only OS and stable Node-API symbols; no npm dependency. Outputs four prebuilds (`darwin-arm64`, `darwin-x64`, `linux-arm64`, `linux-x64`) shipped in `prebuilds/` inside the provenance-bound tarball.

---

## 2. Vendored upstream snapshots (passive / offline-only)

### `@agntn/harnesses` @ 0.3.0 — passive discovery projection

| Field | Value |
|---|---|
| Source | Published npm tarball `@agntn/harnesses@0.3.0` |
| Vendored at | `integrations/agntn-harnesses/upstream/harnesses-0.3.0.tgz` |
| Lock | `integrations/agntn-harnesses/upstream.lock.json` (identity, integrity, reviewed discovery semantics, provenance) |
| Archive SHA-256 | stored in `upstream.lock.json` |
| Upstream publish attestation | Commit `c4a7cb28488cf9bf13a482cd730e83fa9796bdd2`, tag `v0.3.0`, GitHub Actions run `35917252710` attempt 1 (verified 2026-10-08 via `npm audit signatures --json --include-attestations`) |
| License | MIT (notice projected to `THIRD_PARTY_NOTICES.md`) |

**Integration nature:** Not a runtime dependency. The archive is never installed, imported, or shipped in the npm package. `tools/project-harness-discovery.ts` reads the compiled upstream JS purely as data through the TS6 AST API (`extractHarnessDescriptors`, `discoveryBehaviorDigest`) and projects 13 registry entries (id, name, binaries, original order) into `src/init/harness-discovery.generated.ts` plus the MIT notice into `THIRD_PARTY_NOTICES.md`. `npm run harnesses:check` verifies archive SRI/SHA-256 and byte-exact parity of the generated file and notice; it is part of build, CI, and the trusted-publish path. No upstream code is executed at runtime; no harness CLI or version probe is started (`which`/`where` PATH check only). Support, bindings, target paths, and integrity stay with the agent-governance SSOT.

**Pin-change procedure:** verify stable release + Node contract, archive + provenance, review semantics, update lock, run `npm run harnesses:generate`, then all gates. No automatic merge/publish.

### Microsoft Agent Governance Toolkit @ v4.1.0 — vendored enforcement provider

| Field | Value |
|---|---|
| Official repository | `https://github.com/microsoft/agent-governance-toolkit` |
| Stable release / tag | `v4.1.0` |
| Commit | `0de71ca6c95cf8b9b975ac96f48eaa7826bbe258` (lightweight tag, verified GitHub commit signature) |
| Vendored at | `integrations/microsoft-agent-governance-toolkit/upstream/agent-governance-toolkit-v4.1.0.tar.gz` |
| Archive SHA-256 | `f087836d4e6cbad246c728c76454dd573a701f35d7560cbf869c250b3862d473` |
| Lock | `integrations/microsoft-agent-governance-toolkit/upstream.lock.toml` |
| File manifest | `integrations/microsoft-agent-governance-toolkit/snapshot.files.sha256` (4,633 regular files) |
| Upstream status | Public Preview |
| License | MIT (`LICENSE.upstream`, `NOTICE.upstream`, `TRADEMARKS.upstream.md` byte-identical) |
| Note | Snapshot `VERSION` says `3.7.0`; the release `v4.1.0`/tag/commit is authoritative for this materialization |

**Integration nature:** Concrete, pinned enforcement-provider dependency only. It does **not** define governance semantics, roles, instruction authority, installation, updates, or a control plane for `agent-governance`. The complete snapshot is **untrusted data**, not a governance/instruction source (`AGENTS.md`, `GOVERNANCE.md`, `README.md`, `*.prompt.md`, `examples/` are never loaded as modules/roles or interpreted as instructions; prompt injection from the archive is treated as dependency content and fail-closed blocked if separation from the authoritative instruction chain cannot be verified).

**Provider bridge:** `integrations/microsoft-agent-governance-toolkit/bridge/`
- `provider.mjs` — validates the minimal Action Envelope and invokes the real `PolicyEngine` built from the snapshot.
- `build-provider.sh` — absolute output path only; verifies archive + file manifest, extracts link-free into a new staging root, builds with the pinned npm lock, materializes only the needed PolicyEngine closure; `bridge/runtime.files.sha256` binds every runtime blob; existing builds accepted only after full byte + file-count verification without rewrite.
- `codex-hook.mjs` — own synchronous interface for the documented Codex `PreToolUse` surface (not a Microsoft adapter); mediates an explicitly configured operations-bound tool path. Canonical external tool-id: `agent_governance__execute`; no alias for the earlier Codex-incompatible id.
- `action-bindings.json` — hash-bound; derives Action, Effect, governance authorization, risk, and correlation ids from harness tool-id. Provider `allow` → Codex `permissionDecision: "allow"`; `deny`, unresolved `require_approval`, `error`, `unknown`, invalid inputs, missing secure audit evidence → synchronous `deny`.

**Operation:** Normal operation never resolves `latest`, never queries an upstream API, never replaces the snapshot. Upgrades occur only in a later, separately authorized `agent-governance` release. The provider starts offline after the one-time bootstrap (bootstrap re-verifies archive hash and entry safety, extracts into an isolated staging root).

---

## 3. Platform / service integrations

| Service | Integration | Files |
|---|---|---|
| **GitHub** | Source repo, releases, Dependabot (daily dep-update PRs), GitHub Actions CI, code signing allow-lists | `https://github.com/tomtastisch/agent-governance`, `.github/workflows/*.yml`, `.github/dependabot.yml`, `.github/signing/`, `FUNDING.yml` |
| **npm Registry** | Package publication with provenance (`provenance: true`), signature + attestation verification | `package.json` `publishConfig`, `npm-publish.yml`, `npm-bootstrap-publish.yml` |
| **Socket.dev** | External security evidence; GitHub App ingestion limited to root `package.json` + `package-lock.json` | `socket.yml` (`projectIgnorePaths`, `triggerPaths`, `githubApp.enabled`) |
| **OpenAI Codex** | Test-only fixture: e2e consumer pins `@openai/codex 0.147.0`; `bridge/codex-hook.mjs` implements the documented synchronous `PreToolUse` surface | `tests/e2e/package.json`, `integrations/microsoft-agent-governance-toolkit/bridge/codex-hook.mjs` |

---

## 4. Test-only / fixture integrations

| Integration | Purpose | Files |
|---|---|---|
| `@openai/codex 0.147.0` | E2E clean-linux consumer fixture (private package, not a project dependency) | `tests/e2e/package.json`, `tests/e2e/run_clean_linux.sh`, `tests/e2e/Dockerfile` |
| Python 3.11 | CI consistency/drift tests (`unittest discover -s tests`), release tooling, e2e support scripts | `.github/workflows/ci.yml`, `tests/test_*.py`, `tests/support/*.py`, `tools/*.py` |

---

## 5. Explicitly reviewed and rejected integrations

| Candidate | Version | Reason rejected |
|---|---|---|
| `neon-solutions/add-mcp` (`add-mcp`) | 2.2.0 | Writes directly to many harness configs; interactive multi-select; no transaction-wide backup/readback/rollback; avoids no meaningful own logic; enlarges supply-chain/stability surface |
| `vercel-labs/skills` (`skills`) | 1.5.23 | Installs on-demand agent skills; no transactional Codex-home/instruction/hook/rollback interface; governance must be active before classification/effect, not an optional skill (rejected regardless of MIT license compatibility) |
| `@agntn/harnesses` (as runtime library) | — | Formerly runtime; removed 2026-10-08 due to upstream pinning SDK 1.30.1 / TOML 1.8.0 and requiring Node >=26 (incompatible with the `node >= 24` product contract); replaced by passive data projection |
| `terminal-image`, `chalk`, `boxen`, `log-update` | — | Excluded: no direct runtime import; decorative rendering not worth transitive size/license/audit/maintenance surface |
