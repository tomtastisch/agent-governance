#!/usr/bin/env python3
"""Deterministische Release-Metadaten-Validierung (Kern §12, §15, §16, §17).

Drei Modi — alle read-only:
  tree     Repository-/Tree-Konsistenz (VERSION ↔ CHANGELOG ↔ README ↔ INSTALL)
  tag      Tag-Konsistenz (benötigt Git-Historie und einen Tag-Ref)
  release  GitHub-Release-Konsistenz (benötigt Netzwerk und gh CLI)

Kein Modus erstellt Tags, Releases oder verändert das Repository.
"""

import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

VALID_CATEGORIES = {"Added", "Changed", "Fixed", "Removed", "Deprecated", "Security"}
REQUIRED_CATEGORIES = {"Added", "Changed", "Fixed", "Removed"}
BREAKING_MARKER_RE = re.compile(r"\*\*Breaking changes:\*\*\s*(none|present)", re.IGNORECASE)
BREAKING_ENTRY_RE = re.compile(r"\*\*BREAKING:\*\*")
VERSION_HEADING_RE = re.compile(r"^##\s+\[(\d+\.\d+\.\d[^\]]*)\]\s*(?:—\s*(.+))?$", re.MULTILINE)
UNRELEASED_HEADING_RE = re.compile(r"^##\s+\[Unreleased\]", re.MULTILINE)
CATEGORY_HEADING_RE = re.compile(r"^###\s+(\w+)", re.MULTILINE)

STATUS_OK = 0
STATUS_FAIL = 1
STATUS_SKIP = 2


class CheckResult:
    """Sammelt Fehler und Warnungen; ok=True wenn keine Fehler."""

    def __init__(self):
        self.errors = []
        self.warnings = []

    @property
    def ok(self):
        return len(self.errors) == 0

    def add_error(self, msg):
        self.errors.append(msg)

    def add_warning(self, msg):
        self.warnings.append(msg)

    def exit(self):
        for e in self.errors:
            print(f"FAIL: {e}", file=sys.stderr)
        for w in self.warnings:
            print(f"WARN: {w}", file=sys.stderr)
        if self.ok:
            print("OK: all release consistency checks passed")
            return STATUS_OK
        return STATUS_FAIL


def _read(rel, root):
    with open(os.path.join(root, rel), encoding="utf-8") as fh:
        return fh.read()


def _exists(rel, root):
    return os.path.exists(os.path.join(root, rel))


def _git(args, root, timeout=15):
    result = subprocess.run(
        ["git"] + args, cwd=root, capture_output=True, text=True, timeout=timeout
    )
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def _is_valid_semver(v):
    return bool(SEMVER_RE.match(v))


# ═══════════════════════════════════════════════════════════════════════
# Tree-Konsistenz (local-only)
# ═══════════════════════════════════════════════════════════════════════

def check_tree(root=None):
    """Prüft VERSION, CHANGELOG, README, INSTALL auf Konsistenz im Arbeitsbaum.

    Returns CheckResult.
    """
    if root is None:
        root = ROOT
    r = CheckResult()

    # ── VERSION ──
    if not _exists("VERSION", root):
        r.add_error("VERSION fehlt — autoritative SemVer-Quelle erforderlich (Kern §12)")
        return r  # Ohne VERSION sind alle weiteren Prüfungen sinnlos.

    version_raw = _read("VERSION", root).strip()
    version = version_raw.splitlines()[0].strip() if version_raw else ""

    if not version:
        r.add_error("VERSION ist leer")
        return r

    if not _is_valid_semver(version):
        r.add_error(f"VERSION '{version}' ist kein gültiges SemVer (MAJOR.MINOR.PATCH)")

    # ── keine konkurrierende Versionsquelle ──
    _check_no_competing_source(root, r)

    # ── CHANGELOG ──
    if not _exists("CHANGELOG.md", root):
        r.add_error("CHANGELOG.md fehlt (Kern §12 verlangt aktuellen CHANGELOG)")
    else:
        _check_changelog_content(root, version, r)

    # ── README ──
    if _exists("README.md", root):
        _check_readme_version(root, version, r)

    # ── INSTALL ──
    if _exists("INSTALL.md", root):
        _check_install_links(root, r)

    return r


def _check_no_competing_source(root, r):
    """Prüft, dass keine TOML-/JSON-Datei einen version-Schlüssel führt."""
    authority = {"VERSION", "CHANGELOG.md"}
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in {".git", "tests", ".github"}]
        for name in files:
            rel = os.path.relpath(os.path.join(base, name), root)
            if rel in authority:
                continue
            if name.endswith(".toml"):
                txt = _read(rel, root)
                if re.search(r'(?m)^version\s*=\s*"\d+\.\d+\.\d+', txt):
                    r.add_error(f"{rel}: konkurrierende version-Deklaration")
            elif name.endswith(".json"):
                txt = _read(rel, root)
                if re.search(r'"version"\s*:\s*"\d+\.\d+\.\d+', txt):
                    r.add_error(f"{rel}: konkurrierende version-Deklaration")
            elif name.lower() in ("version.txt", "version", ".version"):
                r.add_error(f"{rel}: parallele Versionsdatei neben VERSION")


def _check_changelog_content(root, version, r):
    changelog = _read("CHANGELOG.md", root)

    has_unreleased = bool(UNRELEASED_HEADING_RE.search(changelog))

    # Version headings
    version_entries = [(m.group(1), m.group(2) or "") for m in VERSION_HEADING_RE.finditer(changelog)]

    # --- Prüfe Heading-Struktur ---
    if not has_unreleased and not version_entries:
        r.add_error("CHANGELOG enthält weder [Unreleased] noch einen versionierten Eintrag")

    # --- Duplikate ---
    seen = {}
    for v, _ in version_entries:
        if v in seen:
            r.add_error(f"CHANGELOG: doppelte Versionsüberschrift [{v}]")
        seen[v] = True

    # --- SemVer-Validität ---
    for v, _ in version_entries:
        if not _is_valid_semver(v):
            r.add_error(f"CHANGELOG: '[{v}]' ist kein gültiges SemVer")

    # --- Kategorien ---
    categories_used = set(CATEGORY_HEADING_RE.findall(changelog))
    unknown = categories_used - VALID_CATEGORIES
    if unknown:
        r.add_error(f"CHANGELOG enthält unbekannte Kategorien: {sorted(unknown)}. "
                    f"Zulässig: {sorted(VALID_CATEGORIES)}")

    # --- Breaking-Change-Marker ---
    if not BREAKING_MARKER_RE.search(changelog):
        r.add_error("CHANGELOG fehlt der Marker '**Breaking changes:** none' oder '**Breaking changes:** present'")
    else:
        has_present = bool(re.search(r"\*\*Breaking changes:\*\*\s*present", changelog, re.IGNORECASE))
        if has_present:
            has_breaking_entry = bool(BREAKING_ENTRY_RE.search(changelog))
            if not has_breaking_entry:
                r.add_error("'**Breaking changes:** present' gesetzt, aber kein Eintrag mit '**BREAKING:**' Präfix gefunden")

    # --- Unreleased: erforderliche Kategorien müssen existieren ---
    if has_unreleased:
        # Extrahiere den [Unreleased]-Block bis zur nächsten ##-Überschrift
        m = UNRELEASED_HEADING_RE.search(changelog)
        start = m.end()
        next_heading = re.search(r"\n##\s", changelog[start:])
        unreleased_block = changelog[start:start + next_heading.start()] if next_heading else changelog[start:]
        cats_in_unreleased = set(CATEGORY_HEADING_RE.findall(unreleased_block))
        missing_req = REQUIRED_CATEGORIES - cats_in_unreleased
        if missing_req:
            r.add_error(f"[Unreleased] fehlen erforderliche Kategorien: {sorted(missing_req)}. "
                        f"Leere Kategorien mit '- Keine.' füllen.")

    # --- Abgleich mit VERSION ---
    if has_unreleased and version_entries:
        # Version ist der geplante nächste Release-Stand, aber noch nicht datiert veröffentlicht
        pass  # Das ist der normale Entwicklungszustand
    elif not has_unreleased and version_entries:
        latest = version_entries[0][0]
        if latest != version:
            r.add_error(f"VERSION ({version}) weicht von aktuellstem CHANGELOG-Release ({latest}) ab")


def _check_readme_version(root, version, r):
    """Prüft, dass README genau die aktuelle VERSION referenziert — keine Drift."""
    readme = _read("README.md", root)
    # README zeigt die aktuelle Version als `0.1.0` — muss exakt mit VERSION übereinstimmen.
    # Suche das Pattern: `**Version:** [`...`](VERSION)`
    linked_version = re.search(r"\*\*Version:\*\*\s+\[`([^`]+)`\]\(VERSION\)", readme)
    if linked_version:
        displayed = linked_version.group(1)
        if displayed != version:
            r.add_error(f"README zeigt Version '{displayed}', aber VERSION enthält '{version}'")
    else:
        # Auch ein hartcodiertes v0.1.0 ohne Link ist Drift-gefährdet
        bare_version = re.search(r"\*\*Version:\*\*\s+`?(\d+\.\d+\.\d[^`\s]*)`?", readme)
        if bare_version:
            r.add_error(f"README zeigt Hartversion '{bare_version.group(1)}' ohne VERSION-Link — Drift-Gefahr")
        # Mindestanforderung: README muss VERSION referenzieren
        if "VERSION" not in readme and "versioniert" not in readme and "Release-Tag" not in readme:
            r.add_error("README referenziert keine versionierte Auslieferung (VERSION, Release-Tag)")


def _check_install_links(root, r):
    """Prüft, dass INSTALL.md keinen falschen VERSION-Pfad enthält."""
    inst = _read("INSTALL.md", root)
    # ../VERSION wäre der Pfad von tools/release_check.py aus — falsch im Repo-Root
    if "../VERSION" in inst:
        r.add_error("INSTALL.md referenziert '../VERSION' — korrekter Pfad ist 'VERSION' (vom Repo-Root)")
    if "VERSION" not in inst and "Version" not in inst and "Release" not in inst:
        r.add_warning("INSTALL.md enthält keinen Hinweis auf versionierte Installation")


# ═══════════════════════════════════════════════════════════════════════
# Tag-Konsistenz (benötigt Git-Historie)
# ═══════════════════════════════════════════════════════════════════════

def check_tag(root=None, tag_ref=None, expected_commit=None):
    """Prüft Konsistenz eines Git-Tags gegen VERSION.

    Args:
        root: Repository-Root (default: erkannt)
        tag_ref: Tag-Name (z. B. 'v0.1.0'). Wenn None, wird der erste v*-Tag verwendet.
        expected_commit: Erwarteter Commit-SHA. Wenn None, HEAD.

    Returns CheckResult.
    """
    if root is None:
        root = ROOT
    r = CheckResult()

    if not _exists("VERSION", root):
        r.add_error("VERSION fehlt — Tag-Prüfung ohne Version nicht möglich")
        return r

    version = _read("VERSION", root).strip().splitlines()[0].strip()
    expected_tag = f"v{version}"

    # ── Tag-Name ──
    if tag_ref is None:
        # Nimm den ersten v*-Tag
        out, err, code = _git(["tag", "-l", "v*"], root)
        if code != 0 or not out:
            r.add_error("Kein v*-Tag gefunden (tag-Liste leer oder git fehlgeschlagen)")
            return r
        tag_ref = out.splitlines()[0].strip()

    if tag_ref != expected_tag:
        r.add_error(f"Tag-Name '{tag_ref}' entspricht nicht 'v{{VERSION}}' = '{expected_tag}'")

    # ── Tag-Commit ──
    out, err, code = _git(["show-ref", "--hash", "--verify", f"refs/tags/{tag_ref}"], root)
    if code != 0:
        # Fallback: versuche tag direkt
        out, err, code = _git(["show-ref", "--hash", "--verify", f"refs/tags/{tag_ref}"], root)
    if code != 0:
        r.add_error(f"Tag '{tag_ref}' nicht auflösbar: {err}")
        return r
    tag_commit = out.strip().splitlines()[0] if out.strip() else ""

    if expected_commit is None:
        out2, err2, code2 = _git(["rev-parse", "HEAD"], root)
        if code2 != 0:
            r.add_error(f"HEAD nicht auflösbar: {err2}")
            return r
        expected_commit = out2.strip()

    if tag_commit != expected_commit:
        r.add_error(f"Tag '{tag_ref}' zeigt auf {tag_commit[:12]}, erwartet {expected_commit[:12]}")

    # ── Tag-Signatur (advisory) ──
    out, err, code = _git(["tag", "-v", tag_ref], root)
    if code != 0:
        r.add_warning(f"Tag '{tag_ref}' nicht verifizierbar (unsigniert oder unbekannter Key): {err[:120]}")

    return r


# ═══════════════════════════════════════════════════════════════════════
# GitHub-Release-Konsistenz (benötigt Netzwerk)
# ═══════════════════════════════════════════════════════════════════════

def check_release(root=None, tag_ref=None):
    """Prüft Konsistenz eines GitHub-Releases gegen Tag und VERSION.

    Benötigt gh CLI und Netzwerk. Read-only.

    Args:
        root: Repository-Root
        tag_ref: Tag-Name des Releases. Wenn None, wird v<VERSION> verwendet.

    Returns CheckResult.
    """
    if root is None:
        root = ROOT
    r = CheckResult()

    if not _exists("VERSION", root):
        r.add_error("VERSION fehlt — Release-Prüfung ohne Version nicht möglich")
        return r

    version = _read("VERSION", root).strip().splitlines()[0].strip()
    expected_tag = f"v{version}"

    if tag_ref is None:
        tag_ref = expected_tag

    if tag_ref != expected_tag:
        r.add_error(f"Release-Tag '{tag_ref}' entspricht nicht 'v{{VERSION}}' = '{expected_tag}'")

    # ── Release via gh CLI ──
    try:
        result = subprocess.run(
            ["gh", "release", "view", tag_ref, "--json", "tagName,targetCommitish"],
            cwd=root, capture_output=True, text=True, timeout=30
        )
    except FileNotFoundError:
        r.add_error("gh CLI nicht verfügbar — Release-Prüfung nicht möglich")
        return r
    except subprocess.TimeoutExpired:
        r.add_error(f"gh release view {tag_ref}: Timeout")
        return r

    if result.returncode != 0:
        r.add_error(f"GitHub-Release '{tag_ref}' nicht gefunden: {result.stderr.strip()[:120]}")
        return r

    import json
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        r.add_error(f"gh release view {tag_ref}: ungültige JSON-Antwort")
        return r

    release_tag = data.get("tagName", "")
    if release_tag != tag_ref:
        r.add_error(f"Release-Tag '{release_tag}' weicht von erwartetem Tag '{tag_ref}' ab")

    release_commit = data.get("targetCommitish", "")
    out, err, code = _git(["show-ref", "--hash", "--verify", f"refs/tags/{tag_ref}"], root)
    if code != 0:
        r.add_error(f"Tag '{tag_ref}' für Release-Commit-Vergleich nicht auflösbar")
    else:
        tag_commit = out.strip().splitlines()[0] if out.strip() else ""
        if re.match(r"^[0-9a-f]{40}$", release_commit) and release_commit != tag_commit:
            r.add_error(f"Release-Commit ({release_commit[:12]}) weicht von Tag-Commit ({tag_commit[:12]}) ab")

    return r


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print("usage: python3 tools/release_check.py {tree|tag|release} [args...]", file=sys.stderr)
        return STATUS_FAIL

    mode = sys.argv[1]
    if mode == "tree":
        result = check_tree()
    elif mode == "tag":
        result = check_tag()
    elif mode == "release":
        result = check_release()
    else:
        print(f"unknown mode: {mode}", file=sys.stderr)
        return STATUS_FAIL

    return result.exit()


if __name__ == "__main__":
    sys.exit(main())
