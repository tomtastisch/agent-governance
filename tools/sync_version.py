#!/usr/bin/env python3
"""Synchronizes exactly three npm VERSION projections without reformatting JSON."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile


SEMVER_RE = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-((?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)
JSON_WHITESPACE = " \t\r\n"
JSON_DECODER = json.JSONDecoder()
FileIdentity = tuple[int, int, int, int, int, int]


def fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def _identity(file_stat: os.stat_result) -> FileIdentity:
    return (
        file_stat.st_dev,
        file_stat.st_ino,
        file_stat.st_mode,
        file_stat.st_size,
        file_stat.st_mtime_ns,
        file_stat.st_ctime_ns,
    )


def _read_regular_bytes(path: Path) -> tuple[bytes, FileIdentity]:
    try:
        path_stat = os.lstat(path)
    except OSError as error:
        raise ValueError(f"{path.name} ist nicht sicher lesbar: {error}") from error
    if not stat.S_ISREG(path_stat.st_mode):
        raise ValueError(f"{path.name} muss eine reguläre Nicht-Symlink-Datei sein")
    if not hasattr(os, "O_NOFOLLOW"):
        raise ValueError("O_NOFOLLOW fehlt — sicherer Versionsabgleich nicht verfügbar")
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as error:
        raise ValueError(f"{path.name} ist nicht sicher lesbar: {error}") from error
    try:
        opened_before = os.fstat(descriptor)
        if not stat.S_ISREG(opened_before.st_mode) or _identity(opened_before) != _identity(path_stat):
            raise ValueError(f"{path.name} wurde vor dem Lesen ausgetauscht")
        with os.fdopen(descriptor, "rb", closefd=True) as handle:
            descriptor = -1
            content = handle.read()
            opened_after = os.fstat(handle.fileno())
        if _identity(opened_after) != _identity(opened_before):
            raise ValueError(f"{path.name} wurde während des Lesens verändert")
        return content, _identity(opened_after)
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _read_version_with_identity(root: Path) -> tuple[str, FileIdentity]:
    try:
        raw_bytes, identity = _read_regular_bytes(root / "VERSION")
        raw = raw_bytes.decode("utf-8")
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ValueError(f"VERSION ist nicht lesbar: {error}") from error
    if raw.endswith("\n"):
        raw = raw[:-1]
    if "\n" in raw or "\r" in raw or not SEMVER_RE.fullmatch(raw):
        raise ValueError("VERSION muss genau eine gültige SemVer-Zeile enthalten")
    return raw, identity


def read_version(root: Path) -> str:
    return _read_version_with_identity(root)[0]


def _skip_whitespace(source: str, index: int) -> int:
    while index < len(source) and source[index] in JSON_WHITESPACE:
        index += 1
    return index


def _parse_string(source: str, index: int) -> tuple[str, int]:
    value, end = JSON_DECODER.raw_decode(source, index)
    if not isinstance(value, str):
        raise ValueError("JSON-Objektschlüssel muss eine Zeichenkette sein")
    return value, end


def _parse_value(source: str, index: int):
    index = _skip_whitespace(source, index)
    if index >= len(source):
        raise ValueError("unvollständiges JSON")
    if source[index] == "{":
        return _parse_object(source, index)
    if source[index] == "[":
        return _parse_array(source, index), None
    _value, end = JSON_DECODER.raw_decode(source, index)
    return end, None


def _parse_array(source: str, index: int) -> int:
    index = _skip_whitespace(source, index + 1)
    if index < len(source) and source[index] == "]":
        return index + 1
    while True:
        index, _node = _parse_value(source, index)
        index = _skip_whitespace(source, index)
        if index >= len(source):
            raise ValueError("unvollständiges JSON-Array")
        if source[index] == "]":
            return index + 1
        if source[index] != ",":
            raise ValueError("ungültiges JSON-Array")
        index = _skip_whitespace(source, index + 1)


def _parse_object(source: str, index: int):
    fields = {}
    index = _skip_whitespace(source, index + 1)
    if index < len(source) and source[index] == "}":
        return index + 1, fields
    while True:
        key, index = _parse_string(source, index)
        if key in fields:
            raise ValueError(f"doppelter JSON-Schlüssel '{key}'")
        index = _skip_whitespace(source, index)
        if index >= len(source) or source[index] != ":":
            raise ValueError("ungültiges JSON-Objekt")
        start = _skip_whitespace(source, index + 1)
        end, child = _parse_value(source, start)
        fields[key] = (start, end, child)
        index = _skip_whitespace(source, end)
        if index >= len(source):
            raise ValueError("unvollständiges JSON-Objekt")
        if source[index] == "}":
            return index + 1, fields
        if source[index] != ",":
            raise ValueError("ungültiges JSON-Objekt")
        index = _skip_whitespace(source, index + 1)


def _read_json_layout(path: Path) -> tuple[str, dict, FileIdentity]:
    try:
        source_bytes, identity = _read_regular_bytes(path)
        source = source_bytes.decode("utf-8")
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ValueError(f"{path.name} ist nicht lesbar") from error
    try:
        json.loads(source)
        end, fields = _parse_object(source, _skip_whitespace(source, 0))
    except (json.JSONDecodeError, ValueError) as error:
        raise ValueError(f"{path.name} ist kein gültiges JSON-Objekt: {error}") from error
    if _skip_whitespace(source, end) != len(source):
        raise ValueError(f"{path.name} enthält JSON-Nachlauf")
    return source, fields, identity


def _string_value_span(source: str, fields: dict, key: str, path: Path) -> tuple[int, int]:
    field = fields.get(key)
    if field is None:
        raise ValueError(f"{path.name} benötigt den Stringwert '{key}'")
    start, end, _child = field
    try:
        _value, parsed_end = _parse_string(source, start)
    except (json.JSONDecodeError, ValueError) as error:
        raise ValueError(f"{path.name} benötigt '{key}' als JSON-String") from error
    if parsed_end != end:
        raise ValueError(f"{path.name} benötigt '{key}' als JSON-String")
    return start, end


def _replace_values(source: str, replacements: list[tuple[int, int, str]]) -> bytes:
    for start, end, replacement in sorted(replacements, reverse=True):
        source = source[:start] + replacement + source[end:]
    return source.encode("utf-8")


def _require_identity(path: Path, expected: FileIdentity) -> None:
    try:
        current = os.lstat(path)
    except OSError as error:
        raise OSError(f"{path.name} wurde vor der Mutation entfernt: {error}") from error
    if not stat.S_ISREG(current.st_mode) or _identity(current) != expected:
        raise OSError(f"{path.name} wurde vor der Mutation ausgetauscht oder verändert")


def _stage_sibling(path: Path, content: bytes, expected: FileIdentity) -> Path:
    _require_identity(path, expected)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".sync-version-", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, stat.S_IMODE(expected[2]))
        return temporary
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _replace_all_atomically(
    planned: dict[Path, bytes], expected_identities: dict[Path, FileIdentity]
) -> None:
    for path, expected in expected_identities.items():
        _require_identity(path, expected)
    residuals = sorted(
        residual
        for parent in {path.parent for path in planned}
        for residual in parent.glob(".sync-version-*")
    )
    if residuals:
        raise OSError(
            "Sync-Restdateien erfordern Prüfung vor einem erneuten Lauf: "
            + ", ".join(path.name for path in residuals)
        )

    staged = {}
    backups = {}
    replaced = []
    committed = False
    rollback_errors = []
    try:
        for path, content in planned.items():
            staged[path] = _stage_sibling(path, content, expected_identities[path])
        for path in planned:
            backup_content, backup_identity = _read_regular_bytes(path)
            if backup_identity != expected_identities[path]:
                raise OSError(f"{path.name} wurde vor dem Backup ausgetauscht oder verändert")
            backups[path] = _stage_sibling(path, backup_content, expected_identities[path])
        for path, expected in expected_identities.items():
            _require_identity(path, expected)
        for path in planned:
            os.replace(staged[path], path)
            replaced.append(path)
        committed = True
        for backup in backups.values():
            try:
                backup.unlink(missing_ok=True)
            except OSError as cleanup_error:
                raise OSError(
                    "Backup-Bereinigung nach abgeschlossenem VERSION-Sync fehlgeschlagen; "
                    "Projektionen bleiben committed und Restdateien erhalten"
                ) from cleanup_error
    except BaseException as original_error:
        if committed:
            raise
        for path in reversed(replaced):
            try:
                os.replace(backups[path], path)
            except OSError as rollback_error:
                rollback_errors.append(f"{path.name}: {rollback_error}")
        if rollback_errors:
            raise OSError(
                "VERSION-Projektionen konnten nicht vollständig zurückgerollt werden: "
                + "; ".join(rollback_errors)
            ) from original_error
        raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)
        if not committed and not rollback_errors:
            for backup in backups.values():
                backup.unlink(missing_ok=True)


def synchronize(root: Path) -> None:
    version, version_identity = _read_version_with_identity(root)
    version_path = root / "VERSION"
    package_path = root / "package.json"
    lock_path = root / "package-lock.json"
    package_source, package_fields, package_identity = _read_json_layout(package_path)
    lock_source, lock_fields, lock_identity = _read_json_layout(lock_path)
    packages = lock_fields.get("packages")
    if packages is None or not isinstance(packages[2], dict):
        raise ValueError("package-lock.json benötigt packages als JSON-Objekt")
    root_package = packages[2].get("")
    if root_package is None or not isinstance(root_package[2], dict):
        raise ValueError("package-lock.json benötigt packages[\"\"] als JSON-Objekt")

    planned = {
        package_path: _replace_values(
            package_source,
            [(*_string_value_span(package_source, package_fields, "version", package_path), f'"{version}"')],
        ),
        lock_path: _replace_values(
            lock_source,
            [
                (*_string_value_span(lock_source, lock_fields, "version", lock_path), f'"{version}"'),
                (*_string_value_span(lock_source, root_package[2], "version", lock_path), f'"{version}"'),
            ],
        ),
    }
    _replace_all_atomically(
        planned,
        {
            version_path: version_identity,
            package_path: package_identity,
            lock_path: lock_identity,
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        synchronize(args.root.resolve())
    except (OSError, ValueError) as error:
        return fail(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
