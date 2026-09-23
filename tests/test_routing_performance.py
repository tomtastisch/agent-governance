"""#94: reale Modulabschlüsse, Schutzregeln und gemessener Governance-Kontext."""

import json
from pathlib import Path
import re
import tempfile
import shutil
import unittest

from tests.support.catalog_validator import CatalogValidationError, load_catalog_contract, load_routing_index
from tests.support.neutral_harness import NeutralHarness, NeutralHarnessError
from tests.support.routing_measurement import measure_route

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "bundle"
FIXTURES = ROOT / "tests/fixtures/routing"
CORPUS = json.loads((FIXTURES / "corpus.json").read_text())
BASELINE = json.loads((FIXTURES / "baseline.json").read_text())
RULE = re.compile(r"(?ms)^### ([A-Z]+-\d{3}) — [^\n]+\n.*?(?=^### |^## |\Z)")
KERNEL = {f"GOV-{i:03}" for i in range(1, 7)}
LOCAL = {"DEL-001", "DEL-002", "DEL-004", "DEL-006", "INV-001", "INV-002"}
PROMOTION = {"DEL-003", "DEL-005", "DEL-007", "DEL-008", "DEL-009", "DEL-010"}
SECURITY = {f"SEC-{i:03}" for i in range(1, 5)}

# Zusätzliche Small-Task-Fälle für Phase 2; kein Bestandteil des an Git gebundenen
# Phase-1-Baseline-Korpus, daher separat geführt.
SMALL_TASKS = {
    "git_status": ["git_repository"],
    "doc_lookup": ["documentation"],
    "targeted_test": ["testing"],
}


def loaded_rules(bundle, measurement):
    rules = {}
    for path in measurement["files"]:
        if path.endswith(".md"):
            for match in RULE.finditer((bundle / path).read_text()):
                rules[match[1]] = match[0].strip()
    return rules


def semantic_text(text):
    # Verschobene Regeln behalten ihre IDs und Semantik; Linkziele dürfen umziehen.
    return " ".join(re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", text).split())


class RoutingPerformance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.routes = {name: measure_route(BUNDLE, triggers, 1) for name, triggers in CORPUS.items()}

    def test_messung_liest_bootstrap_manifest_ssot_und_kataloge_tatsaechlich(self):
        route = self.routes["bare_analysis"]
        for path in ("GOVERNANCE.md", "agent-governance/manifest.toml",
                     "agent-governance/ssot/manifest.toml", "agent-governance/ssot/routing/triggers.toml"):
            self.assertEqual(route["files"][path], (BUNDLE / path).stat().st_size)
        self.assertIn("agent-governance/modules/evidence.md", route["files"])
        self.assertEqual(route["file_count"], len(route["files"]))
        self.assertEqual(route["bytes"], sum(route["files"].values()))
        self.assertEqual(route["read_calls"], route["file_count"])
        self.assertEqual(route["tool_calls"], 0)
        self.assertEqual(route["model_cycles"], 0)
        self.assertIsNone(route["tokens"])

    def test_normale_tool_und_analysepfade_laden_keine_security_oder_delivery(self):
        for name in ("read_only_analysis", "normal_tool_routing"):
            with self.subTest(name=name):
                route = self.routes[name]
                self.assertEqual(set(route["modules"]), {"modules/evidence.md", "modules/tool-routing.md"})
                self.assertLess(route["bytes"], BASELINE["cases"][name]["bytes"])
                self.assertLess(route["file_count"], BASELINE["cases"][name]["file_count"])

    def test_lokale_arbeit_erhaelt_verifikation_und_bestandsschutz_ohne_promotion(self):
        for name in ("local_implementation", "local_test", "refactoring"):
            with self.subTest(name=name):
                route = self.routes[name]
                rules = loaded_rules(BUNDLE, route)
                self.assertLessEqual(KERNEL | LOCAL, rules.keys())
                self.assertFalse(PROMOTION & rules.keys())
                self.assertNotIn("modules/security.md", route["modules"])
                self.assertLess(route["bytes"], BASELINE["cases"][name]["bytes"])

    def test_safety_kernel_ist_in_jedem_fall_aktiv(self):
        for name, route in self.routes.items():
            with self.subTest(name=name):
                self.assertLessEqual(KERNEL, loaded_rules(BUNDLE, route).keys())

    def test_security_negativkorpus_verliert_keine_schutz_oder_lieferregeln(self):
        for name in ("authentication", "authorization", "secret_handling", "dependency_change",
                     "security_policy", "governance_change", "prompt_injection", "tool_permission",
                     "external_file", "external_write", "publishing", "destructive_operation", "sec"):
            with self.subTest(name=name):
                rules = loaded_rules(BUNDLE, self.routes[name])
                self.assertLessEqual(KERNEL | LOCAL | SECURITY | PROMOTION, rules.keys())

    def test_externe_wirkung_laed_security_auch_ohne_impliziten_toolpfad(self):
        rules = loaded_rules(BUNDLE, self.routes["external_effect_only"])
        self.assertLessEqual(SECURITY | {f"ENF-{i:03}" for i in range(1, 6)}, rules.keys())

    def test_promotion_release_qa_und_arch_behalten_alle_liefergates(self):
        for name in ("promotion", "release", "publishing", "qa", "architecture"):
            with self.subTest(name=name):
                self.assertLessEqual(LOCAL | PROMOTION, loaded_rules(BUNDLE, self.routes[name]).keys())

    def test_verschobene_und_security_regeln_behalten_ihre_semantik(self):
        current = loaded_rules(BUNDLE, self.routes["publishing"])
        for rule in LOCAL | PROMOTION | SECURITY | {f"ENF-{i:03}" for i in range(1, 6)} | (KERNEL - {"GOV-006"}):
            with self.subTest(rule=rule):
                self.assertEqual(semantic_text(current[rule]), semantic_text(BASELINE["rules"][rule]["text"]))

    def test_resume_regeln_bleiben_unveraendert_geladen(self):
        current = loaded_rules(BUNDLE, self.routes["resume"])
        for rule, previous in BASELINE["rules"].items():
            if rule.startswith("RES-"):
                self.assertEqual(semantic_text(current[rule]), semantic_text(previous["text"]))

    def test_unbekannte_und_nicht_eindeutige_trigger_scheitern_geschlossen(self):
        for triggers in (["unknown"], ["analysis", "unknown"], [None], [["analysis", "release"]]):
            with self.subTest(triggers=triggers):
                with self.assertRaises(NeutralHarnessError):
                    measure_route(BUNDLE, triggers, 1)

    def test_manipuliertes_manifest_und_fehlende_evidence_scheitern_geschlossen(self):
        for mutation in ("manifest", "evidence"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                bundle = Path(tmp).resolve() / "bundle"
                shutil.copytree(BUNDLE, bundle)
                manifest = bundle / "agent-governance/manifest.toml"
                if mutation == "manifest":
                    manifest.write_text(manifest.read_text().replace('unknown = "block"', 'unknown = "allow"'))
                else:
                    (bundle / "agent-governance/modules/evidence.md").unlink()
                with self.assertRaises(CatalogValidationError):
                    measure_route(bundle, ["analysis"], 1)

    def test_trigger_ids_kommen_weiterhin_aus_dem_bestehenden_katalog(self):
        current = load_catalog_contract(BUNDLE / "agent-governance")
        for route in CORPUS.values():
            self.assertLessEqual(set(route), current.triggers)

    def test_phasenwechsel_laed_gates_vor_der_lieferentscheidung_nach(self):
        for initial in (["implementation"], ["testing"], ["status_reporting"], ["context_handoff"]):
            with self.subTest(initial=initial):
                before = loaded_rules(BUNDLE, measure_route(BUNDLE, initial, 1))
                self.assertFalse(PROMOTION & before.keys())
                for transition in ("release", "quality_review", "security_review"):
                    after = loaded_rules(BUNDLE, measure_route(BUNDLE, [*initial, transition], 1))
                    self.assertLessEqual(PROMOTION | LOCAL, after.keys())
                security = loaded_rules(BUNDLE, measure_route(BUNDLE, [*initial, "security_sensitive_change"], 1))
                self.assertLessEqual(SECURITY | PROMOTION, security.keys())

    def test_benchmark_ist_keine_eigene_integrity_oder_klassifikationsauthority(self):
        with self.assertRaises(ValueError):
            measure_route(BUNDLE, ["analysis"], 0)
        contract = load_catalog_contract(BUNDLE / "agent-governance")
        self.assertEqual(contract.manifest["routing"], {"unknown": "block", "ambiguous": "block"})
        self.assertEqual(set(contract.manifest["modules"]) - set(BASELINE["manifest"]["modules"]), {"verification"})


class LazyDomainLoading(unittest.TestCase):
    def test_kleine_analyse_laed_keine_irrelevanten_domains(self):
        route = measure_route(BUNDLE, ["analysis"], 1)
        for path in (
            "agent-governance/ssot/routing/tools.toml",
            "agent-governance/ssot/routing/scopes.toml",
            "agent-governance/ssot/routing/policy-tags.toml",
            "agent-governance/ssot/commands/commands.toml",
            "agent-governance/ssot/discovery/discovery-signals.toml",
            "agent-governance/ssot/work-items/classifications.toml",
            "agent-governance/ssot/work-items/projections/github-labels.toml",
            "agent-governance/templates/manifest.toml",
        ):
            self.assertNotIn(path, route["files"])

    def test_tool_routing_laed_tools_scopes_policy_tags(self):
        route = measure_route(BUNDLE, ["tool_selection"], 1)
        for path in (
            "agent-governance/ssot/routing/tools.toml",
            "agent-governance/ssot/routing/scopes.toml",
            "agent-governance/ssot/routing/policy-tags.toml",
        ):
            self.assertIn(path, route["files"])

    def test_templates_modul_laed_template_index(self):
        route = measure_route(BUNDLE, ["status_reporting"], 1)
        self.assertIn("agent-governance/templates/manifest.toml", route["files"])

    def test_lazy_pfad_loest_gleiche_module_wie_voller_vertrag(self):
        full = load_catalog_contract(BUNDLE / "agent-governance")
        routing = load_routing_index(BUNDLE / "agent-governance")
        harness = object.__new__(NeutralHarness)
        harness.manifest_dir = BUNDLE / "agent-governance"
        for triggers in (["analysis"], ["tool_selection"], ["implementation", "git_repository"],
                         ["external_effect"], ["resume_continuation"]):
            with self.subTest(triggers=triggers):
                fm, fr, _ = harness._resolve_routes(full.manifest, full.triggers, triggers)
                rm, rr, _ = harness._resolve_routes(routing.manifest, routing.triggers, triggers)
                self.assertEqual(fm, rm)
                self.assertEqual(fr, rr)

    def test_fehlender_tool_katalog_scheitert_erst_bei_bedarf(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp).resolve() / "bundle"
            shutil.copytree(BUNDLE, bundle)
            (bundle / "agent-governance/ssot/routing/tools.toml").unlink()
            route = measure_route(bundle, ["analysis"], 1)
            self.assertNotIn("agent-governance/ssot/routing/tools.toml", route["files"])
            with self.assertRaises(CatalogValidationError):
                measure_route(bundle, ["tool_selection"], 1)

    def test_small_tasks_sind_minimal_und_ohne_promotion(self):
        for name, triggers in SMALL_TASKS.items():
            with self.subTest(name=name):
                route = measure_route(BUNDLE, triggers, 1)
                rules = loaded_rules(BUNDLE, route)
                self.assertLessEqual(KERNEL, rules.keys())
                self.assertFalse(PROMOTION & rules.keys())
                self.assertNotIn("modules/security.md", route["modules"])
                self.assertNotIn("modules/delivery.md", route["modules"])


if __name__ == "__main__":
    unittest.main()
