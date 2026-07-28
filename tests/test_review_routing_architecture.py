#!/usr/bin/env python3
"""Architekturregeln für die importblinde Review-Routing-Laufzeit."""
import ast
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import inspect
import json
from pathlib import Path
import tomllib
from typing import get_args, get_origin, get_type_hints
import unittest
from unittest.mock import patch

from review_routing.contracts import (
    AdapterFactory,
    BillingPrincipal,
    CapabilityArtifactKind,
    CapabilityEvidenceReference,
    CapabilityEvidenceSource,
    CliDependencies,
    ConfigPort,
    DiagnosticStatus,
    CyclicProviderError,
    DuplicateProviderError,
    MissingProviderError,
    OperatorEvidencePin,
    OperatorEvidenceTrustPort,
    ProbeRequest,
    RuntimeTrustSource,
    StatusSnapshot,
    CommandResult,
)
from review_routing.registry import RuntimeRegistry


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc)
REPOSITORY = "tomtastisch/agent-governance"


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


class PinnedOperatorTrust(OperatorEvidenceTrustPort):
    def __init__(self, source_reference: str, artifact: bytes):
        self.pin = OperatorEvidencePin(
            source_reference=source_reference,
            expected_digest="sha256:" + hashlib.sha256(artifact).hexdigest(),
            pin_source=RuntimeTrustSource.PUBLISHER_APP,
        )

    def load(self, source_reference):
        return self.pin if source_reference == self.pin.source_reference else None


class RegistryCommand:
    def __init__(self):
        self.calls = []

    def run(self, argv, timeout_seconds):
        self.calls.append(argv)
        endpoint = argv[-1]
        payloads = {
            "/user": {"login": "tom"},
            "/users/tom/settings/billing/ai_credit/usage?year=2026&month=7": {
                "usageItems": [{"unitType": "credits", "grossQuantity": 1}]
            },
        }
        if endpoint not in payloads:
            raise AssertionError(f"unexpected endpoint: {endpoint}")
        return CommandResult(
            return_code=0,
            stdout=(
                b"HTTP/2 200\r\ncontent-type: application/json\r\n\r\n"
                + json.dumps(payloads[endpoint]).encode("utf-8")
            ),
            stderr=b"",
        )


class RegistryStatus:
    def fetch(self, timeout_seconds):
        return StatusSnapshot(
            status=DiagnosticStatus.AVAILABLE,
            source="github_status",
            observed_at=NOW,
        )


class RegistryClock:
    def now(self):
        return NOW


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
            "review_routing/evidence.py",
            "review_routing/output_policy.py",
            "review_routing/adapters/git_cli.py",
            "review_routing/adapters/github_gh.py",
            "review_routing/adapters/toml_config.py",
        ):
            with self.subTest(relative_path=relative_path):
                self.assertEqual(
                    imported_review_routing_modules(ROOT / relative_path),
                    {"review_routing.contracts"},
                )

    def test_cli_composition_root_imports_only_contracts_and_registry(self):
        self.assertEqual(
            imported_review_routing_modules(ROOT / "review_routing/__main__.py"),
            {"review_routing.contracts", "review_routing.registry"},
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
            BlockEvidenceVerifier,
            CapabilityEvidenceVerifier,
            GitHubGhProbe,
            GitHubStatus,
            SubprocessCommand,
            SystemClock,
        )
        from review_routing.registry import DevelopmentOperatorEvidenceTrust
        from review_routing.contracts import (
            BlockEvidenceVerifierPort,
            CapabilityEvidenceVerifierPort,
            ClockPort,
            CommandPort,
            OperatorEvidenceTrustPort,
            ProbePort,
            PullRequestStatePort,
            StatusPort,
        )

        registry = RuntimeRegistry.bootstrap(None)

        self.assertIsInstance(registry.resolve(CommandPort), SubprocessCommand)
        self.assertIsInstance(registry.resolve(StatusPort), GitHubStatus)
        self.assertIsInstance(registry.resolve(ClockPort), SystemClock)
        self.assertIsInstance(
            registry.resolve(OperatorEvidenceTrustPort),
            DevelopmentOperatorEvidenceTrust,
        )
        self.assertIsInstance(
            registry.resolve(CapabilityEvidenceVerifierPort),
            CapabilityEvidenceVerifier,
        )
        self.assertIsInstance(
            registry.resolve(BlockEvidenceVerifierPort),
            BlockEvidenceVerifier,
        )
        self.assertIsInstance(registry.resolve(ProbePort), GitHubGhProbe)
        self.assertIsInstance(registry.resolve(PullRequestStatePort), GitHubGhProbe)

    def test_bootstrap_resolves_evidence_validator_port(self):
        from review_routing.contracts import (
            EvidenceValidatorPort,
            GatePublisherPort,
            PriorGateEvidencePort,
        )
        from review_routing.evidence import EvidenceValidator

        self.assertIsInstance(
            RuntimeRegistry.bootstrap(None).resolve(EvidenceValidatorPort),
            EvidenceValidator,
        )
        with self.assertRaises(MissingProviderError):
            RuntimeRegistry.bootstrap(None).resolve(GatePublisherPort)
        with self.assertRaises(MissingProviderError):
            RuntimeRegistry.bootstrap(None).resolve(PriorGateEvidencePort)

    def test_bootstrap_resolves_output_policy_port(self):
        from review_routing.contracts import OutputPolicyPort
        from review_routing.output_policy import OutputPolicy

        runtime = tomllib.loads(
            (ROOT / "review_routing/runtime.toml").read_text(encoding="utf-8")
        )
        self.assertIn("review_routing.output_policy", runtime["modules"])
        self.assertIsInstance(
            RuntimeRegistry.bootstrap(None).resolve(OutputPolicyPort),
            OutputPolicy,
        )

    def test_bootstrap_injects_the_exact_operator_trust_into_a_positive_probe(self):
        from review_routing.adapters import github_gh
        from review_routing.contracts import (
            BlockEvidenceVerifierPort,
            CapabilityEvidenceVerifierPort,
            ProbePort,
        )

        principal = BillingPrincipal(
            kind="personal",
            identifier="tom",
            review_mode="manual",
            requester="tom",
            pull_request_author=None,
            source="github_api",
            observed_at=NOW,
            expires_at=NOW + timedelta(minutes=15),
        )
        source_reference = "registry_operator_capability"
        document = {
            "schema_version": 1,
            "kind": CapabilityArtifactKind.OPERATOR_SETTING.value,
            "repository": REPOSITORY,
            "principal_identity": list(principal.identity),
            "review_mode": "manual",
            "observed_at": "2026-07-26T12:00:00Z",
            "expires_at": "2026-07-26T12:10:00Z",
            "source_reference": source_reference,
        }
        artifact = json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        trust = PinnedOperatorTrust(source_reference, artifact)
        command = RegistryCommand()
        status = RegistryStatus()
        clock = RegistryClock()

        with (
            patch.object(github_gh, "SubprocessCommand", return_value=command),
            patch.object(github_gh, "GitHubStatus", return_value=status),
            patch.object(github_gh, "SystemClock", return_value=clock),
        ):
            registry = RuntimeRegistry.bootstrap(
                CliDependencies(operator_evidence_trust_port=trust)
            )
            capability_verifier = registry.resolve(CapabilityEvidenceVerifierPort)
            block_verifier = registry.resolve(BlockEvidenceVerifierPort)
            probe = registry.resolve(ProbePort)

        self.assertIs(registry.resolve(OperatorEvidenceTrustPort), trust)
        self.assertIs(capability_verifier._operator_trust, trust)
        self.assertIs(block_verifier._operator_trust, trust)
        self.assertIs(probe._capability_verifier, capability_verifier)
        self.assertIs(probe._block_verifier, block_verifier)

        report = probe.probe(
            ProbeRequest(
                repository=REPOSITORY,
                review_mode="manual",
                manual_requester="tom",
                capability_reference=CapabilityEvidenceReference(
                    schema_version=1,
                    source=CapabilityEvidenceSource.OPERATOR_PINNED,
                    repository=REPOSITORY,
                    review_mode="manual",
                    principal_identity=principal.identity,
                    source_reference=source_reference,
                    artifact=artifact,
                ),
            )
        )

        self.assertTrue(report.copilot_usable)
        self.assertEqual(report.capability_status, "valid")

    def test_github_port_signatures_are_closed(self):
        from review_routing.contracts import (
            BlockEvidenceVerifierPort,
            CapabilityEvidenceVerifierPort,
            ClockPort,
            CommandPort,
            OperatorEvidenceTrustPort,
            ProbePort,
            PullRequestStatePort,
            StatusPort,
            EvidenceValidatorPort,
            GatePublisherPort,
            PriorGateEvidencePort,
        )

        expected = {
            CommandPort.run: ("self", "argv", "timeout_seconds"),
            StatusPort.fetch: ("self", "timeout_seconds"),
            ClockPort.now: ("self",),
            ProbePort.probe: ("self", "request"),
            PullRequestStatePort.load: ("self", "repository", "pull_request_number"),
            OperatorEvidenceTrustPort.load: ("self", "source_reference"),
            CapabilityEvidenceVerifierPort.verify: (
                "self",
                "reference",
                "repository",
                "principal",
                "review_mode",
                "observed_at",
            ),
            BlockEvidenceVerifierPort.verify: (
                "self",
                "reference",
                "repository",
                "principal",
                "review_mode",
                "observed_at",
            ),
            EvidenceValidatorPort.validate: (
                "self",
                "context",
                "evidence",
                "runtime",
                "trusted_config",
                "trusted_diff",
                "risk_classifier",
                "routing_policy",
            ),
            GatePublisherPort.publish: ("self", "result"),
            PriorGateEvidencePort.load_immediate: (
                "self",
                "repository",
                "pull_request_number",
                "current_head_sha",
            ),
        }

        for method, parameter_names in expected.items():
            with self.subTest(method=method.__qualname__):
                self.assertEqual(tuple(inspect.signature(method).parameters), parameter_names)


if __name__ == "__main__":
    unittest.main()
