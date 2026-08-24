#!/usr/bin/env python3
"""Generate or verify the deterministic installer payload manifest."""

from __future__ import annotations

import hashlib
from pathlib import Path
import stat
import sys


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "release.files.sha256"
TOP_LEVEL = ("VERSION",)
TREES = ("bundle",)
EXCLUDED = {"bundle/agent-governance/local/user-rules.md"}


def payload_files() -> list[Path]:
    files: list[Path] = []
    for relative in TOP_LEVEL:
        files.append(ROOT / relative)
    for tree in TREES:
        for candidate in (ROOT / tree).rglob("*"):
            relative = candidate.relative_to(ROOT).as_posix()
            mode = candidate.lstat().st_mode
            if stat.S_ISLNK(mode):
                raise RuntimeError(f"payload link is forbidden: {relative}")
            if stat.S_ISREG(mode) and relative not in EXCLUDED:
                files.append(candidate)
            elif not stat.S_ISDIR(mode) and relative not in EXCLUDED:
                raise RuntimeError(f"unexpected payload type: {relative}")
    return sorted(files, key=lambda item: item.relative_to(ROOT).as_posix().encode())


def render() -> str:
    lines = []
    for path in payload_files():
        relative = path.relative_to(ROOT).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {relative}")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    if argv == ["generate"]:
        OUTPUT.write_text(render(), encoding="utf-8", newline="\n")
        return 0
    if argv == ["check"]:
        if not OUTPUT.is_file() or OUTPUT.is_symlink():
            print("FAIL: release.files.sha256 is missing or unsafe", file=sys.stderr)
            return 1
        if OUTPUT.read_text(encoding="utf-8") != render():
            print("FAIL: release.files.sha256 is stale", file=sys.stderr)
            return 1
        print("OK: installer release manifest is current")
        return 0
    print("usage: release_manifest.py generate|check", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
