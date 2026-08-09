#!/usr/bin/env python3
"""Mechanische Verträge des kanonischen Governance-Bundles."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import re
import tempfile
import unicodedata
import unittest
from unittest import mock

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


def resolve_module_closure(modules: dict, roots: list[str]) -> tuple[str, ...]:
    """Löst eine Modulmenge deterministisch und bei Graphfehlern fail-closed auf."""
    visiting: list[str] = []
    visited: set[str] = set()
    closure: list[str] = []

    def visit(name: str) -> None:
        if name not in modules:
            raise ValueError(f"unbekanntes Modul: {name}")
        if name in visiting:
            cycle = " -> ".join([*visiting[visiting.index(name):], name])
            raise ValueError(f"zirkuläre Modulabhängigkeit: {cycle}")
        if name in visited:
            return
        visiting.append(name)
        for dependency in modules[name]["dependencies"]:
            visit(dependency)
        visiting.pop()
        visited.add(name)
        closure.append(name)

    for root in roots:
        visit(root)
    return tuple(closure)


def rule_ids(path: Path) -> set[str]:
    return set(RULE_ID_RE.findall(path.read_text(encoding="utf-8")))


def rule_references(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    return set(RULE_TOKEN_RE.findall(text)) - set(RULE_ID_RE.findall(text))


def rule_definitions() -> dict[str, list[Path]]:
    definitions: dict[str, list[Path]] = {}
    for path in normative_files():
        for rule_id in RULE_ID_RE.findall(path.read_text(encoding="utf-8")):
            definitions.setdefault(rule_id, []).append(path.resolve())
    return definitions


def markdown_anchors(text: str) -> set[str]:
    anchors: set[str] = set()
    for heading in re.findall(r"(?m)^#{1,6}\s+(.+?)\s*$", text):
        normalized = unicodedata.normalize("NFKD", heading)
        ascii_heading = normalized.encode("ascii", "ignore").decode("ascii").lower()
        without_punctuation = re.sub(r"[^a-z0-9_\-\s]", "", ascii_heading)
        anchors.add(re.sub(r"\s", "-", without_punctuation).strip("-"))
    return anchors


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

    def test_bootstrap_links_only_to_manifest_entry_chain(self):
        local_targets = {
            target.split("#", 1)[0]
            for _label, target in MARKDOWN_LINK_RE.findall(
                BOOTSTRAP.read_text(encoding="utf-8")
            )
            if not re.match(r"^(?:https?://|mailto:|#)", target)
        }
        self.assertEqual(local_targets, {"agent-governance/manifest.toml"})


class ManifestContract(unittest.TestCase):
    def setUp(self):
        self.data = load_manifest()

    def test_manifest_has_only_static_index_sections(self):
        self.assertEqual(set(self.data), {
            "schema_version", "local_rules", "routing", "modules", "roles"
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
        for module in modules:
            resolve_module_closure(modules, [module])

    def test_module_closure_rejects_unknown_modules(self):
        modules = {"evidence": {"dependencies": ["missing"]}}
        with self.assertRaisesRegex(ValueError, "unbekanntes Modul: missing"):
            resolve_module_closure(modules, ["evidence"])

    def test_module_closure_rejects_cycles(self):
        modules = {
            "evidence": {"dependencies": ["delivery"]},
            "delivery": {"dependencies": ["evidence"]},
        }
        with self.assertRaisesRegex(ValueError, "evidence -> delivery -> evidence"):
            resolve_module_closure(modules, ["evidence"])

    def test_module_paths_have_unique_ownership(self):
        owners: dict[Path, str] = {}
        for name, entry in self.data["modules"].items():
            path = (MANIFEST.parent / entry["path"]).resolve()
            self.assertNotIn(path, owners, f"{path}: {owners.get(path)} und {name}")
            owners[path] = name

    def test_manifest_owns_every_module_and_role_file(self):
        root = MANIFEST.parent
        manifested = {
            (root / entry["path"]).resolve()
            for group in (self.data["modules"], self.data["roles"])
            for entry in group.values()
        }
        present = {
            *map(Path.resolve, (root / "modules").glob("*.md")),
            *map(Path.resolve, (root / "roles").glob("*.md")),
        }
        self.assertEqual(manifested, present)

    def test_roles_reference_known_modules(self):
        modules = set(self.data["modules"])
        for name, entry in self.data["roles"].items():
            self.assertEqual(set(entry), {"path", "triggers", "modules"}, name)
            self.assertTrue(entry["triggers"], name)
            self.assertTrue(set(entry["modules"]) <= modules, name)

    def test_rule_references_are_in_effective_module_closure(self):
        modules = self.data["modules"]
        module_paths = {
            name: (MANIFEST.parent / entry["path"]).resolve()
            for name, entry in modules.items()
        }
        definitions = rule_definitions()

        def assert_references_loaded(source: Path, closure: tuple[str, ...]) -> None:
            effective_paths = {BOOTSTRAP.resolve(), *(module_paths[name] for name in closure)}
            for rule_id in rule_references(source):
                locations = definitions.get(rule_id, [])
                self.assertEqual(len(locations), 1,
                                 f"{source}: {rule_id} hat {len(locations)} Definitionen")
                self.assertIn(locations[0], effective_paths,
                              f"{source}: {rule_id} ist nicht im Modulabschluss geladen")

        for name, path in module_paths.items():
            assert_references_loaded(path, resolve_module_closure(modules, [name]))
        for role_name, entry in self.data["roles"].items():
            path = (MANIFEST.parent / entry["path"]).resolve()
            assert_references_loaded(
                path, resolve_module_closure(modules, entry["modules"])
            )

    def test_independent_roles_load_required_review_rules(self):
        required_rules = {
            "architecture": {"INV-003", "DEL-003"},
            "triage": {"INV-003"},
            "quality_assurance": {"DEL-003"},
            "security_review": {"INV-003", "DEL-003"},
        }
        modules = self.data["modules"]
        module_paths = {
            name: (MANIFEST.parent / entry["path"]).resolve()
            for name, entry in modules.items()
        }
        for role_name, expected in required_rules.items():
            closure = resolve_module_closure(
                modules, self.data["roles"][role_name]["modules"]
            )
            effective = set().union(*(rule_ids(module_paths[name]) for name in closure))
            self.assertEqual(expected - effective, set(),
                             f"{role_name}: nicht geladen: {sorted(expected - effective)}")

    def test_no_trigger_loads_every_module(self):
        modules = self.data["modules"]
        for trigger in self.data["routing"]["known_triggers"]:
            selected = {
                name for name, entry in modules.items() if trigger in entry["triggers"]
            }
            self.assertNotEqual(selected, set(modules), trigger)

    def test_refactoring_route_includes_delivery_gates(self):
        modules = self.data["modules"]
        selected = [
            name for name, entry in modules.items()
            if "refactoring" in entry["triggers"]
        ]
        closure = resolve_module_closure(modules, selected)
        self.assertIn("delivery", closure)

    def test_tool_routing_has_closed_trigger_scope(self):
        module = self.data["modules"]["tool_routing"]
        self.assertEqual(
            set(module["triggers"]), {"tool_selection", "agent_dependencies"}
        )
        self.assertEqual(module["dependencies"], ["security"])


class ToolRoutingContract(unittest.TestCase):
    def setUp(self):
        self.path = GOVERNANCE_ROOT / "modules" / "tool-routing.md"
        self.text = self.path.read_text(encoding="utf-8")

    def test_every_catalog_entry_has_the_same_governance_fields(self):
        entries = re.split(r"(?m)^#### ", self.text)[1:]
        self.assertGreaterEqual(len(entries), 7)
        required = {
            "Name", "Zweck", "Trigger", "Erforderlich", "Nützlich",
            "Evidenzgewinn", "Read-/Write-Grenze", "Fallback",
            "Keine Folgerung",
        }
        for entry in entries:
            fields = set(re.findall(r"(?m)^\*\*([^*]+):\*\*", entry))
            self.assertEqual(required - fields, set(), entry.splitlines()[0])

    def test_apm_contract_uses_declared_state_and_read_only_audit(self):
        self.assertIn("Microsoft APM", self.text)
        self.assertIn("`apm.yml`", self.text)
        self.assertIn("`apm.lock.yaml`", self.text)
        self.assertIn("`apm audit --ci`", self.text)

    def test_catalog_does_not_model_tool_installation_or_availability(self):
        self.assertNotRegex(
            self.text,
            r"(?i)\b(?:Installation|installiert|deinstalliert|Verfügbarkeit|"
            r"nicht verfügbar|lokal verfügbar|vorhanden\w*)\b",
        )


class ReviewContract(unittest.TestCase):
    def setUp(self):
        self.delivery = (GOVERNANCE_ROOT / "modules" / "delivery.md").read_text(
            encoding="utf-8"
        )
        self.security = (GOVERNANCE_ROOT / "modules" / "security.md").read_text(
            encoding="utf-8"
        )
        self.tools = (GOVERNANCE_ROOT / "modules" / "tool-routing.md").read_text(
            encoding="utf-8"
        )

    def test_roles_and_review_providers_are_separate(self):
        for token in ("Rolle", "Provider", "GitHub Copilot", "Exact Head"):
            self.assertIn(token, self.delivery)
        self.assertNotIn("QA == Copilot", self.delivery)
        self.assertRegex(self.delivery, r"frischer\s+unabhängiger read-only")
        self.assertIn("`no`", self.delivery)
        self.assertIn("`unknown`", self.delivery)
        self.assertRegex(self.delivery, r"(?i)Retry-Spam")

    def test_finding_lifecycle_is_closed(self):
        for classification in (
            "blocking-valid", "nonblocking-valid", "invalid", "not-applicable"
        ):
            self.assertIn(f"`{classification}`", self.delivery)
        self.assertRegex(self.delivery, r"(?is)Korrektur.+erneut")

    def test_security_gate_has_explicit_risk_triggers(self):
        required = (
            "Security-Regeln", "Authentifizierung", "Autorisierung", "Secrets",
            "Berechtigungen", "Trust Boundaries", "Prompt-Injection",
            "externe Schreibwirkungen", "Review-Freigaberegeln",
            "Tool-Berechtigungen", "Fail-closed",
        )
        for term in required:
            self.assertIn(term, self.security)
        self.assertRegex(self.security, r"(?is)rein redaktionell.+kein.+Security-Gate")

    def test_tool_catalog_delegates_review_semantics_to_delivery_ssot(self):
        self.assertIn("[DEL-008]", self.tools)
        self.assertIn("[DEL-009]", self.tools)

    def test_security_tool_trigger_delegates_to_security_ssot(self):
        entry = self.tools.split("#### Security-Diff-Prüfung", 1)[1].split(
            "#### Microsoft APM", 1
        )[0]
        trigger = re.search(r"(?m)^\*\*Trigger:\*\* (.+)$", entry)
        self.assertIsNotNone(trigger)
        self.assertIn("[SEC-001]", trigger.group(1))
        for duplicated_term in (
            "Authentisierung", "Autorisierung", "Secrets", "Berechtigungen",
            "Trust Boundaries", "Prompt-Injection", "Review-Freigaberegeln",
            "Tool-Berechtigungen",
        ):
            self.assertNotIn(duplicated_term, trigger.group(1))


class TemplateContract(unittest.TestCase):
    def setUp(self):
        self.path = GOVERNANCE_ROOT / "modules" / "templates.md"
        self.text = self.path.read_text(encoding="utf-8")

    def test_manifest_routes_templates_without_global_import(self):
        module = load_manifest()["modules"]["templates"]
        self.assertEqual(
            set(module["triggers"]),
            {
                "implementation", "release", "quality_review", "security_review",
                "context_handoff", "status_reporting",
            },
        )
        self.assertEqual(module["dependencies"], ["delivery"])

    def test_strict_templates_cover_drift_prone_operations(self):
        strict = self.text.split("## Strikte Vorlagen", 1)[1].split(
            "## Strukturierte Verträge", 1
        )[0]
        for heading in (
            "### Commit", "### Branch", "### Push-/PR-Checkpoint",
            "### PR-Beschreibung und Reviewevidenz", "### QA-/SEC-Finding",
            "### Kontextübergabe",
        ):
            self.assertIn(heading, strict)
        self.assertIn("<type>(<scope>): <imperative summary>", strict)
        self.assertIn("<type>/<scope>/<short-topic>", strict)
        self.assertIn("<Exact-Head-SHA>", strict)

    def test_free_form_interactions_use_structured_contracts(self):
        structured = self.text.split("## Strukturierte Verträge", 1)[1]
        for heading in (
            "### Antwort und Status", "### Toolfehler und Blocker",
            "### Abschlussaussage",
        ):
            self.assertIn(heading, structured)

    def test_template_markers_have_one_normative_owner(self):
        owners = [
            path for path in normative_files()
            if "<Exact-Head-SHA>" in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(owners, [self.path])


class NormativeSourceContract(unittest.TestCase):
    def test_markdown_link_check_rejects_unknown_fragment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.md"
            target = root / "target.md"
            source.write_text("[Ziel](target.md#fehlt)\n", encoding="utf-8")
            target.write_text("# Vorhanden\n", encoding="utf-8")

            case = NormativeSourceContract("test_markdown_file_links_resolve")
            result = unittest.TestResult()
            with mock.patch(f"{__name__}.normative_files", return_value=[source]):
                case.run(result)

            self.assertEqual(result.errors, [])
            self.assertEqual(len(result.failures), 1)

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
                if re.match(r"^(?:https?://|mailto:)", target):
                    continue
                raw_path, separator, fragment = target.partition("#")
                resolved = path.resolve() if not raw_path else (path.parent / raw_path).resolve()
                self.assertTrue(resolved.is_file(), f"{path}: {target}")
                if separator:
                    anchors = markdown_anchors(resolved.read_text(encoding="utf-8"))
                    self.assertIn(fragment, anchors, f"{path}: {target}")

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
