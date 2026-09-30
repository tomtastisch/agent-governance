#!/usr/bin/env python3
"""Release-Metadaten vor dem finalen Exact-Head-Gate im selben PR vorbereiten.

Kein Commit, Tag, Netzwerkzugriff oder Publishing. Vertrag: docs/releasing.md.
"""
from __future__ import annotations

import argparse
from datetime import date
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

if __package__:
    from . import release_check, release_manifest, sync_citation, sync_version
else:
    import release_check
    import release_manifest
    import sync_citation
    import sync_version


METADATA = ("VERSION", "CHANGELOG.md", "package.json", "package-lock.json", "CITATION.cff", "release.files.sha256")
# Arbeits-/Builddaten gehören nicht zum Release-Quellbaum.
EXCLUDED_DIRS = {".git", ".worktrees", "node_modules", "dist", "prebuilds", "_site", "__pycache__", ".pytest_cache"}


def target_version(current: str, bump: str | None, target: str | None) -> str:
    if (bump is None) == (target is None):
        raise ValueError("genau --bump oder --target erforderlich")
    if bump is not None:
        if bump not in {"patch", "minor", "major"}:
            raise ValueError("unbekannter Bump")
        parsed = sync_version.SEMVER_RE.fullmatch(current)
        if parsed is None or parsed[4] is not None or parsed[5] is not None:
            raise ValueError("Bump benötigt eine stabile Version ohne Buildmetadaten; explizites Ziel verwenden")
        major, minor, patch = map(int, parsed.group(1, 2, 3))
        target = {"patch": f"{major}.{minor}.{patch + 1}", "minor": f"{major}.{minor + 1}.0", "major": f"{major + 1}.0.0"}[bump]
    if not isinstance(target, str) or not sync_version.SEMVER_RE.fullmatch(target):
        raise ValueError("Zielversion muss gültiges SemVer sein")
    if target != current and release_check._semver_cmp(target, current) <= 0:
        raise ValueError("Zielversion muss größer als VERSION sein")
    return target


def cut_changelog(source: str, current: str, target: str, release_date: str, root: Path) -> str:
    if "\r" in source:
        raise ValueError("CHANGELOG benötigt die Repositorykonvention LF")
    headings = list(re.finditer(r"^## .*$", source, re.MULTILINE))
    if len(headings) < 2 or headings[0][0] != "## [Unreleased]":
        raise ValueError("CHANGELOG benötigt genau einen führenden Unreleased-Bereich und Releasehistorie")
    for heading in headings[1:]:
        if release_check.VERSION_HEADING_RE.fullmatch(heading[0]) is None:
            raise ValueError("mehrdeutige CHANGELOG-Überschrift")
    start, end = headings[0].end() + 1, headings[1].start()
    body = source[start:end]
    for index, heading in enumerate(headings):
        section_end = headings[index + 1].start() if index + 1 < len(headings) else len(source)
        section = source[heading.end() + 1:section_end]
        section_categories = re.findall(r"^### (.*)$", section, re.MULTILINE)
        if len(section_categories) != len(set(section_categories)) or not set(section_categories) <= release_check.VALID_CATEGORIES:
            raise ValueError("mehrdeutige CHANGELOG-Kategorien")
        if len(release_check.BREAKING_MARKER_RE.findall(section)) != 1:
            raise ValueError("mehrdeutiger Breaking-Marker")
    categories = re.findall(r"^### (.*)$", body, re.MULTILINE)
    result = release_check.CheckResult()
    existing_date = release_check._check_changelog_sections(root, current, result, source)
    if not result.ok:
        raise ValueError("; ".join(result.errors))
    empty_body = "\n" + "\n".join(f"### {category}\n\n- Keine.\n" for category in categories) + "\n**Breaking changes:** none\n\n"
    if target == current:
        if existing_date != release_date or body != empty_body:
            raise ValueError("gleiches Ziel benötigt denselben Release-Tag und einen leeren kanonischen Unreleased-Bereich")
        return source
    return source[:start] + empty_body + f"## [{target}] — {release_date}\n" + body + source[end:]


def snapshot(root: Path) -> tuple[dict[Path, bytes], dict[Path, sync_version.FileIdentity]]:
    contents, identities = {}, {}
    for base, directories, files in os.walk(root, followlinks=False):
        directories[:] = sorted(name for name in directories if name not in EXCLUDED_DIRS)
        for name in directories:
            if not stat.S_ISDIR((Path(base) / name).lstat().st_mode):
                raise ValueError("Release-Quellbaum darf keine Verzeichnislinks enthalten")
        for name in sorted(files):
            if name == ".git" or name == ".DS_Store":
                continue
            path = Path(base) / name
            content, identity = sync_version._read_regular_bytes(path)
            contents[path.relative_to(root)] = content
            identities[path] = identity
    return contents, identities


def prepare(root: Path, *, bump: str | None = None, target: str | None = None, release_date: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", release_date):
        raise ValueError("Release-Datum benötigt YYYY-MM-DD")
    date.fromisoformat(release_date)
    current = sync_version.read_version(root)
    version = target_version(current, bump, target)
    contents, identities = snapshot(root)
    for name in METADATA:
        if Path(name) not in contents:
            raise ValueError(f"{name} fehlt")
    # Bindet auch VERSION aus dem ersten Read an den vollständigen Snapshot.
    if contents[Path("VERSION")] not in {current.encode(), (current + "\n").encode()}:
        raise ValueError("VERSION während Vorbereitung verändert")
    changelog = cut_changelog(contents[Path("CHANGELOG.md")].decode("utf-8"), current, version, release_date, root)
    with tempfile.TemporaryDirectory(prefix="agent-governance-prepare-") as directory:
        candidate = Path(directory)
        for relative, content in contents.items():
            path = candidate / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        (candidate / "VERSION").write_bytes((version + "\n").encode())
        (candidate / "CHANGELOG.md").write_bytes(changelog.encode("utf-8"))
        sync_version.synchronize(candidate)
        sync_citation.synchronize(candidate)
        manifest = release_manifest.render(candidate)
        (candidate / "release.files.sha256").write_text(manifest, encoding="utf-8", newline="\n")
        result = release_check.check_tree(str(candidate))
        if not result.ok:
            raise ValueError("; ".join(result.errors))
        if (candidate / "release.files.sha256").read_text() != release_manifest.render(candidate):
            raise ValueError("Release-Manifest driftet")
        planned = {root / name: (candidate / name).read_bytes() for name in METADATA}
    # Keine Eingabeänderung oder neue Datei während der Kandidatenprüfung übernehmen.
    _current_contents, current_identities = snapshot(root)
    if current_identities != identities:
        raise ValueError("Release-Quellbaum während Vorbereitung verändert")
    changed = {path: content for path, content in planned.items() if content != contents[path.relative_to(root)]}
    if changed:
        sync_version._replace_all_atomically(changed, identities)
    return version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    intent = parser.add_mutually_exclusive_group(required=True)
    intent.add_argument("--bump", choices=("patch", "minor", "major"))
    intent.add_argument("--target")
    parser.add_argument("--date", required=True, help="bewusstes Release-Datum YYYY-MM-DD; kein Uhr-Fallback")
    args = parser.parse_args(argv)
    try:
        version = prepare(args.root.resolve(), bump=args.bump, target=args.target, release_date=args.date)
    except (OSError, ValueError, UnicodeError, RuntimeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"OK: Release {version} vorbereitet; relevante Gates und Reviews am neuen Exact Head erforderlich")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
