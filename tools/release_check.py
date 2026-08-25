#!/usr/bin/env python3
"""Deterministische Release-Metadaten-Validierung des Repositorys.

Vier Modi — alle read-only:
  tree         Repository-/Tree-Konsistenz (VERSION, CHANGELOG, Dokumentlinks)
  docs-remote  Kanonische Dokumentziele auf GitHub main (benötigt Netzwerk und gh CLI)
  tag          Tag-Konsistenz (benötigt Git-Historie, Tag-Ref und optional erwarteten Commit)
  release      GitHub-Release-Konsistenz (benötigt Netzwerk und gh CLI)

Kein Modus erstellt Tags, Releases oder verändert das Repository.
"""

import base64
import binascii
from datetime import date as calendar_date
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from urllib.parse import quote, urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SEMVER_RE = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-((?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
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
DOCUMENTATION_LINK_LINE_RE = re.compile(
    r"^- \[[\w ,./&-]+\]\(([^()\s]+)\)$"
)
DOCUMENTATION_SECTION_RE = re.compile(
    r"(?ms)^## Dokumentation\s*$\n(?P<body>.*?)(?=^##\s|\Z)"
)

CANONICAL_DOCUMENT_PATHS = (
    "docs/installer-cli-reference.md",
    "docs/harness-recipes.md",
    "docs/installer-architecture.md",
    "docs/installer-threat-model.md",
    "docs/installer-json-schemas.md",
    "CHANGELOG.md",
    "bundle/GOVERNANCE.md",
)
GITHUB_HOST = "github.com"
GITHUB_OWNER = "tomtastisch"
GITHUB_REPOSITORY = "agent-governance"
GITHUB_CURRENT_REF = "main"

STATUS_OK = 0
STATUS_FAIL = 1

RELEASE_ALLOWED_SIGNERS_REL = os.path.join(
    ".github", "signing", "allowed_signers"
)
RELEASE_SIGNER_PRINCIPAL = "82227609+tomtastisch@users.noreply.github.com"
RELEASE_SIGNER_NAMESPACE = "git"
RELEASE_SIGNER_KEY_TYPE = "ssh-ed25519"
RELEASE_SIGNER_FINGERPRINT = (
    "SHA256:Ltw3DKt+a7felQ4r3C+iKSqeo3/4F9XyqO5sJMP1+TM"
)

VENDORED_UPSTREAM_REL = os.path.join(
    "integrations", "microsoft-agent-governance-toolkit", "upstream"
)
VENDORED_UPSTREAM_SENTINELS = (
    os.path.join(
        "integrations", "microsoft-agent-governance-toolkit", "upstream.lock.toml"
    ),
    os.path.join(
        "integrations", "microsoft-agent-governance-toolkit", "snapshot.files.sha256"
    ),
)


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
        allowed_signers, trust_error = _validate_release_trust_anchor(root)
        if trust_error:
            return False, trust_error

        out, err, code = GitRunner.run(
            [
                "-c",
                f"gpg.ssh.allowedSignersFile={allowed_signers}",
                "tag",
                "-v",
                tag_ref,
            ],
            root,
        )
        if code == 0:
            return True, out or err
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

    @staticmethod
    def api_content(endpoint, root, timeout=30):
        """Read-only: gibt das geparste GitHub-Contents-Objekt oder einen Fehler zurück."""
        try:
            result = subprocess.run(
                ["gh", "api", endpoint],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError:
            return None, "gh CLI nicht verfügbar"
        except subprocess.TimeoutExpired:
            return None, f"gh api {endpoint}: Timeout"
        except OSError as error:
            return None, f"gh api {endpoint}: nicht ausführbar: {error}"

        if result.returncode != 0:
            detail = result.stderr.strip()[:200] or f"Exit {result.returncode}"
            return None, f"gh api {endpoint}: {detail}"
        try:
            return json.loads(result.stdout), None
        except json.JSONDecodeError:
            return None, f"gh api {endpoint}: ungültige JSON-Antwort"


# ── Hilfsfunktionen ──


def _read(rel, root):
    with open(os.path.join(root, rel), encoding="utf-8") as fh:
        return fh.read()


def _exists(rel, root):
    return os.path.exists(os.path.join(root, rel))


def _validate_release_trust_anchor(root):
    """Validiert den versionierten SSH-Release-Trust-Anchor fail-closed."""
    allowed_signers = os.path.abspath(
        os.path.join(root, RELEASE_ALLOWED_SIGNERS_REL)
    )

    try:
        file_stat = os.lstat(allowed_signers)
    except OSError:
        return "", f"Release trust anchor fehlt: {RELEASE_ALLOWED_SIGNERS_REL}"

    if stat.S_ISLNK(file_stat.st_mode) or not stat.S_ISREG(file_stat.st_mode):
        return "", "Release trust anchor muss eine reguläre Nicht-Symlink-Datei sein"

    try:
        with open(allowed_signers, encoding="utf-8") as fh:
            active_lines = [
                line.strip()
                for line in fh
                if line.strip() and not line.lstrip().startswith("#")
            ]
    except (OSError, UnicodeError):
        return "", "Release trust anchor ist nicht lesbar"

    if len(active_lines) != 1:
        return "", "Release trust anchor muss genau einen aktiven Signer enthalten"

    fields = active_lines[0].split()
    if len(fields) != 4:
        return "", "Release trust anchor muss exakt vier Felder enthalten"

    principal, options, key_type, key_blob = fields
    if principal != RELEASE_SIGNER_PRINCIPAL:
        return "", "Release trust anchor enthält nicht den genehmigten Principal"
    if options != f'namespaces="{RELEASE_SIGNER_NAMESPACE}"':
        return "", "Release trust anchor enthält nicht exakt den Git-Namespace"
    if key_type != RELEASE_SIGNER_KEY_TYPE:
        return "", "Release trust anchor enthält nicht den genehmigten Key-Typ"

    try:
        decoded_key = base64.b64decode(key_blob, validate=True)
    except (binascii.Error, ValueError):
        return "", "Release trust anchor enthält kein gültiges Base64-Keyblob"

    fingerprint = "SHA256:" + base64.b64encode(
        hashlib.sha256(decoded_key).digest()
    ).decode("ascii").rstrip("=")
    if fingerprint != RELEASE_SIGNER_FINGERPRINT:
        return "", "Release trust anchor stimmt nicht mit dem genehmigten Fingerprint überein"

    return allowed_signers, ""


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

    version = _check_version_release_metadata(root, r)
    if version is None:
        return r

    document_links = _check_document_links(root)
    r.errors.extend(document_links.errors)
    r.warnings.extend(document_links.warnings)

    return r


def _check_version_release_metadata(root, r):
    """Validates VERSION projections and its unique current changelog release read-only."""
    if not _exists("VERSION", root):
        r.add_error("VERSION fehlt — autoritative SemVer-Quelle erforderlich")
        return None

    with open(os.path.join(root, "VERSION"), encoding="utf-8", newline="") as handle:
        version_raw = handle.read()
    if version_raw.endswith("\n"):
        version_raw = version_raw[:-1]
    if "\n" in version_raw or "\r" in version_raw or not _is_valid_semver(version_raw):
        r.add_error("VERSION muss exakt SemVer oder SemVer mit einem finalen LF enthalten")
        return None

    version = version_raw

    _check_version_projections(root, version, r)
    _check_no_competing_source(root, r)

    if not _exists("CHANGELOG.md", root):
        r.add_error("CHANGELOG.md fehlt — aktueller CHANGELOG erforderlich")
    else:
        _check_changelog_sections(root, version, r)
    return version


def _check_version_projections(root, version, r):
    """Checks every npm projection independently from the write-only synchronizer."""
    for rel in ("package.json", "package-lock.json"):
        if not _exists(rel, root):
            r.add_error(f"{rel} fehlt — VERSION-Projektion erforderlich")
            continue
        try:
            data = json.loads(_read(rel, root))
        except (json.JSONDecodeError, OSError):
            r.add_error(f"{rel}: ungültiges JSON für VERSION-Abgleich")
            continue
        if not isinstance(data, dict):
            r.add_error(f"{rel}: JSON-Objekt für VERSION-Abgleich erforderlich")
            continue
        if data.get("version") != version:
            r.add_error(f"{rel}-Version ({data.get('version')}) weicht von VERSION ({version}) ab")
        if rel == "package-lock.json":
            packages = data.get("packages")
            root_package = packages.get("") if isinstance(packages, dict) else None
            if not isinstance(root_package, dict):
                r.add_error("package-lock.json Root-Paketstruktur packages[\"\"] fehlt oder ist ungültig")
            elif root_package.get("version") != version:
                r.add_error(
                    f"package-lock.json Root-Paketversion ({root_package.get('version')}) "
                    f"weicht von VERSION ({version}) ab"
                )


def _check_no_competing_source(root, r):
    authority = {"VERSION", "CHANGELOG.md"}
    authoritative_version = _read("VERSION", root).strip()
    vendored_root = os.path.abspath(os.path.join(root, VENDORED_UPSTREAM_REL))
    vendored_materialized = all(_exists(path, root) for path in VENDORED_UPSTREAM_SENTINELS)
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in {".git", "tests", ".github", "node_modules", "dist"}]
        if vendored_materialized:
            dirs[:] = [
                directory
                for directory in dirs
                if os.path.abspath(os.path.join(base, directory)) != vendored_root
            ]
        for name in files:
            rel = os.path.relpath(os.path.join(base, name), root)
            if rel in authority:
                continue
            if name.endswith(".toml"):
                txt = _read(rel, root)
                if re.search(r'(?m)^version\s*=\s*"\d+\.\d+\.\d+', txt):
                    r.add_error(f"{rel}: konkurrierende version-Deklaration")
            elif name.endswith(".json"):
                if rel in {"package.json", "package-lock.json"}:
                    continue
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

    current_sections = [(ver, section_date, body) for ver, section_date, body in release_sections if ver == version]
    if len(current_sections) != 1:
        r.add_error(
            f"CHANGELOG muss genau einen aktuellen Abschnitt [{version}] enthalten; gefunden: {len(current_sections)}"
        )
        return

    current_version, current_date, current_body = current_sections[0]
    if not release_sections or release_sections[0][0] != current_version:
        r.add_error(f"[{version}] muss der erste versionierte CHANGELOG-Abschnitt sein")
    if not current_date or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", current_date):
        r.add_error(f"[{version}] benötigt ein gültiges ISO-Datum (YYYY-MM-DD)")
    else:
        try:
            calendar_date.fromisoformat(current_date)
        except ValueError:
            r.add_error(f"[{version}] benötigt ein gültiges ISO-Datum (YYYY-MM-DD)")

    current_meta = _parse_section("", current_body)
    missing = REQUIRED_CATEGORIES - current_meta["categories"]
    if missing:
        r.add_error(f"[{version}] fehlen erforderliche Kategorien: {sorted(missing)}")
    if current_meta["marker"] is None:
        r.add_error(f"[{version}] fehlt der Marker '**Breaking changes:** none' oder '**Breaking changes:** present'")


def _semver_cmp(a, b):
    """Vergleicht zwei SemVer-Strings. >0 wenn a > b, 0 wenn gleich, <0 wenn a < b."""
    def parts(v):
        without_build = v.split("+", 1)[0]
        core, separator, prerelease = without_build.partition("-")
        return tuple(int(x) for x in core.split(".")), (
            prerelease.split(".") if separator else None
        )

    (core_a, pre_a), (core_b, pre_b) = parts(a), parts(b)
    if core_a != core_b:
        return 1 if core_a > core_b else -1
    if pre_a is None or pre_b is None:
        if pre_a is None and pre_b is None:
            return 0
        return 1 if pre_a is None else -1

    for identifier_a, identifier_b in zip(pre_a, pre_b):
        if identifier_a == identifier_b:
            continue
        numeric_a, numeric_b = identifier_a.isdigit(), identifier_b.isdigit()
        if numeric_a and numeric_b:
            return 1 if int(identifier_a) > int(identifier_b) else -1
        if numeric_a != numeric_b:
            return -1 if numeric_a else 1
        return 1 if identifier_a > identifier_b else -1

    if len(pre_a) == len(pre_b):
        return 0
    return 1 if len(pre_a) > len(pre_b) else -1


def _check_document_links(root):
    """Prüft den exakten README-Linkvertrag vollständig offline."""
    r = CheckResult()
    root_real = os.path.realpath(os.path.abspath(root))

    if os.path.lexists(os.path.join(root_real, "INSTALL.md")):
        r.add_error("INSTALL.md muss nach abgeschlossener Inhaltsmigration entfernt sein")
    if os.path.lexists(os.path.join(root_real, "docs", "images")):
        r.add_error("veralteter Pfad docs/images muss entfernt sein")

    for path in CANONICAL_DOCUMENT_PATHS:
        _check_confined_regular_file(root_real, path, r)

    if not _check_confined_regular_file(root_real, "README.md", r):
        return r

    readme = _read("README.md", root_real)
    section = DOCUMENTATION_SECTION_RE.search(readme)
    if section is None:
        r.add_error("README.md: Abschnitt 'Dokumentation' fehlt")
        return r

    seen = {path: 0 for path in CANONICAL_DOCUMENT_PATHS}
    urls = []
    for line in section.group("body").splitlines():
        if not line.strip():
            continue
        link = DOCUMENTATION_LINK_LINE_RE.fullmatch(line)
        if link is None:
            r.add_error(
                "README.md: Dokumentationsabschnitt verletzt die geschlossene Markdown-Grammatik"
            )
            continue
        urls.append(link.group(1))
    for url in urls:
        path = _validate_current_document_url(url, r)
        if path in seen:
            seen[path] += 1

    for path, count in seen.items():
        if count == 0:
            r.add_error(f"README.md: kanonischer Dokumentlink fehlt: {path}")
        elif count > 1:
            r.add_error(f"README.md: kanonischer Dokumentlink ist mehrfach vorhanden: {path}")
    return r


def _check_confined_regular_file(root_real, path, r):
    """Lehnt Root-Escape, fehlende Pfade, Symlinks und Nicht-Dateien ab."""
    candidate = os.path.join(root_real, *path.split("/"))
    target_real = os.path.realpath(candidate)
    try:
        confined = os.path.commonpath((root_real, target_real)) == root_real
    except ValueError:
        confined = False
    if not confined:
        r.add_error(f"{path}: lokales Ziel verlässt das Repository")
        return False
    try:
        file_stat = os.lstat(candidate)
    except OSError:
        r.add_error(f"{path}: lokales Ziel fehlt oder ist keine reguläre Datei")
        return False
    if stat.S_ISLNK(file_stat.st_mode):
        r.add_error(f"{path}: lokales Ziel darf kein Symlink sein")
        return False
    if not stat.S_ISREG(file_stat.st_mode):
        r.add_error(f"{path}: lokales Ziel ist keine reguläre Datei")
        return False
    return True


def _validate_current_document_url(url, r):
    """Validiert genau eine URL aus dem README-Dokumentationsabschnitt."""
    try:
        parsed = urlsplit(url)
    except ValueError as error:
        r.add_error(f"README.md: ungültige Dokument-URL '{url}': {error}")
        return None

    if parsed.scheme != "https":
        r.add_error(f"README.md: Dokumentlink verwendet nicht https: {url}")
        return None
    if parsed.netloc != GITHUB_HOST:
        r.add_error(f"README.md: Dokumentlink hat unerwarteten Host: {url}")
        return None
    if parsed.query or parsed.fragment:
        r.add_error(f"README.md: Dokumentlink enthält unerlaubtes Query/Fragment: {url}")
        return None
    if "%" in parsed.path or "\\" in parsed.path:
        r.add_error(f"README.md: Dokumentlink enthält einen kodierten oder ungültigen Pfad: {url}")
        return None

    parts = parsed.path.split("/")
    if any(part in {".", ".."} for part in parts):
        r.add_error(f"README.md: Dokumentlink enthält Pfadtraversal: {url}")
        return None
    if len(parts) < 6 or parts[0] != "":
        r.add_error(f"README.md: Dokumentlink hat eine ungültige GitHub-Pfadform: {url}")
        return None
    if parts[1:3] != [GITHUB_OWNER, GITHUB_REPOSITORY]:
        r.add_error(f"README.md: Dokumentlink hat unerwartetes Owner/Repository: {url}")
        return None
    if parts[3] != "blob":
        r.add_error(f"README.md: Dokumentlink verwendet nicht die GitHub-blob-Ansicht: {url}")
        return None
    if parts[4] != GITHUB_CURRENT_REF:
        r.add_error(f"README.md: Dokumentlink verwendet nicht den main-Ref: {url}")
        return None

    repo_path = "/".join(parts[5:])
    if repo_path not in CANONICAL_DOCUMENT_PATHS:
        r.add_error(f"README.md: unerwarteter Dokumentpfad: {repo_path}")
        return None
    return repo_path


def _contents_endpoint(path):
    """Baut einen argument-sicheren GitHub-Contents-Endpunkt aus dem geschlossenen Pfadsatz."""
    if path not in CANONICAL_DOCUMENT_PATHS:
        raise ValueError(f"unerwarteter Dokumentpfad: {path}")
    encoded_path = "/".join(quote(part, safe="") for part in path.split("/"))
    return (
        f"repos/{GITHUB_OWNER}/{GITHUB_REPOSITORY}/contents/"
        f"{encoded_path}?ref={GITHUB_CURRENT_REF}"
    )


def check_docs_remote(root=None, gh=None, timeout=30):
    """Prüft den geschlossenen kanonischen Dokumentpfadsatz auf GitHub main."""
    if root is None:
        root = ROOT
    runner = gh or GhRunner
    r = CheckResult()
    for path in CANONICAL_DOCUMENT_PATHS:
        endpoint = _contents_endpoint(path)
        data, error = runner.api_content(endpoint, root, timeout=timeout)
        if error:
            r.add_error(f"Remote-Dokumentziel fehlt oder ist nicht prüfbar ({path}): {error}")
        elif not isinstance(data, dict):
            r.add_error(f"Remote-Dokumentziel ist kein GitHub-Contents-Dateiobjekt ({path})")
        elif data.get("type") != "file":
            r.add_error(f"Remote-Dokumentziel hat nicht type 'file' ({path})")
        elif data.get("path") != path:
            r.add_error(f"Remote-Dokumentziel hat nicht den erwarteten path ({path})")
    return r


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

    version = _check_version_release_metadata(root, r)
    if version is None or not r.ok:
        return r
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

def check_release(root=None, tag_ref=None, gh=None, verifier=None):
    """Prüft Konsistenz eines GitHub-Releases gegen Tag und VERSION.

    Args:
        root: Repository-Root
        tag_ref: Tag-Name. Wenn None → v{VERSION}
        gh: GhRunner-artiges Objekt mit release_view(tag, root) → (dict|None, str|None).
            Wenn None → GhRunner.release_view.
        verifier: Callable(tag_ref, root) → (ok: bool, detail: str).
            Wenn None → GitRunner.verify_signature.
    """
    if root is None:
        root = ROOT
    r = CheckResult()

    version = _check_version_release_metadata(root, r)
    if version is None or not r.ok:
        return r
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

    expected_prerelease = SEMVER_RE.match(version).group(4) is not None
    if data.get("isPrerelease") is not expected_prerelease:
        r.add_error(
            f"GitHub-Release '{tag_ref}' Prerelease-Flag "
            f"({data.get('isPrerelease')}) entspricht nicht VERSION ({version})"
        )

    # ── Commit-Vergleich (Greptile-Finding #4) ──
    # Peeling: lokalen Tag auf Commit auflösen
    local_commit, peel_err = GitRunner.peel_to_commit(tag_ref, root)
    if peel_err:
        r.add_error(f"Lokaler Tag '{tag_ref}' nicht auf Commit auflösbar: {peel_err}")
        return r

    vf = verifier or GitRunner.verify_signature
    sig_ok, sig_detail = vf(tag_ref, root)
    if not sig_ok:
        r.add_error(f"Tag '{tag_ref}' Signaturprüfung fehlgeschlagen: {sig_detail[:200]}")

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
        print("       python3 tools/release_check.py docs-remote", file=sys.stderr)
        print("       python3 tools/release_check.py tag [TAG_NAME] [EXPECTED_COMMIT]", file=sys.stderr)
        print("       python3 tools/release_check.py release [TAG_NAME]", file=sys.stderr)
        return STATUS_FAIL

    mode = sys.argv[1]
    if mode == "tree":
        result = check_tree()
    elif mode == "docs-remote":
        result = check_docs_remote()
    elif mode == "tag":
        tag_ref = sys.argv[2] if len(sys.argv) > 2 else None
        expected_commit = sys.argv[3] if len(sys.argv) > 3 else None
        result = check_tag(tag_ref=tag_ref, expected_commit=expected_commit)
    elif mode == "release":
        tag_ref = sys.argv[2] if len(sys.argv) > 2 else None
        result = check_release(tag_ref=tag_ref)
    else:
        print(f"unknown mode: {mode}", file=sys.stderr)
        return STATUS_FAIL

    return result.exit()


if __name__ == "__main__":
    sys.exit(main())
