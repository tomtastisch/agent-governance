#!/usr/bin/env python3
"""Verify the exact minimal Microsoft provider runtime without trusting its receipt."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys


LINE = re.compile(r"^([0-9a-f]{64})  ([A-Za-z0-9._/-]+)$")


def fail(message: str) -> None:
    raise SystemExit(f"verify-runtime: {message}")


def read_nonwritable_regular_file(path: Path, label: str) -> bytes:
    flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        fail(f"{label} is not a readable regular file")
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o022:
            fail(f"{label} is group- or world-writable")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            return handle.read()
    finally:
        os.close(descriptor)


def load_expected(path: Path) -> tuple[bytes, dict[str, str]]:
    if not path.is_absolute() or path.is_symlink():
        fail("expected manifest is not an absolute regular file")
    payload = read_nonwritable_regular_file(path, "expected manifest")
    expected: dict[str, str] = {}
    for raw_line in payload.decode("ascii").splitlines():
        match = LINE.fullmatch(raw_line)
        if match is None:
            fail("expected manifest format is invalid")
        digest, relative = match.groups()
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts or relative in expected:
            fail("expected manifest path is invalid")
        expected[relative] = digest
    if not expected:
        fail("expected manifest is empty")
    return payload, expected


def verify(expected_manifest: Path, runtime: Path) -> None:
    payload, expected = load_expected(expected_manifest)
    if not runtime.is_absolute() or not runtime.is_dir() or runtime.is_symlink():
        fail("runtime is not an absolute real directory")
    if runtime.resolve(strict=True) != runtime:
        fail("runtime path contains a symlink")
    installed_manifest = runtime / "runtime.files.sha256"
    if installed_manifest.is_symlink():
        fail("runtime manifest is missing")
    if read_nonwritable_regular_file(installed_manifest, "runtime manifest") != payload:
        fail("runtime manifest integrity mismatch")

    actual: set[str] = set()
    for candidate in runtime.rglob("*"):
        relative = candidate.relative_to(runtime).as_posix()
        if candidate.is_symlink():
            fail("runtime contains a symlink")
        if candidate.is_file():
            actual.add(relative)
        elif not candidate.is_dir():
            fail("runtime contains a special file")
    if actual != set(expected) | {"runtime.files.sha256"}:
        fail("runtime file set integrity mismatch")

    for relative, digest in expected.items():
        candidate = runtime / relative
        observed = hashlib.sha256(
            read_nonwritable_regular_file(candidate, "runtime file")
        ).hexdigest()
        if observed != digest:
            fail("runtime byte integrity mismatch")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: verify-runtime.py EXPECTED_MANIFEST ABSOLUTE_RUNTIME", file=sys.stderr)
        return 2
    verify(Path(argv[1]), Path(os.path.normpath(argv[2])))
    print("verify-runtime: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
