# Transactional Installer and Codex Adapter Design

> Historische Evidenz - nicht normativ.

## Status and scope

This design prepares version 0.6.0 from exact base
`c4fa1b20dcea87a7b74882d7621da5828634766e`. It adds a distributable,
non-interactive installer consumer without changing the normative governance source:
`bundle/GOVERNANCE.md`, `bundle/agent-governance/manifest.toml`, and
`Installation.bootstrap.prompt.md` retain their existing authority. Codex is the only productive
harness adapter. OpenCode, Claude Code, and every other detected harness return a structured
`UNSUPPORTED` result without mutation.

The installer never targets the user's active installation during repository tests. Tests use an
explicit isolated home and allowed root. Merge, tag creation, release publication, registry
publication, and Issue #15 closure are outside this design.

## Confirmed baseline and problem

The repository currently has no root package or productive installer CLI. Its executable
installation contract is prose and its transaction implementation is a Python test reference.
The baseline has 322 passing unit tests plus a passing release-tree and whitespace check. Version
`0.5.0` is the single value in `VERSION`, so the next feature-bearing minor is `0.6.0`.

Official Codex documentation confirms that global instructions are discovered from the Codex home
as `AGENTS.override.md` or otherwise `AGENTS.md`, that user configuration is stored in
`config.toml`, and that lifecycle hooks are discovered from `hooks.json` or inline configuration.
It also confirms that multiple hook sources are additive and that non-managed command hooks require
trust. Therefore the adapter must inventory both global instruction names and both hook
representations, and must never claim universal interception or silently overwrite ambiguity.

## Considered approaches

### A. Minimal in-repository TypeScript core (selected)

Use Node built-ins for filesystem transactions, hashing, process control, and JSON. Keep TOML and
Markdown parsing narrow and schema-bound to the repository's own known structures. Runtime code has
no third-party dependency; TypeScript and Node type declarations are development-only and locked.
This keeps every productive write behind the installer's planner, staging, readback, and rollback
ports.

### B. Wrap `add-mcp`

The checked `add-mcp` package is Apache-2.0 and supports Codex TOML, but it is designed to write MCP
configuration for many harnesses, includes interactive and broad auto-detection behavior, and has
multiple runtime dependencies. Its direct upsert API does not supply the transaction-wide backup,
path-identity, instruction migration, runtime verification, or rollback guarantees required here.
Codex governance already uses a documented synchronous `PreToolUse` hook, so no MCP entry is needed
for 0.6.0. Adopting it would enlarge the supply chain without avoiding meaningful core logic.

### C. Deliver governance through `vercel-labs/skills`

The checked `skills` package is MIT and distributes demand-loaded agent skills. That lifecycle is
incompatible with governance that must be active before task classification and effects. It also
does not own Codex global instruction, hook, backup, or rollback semantics. It is rejected for this
release.

## Architecture

The package exposes a CLI and focused internal modules:

- **filesystem boundary** validates absolute allowed roots, every existing path component, regular
  file/directory types, symlink absence, and parent identity before mutation;
- **release verifier** validates `VERSION`, required release files, manifest paths, and a complete
  deterministic digest inventory generated from the release tree;
- **inspector/classifier** returns exactly `FRESH`, `CURRENT`, `LEGACY`, `UNKNOWN`, or
  `UNSUPPORTED` with evidence identifiers that contain no private content fingerprints;
- **planner** produces a stable JSON plan with explicit phases and resources before writes;
- **transaction engine** executes `inspect -> classify -> plan -> backup -> stage -> activate ->
  verify`, and enters an idempotent rollback path on any post-backup failure;
- **Codex adapter** owns only Codex home discovery, global instruction binding, hook binding, safe
  legacy recognition, and fresh-process verification;
- **CLI** exposes `inspect`, `plan`, `install`, `verify`, `rollback`, and `status` plus `--dry-run`,
  `--json`, explicit `--harness`, `--home`, `--allowed-root`, and `--release-root` options.

The installer state receipt is stored beneath the selected installation root. It contains public
release identity, planned resource identifiers, phase status, and rollback state, but never tokens,
private rule content, content hashes, sizes, or line counts. Machine output is deterministic apart
from explicitly identified transaction IDs and timestamps, which are absent from dry-run and
status output.

## Codex binding and data flow

The selected isolated Codex home must be an absolute non-symlink directory inside the explicit
allowed root. A fresh install stages the release payload below an installation directory, creates a
byte-identical global `AGENTS.md` binding to the staged `bundle/GOVERNANCE.md`, and creates a
`hooks.json` entry matching only `agent_governance__execute`. Existing unrelated hook groups remain
byte-semantically preserved. Existing `AGENTS.override.md`, conflicting global instructions,
inline hooks, duplicate governance hooks, unknown legacy imports, or unparseable hook JSON produce
`UNKNOWN` and stop before mutation.

Legacy migration recognizes only enumerated historical paths and exact import forms supported by
fixtures. It migrates personal rules byte-for-byte to the manifest-declared `local_rules` path and
removes an old active binding only after the new state verifies. Ambiguous rule ownership stops.
MCP configuration is inventoried but not changed because the required enforcement path is a Codex
hook. The result explicitly reports `mcpMutation: false` and `approvalExpansion: false`.

## Transaction and rollback guarantees

Before the first productive rename, all affected present objects and explicit absences are backed
up to a transaction directory outside active instruction names. Backup readback is bytewise and
mode-aware. Staging occurs under the same filesystem boundary as each activation target. Immediately
before activation, the engine rechecks parent identities and target types. Activation uses rename
within one filesystem; replacing multiple resources is transactionally coordinated and never
reported successful until complete readback and runtime verification pass.

On failure the engine restores present resources from verified backups, removes resources that were
previously absent, and verifies the restored state. Rollback can be repeated. If restore itself
fails, recoverable backup and retired paths remain in place and the structured error reports
`rollbackStatus: FAILED`; it never deletes the last recoverable copy.

## Error and result contract

Every failure contains a stable code, phase, abstract resource ID, safe cause, and rollback status.
Exit codes are: `0` success/current, `2` invalid invocation, `3` unsupported harness, `4` unknown or
unsafe state, `5` verification failure with successful rollback, and `6` rollback failure. Human
output is rendered from the same structured result as JSON output.

The implemented 0.6.0 core does not register signal handlers. `SIGTERM`, `SIGINT`, `SIGKILL`, host
power loss, and filesystem failure can interrupt activation. The receipt is created only after
successful verification, so a hard interruption before that point requires manual inspection of
the retained backup and retired paths; explicit `rollback` is supported after a completed install.

### Signal-recovery continuation

The completion slice replaces that limitation for catchable `SIGINT` and `SIGTERM`. A signal
coordinator registers one listener per signal for one productive install call, latches only the
first signal, and removes both listeners in `finally`. The handlers never perform filesystem work:
they only record interruption. Checkpoints before the first productive mutation, between atomic
renames, before verification, and before success serialization turn the latched signal into one
serialized rollback after any in-flight atomic operation completes. Repeated signals cannot start
a concurrent rollback.

After backup and staging have verified, but before activation, the installer atomically writes and
reads back a schema-2 receipt with state `PREPARED`. Successful verification advances it to
`COMMITTED`; successful rollback advances it to `ROLLED_BACK`. Therefore a catchable signal returns
structured interruption evidence and conventional exit status 130 (`SIGINT`) or 143 (`SIGTERM`),
while an uncatchable `SIGKILL`, runtime crash, or power loss leaves a validated `PREPARED` recovery
entry for an explicit later rollback. The journal does not claim to make interrupted multi-file
activation atomic, and post-crash recovery remains fail-closed if receipt, backup, targets, or path
boundaries cannot be validated.

## Test strategy

Each behavior change begins with a failing Node test. Unit and fixture tests cover every state,
manifest and digest tampering, traversal, symlinks at each boundary, unexpected file types,
conflicting roots and markers, backup/readback failure, phase-by-phase fault injection, personal
rule preservation, deterministic planning, activation, rollback, repeated rollback, idempotent
second install, hook preservation, no MCP or approval expansion, and unsupported harnesses.

Integration tests execute the built CLI against isolated temporary homes. A Codex fresh-session E2E
uses the repository's pinned Codex version only where credentials and the existing secure launcher
are available; CI runs the non-secret fixture matrix on Linux and macOS and keeps the existing
credentialed clean-Linux gate separate. Platform claims remain limited to the runners and exact
Codex version that actually pass.

CI adds Node 24 package install, format, typecheck, unit/integration tests, build, `npm pack --dry-run`
content inspection, `npm audit`, and Linux/macOS fixture jobs while preserving existing Python and
release checks. Documentation records dependency provenance, rejected candidates, enforcement
limits, migration, recovery, and release preparation without claiming publication.

## Self-review

The design has no placeholders. The selected architecture preserves one normative bootstrap
contract, keeps all foreign writers outside productive files, makes unsupported harness behavior
explicit, avoids an unnecessary MCP mutation, and maps every requested phase to a testable module.
The scope is large but cohesive: every component participates in one transactional Codex install
flow and one package artifact.
