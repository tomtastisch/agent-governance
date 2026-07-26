#!/usr/bin/env python3
"""Architekturregeln für die importblinde Review-Routing-Laufzeit."""
import ast
from dataclasses import dataclass
import inspect
from pathlib import Path
from typing import get_args, get_origin, get_type_hints
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

    def test_domain_and_adapter_modules_import_only_contracts(self):
        for relative_path in (
            "review_routing/registry.py",
            "review_routing/policy.py",
            "review_routing/risk.py",
            "review_routing/adapters/git_cli.py",
            "review_routing/adapters/github_gh.py",
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

    def test_resolve_preserves_the_requested_port_type(self):
        hints = get_type_hints(RuntimeRegistry.resolve)
        requested_type = get_args(hints["port"])[0]

        self.assertIs(get_origin(hints["port"]), type)
        self.assertEqual(getattr(requested_type, "__name__", None), "T")
        self.assertIs(hints["return"], requested_type)

    def test_bootstrap_resolves_the_policy_port(self):
        from review_routing.contracts import RoutingPolicyPort
        from review_routing.policy import RoutingPolicy

        self.assertIsInstance(RuntimeRegistry.bootstrap(None).resolve(RoutingPolicyPort), RoutingPolicy)

    def test_bootstrap_resolves_risk_and_local_git_ports(self):
        from review_routing.adapters.git_cli import LocalGit
        from review_routing.contracts import DiffSourcePort, PolicySourcePort, RiskClassifierPort
        from review_routing.risk import RiskClassifier

        registry = RuntimeRegistry.bootstrap(None)

        self.assertIsInstance(registry.resolve(RiskClassifierPort), RiskClassifier)
        self.assertIsInstance(registry.resolve(PolicySourcePort), LocalGit)
        self.assertIsInstance(registry.resolve(DiffSourcePort), LocalGit)

    def test_bootstrap_resolves_github_ports(self):
        from review_routing.adapters.github_gh import (
            GitHubGhProbe,
            GitHubStatus,
            SubprocessCommand,
            SystemClock,
        )
        from review_routing.contracts import (
            ClockPort,
            CommandPort,
            ProbePort,
            PullRequestStatePort,
            StatusPort,
        )

        registry = RuntimeRegistry.bootstrap(None)

        self.assertIsInstance(registry.resolve(CommandPort), SubprocessCommand)
        self.assertIsInstance(registry.resolve(StatusPort), GitHubStatus)
        self.assertIsInstance(registry.resolve(ClockPort), SystemClock)
        self.assertIsInstance(registry.resolve(ProbePort), GitHubGhProbe)
        self.assertIsInstance(registry.resolve(PullRequestStatePort), GitHubGhProbe)

    def test_github_port_signatures_are_closed(self):
        from review_routing.contracts import (
            ClockPort,
            CommandPort,
            ProbePort,
            PullRequestStatePort,
            StatusPort,
        )

        expected = {
            CommandPort.run: ("self", "argv", "timeout_seconds"),
            StatusPort.fetch: ("self", "timeout_seconds"),
            ClockPort.now: ("self",),
            ProbePort.probe: ("self", "request"),
            PullRequestStatePort.load: ("self", "repository", "pull_request_number"),
        }

        for method, parameter_names in expected.items():
            with self.subTest(method=method.__qualname__):
                self.assertEqual(tuple(inspect.signature(method).parameters), parameter_names)


if __name__ == "__main__":
    unittest.main()
