#!/usr/bin/env python3
"""Deterministische Release-Metadaten-Validierung des Repositorys.

Drei Modi — alle read-only:
  tree     Repository-/Tree-Konsistenz (VERSION ↔ CHANGELOG ↔ README ↔ INSTALL)
  tag      Tag-Konsistenz (benötigt Git-Historie und einen Tag-Ref)
  release  GitHub-Release-Konsistenz (benötigt Netzwerk und gh CLI)

Kein Modus erstellt Tags, Releases oder verändert das Repository.
"""

import json
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
SECTION_SPLIT_RE = re.compile(r"(?=^##\s+\[)", re.MULTILINE)
CHANGELOG_LINK_RE = re.compile(r"^\[(\d+\.\d+\.\d[^\]]*)\]:\s*(https?://\S+)", re.MULTILINE)

STATUS_OK = 0
STATUS_FAIL = 1


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


# ── Injizierbare Abhängigkeiten ──


class GitRunner:
    """Wrapper für git-CLI-Aufrufe — in Tests austauschbar."""

    @staticmethod
    def run(args, root, timeout=15):
        result = subprocess.run(
            ["git"] + args, cwd=root, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode

    @staticmethod
    def peel_to_commit(tag_ref, root):
        """Löst Tag auf den zugrunde liegenden Commit auf (annotierte Tags peelen)."""
        out, err, code = GitRunner.run(
            ["rev-parse", f"{tag_ref}^{{commit}}"], root
        )
        if code == 0:
            return out, ""
        return "", f"Cannot peel '{tag_ref}' to commit: {err}"

    @staticmethod
    def verify_signature(tag_ref, root):
        """Prüft die Signatur eines Tags. Gibt (success: bool, detail: str)."""
        out, err, code = GitRunner.run(["tag", "-v", tag_ref], root)
        if code == 0:
            return True, out
        return False, err[:200]


class GhRunner:
    """Wrapper für gh-CLI-Aufrufe — in Tests austauschbar."""

    @staticmethod
    def release_view(tag, root, timeout=30):
        """Read-only: gh release view --json. Gibt (data: dict|None, error: str|None)."""
        try:
            result = subprocess.run(
                ["gh", "release", "view", tag,
                 "--json", "tagName,targetCommitish,isDraft,isPrerelease"],
                cwd=root, capture_output=True, text=True, timeout=timeout
            )
        except FileNotFoundError:
            return None, "gh CLI nicht verfügbar"
        except subprocess.TimeoutExpired:
            return None, f"gh release view {tag}: Timeout"

        if result.returncode != 0:
            return None, f"GitHub-Release '{tag}' nicht gefunden: {result.stderr.strip()[:120]}"

        try:
            return json.loads(result.stdout), None
        except json.JSONDecodeError:
            return None, f"gh release view {tag}: ungültige JSON-Antwort"


# ── Hilfsfunktionen ──


def _read(rel, root):
    with open(os.path.join(root, rel), encoding="utf-8") as fh:
        return fh.read()


def _exists(rel, root):
    return os.path.exists(os.path.join(root, rel))


def _is_valid_semver(v):
    return bool(SEMVER_RE.match(v))


def _split_changelog_sections(changelog):
    """Teilt CHANGELOG-Text in Abschnitte: [(heading_line, body), ...]."""
    parts = SECTION_SPLIT_RE.split(changelog)
    sections = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        lines = part.split("\n")
        heading = lines[0].strip()
        body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
        sections.append((heading, body))
    return sections


def _parse_section(heading, body):
    """Parst einen CHANGELOG-Abschnitt und gibt Metadaten zurück."""
    cats = set(CATEGORY_HEADING_RE.findall(body))
    breaking_marker = BREAKING_MARKER_RE.search(body)
    has_breaking_entries = bool(BREAKING_ENTRY_RE.search(body))
    marker_value = breaking_marker.group(1).lower() if breaking_marker else None
    return {"categories": cats, "marker": marker_value, "has_breaking_entries": has_breaking_entries}


# ═══════════════════════════════════════════════════════════════════════
# Tree-Konsistenz
# ═══════════════════════════════════════════════════════════════════════

def check_tree(root=None):
    if root is None:
        root = ROOT
    r = CheckResult()

    # ── VERSION ──
    if not _exists("VERSION", root):
        r.add_error("VERSION fehlt — autoritative SemVer-Quelle erforderlich")
        return r

    version_raw = _read("VERSION", root)
    version_lines = [l for l in version_raw.splitlines() if l.strip()]
    if len(version_lines) != 1:
        r.add_error(f"VERSION enthält {len(version_lines)} nichtleere Zeilen — "
                    "exakt eine SemVer-Zeile erwartet (plus optionales finales Newline)")
        return r

    version = version_lines[0].strip()
    if not _is_valid_semver(version):
        r.add_error(f"VERSION '{version}' ist kein gültiges SemVer (MAJOR.MINOR.PATCH)")

    _check_no_competing_source(root, r)

    # ── CHANGELOG ──
    if not _exists("CHANGELOG.md", root):
        r.add_error("CHANGELOG.md fehlt — aktueller CHANGELOG erforderlich")
    else:
        _check_changelog_sections(root, version, r)

    # ── README (fehlend = Fehler) ──
    if not _exists("README.md", root):
        r.add_error("README.md fehlt")
    else:
        _check_readme_version(root, version, r)

    # ── INSTALL (fehlend = Fehler, ohne Versionsvertrag = Fehler) ──
    if not _exists("INSTALL.md", root):
        r.add_error("INSTALL.md fehlt")
    else:
        _check_install_links(root, r)

    return r


def _check_no_competing_source(root, r):
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


def _check_changelog_sections(root, version, r):
    """Abschnittsweise CHANGELOG-Validierung (Greptile-Finding #2)."""
    changelog = _read("CHANGELOG.md", root)
    sections = _split_changelog_sections(changelog)

    if not sections:
        r.add_error("CHANGELOG enthält weder [Unreleased] noch einen versionierten Eintrag")
        return

    # Prüfe Release-Links: dürfen nur für existierende Releases existieren
    links = dict(CHANGELOG_LINK_RE.findall(changelog))
    release_tags_present = bool(
        subprocess.run(["git", "tag", "-l", f"v{version}"], cwd=root,
                       capture_output=True, text=True).stdout.strip()
    )
    if not release_tags_present:
        # Kein Release-Tag → keine Release-Links in CHANGELOG
        if links:
            r.add_error(f"CHANGELOG enthält Release-Links ({sorted(links.keys())}), "
                        "aber kein v<VERSION>-Tag existiert. Links erst nach Release hinzufügen.")

    # Klassifiziere Abschnitte
    unreleased_sections = []
    release_sections = []
    for heading, body in sections:
        if UNRELEASED_HEADING_RE.match(heading):
            unreleased_sections.append((heading, body))
        else:
            m = VERSION_HEADING_RE.match(heading)
            if m:
                release_sections.append((m.group(1), m.group(2) or "", body))
            # Andernfalls ignorieren (Preamble etc.)

    # ── [Unreleased]-Prüfungen ──

    if len(unreleased_sections) == 0:
        r.add_error("[Unreleased]-Abschnitt fehlt")
    elif len(unreleased_sections) > 1:
        r.add_error(f"{len(unreleased_sections)} [Unreleased]-Abschnitte — genau einer erlaubt")
    elif release_sections and sections and unreleased_sections:
        # Finde den ersten ##-Abschnitt (nach Preamble) und prüfe ob es [Unreleased] ist
        first_heading_section = next(
            (s for s in sections if UNRELEASED_HEADING_RE.match(s[0]) or VERSION_HEADING_RE.match(s[0])),
            None
        )
        if first_heading_section and first_heading_section != unreleased_sections[0]:
            r.add_error("[Unreleased] muss vor versionierten Abschnitten stehen")

    for heading, body in unreleased_sections:
        meta = _parse_section(heading, body)
        missing = REQUIRED_CATEGORIES - meta["categories"]
        if missing:
            r.add_error(f"[Unreleased] fehlen erforderliche Kategorien: {sorted(missing)}. "
                        f"Leere Kategorien mit '- Keine.' füllen.")
        unknown = meta["categories"] - VALID_CATEGORIES
        if unknown:
            r.add_error(f"[Unreleased] enthält unbekannte Kategorien: {sorted(unknown)}")
        if meta["marker"] is None:
            r.add_error("[Unreleased] fehlt der Marker '**Breaking changes:** none' oder '**Breaking changes:** present'")
        elif meta["marker"] == "present" and not meta["has_breaking_entries"]:
            r.add_error("[Unreleased]: '**Breaking changes:** present' gesetzt, "
                        "aber kein Eintrag mit '**BREAKING:**' Präfix gefunden")

    # ── Release-Abschnitt-Prüfungen ──

    seen = {}
    prev_version = None
    for ver, date, body in release_sections:
        if ver in seen:
            r.add_error(f"CHANGELOG: doppelte Versionsüberschrift [{ver}]")
        seen[ver] = True

        if not _is_valid_semver(ver):
            r.add_error(f"CHANGELOG: '[{ver}]' ist kein gültiges SemVer")

        # SemVer-Reihenfolge: höhere Versionen müssen VOR niedrigeren stehen
        if prev_version is not None:
            if _semver_cmp(prev_version, ver) <= 0:
                r.add_error(f"CHANGELOG: [{prev_version}] vor [{ver}] — "
                            f"Versionen müssen absteigend (neueste zuerst) stehen")
        prev_version = ver

        meta = _parse_section("", body)
        unknown = meta["categories"] - VALID_CATEGORIES
        if unknown:
            r.add_error(f"[{ver}]: unbekannte Kategorien {sorted(unknown)}")
        if meta["marker"] is None:
            r.add_error(f"[{ver}] fehlt der Marker '**Breaking changes:** none' oder '**Breaking changes:** present'")
        elif meta["marker"] == "present" and not meta["has_breaking_entries"]:
            r.add_error(f"[{ver}]: '**Breaking changes:** present' ohne '**BREAKING:**' Eintrag")

    # ── Abgleich mit VERSION ──
    if unreleased_sections:
        pass  # Entwicklungszustand: Version ist Ziel, noch nicht veröffentlicht
    elif release_sections:
        latest = release_sections[0][0]
        if latest != version:
            r.add_error(f"VERSION ({version}) weicht von aktuellstem CHANGELOG-Release ({latest}) ab")


def _semver_cmp(a, b):
    """Vergleicht zwei SemVer-Strings. >0 wenn a > b, 0 wenn gleich, <0 wenn a < b."""
    def parts(v):
        core = v.split("-")[0]
        return tuple(int(x) for x in core.split("."))
    pa, pb = parts(a), parts(b)
    if pa > pb: return 1
    if pa < pb: return -1
    return 0


def _check_readme_version(root, version, r):
    readme = _read("README.md", root)
    linked_version = re.search(r"\*\*Version:\*\*\s+\[`([^`]+)`\]\(VERSION\)", readme)
    if linked_version:
        displayed = linked_version.group(1)
        if displayed != version:
            r.add_error(f"README zeigt Version '{displayed}', aber VERSION enthält '{version}'")
    else:
        bare_version = re.search(r"\*\*Version:\*\*\s+`?(\d+\.\d+\.\d[^`\s]*)`?", readme)
        if bare_version:
            r.add_error(f"README zeigt Hartversion '{bare_version.group(1)}' ohne VERSION-Link — Drift-Gefahr")
        # README muss VERSION als autoritative Quelle nennen
        if "VERSION" not in readme and "versioniert" not in readme and "Release-Tag" not in readme:
            r.add_error("README referenziert keine versionierte Auslieferung (VERSION, Release-Tag)")


def _check_install_links(root, r):
    inst = _read("INSTALL.md", root)
    if "../VERSION" in inst:
        r.add_error("INSTALL.md referenziert '../VERSION' — korrekter Pfad ist 'VERSION' (vom Repo-Root)")
    # INSTALL muss den VERSION-Pfad oder Release-Referenz enthalten (kein Warning mehr)
    if "VERSION" not in inst and "Version" not in inst and "Release" not in inst:
        r.add_error("INSTALL.md enthält keinen Hinweis auf versionierte Installation (VERSION/Release)")


# ═══════════════════════════════════════════════════════════════════════
# Tag-Konsistenz
# ═══════════════════════════════════════════════════════════════════════

def check_tag(root=None, tag_ref=None, expected_commit=None, verifier=None):
    """Prüft Konsistenz eines Git-Tags gegen VERSION.

    Args:
        root: Repository-Root
        tag_ref: Tag-Name. Wenn None → deterministisch v{VERSION}
        expected_commit: Erwarteter Commit-SHA. Wenn None, HEAD.
        verifier: Callable(tag_ref, root) → (ok: bool, detail: str).
                  Wenn None → GitRunner.verify_signature.
    """
    if root is None:
        root = ROOT
    r = CheckResult()

    if not _exists("VERSION", root):
        r.add_error("VERSION fehlt — Tag-Prüfung ohne Version nicht möglich")
        return r

    version = _read("VERSION", root).strip().splitlines()[0].strip()
    expected_tag = f"v{version}"

    # ── Tag deterministisch wählen (Greptile-Finding #1) ──
    if tag_ref is None:
        tag_ref = expected_tag
    if tag_ref != expected_tag:
        r.add_error(f"Tag-Name '{tag_ref}' entspricht nicht 'v{{VERSION}}' = '{expected_tag}'")

    # ── Tag existiert? ──
    out, err, code = GitRunner.run(["tag", "-l", tag_ref], root)
    if code != 0 or not out.strip():
        r.add_error(f"Tag '{tag_ref}' nicht gefunden")
        return r

    # ── Tag-Commit via peel (Greptile-Finding #3) ──
    tag_commit, peel_err = GitRunner.peel_to_commit(tag_ref, root)
    if peel_err:
        r.add_error(f"Tag '{tag_ref}' nicht auf Commit auflösbar: {peel_err}")
        return r

    if expected_commit is None:
        out2, err2, code2 = GitRunner.run(["rev-parse", "HEAD"], root)
        if code2 != 0:
            r.add_error(f"HEAD nicht auflösbar: {err2}")
            return r
        expected_commit = out2.strip()

    if tag_commit != expected_commit:
        r.add_error(f"Tag '{tag_ref}' zeigt auf {tag_commit[:12]}, erwartet {expected_commit[:12]}")

    # ── Signaturprüfung (blockierend wenn README signierten Tag verlangt) ──
    vf = verifier or GitRunner.verify_signature
    sig_ok, sig_detail = vf(tag_ref, root)
    if not sig_ok:
        r.add_error(f"Tag '{tag_ref}' Signaturprüfung fehlgeschlagen: {sig_detail[:200]}")

    return r


# ═══════════════════════════════════════════════════════════════════════
# GitHub-Release-Konsistenz
# ═══════════════════════════════════════════════════════════════════════

def check_release(root=None, tag_ref=None, gh=None):
    """Prüft Konsistenz eines GitHub-Releases gegen Tag und VERSION.

    Args:
        root: Repository-Root
        tag_ref: Tag-Name. Wenn None → v{VERSION}
        gh: GhRunner-artiges Objekt mit release_view(tag, root) → (dict|None, str|None).
            Wenn None → GhRunner.release_view.
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

    # ── Release-Daten via gh ──
    gh_runner = gh or GhRunner
    data, error = gh_runner.release_view(tag_ref, root)
    if error:
        r.add_error(error)
        return r
    if data is None:
        r.add_error(f"GitHub-Release '{tag_ref}': keine Daten")
        return r

    # ── tagName ──
    release_tag_name = data.get("tagName", "")
    if release_tag_name != tag_ref:
        r.add_error(f"Release-tagName '{release_tag_name}' != erwartet '{tag_ref}'")

    # ── Draft ──
    if data.get("isDraft", False):
        r.add_error(f"GitHub-Release '{tag_ref}' ist ein Draft — muss published sein")

    # ── Commit-Vergleich (Greptile-Finding #4) ──
    # Peeling: lokalen Tag auf Commit auflösen
    local_commit, peel_err = GitRunner.peel_to_commit(tag_ref, root)
    if peel_err:
        r.add_error(f"Lokaler Tag '{tag_ref}' nicht auf Commit auflösbar: {peel_err}")
        return r

    target = data.get("targetCommitish", "")
    resolved, resolve_err = _resolve_target_commitish(target, root)
    if resolve_err:
        r.add_error(f"targetCommitish '{target}' nicht auflösbar: {resolve_err}")
    elif resolved != local_commit:
        r.add_error(f"Release-targetCommitish '{target}' ({resolved[:12]}) "
                    f"weicht von Tag-Commit ({local_commit[:12]}) ab")

    return r


def _resolve_target_commitish(target, root):
    """Löst targetCommitish deterministisch auf einen Commit-SHA auf.

    Priorität:
      1. 40-stelliger Hex-SHA (direkt)
      2. refs/heads/<target>
      3. refs/remotes/origin/<target>
      4. <target> (normaler Git-Ref)

    Jede Auflösung endet mit git rev-parse ref^{commit} (Peeling).
    Gibt (sha: str, error: str|None).
    """
    if re.match(r"^[0-9a-f]{40}$", target):
        return target, None

    for ref in (f"refs/heads/{target}", f"refs/remotes/origin/{target}", target):
        out, err, code = GitRunner.run(["rev-parse", f"{ref}^{{commit}}"], root)
        if code == 0 and out.strip():
            return out.strip(), None

    return "", f"'{target}' nicht auflösbar (weder SHA, refs/heads/, refs/remotes/origin/ noch Bare-Ref)"


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print("usage: python3 tools/release_check.py tree", file=sys.stderr)
        print("       python3 tools/release_check.py tag [TAG_NAME]", file=sys.stderr)
        print("       python3 tools/release_check.py release [TAG_NAME]", file=sys.stderr)
        return STATUS_FAIL

    mode = sys.argv[1]
    if mode == "tree":
        result = check_tree()
    elif mode == "tag":
        tag_ref = sys.argv[2] if len(sys.argv) > 2 else None
        result = check_tag(tag_ref=tag_ref)
    elif mode == "release":
        tag_ref = sys.argv[2] if len(sys.argv) > 2 else None
        result = check_release(tag_ref=tag_ref)
    else:
        print(f"unknown mode: {mode}", file=sys.stderr)
        return STATUS_FAIL

    return result.exit()


if __name__ == "__main__":
    sys.exit(main())
