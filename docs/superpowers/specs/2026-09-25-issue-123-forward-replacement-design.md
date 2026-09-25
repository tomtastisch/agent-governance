# Forward-only replacement of an unverifiable installation

Approved scope: issue #123, blocker of #122. The user approved a versions-neutral,
reversible replacement capability. Socket implementation remains paused.

## Evidence and limits

Base: `b5516f0806f67a582eb13013a5322d4a385acb9a`, published baseline 1.6.0.
The current verifier accepts the installed 1.5.2 bundle. Its active receipt fails
because persistent device identities differ while inode and mode match. The
original triggering event is unknown; the later macOS update cannot explain the
first failure. A fresh 1.5.2 installation made with the current installer updates
to 1.6.0 and verifies successfully. No historical validator is justified.

## Interface and ownership

Add a narrow public package export `./replacement` with `replaceInstallation`.
Do not invent another CLI command or modify the existing command catalog. This
additive package capability is SemVer minor; do not bump the release here.

The request explicitly supplies the source installation root, a **new absent**
installation root, release root, target root and relative Markdown entry file.
It may supply current-contract validated local rules and a read-only dry-run.
Source and destination installation roots must be disjoint; the entry/target
must be outside both. Destination parent must already be canonical and safe.

Do not read, translate, trust, mutate, copy, or regenerate old receipts, bindings,
release schemas or old local rules. The old installation root remains intact,
including every other binding and shared release. Its only affected reference is
the explicitly selected entry. Private rules are carried forward only from an
explicit source validated by the existing current-contract local-rules reader.

## Transaction

1. Validate request paths, current release, optional rule source, and one
   unambiguous current managed-marker envelope in the entry. Reuse the existing
   managed-block parser. The old block is opaque, never a source of authority.
   Reject malformed/duplicate/foreign markers, symlinks, nonregular files,
   hardlinked entries, and an existing replacement installation root.
2. Bind source/destination/entry parents and the entry snapshot before mutation;
   probe the native filesystem capability. A dry-run performs no writes and
   reports a plan, never CURRENT.
3. Exclusively reserve the fresh destination root and a private, unique
   quarantine directory adjacent to the entry. Record resource references and
   preserve the complete original entry before removal from its live name.
   Use native no-clobber, identity-bound primitives. Verify the detached entry
   against the bound snapshot; never overwrite a concurrent writer.
4. Recreate only the user-owned bytes outside the managed envelope. Invoke the
   normal current InstallerTransaction.install path against the fresh root and
   actual target. New receipts/backups/identities are created only by it.
5. Perform fresh verify/status before reporting success. Preserve the quarantine
   even after success; no automatic deletion or cleanup of old managed state.
6. On failure, restore the original entry only when the live namespace still
   belongs to this attempt, using existing identity/snapshot/no-clobber guards.
   If safe restoration cannot be proved, retain the original in quarantine and
   report failure and its resource reference. SIGKILL/power loss must never be
   described as atomically rolled back; retained isolation is the safety floor.

No global filesystem search, new runtime dependency, legacy branch, weakened
device check, broad catch-and-continue, secret output or external network effect.
Errors/results contain safe metadata only. Existing same-UID final-component
race limitations remain explicit; all observable substitutions fail closed.

## Acceptance and delivery

Tests exercise real filesystems and the actual installer: opaque unusable old
metadata, user-byte preservation, fresh CURRENT/verify, other-binding preservation,
dry-run, malformed markers, unsafe paths, hardlinks, destination collisions,
fault recovery, parent/entry replacements and concurrent attempts. No secret or
private content may occur in result/error metadata. Test package consumption of
the new export. Run the relevant full Node/Python/typecheck/lint/build/package/
audit/license/release gates, CI and independent QA/SEC on the final exact head.
Stop before merge/release for explicit authorization. Only a published target
may then replace the active OpenCode installation; #122 resumes after CURRENT.
