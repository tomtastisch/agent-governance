"""Cross-Language-Conformance-Gate (#90) — Python-Seite.

Koppelt die produktiven TypeScript-Validatoren und die unabhängige Python-Testreferenz
über einen expliziten Conformance-Vertrag. Beide Implementierungen bleiben unabhängig,
lesen aber dieselbe sprachneutrale Contract-Fixture und prüfen dieselbe Mutation-Batterie:

- `contracts/governance-contract.json` (gemeinsame Strukturdefinitionen)
- `tests/contracts/conformance-mutations.json` (gemeinsame Mutation-Batterie)

Die TypeScript-Seite desselben Gates läuft in `tests/installer/conformance.test.ts`
(über `npm test`, inklusive `node_modules`). Diese Datei prüft ausschließlich die
Python-Referenz gegen dieselben Fixtures; die Sprache ist so unabhängig wie die
Validierungslogik selbst.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests.support.catalog_validator import CatalogValidationError, load_catalog_contract


ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE_ROOT = ROOT / "bundle" / "agent-governance"
CONTRACT_FIXTURE = ROOT / "contracts" / "governance-contract.json"
MUTATIONS_FIXTURE = ROOT / "tests" / "contracts" / "conformance-mutations.json"


def _apply_mutation(root: Path, mutation: dict) -> Path:
    target = root / "agent-governance"
    shutil.copytree(GOVERNANCE_ROOT, target)
    relative = mutation["file"]
    path = target / relative
    text = path.read_text(encoding="utf-8")
    find = mutation["find"]
    replace = mutation["replace"]
    if find not in text:
        raise AssertionError(f"Mutation-Anker fehlt: {relative}: {find}")
    path.write_text(text.replace(find, replace, 1), encoding="utf-8")
    return target


class ContractFixtureContract(unittest.TestCase):
    def test_contract_fixture_is_shared_and_well_formed(self):
        data = json.loads(CONTRACT_FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], 1)
        for group in ("fields", "domains", "vocabularies"):
            self.assertIn(group, data)
        self.assertEqual(
            data["domains"]["ssot"], ["routing", "commands", "discovery", "work_items"]
        )
        self.assertIn("tool", data["fields"])
        self.assertIn("command", data["fields"])

    def test_mutation_battery_is_well_formed(self):
        data = json.loads(MUTATIONS_FIXTURE.read_text(encoding="utf-8"))
        mutations = data["mutations"]
        self.assertTrue(mutations)
        ids = [mutation["id"] for mutation in mutations]
        self.assertEqual(len(ids), len(set(ids)))
        for mutation in mutations:
            for key in ("id", "file", "find", "replace"):
                self.assertIn(key, mutation)


class CrossLanguageConformance(unittest.TestCase):
    def test_valid_bundle_is_accepted_by_python_reference(self):
        load_catalog_contract(GOVERNANCE_ROOT)

    def test_each_mutation_is_rejected_by_python_reference(self):
        mutations = json.loads(MUTATIONS_FIXTURE.read_text(encoding="utf-8"))["mutations"]
        for mutation in mutations:
            with self.subTest(mutation=mutation["id"]):
                with tempfile.TemporaryDirectory(prefix="agent-governance-conformance-") as directory:
                    mutated_root = _apply_mutation(Path(directory), mutation)
                    with self.assertRaises(CatalogValidationError):
                        load_catalog_contract(mutated_root)

    def test_contract_fixture_drives_python_reference(self):
        """Die Python-Referenz leitet ihre Feld-/Vokabularmengen aus der Fixture ab."""
        from tests.support import catalog_validator

        data = json.loads(CONTRACT_FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(catalog_validator.MODULE_FIELDS, set(data["fields"]["module"]))
        self.assertEqual(catalog_validator.TOOL_FIELDS, set(data["fields"]["tool"]))
        self.assertEqual(
            catalog_validator.TEMPLATE_CATEGORIES,
            set(data["vocabularies"]["template_categories"]),
        )
        self.assertEqual(
            catalog_validator.SSOT_DOMAIN_CATALOGS["routing"],
            set(data["domains"]["ssot_catalogs"]["routing"]),
        )


if __name__ == "__main__":
    unittest.main()
