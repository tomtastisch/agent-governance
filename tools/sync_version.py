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
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)
JSON_WHITESPACE = " \t\r\n"
JSON_DECODER = json.JSONDecoder()


def fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def read_version(root: Path) -> str:
    try:
        raw = (root / "VERSION").read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ValueError(f"VERSION ist nicht lesbar: {error}") from error
    if raw.endswith("\n"):
        raw = raw[:-1]
    if "\n" in raw or "\r" in raw or not SEMVER_RE.fullmatch(raw):
        raise ValueError("VERSION muss genau eine gültige SemVer-Zeile enthalten")
    return raw


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


def _read_json_layout(path: Path) -> tuple[str, dict]:
    try:
        source = path.read_bytes().decode("utf-8")
    except FileNotFoundError as error:
        raise ValueError(f"{path.name} fehlt") from error
    except (OSError, UnicodeDecodeError) as error:
        raise ValueError(f"{path.name} ist nicht lesbar") from error
    try:
        json.loads(source)
        end, fields = _parse_object(source, _skip_whitespace(source, 0))
    except (json.JSONDecodeError, ValueError) as error:
        raise ValueError(f"{path.name} ist kein gültiges JSON-Objekt: {error}") from error
    if _skip_whitespace(source, end) != len(source):
        raise ValueError(f"{path.name} enthält JSON-Nachlauf")
    return source, fields


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


def _stage_sibling(path: Path, content: bytes) -> Path:
    descriptor, temporary_name = tempfile.mkstemp(prefix=".sync-version-", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, stat.S_IMODE(path.stat().st_mode))
        return temporary
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _replace_all_atomically(planned: dict[Path, bytes]) -> None:
    staged = {}
    backups = {}
    replaced = []
    try:
        for path, content in planned.items():
            staged[path] = _stage_sibling(path, content)
        for path in planned:
            backups[path] = _stage_sibling(path, path.read_bytes())
        for path in planned:
            os.replace(staged[path], path)
            replaced.append(path)
        for backup in backups.values():
            backup.unlink(missing_ok=True)
    except BaseException as original_error:
        rollback_errors = []
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
        for temporary in (*staged.values(), *backups.values()):
            temporary.unlink(missing_ok=True)


def synchronize(root: Path) -> None:
    version = read_version(root)
    package_path = root / "package.json"
    lock_path = root / "package-lock.json"
    package_source, package_fields = _read_json_layout(package_path)
    lock_source, lock_fields = _read_json_layout(lock_path)
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
    _replace_all_atomically(planned)


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
