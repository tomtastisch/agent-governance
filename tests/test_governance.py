#!/usr/bin/env python3
"""Konsistenz- und Drift-Tests für das Agent-Governance-Regelwerk (Kern §9, §11, §13).

Diese Suite greift real: sie liest die Regelwerksdateien und schlägt fehl, sobald eine Quelle
gegen eine andere driftet (z. B. eine Regel nennt einen Port, den kein Adapter definiert; ein
Werkzeug im Brewfile fehlt im Katalog `tools/tools.md`; ein §-Verweis zeigt ins Leere). Ziel:
die SSOT-Zusagen des Kerns ohne menschliche Pflege überprüfbar halten.

Ausführung ohne Fremdabhängigkeiten:
    python3 -m unittest discover -s tests

Die `core/branch-tags.toml`-Validierung nutzt das stdlib-Modul `tomllib` (Python 3.11+); auf
älteren Interpretern überspringt sich nur dieser Prüfblock sauber, die übrigen Checks laufen
weiter. CI pinnt 3.11 und erzwingt daher die volle Prüfung.
"""
import os
import re
import unittest

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11: nur die TOML-Prüfung entfällt, Rest läuft weiter.
    tomllib = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def exists(rel):
    return os.path.exists(os.path.join(ROOT, rel))


def load_toml(rel):
    with open(os.path.join(ROOT, rel), "rb") as fh:
        return tomllib.load(fh)


def tracked_markdown(exclude=()):
    """Alle .md-Dateien des Repos, ohne .git/tests/.github und ohne explizite Ausnahmen."""
    out = []
    skip_dirs = {".git", "tests", ".github"}
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for name in files:
            if not name.endswith(".md"):
                continue
            rel = os.path.relpath(os.path.join(base, name), ROOT)
            if rel not in exclude:
                out.append(rel)
    return out


def first_column_keys(text):
    """Backtick-Schlüssel der ersten Tabellenspalte: `| \\`key\\` | ... |`."""
    return set(re.findall(r"(?m)^\|\s*`([^`]+)`\s*\|", text))


def get_section(text, heading):
    """Text zwischen einer `## Überschrift` und der nächsten `## `-Überschrift."""
    m = re.search(r"(?m)^" + re.escape(heading) + r"\s*$", text)
    if not m:
        return ""
    start = m.end()
    nxt = re.search(r"(?m)^##\s", text[start:])
    return text[start:start + nxt.start()] if nxt else text[start:]


CORE = read("core/core.md")
CLAUDE = read("adapters/claude.md")
CODEX = read("adapters/codex.md")
README = read("README.md")
PROFILE_EX = read("profile/profile.example.md")
TOOLS = read("tools/tools.md")
BREW = read("tools/Brewfile")
BREW_OPT = read("tools/Brewfile.optional")
TPL_CLAUDE = read("templates/CLAUDE.md")

ROLES = ("ak", "st", "qa", "sec")


class PortContract(unittest.TestCase):
    """Kern ↔ Adapter ↔ README-Port-Vertrag: jede referenzierte Bindung ist definiert."""

    def setUp(self):
        self.readme_ports = first_column_keys(get_section(README, "## Port-Vertrag"))
        self.claude_keys = first_column_keys(get_section(CLAUDE, "## Bindings"))
        self.codex_keys = first_column_keys(get_section(CODEX, "## Bindings"))
        # `key` ist im Intro nur ein Format-Beispiel (`[BINDING:key]`), kein echter Schlüssel.
        self.used = set(re.findall(r"\[BINDING:([a-z0-9_.]+)\]", CORE)) - {"key"}

    def test_readme_declares_ports(self):
        self.assertTrue(self.readme_ports, "Port-Vertrag-Tabelle in README nicht gefunden")

    def test_used_bindings_are_declared(self):
        missing = self.used - self.readme_ports
        self.assertFalse(missing, f"Im Kern genutzte, aber im Port-Vertrag fehlende Bindungen: {missing}")

    def test_each_adapter_realizes_every_declared_port(self):
        for name, txt in (("claude", CLAUDE), ("codex", CODEX)):
            for key in self.readme_ports:
                self.assertIn(f"`{key}`", txt, f"Adapter {name} realisiert Port '{key}' nicht")

    def test_adapters_define_no_undeclared_binding(self):
        for name, keys in (("claude", self.claude_keys), ("codex", self.codex_keys)):
            extra = keys - self.readme_ports
            self.assertFalse(extra, f"Adapter {name} definiert nicht deklarierte Bindung(en): {extra}")


class ProfileContract(unittest.TestCase):
    def setUp(self):
        self.profile_keys = first_column_keys(PROFILE_EX)
        self.used = set(re.findall(r"\[PROFILE:([a-z0-9_.]+)\]", CORE)) - {"key"}

    def test_used_profile_keys_defined(self):
        missing = self.used - self.profile_keys
        self.assertFalse(missing, f"Im Kern genutzte, aber im Profil fehlende Schlüssel: {missing}")

    def test_readme_mentions_every_profile_key(self):
        for key in self.profile_keys:
            self.assertIn(f"`{key}`", README, f"README nennt Profilschlüssel '{key}' nicht")


class SectionReferences(unittest.TestCase):
    def setUp(self):
        self.nums = [int(n) for n in re.findall(r"(?m)^## (\d+)\.", CORE)]

    def test_sections_contiguous(self):
        self.assertEqual(self.nums, list(range(1, len(self.nums) + 1)),
                         "Kern-Abschnitte sind nicht lückenlos von 1 an nummeriert")

    def test_no_dangling_section_reference(self):
        valid = set(self.nums)
        for rel in ["core/core.md", "core/roles/qa.md", "core/roles/ak.md",
                    "core/roles/st.md", "core/roles/sec.md", "tools/tools.md"]:
            for ref in re.findall(r"§(\d+)", read(rel)):
                self.assertIn(int(ref), valid, f"{rel}: Verweis §{ref} zeigt auf keinen Abschnitt")


class Roles(unittest.TestCase):
    def test_role_extension_files_exist(self):
        for r in ROLES:
            self.assertTrue(exists(f"core/roles/{r}.md"), f"Rollenerweiterung core/roles/{r}.md fehlt")

    def test_subagent_wrappers_exist(self):
        for r in ROLES:
            self.assertTrue(exists(f"templates/claude-agents/{r}-agent.md"),
                            f"Subagent-Wrapper {r}-agent.md fehlt")

    def test_core_routing_table_lists_roles(self):
        routing = get_section(CORE, "## 6. Rollen & Routing")
        for r in ROLES:
            self.assertRegex(routing, rf"\b{r.upper()}\b", f"§6 nennt Rolle {r.upper()} nicht")


class PathFreeCore(unittest.TestCase):
    """Der Kern bleibt pfadfrei; nur Adapter/Templates kennen den Root-Pfad (templates/README)."""

    def test_core_has_no_root_path(self):
        core_dir = os.path.join(ROOT, "core")
        for base, _dirs, files in os.walk(core_dir):
            for name in files:
                if name.endswith(".md"):
                    txt = read(os.path.relpath(os.path.join(base, name), ROOT))
                    self.assertNotIn("~/agent-governance", txt,
                                     f"core/{name} enthält einen Root-Pfad — Kern muss pfadfrei sein")


class ToolsCatalog(unittest.TestCase):
    def test_no_leftover_toml_manifest(self):
        self.assertFalse(exists("tools/tools.toml"), "tools/tools.toml sollte konsolidiert (entfernt) sein")

    def test_no_file_references_toml(self):
        # tools.md darf die Ablösung historisch erwähnen; sonst kein Verweis auf das alte Manifest.
        for rel in tracked_markdown(exclude=("tools/tools.md",)):
            self.assertNotIn("tools.toml", read(rel), f"{rel} verweist noch auf das entfernte tools.toml")

    def test_brewfiles_documented_and_correctly_classified(self):
        # Der Standard-Pfad (Brewfile) darf keine freigabepflichtigen (optionalen) Werkzeuge
        # mitziehen: Pflichtpakete stehen als erforderlich, optionale als optional in tools.md.
        cli = get_section(TOOLS, "## CLI-Grundwerkzeuge")
        self.assertTrue(cli, "Abschnitt '## CLI-Grundwerkzeuge' in tools/tools.md fehlt")
        req_line = next((ln for ln in cli.splitlines() if "erforderlich" in ln), "")
        opt_line = next((ln for ln in cli.splitlines() if "Optional empfohlen" in ln), "")
        req_doc = set(re.findall(r"`([^`]+)`", req_line))
        opt_doc = set(re.findall(r"`([^`]+)`", opt_line))
        req_pkgs = set(re.findall(r'brew\s+"([^"]+)"', BREW))
        opt_pkgs = set(re.findall(r'brew\s+"([^"]+)"', BREW_OPT))
        self.assertTrue(req_pkgs, "Erforderliches Brewfile enthält keine Pakete")
        both = req_pkgs & opt_pkgs
        self.assertFalse(both, f"Paket in erforderlichem UND optionalem Brewfile: {both}")
        for pkg in req_pkgs:
            self.assertIn(pkg, req_doc,
                          f"Pflichtpaket '{pkg}' ist in tools/tools.md nicht als erforderlich dokumentiert")
        for pkg in opt_pkgs:
            self.assertIn(pkg, opt_doc,
                          f"Optionales Paket '{pkg}' ist in tools/tools.md nicht als optional dokumentiert")

    def test_every_tool_entry_is_complete(self):
        # Jeder ###-Eintrag braucht eine Freigabe-Kennzeichnung und einen Installationsblock.
        blocks = re.split(r"(?m)^### ", TOOLS)[1:]
        self.assertTrue(blocks, "tools/tools.md enthält keine Werkzeug-Einträge (###)")
        for block in blocks:
            title = block.splitlines()[0].strip()
            self.assertRegex(block, r"(Standard-Setup|Optional empfohlen)",
                             f"Werkzeug '{title}' ohne Freigabe-Kennzeichnung")
            self.assertIn("```", block, f"Werkzeug '{title}' ohne Installationsblock")

    def test_links_are_well_formed(self):
        for url in re.findall(r"https?://\S+", TOOLS):
            url = url.rstrip(">).,")
            self.assertRegex(url, r"^https?://[^\s]+\.[^\s]+$", f"Ungültige URL-Form: {url}")


class Templates(unittest.TestCase):
    def test_claude_imports_resolve(self):
        for imp in re.findall(r"@~/agent-governance/(\S+)", TPL_CLAUDE):
            if imp == "profile/profile.md":
                # profile.md ist nutzerlokal (.gitignore) — im Repo liegt nur das Beispiel.
                self.assertTrue(exists("profile/profile.example.md"),
                                "profile/profile.example.md fehlt")
            else:
                self.assertTrue(exists(imp), f"Import {imp} in templates/CLAUDE.md zeigt ins Leere")


class BranchTags(unittest.TestCase):
    """`core/branch-tags.toml` ist wohlgeformt, git-ref-sicher und driftfrei mit dem Kern (§15)."""

    TAG_RE = re.compile(r"^[a-z][a-z0-9-]*$")
    TOML_REL = "core/branch-tags.toml"

    def setUp(self):
        if tomllib is None:
            self.skipTest("tomllib erfordert Python 3.11+; TOML-Validierung nur dort")
        self.assertTrue(exists(self.TOML_REL), f"{self.TOML_REL} fehlt")
        self.data = load_toml(self.TOML_REL)
        self.entries = self.data.get("tags", [])

    def test_has_entries(self):
        self.assertTrue(self.entries, "core/branch-tags.toml enthält keine [[tags]]-Einträge")

    def test_entries_complete(self):
        for i, e in enumerate(self.entries):
            for field in ("tag", "name", "description"):
                val = e.get(field)
                self.assertTrue(isinstance(val, str) and val.strip(),
                                f"[[tags]]-Eintrag #{i} ohne nicht-leeres Feld '{field}'")

    def test_tags_ref_safe(self):
        for e in self.entries:
            tag = e.get("tag", "")
            self.assertRegex(tag, self.TAG_RE,
                             f"Tag '{tag}' ist nicht git-ref-sicher (Kleinbuchstaben/Ziffern/'-', "
                             f"Beginn mit Buchstabe)")

    def test_tags_unique(self):
        tags = [e.get("tag") for e in self.entries]
        dupes = {t for t in tags if tags.count(t) > 1}
        self.assertFalse(dupes, f"Doppelte Tags in core/branch-tags.toml: {dupes}")

    def test_default_refers_to_existing_tag(self):
        default = self.data.get("default")
        self.assertTrue(default, "core/branch-tags.toml deklariert keinen 'default'-Tag")
        self.assertIn(default, {e.get("tag") for e in self.entries},
                      f"'default = \"{default}\"' zeigt auf keinen definierten Tag")

    def test_core_references_tag_file(self):
        self.assertIn(self.TOML_REL, CORE,
                      "Kern §15 verweist nicht auf core/branch-tags.toml (Drift)")

    def test_retired_binding_absent(self):
        # Der abgelöste Agenten-Präfix-Port darf nirgends mehr referenziert werden.
        for rel in ("core/core.md", "README.md", "adapters/claude.md", "adapters/codex.md"):
            self.assertNotIn("vcs.branch_prefix", read(rel),
                             f"{rel} verweist noch auf den abgelösten Port vcs.branch_prefix")


class ReleaseConsistency(unittest.TestCase):
    """Autoritative SemVer-Quelle, CHANGELOG- und Release-Metadaten-Konsistenz (Kern §12, §14)."""

    VERSION_REL = "VERSION"
    CHANGELOG_REL = "CHANGELOG.md"
    LINK_REL = "https://github.com/tomtastisch/agent-governance/releases/tag"

    # SemVer 2.0.0: MAJOR.MINOR.PATCH[-prerelease][+build]
    SEMVER_RE = re.compile(
        r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
        r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
        r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
        r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
    )

    @property
    def version(self):
        if not exists(self.VERSION_REL):
            return None
        return read(self.VERSION_REL).strip()

    # ── Existenz & Form ──

    def test_version_file_exists(self):
        self.assertTrue(exists(self.VERSION_REL),
                        f"{self.VERSION_REL} fehlt — autoritative SemVer-Quelle erforderlich (Kern §12)")

    def test_version_is_valid_semver(self):
        v = self.version
        if v is None:
            self.skipTest(f"{self.VERSION_REL} nicht vorhanden")
        self.assertRegex(v, self.SEMVER_RE,
                         f"'{v}' ist kein gültiges SemVer (MAJOR.MINOR.PATCH)")

    def test_no_competing_version_sources(self):
        """Keine zweite SemVer-Quelle außerhalb VERSION und CHANGELOG."""
        competing = set()
        authority = {self.VERSION_REL, self.CHANGELOG_REL}
        # TOML-Dateien: version = "..."
        for base, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d not in {".git", "tests", ".github"}]
            for name in files:
                rel = os.path.relpath(os.path.join(base, name), ROOT)
                if rel in authority:
                    continue
                if name.endswith(".toml"):
                    txt = read(rel)
                    for m in re.finditer(r'version\s*=\s*"(\d+\.\d+\.\d+[^"]*)"', txt):
                        competing.add(f"{rel}: version = \"{m.group(1)}\"")
                elif name.endswith(".json"):
                    txt = read(rel)
                    for m in re.finditer(r'"version"\s*:\s*"(\d+\.\d+\.\d+[^"]*)"', txt):
                        competing.add(f"{rel}: \"version\": \"{m.group(1)}\"")
                elif name == "VERSION":
                    continue  # SSOT — bereits geprüft
                elif name.lower() in ("version.txt", "version", ".version"):
                    competing.add(f"{rel}: parallele Versionsdatei neben {self.VERSION_REL}")
        self.assertFalse(competing, f"Konkurrierende Versionsquellen: {competing}")

    # ── CHANGELOG ──

    def test_changelog_exists(self):
        self.assertTrue(exists(self.CHANGELOG_REL),
                        f"{self.CHANGELOG_REL} fehlt (Kern §12 verlangt aktuellen CHANGELOG)")

    def test_changelog_has_current_version(self):
        v = self.version
        if v is None:
            self.skipTest(f"{self.VERSION_REL} nicht vorhanden")
        if not exists(self.CHANGELOG_REL):
            self.skipTest(f"{self.CHANGELOG_REL} nicht vorhanden")
        changelog = read(self.CHANGELOG_REL)
        self.assertIn(f"## [{v}]", changelog,
                      f"CHANGELOG enthält keinen Eintrag '## [{v}]' für die aktuelle Version")

    def test_changelog_version_matches_source(self):
        v = self.version
        if v is None:
            self.skipTest(f"{self.VERSION_REL} nicht vorhanden")
        if not exists(self.CHANGELOG_REL):
            self.skipTest(f"{self.CHANGELOG_REL} nicht vorhanden")
        changelog = read(self.CHANGELOG_REL)
        versions = re.findall(r"##\s+\[(\d+\.\d+\.\d[^\]]*)\]", changelog)
        if not versions:
            self.skipTest("CHANGELOG enthält keine versionierte Überschrift")
        self.assertEqual(v, versions[0],
                         f"VERSION ({v}) weicht von aktuellstem CHANGELOG-Eintrag ({versions[0]}) ab")

    VALID_CATEGORIES = {"Added", "Changed", "Fixed", "Removed", "Deprecated", "Security"}

    def test_changelog_has_required_categories(self):
        """CHANGELOG nutzt das vereinbarte Kategorie-Vokabular; leere Kategorien weglassbar."""
        if not exists(self.CHANGELOG_REL):
            self.skipTest(f"{self.CHANGELOG_REL} nicht vorhanden")
        changelog = read(self.CHANGELOG_REL)
        used = set(re.findall(r"^### (\w+)", changelog, re.MULTILINE))
        self.assertTrue(used, "CHANGELOG enthält keine Kategorie-Überschriften (### Kategorie)")
        unknown = used - self.VALID_CATEGORIES
        self.assertFalse(unknown,
                         f"CHANGELOG enthält unbekannte Kategorien: {unknown}. "
                         f"Zulässig: {sorted(self.VALID_CATEGORIES)}")
        # Mindestens eine der Kern-Kategorien muss verwendet werden
        core_cats = {"Added", "Changed", "Fixed", "Removed"}
        self.assertTrue(used & core_cats,
                        f"CHANGELOG nutzt keine der Kern-Kategorien {sorted(core_cats)}")

    def test_changelog_breaking_changes_explicit(self):
        """Breaking Changes müssen im CHANGELOG ausdrücklich gekennzeichnet sein (Kern §12)."""
        if not exists(self.CHANGELOG_REL):
            self.skipTest(f"{self.CHANGELOG_REL} nicht vorhanden")
        changelog = read(self.CHANGELOG_REL)
        # Wenn Breaking Changes existieren, müssen sie unter einer entsprechenden Rubrik stehen.
        # Der CHANGELOG muss mindestens die Kategorien enthalten; Breaking Changes sind optional.
        has_breaking_section = "### Breaking" in changelog or "### BREAKING" in changelog
        has_breaking_text = "**Breaking" in changelog or "BREAKING" in changelog
        # Kein Fehler, wenn keine Breaking Changes — nur prüfen, dass das Format unterstützt wird.
        if has_breaking_text and not has_breaking_section:
            self.fail("CHANGELOG enthält Breaking-Change-Hinweise ohne '### Breaking'-Kategorie")

    def test_changelog_no_imaginary_releases(self):
        """Keine erfundenen historischen Releases mit Datum, die nie existiert haben."""
        if not exists(self.CHANGELOG_REL):
            self.skipTest(f"{self.CHANGELOG_REL} nicht vorhanden")
        changelog = read(self.CHANGELOG_REL)
        # Der initiale CHANGELOG darf genau einen versionierten Eintrag enthalten (0.1.0).
        versions = re.findall(r"##\s+\[(\d+\.\d+\.\d[^\]]*)\]", changelog)
        self.assertLessEqual(len(versions), 1,
                             f"CHANGELOG enthält {len(versions)} Versionseinträge — "
                             f"für den ersten Release wird genau ein Eintrag erwartet")

    # ── README / INSTALL ──

    def test_readme_references_version_source(self):
        has_ref = "VERSION" in README or "versioniert" in README or "Release-Tag" in README
        self.assertTrue(has_ref,
                        "README referenziert keine versionierte Auslieferung oder Release-Tags")

    def test_install_references_versioned_setup(self):
        inst = read("INSTALL.md")
        has_ref = ("Version" in inst or "Release" in inst or "versioniert" in inst
                   or "Tag" in inst or "SemVer" in inst)
        self.assertTrue(has_ref,
                        "INSTALL.md enthält keinen Hinweis auf versionierte Installation")


if __name__ == "__main__":
    unittest.main()
