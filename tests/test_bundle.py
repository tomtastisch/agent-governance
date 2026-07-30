#!/usr/bin/env python3
"""Mechanische Verträge des kanonischen Governance-Bundles."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import re
import unittest

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - das Projekt erfordert Python 3.11+
    tomllib = None


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "bundle"
BOOTSTRAP = BUNDLE / "GOVERNANCE.md"
GOVERNANCE_ROOT = BUNDLE / "agent-governance"
MANIFEST = GOVERNANCE_ROOT / "manifest.toml"
RULE_ID_RE = re.compile(r"(?m)^### ([A-Z][A-Z0-9-]*-\d{3}) — ")
RULE_TOKEN_RE = re.compile(r"\b[A-Z][A-Z0-9-]*-\d{3}\b")
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
FORBIDDEN_MANIFEST_TERMS = {
    "provider",
    "session",
    "availability",
    "queue",
    "lease",
    "delegation",
    "runtime",
    "registry",
    "endpoint",
}


def load_manifest() -> dict:
    if tomllib is None:
        raise unittest.SkipTest("tomllib erfordert Python 3.11+")
    with MANIFEST.open("rb") as handle:
        return tomllib.load(handle)


def normative_files() -> list[Path]:
    return [BOOTSTRAP, *sorted((GOVERNANCE_ROOT / "modules").glob("*.md")),
            *sorted((GOVERNANCE_ROOT / "roles").glob("*.md"))]


class BundleLayout(unittest.TestCase):
    def test_only_governance_is_a_bootstrap_source(self):
        self.assertTrue(BOOTSTRAP.is_file())
        forbidden = [
            path.relative_to(ROOT).as_posix()
            for path in BUNDLE.rglob("*")
            if path.is_file() and path.name in {"AGENTS.md", "CLAUDE.md"}
        ]
        self.assertEqual(forbidden, [])

    def test_bootstrap_respects_utf8_budget(self):
        payload = BOOTSTRAP.read_bytes()
        payload.decode("utf-8")
        self.assertLessEqual(len(payload), 8 * 1024)

    def test_bundle_contains_no_home_or_machine_absolute_paths(self):
        for path in normative_files():
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("~/", text, path)
            self.assertNotRegex(text, r"(?m)(?:^|[\s`])/(?:Users|home)/", path)
            self.assertNotRegex(text, r"(?i)[A-Z]:\\Users\\", path)

    def test_real_local_rules_file_is_ignored(self):
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("bundle/agent-governance/local/user-rules.md", ignored)


class ManifestContract(unittest.TestCase):
    def setUp(self):
        self.data = load_manifest()

    def test_manifest_has_only_static_index_sections(self):
        self.assertEqual(set(self.data), {
            "schema_version", "bootstrap", "local_rules", "routing", "modules", "roles"
        })
        lowered = MANIFEST.read_text(encoding="utf-8").lower()
        for term in FORBIDDEN_MANIFEST_TERMS:
            self.assertNotRegex(lowered, rf"(?<![a-z]){re.escape(term)}(?![a-z])", term)

    def test_routing_is_closed_and_fail_closed(self):
        routing = self.data["routing"]
        self.assertEqual(set(routing), {"known_triggers", "unknown", "ambiguous"})
        self.assertEqual(routing["unknown"], "block")
        self.assertEqual(routing["ambiguous"], "block")
        known = routing["known_triggers"]
        self.assertTrue(known)
        self.assertEqual(len(known), len(set(known)))
        self.assertNotIn("all", known)
        referenced = {
            trigger
            for group in (self.data["modules"], self.data["roles"])
            for entry in group.values()
            for trigger in entry["triggers"]
        }
        self.assertEqual(set(known), referenced)

    def test_paths_are_relative_and_resolve(self):
        manifest_root = MANIFEST.parent
        required_paths = [
            self.data["bootstrap"],
            *(entry["path"] for entry in self.data["modules"].values()),
            *(entry["path"] for entry in self.data["roles"].values()),
        ]
        for raw in required_paths:
            pure = PurePosixPath(raw)
            self.assertFalse(pure.is_absolute(), raw)
            self.assertNotIn("~", pure.parts, raw)
            resolved = (manifest_root / Path(*pure.parts)).resolve()
            self.assertTrue(resolved.is_file(), raw)
            self.assertTrue(os.path.commonpath((resolved, BUNDLE.resolve())) == str(BUNDLE.resolve()),
                            raw)
        local = PurePosixPath(self.data["local_rules"])
        self.assertFalse(local.is_absolute())
        example = (manifest_root / local.parent / f"{local.stem}.example{local.suffix}").resolve()
        self.assertTrue(example.is_file())

    def test_module_dependencies_are_known_and_acyclic(self):
        modules = self.data["modules"]
        for name, entry in modules.items():
            self.assertEqual(set(entry), {"path", "triggers", "dependencies"}, name)
            self.assertTrue(entry["triggers"], name)
            self.assertNotIn("all", entry["triggers"], name)
            self.assertTrue(set(entry["dependencies"]) <= set(modules), name)

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(name: str) -> None:
            if name in visiting:
                self.fail(f"zirkuläre Modulabhängigkeit bei {name}")
            if name in visited:
                return
            visiting.add(name)
            for dependency in modules[name]["dependencies"]:
                visit(dependency)
            visiting.remove(name)
            visited.add(name)

        for module in modules:
            visit(module)

    def test_roles_reference_known_modules(self):
        modules = set(self.data["modules"])
        for name, entry in self.data["roles"].items():
            self.assertEqual(set(entry), {"path", "triggers", "modules"}, name)
            self.assertTrue(entry["triggers"], name)
            self.assertTrue(set(entry["modules"]) <= modules, name)

    def test_no_trigger_loads_every_module(self):
        modules = self.data["modules"]
        for trigger in self.data["routing"]["known_triggers"]:
            selected = {
                name for name, entry in modules.items() if trigger in entry["triggers"]
            }
            self.assertNotEqual(selected, set(modules), trigger)


class NormativeSourceContract(unittest.TestCase):
    def test_rule_ids_are_unique(self):
        definitions: dict[str, Path] = {}
        for path in normative_files():
            for rule_id in RULE_ID_RE.findall(path.read_text(encoding="utf-8")):
                self.assertNotIn(rule_id, definitions,
                                 f"{rule_id}: {definitions.get(rule_id)} und {path}")
                definitions[rule_id] = path
        self.assertTrue(definitions)

    def test_rule_references_link_to_the_defining_source(self):
        definitions: dict[str, Path] = {}
        for path in normative_files():
            for rule_id in RULE_ID_RE.findall(path.read_text(encoding="utf-8")):
                definitions[rule_id] = path.resolve()

        for path in normative_files():
            text = path.read_text(encoding="utf-8")
            defined_here = set(RULE_ID_RE.findall(text))
            links = {
                label: target
                for label, target in MARKDOWN_LINK_RE.findall(text)
                if RULE_TOKEN_RE.fullmatch(label)
            }
            for token in RULE_TOKEN_RE.findall(text):
                if token in defined_here:
                    continue
                self.assertIn(token, links, f"{path}: {token} ohne Quellenlink")
                target = links[token].split("#", 1)[0]
                resolved = (path.parent / target).resolve()
                self.assertEqual(resolved, definitions.get(token),
                                 f"{path}: {token} zeigt auf falsche Quelle")

    def test_markdown_file_links_resolve(self):
        for path in normative_files():
            for _label, target in MARKDOWN_LINK_RE.findall(path.read_text(encoding="utf-8")):
                if re.match(r"^(?:https?://|mailto:|#)", target):
                    continue
                resolved = (path.parent / target.split("#", 1)[0]).resolve()
                self.assertTrue(resolved.is_file(), f"{path}: {target}")

    def test_no_exact_normalized_paragraph_duplicates(self):
        seen: dict[str, Path] = {}
        for path in normative_files():
            text = path.read_text(encoding="utf-8")
            for paragraph in re.split(r"\n\s*\n", text):
                normalized = " ".join(paragraph.split())
                if len(normalized) < 80 or normalized.startswith(("#", "```", "|")):
                    continue
                self.assertNotIn(normalized, seen,
                                 f"Absatzduplikat in {seen.get(normalized)} und {path}")
                seen[normalized] = path


if __name__ == "__main__":
    unittest.main()
