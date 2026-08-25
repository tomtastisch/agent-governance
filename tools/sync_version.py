#!/usr/bin/env python3
"""Synchronizes the three npm VERSION projections without changing release history."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


def fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def read_version(root: Path) -> str:
    try:
        raw = (root / "VERSION").read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(f"VERSION ist nicht lesbar: {error}") from error
    if raw.endswith("\n"):
        raw = raw[:-1]
    if "\n" in raw or "\r" in raw or not SEMVER_RE.fullmatch(raw):
        raise ValueError("VERSION muss genau eine gültige SemVer-Zeile enthalten")
    return raw


def read_json_object(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"{path.name} fehlt") from error
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{path.name} ist kein gültiges JSON") from error
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} muss ein JSON-Objekt sein")
    return value


def synchronize(root: Path) -> None:
    version = read_version(root)
    package_path = root / "package.json"
    lock_path = root / "package-lock.json"
    package = read_json_object(package_path)
    lock = read_json_object(lock_path)
    packages = lock.get("packages")
    if not isinstance(packages, dict) or not isinstance(packages.get(""), dict):
        raise ValueError("package-lock.json benötigt packages[\"\"] als Objekt")

    package["version"] = version
    lock["version"] = version
    packages[""]["version"] = version

    package_path.write_text(json.dumps(package, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lock_path.write_text(json.dumps(lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        synchronize(args.root.resolve())
    except ValueError as error:
        return fail(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
