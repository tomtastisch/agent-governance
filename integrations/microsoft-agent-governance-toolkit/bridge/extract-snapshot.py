#!/usr/bin/env python3
"""Verifiziert und extrahiert einen gepinnten Snapshot ohne Link- oder Pfadtraversal."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tarfile


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        digest, separator, raw_path = line.partition("  ")
        if separator != "  " or not SHA256_RE.fullmatch(digest):
            raise ValueError(f"ungültiger Manifesteintrag in Zeile {line_number}")
        pure = PurePosixPath(raw_path)
        if pure.is_absolute() or ".." in pure.parts or not raw_path.startswith("upstream/"):
            raise ValueError(f"unsicherer Manifestpfad in Zeile {line_number}")
        if raw_path in entries:
            raise ValueError(f"doppelter Manifestpfad in Zeile {line_number}")
        entries[raw_path] = digest
    return entries


def validate_members(
    archive: tarfile.TarFile,
    expected_files: dict[str, str],
) -> tuple[list[tarfile.TarInfo], str]:
    members = archive.getmembers()
    roots: set[str] = set()
    observed: dict[str, str] = {}
    for member in members:
        pure = PurePosixPath(member.name)
        if pure.is_absolute() or ".." in pure.parts or len(pure.parts) < 1:
            raise ValueError("Archiv enthält unsicheren Pfad")
        roots.add(pure.parts[0])
        if member.issym() or member.islnk() or member.isdev() or member.isfifo():
            raise ValueError("Archiv enthält Link, Gerät oder FIFO")
        if not member.isdir() and not member.isfile():
            raise ValueError("Archiv enthält unbekannten Eintragstyp")
        if not member.isfile():
            continue
        if len(pure.parts) < 2:
            raise ValueError("Archivdatei liegt außerhalb des Release-Roots")
        raw_path = f"upstream/{'/'.join(pure.parts[1:])}"
        if raw_path in observed:
            raise ValueError("Archiv enthält doppelten Dateipfad")
        extracted = archive.extractfile(member)
        if extracted is None:
            raise ValueError("Archivdatei ist nicht lesbar")
        observed[raw_path] = hashlib.sha256(extracted.read()).hexdigest()
    if len(roots) != 1:
        raise ValueError("Archiv besitzt keinen eindeutigen Release-Root")
    if observed != expected_files:
        raise ValueError("Snapshotmanifest stimmt nicht mit dem Archiv überein")
    return members, next(iter(roots))


def extract_verified(
    archive_path: Path,
    manifest_path: Path,
    destination: Path,
    expected_archive_sha256: str,
) -> None:
    for path, label in ((archive_path, "Archiv"), (manifest_path, "Manifest")):
        if not path.is_absolute() or path.is_symlink() or not path.is_file():
            raise ValueError(f"{label} muss eine absolute reguläre Datei sein")
    if not destination.is_absolute() or destination.exists() or destination.is_symlink():
        raise ValueError("Ziel muss ein neuer absoluter Pfad sein")
    if not SHA256_RE.fullmatch(expected_archive_sha256):
        raise ValueError("erwarteter Archivhash ist ungültig")
    if file_sha256(archive_path) != expected_archive_sha256:
        raise ValueError("Archivhash stimmt nicht mit dem Pin überein")

    expected_files = load_manifest(manifest_path)
    with tarfile.open(archive_path, "r:gz") as archive:
        members, _release_root = validate_members(archive, expected_files)
        destination.mkdir(mode=0o700)
        for member in members:
            pure = PurePosixPath(member.name)
            target = destination.joinpath(*pure.parts)
            if os.path.commonpath((destination, target)) != str(destination):
                raise ValueError("aufgelöster Archivpfad verlässt das Ziel")
            if member.isdir():
                target.mkdir(mode=0o755, parents=True, exist_ok=True)
                continue
            target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            extracted = archive.extractfile(member)
            if extracted is None:
                raise ValueError("Archivdatei ist nicht lesbar")
            with target.open("xb") as output:
                shutil.copyfileobj(extracted, output)
            os.chmod(target, member.mode & 0o1777)


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print(
            "usage: extract-snapshot.py ARCHIVE MANIFEST DESTINATION ARCHIVE_SHA256",
            file=sys.stderr,
        )
        return 2
    try:
        extract_verified(
            Path(argv[1]),
            Path(argv[2]),
            Path(argv[3]),
            argv[4],
        )
    except (OSError, ValueError, tarfile.TarError) as error:
        print(f"extract-snapshot: FAIL: {error}", file=sys.stderr)
        return 1
    print("extract-snapshot: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
