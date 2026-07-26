#!/usr/bin/env python3
"""Architekturregeln für die importblinde Review-Routing-Laufzeit."""
import ast
from dataclasses import dataclass
from pathlib import Path
import unittest

from review_routing.contracts import (
    AdapterFactory,
    ConfigPort,
    CyclicProviderError,
    DuplicateProviderError,
    MissingProviderError,
)
from review_routing.registry import RuntimeRegistry


ROOT = Path(__file__).resolve().parents[1]


class ExamplePort:
    pass


class DependentPort:
    pass


@dataclass(frozen=True)
class Factory(AdapterFactory):
    provided_ports: tuple[type[object], ...]
    required_ports: tuple[type[object], ...] = ()

    def build(self, dependencies):
        return {port: object() for port in self.provided_ports}


def imported_review_routing_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names if alias.name.startswith("review_routing"))
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("review_routing"):
            modules.add(node.module)
    return modules


class ImportBoundaryTest(unittest.TestCase):
    """Die vorhandenen Fachmodule kennen ausschließlich den Vertragsrand."""

    def test_contracts_imports_no_project_module(self):
        self.assertEqual(imported_review_routing_modules(ROOT / "review_routing/contracts.py"), set())

    def test_registry_and_toml_adapter_import_only_contracts(self):
        for relative_path in (
            "review_routing/registry.py",
            "review_routing/adapters/toml_config.py",
        ):
            with self.subTest(relative_path=relative_path):
                self.assertEqual(
                    imported_review_routing_modules(ROOT / relative_path),
                    {"review_routing.contracts"},
                )


class RegistryFailureTest(unittest.TestCase):
    """Provider-Fehler sind sichtbar und typisiert statt stiller Ausfall."""

    def test_missing_provider_is_typed(self):
        with self.assertRaises(MissingProviderError):
            RuntimeRegistry().resolve(ExamplePort)

    def test_duplicate_provider_is_typed(self):
        registry = RuntimeRegistry()
        registry.register(Factory((ExamplePort,)))

        with self.assertRaises(DuplicateProviderError):
            registry.register(Factory((ExamplePort,)))

    def test_cyclic_providers_are_typed(self):
        registry = RuntimeRegistry()
        registry.register(Factory((ExamplePort,), (DependentPort,)))
        registry.register(Factory((DependentPort,), (ExamplePort,)))

        with self.assertRaises(CyclicProviderError):
            registry.resolve(ExamplePort)


if __name__ == "__main__":
    unittest.main()
