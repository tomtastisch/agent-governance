#!/usr/bin/env python3
"""Projiziert VERSION und das aktuelle CHANGELOG-Datum nach CITATION.cff.

Release-Ablauf: docs/releasing.md. Keine Datums-/Versionsoption oder neue Authority.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

if __package__:
    from .release_check import CheckResult, _check_changelog_sections, citation_fields
    from .sync_version import _read_regular_bytes, _read_version_with_identity, _replace_all_atomically, _require_identity
else:
    from release_check import CheckResult, _check_changelog_sections, citation_fields
    from sync_version import _read_regular_bytes, _read_version_with_identity, _replace_all_atomically, _require_identity


def synchronize(root: Path) -> None:
    version, version_identity = _read_version_with_identity(root)
    changelog_path = root / "CHANGELOG.md"
    citation_path = root / "CITATION.cff"
    changelog, changelog_identity = _read_regular_bytes(changelog_path)
    citation, citation_identity = _read_regular_bytes(citation_path)
    result = CheckResult()
    release_date = _check_changelog_sections(root, version, result, changelog.decode("utf-8"))
    if not result.ok or release_date is None:
        raise ValueError("; ".join(result.errors))
    source = citation.decode("utf-8")
    citation_fields(source)
    projected = []
    for line in source.splitlines(keepends=True):
        if line.startswith("commit:"):
            continue
        ending = line[len(line.rstrip("\r\n")):]
        if line.startswith("version:"):
            line = f"version: {version}{ending}"
        elif line.startswith("date-released:"):
            line = f"date-released: '{release_date}'{ending}"
        projected.append(line)
    output = "".join(projected).encode("utf-8")
    citation_fields(output.decode("utf-8"))
    identities = {root / "VERSION": version_identity, changelog_path: changelog_identity, citation_path: citation_identity}
    for path, identity in identities.items():
        _require_identity(path, identity)
    if output != citation:
        _replace_all_atomically(
            {citation_path: output},
            identities,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        synchronize(args.root.resolve())
    except (OSError, ValueError, UnicodeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
