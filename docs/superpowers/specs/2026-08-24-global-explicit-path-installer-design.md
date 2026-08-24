# Global Explicit-Path Installer Design

## Status and decision

This specification records the user-approved `GLOBAL_EXPLICIT_PATH_MANAGED_BLOCK` architecture
for the first public `@tomtastisch/agent-governance` release. It supersedes the unpublished
Codex-only installer design. The governance bundle remains the only normative source; the
installer materializes a reproducible projection that points to the installed bundle.

## Scope

The package provides a global, non-interactive, zero-runtime-dependency Node.js CLI. Every target
is explicit: an absolute canonical `--target-root`, a relative Markdown `--entry-file`, global
`--scope`, and an absolute canonical `--installation-root`. The runtime contains no harness names,
presets, detection, adapters, hooks, MCP mutation, approval logic, or harness-specific parsers.

The supported commands are `inspect`, `plan`, `install`, `verify`, `status`, `update`, `uninstall`,
and `rollback`. Mutating commands support `--dry-run`; all commands support deterministic JSON and
non-interactive operation. Unknown options, duplicate values, relative roots, root escape,
symlinks, non-Markdown entries, unexpected file types, ambiguous markers, inventory drift, and
identity changes fail closed before productive mutation.

## Installed layout and release integrity

`<installation-root>/releases/<version>/bundle` contains the verified release bundle,
`<installation-root>/current.json` atomically identifies the active version and digests, and
`<installation-root>/backups` contains immutable per-transaction backups and receipts. A metadata
file is preferred over a `current` symlink so trusted internal links and untrusted target links do
not share one validation path.

The package ships a closed inventory of the governance payload. Verification rejects missing
inventory entries, additional normative files, traversal, links, non-regular payload files,
oversized files, duplicate paths, unsupported manifest shape, and digest mismatch. Staging is on
the destination filesystem. Activation uses write-with-exclusive-create, readback, atomic rename,
directory identity revalidation, and a durable receipt; no active pointer or entry file changes
before the staged release and backup have both been verified.

## Managed block

The entry contains at most one block delimited by:

```text
<!-- BEGIN AGENT_GOVERNANCE_MANAGED_V1 -->
<!-- END AGENT_GOVERNANCE_MANAGED_V1 -->
```

The generated body identifies itself as a projection and records the governance version,
canonical installation root, normative bootstrap and manifest paths, their expected SHA-256
digests, the mandatory pre-response load order, separation of personal local rules, and
fail-closed behavior. It is derived solely from the verified installed release.

Bytes outside the block are preserved exactly. Existing LF or CRLF is retained; a new file uses
UTF-8 without BOM and LF. Duplicate, incomplete, nested, or foreign-version markers are rejected.
`verify` compares the exact deterministic block. `update` replaces only that block. `uninstall`
removes only that block. Rollback restores the complete pre-mutation entry bytes.

## Transaction and recovery

Before the first productive mutation, the installer captures target identities and writes a
byte-for-byte backup, reads it back, and records whether each resource was absent. The receipt
uses closed schemas and transitions through `PREPARED`, `COMMITTED`, or `ROLLED_BACK`. Failures and
catchable signals are serialized through one rollback. Repeated rollback, install, update,
uninstall, and recovery are idempotent. `SIGKILL`, power loss, and filesystem failure cannot be
made fully atomic; a verified prepared receipt enables explicit fail-closed recovery.

## Local rules

`--local-rules` is optional and explicit. It is copied only into the installed bundle path declared
by the manifest, must be a regular non-symlink file, and is never logged or included in output
fingerprints. Absence is valid. Updates preserve the installed local-rules content unless a new
explicit source is supplied.

## Evidence and compatibility

JSON output uses closed versioned schemas, stable outcome names, capability states, resource IDs,
phase, rollback status, and numeric exit codes; it never includes entry contents or local rules.
Filesystem tests are harness-neutral. Harness recipes live only in documentation and E2E fixtures,
must cite current primary documentation, and earn `HARNESS_E2E_VERIFIED` only from a fresh process
that proves entry loading, root and manifest resolution, synthetic local rules, legacy absence, and
fail-closed behavior.

Release proceeds through `1.0.0-rc.N` under `next`, public-registry readback and fresh-install
verification, then a separate `1.0.0` promotion under `latest`. Both releases require signed tags,
repository release checks, npm provenance or trusted publishing, independent QA and security
review, and exact-head CI.

## Explicit non-goals

The installer does not install models or harnesses, infer a home directory, default to the current
directory, modify projects, configure providers, hooks, MCP, approvals, or enforcement, support
unknown entry formats, or claim universal pre-effect enforcement.
