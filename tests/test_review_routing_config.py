#!/usr/bin/env python3
"""Verhaltensspezifikation für die zentrale Review-Routing-Policy."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import tomllib
import unittest

from review_routing.adapters.toml_config import TomlConfig
from review_routing.contracts import (
    CliDependencies,
    ConfigPort,
    DocumentTrust,
    PolicyDocument,
    PolicyValidationError,
    RuntimeTrustConfig,
    RuntimeTrustSource,
    RuntimeTrustPort,
    RuntimeTrustMismatchError,
)
from review_routing.registry import RuntimeRegistry


ROOT = Path(__file__).resolve().parents[1]


class StaticRuntimeTrust(RuntimeTrustPort):
    """Test-double an der externen Vertrauensgrenze."""

    def __init__(self, config: RuntimeTrustConfig):
        self._config = config

    def load(self) -> RuntimeTrustConfig:
        return self._config


class RoutingPolicyFileTest(unittest.TestCase):
    """Die Datei enthält die vollständige Policy, ohne Runtime-Steuerung."""

    def test_policy_has_closed_routing_and_gate_shape(self):
        raw = tomllib.loads((ROOT / "core/review-routing.toml").read_text(encoding="utf-8"))

        self.assertEqual(raw["schema_version"], 1)
        self.assertEqual(set(raw["routing"]), {"checkpoint", "final_exact_head"})
        self.assertEqual(
            set(raw["routing"]["final_exact_head"]["usable"]),
            {"low", "medium", "high", "critical"},
        )
        self.assertNotIn("remaining", json.dumps(raw).lower())
        self.assertNotIn("runtime", raw)
        self.assertTrue(raw["gate"]["required_checks"])
        for required_check in raw["gate"]["required_checks"]:
            self.assertEqual(set(required_check), {"name", "source_app_slug"})
        self.assertTrue(raw["gate"]["publisher"]["expected_app_slug"])
        for marker in raw["risk"]["path_markers"]:
            self.assertEqual(set(marker), {"glob", "level", "security_relevant"})

    def test_parser_accepts_the_checked_in_policy(self):
        document = PolicyDocument(
            content=(ROOT / "core/review-routing.toml").read_text(encoding="utf-8"),
            trust=DocumentTrust.DEVELOPMENT,
            source="core/review-routing.toml",
        )

        config = TomlConfig().parse_routing(document)

        self.assertEqual(config.schema_version, 1)
        self.assertEqual(config.routes["checkpoint"][True]["low"], "local_checks")
        self.assertEqual(config.routes["final_exact_head"][False]["critical"], "qa_sec")

    def test_parser_rejects_runtime_injection_before_any_factory_is_loaded(self):
        policy = (ROOT / "core/review-routing.toml").read_text(encoding="utf-8")
        injected = PolicyDocument(
            content=policy + '\n[runtime]\nmodules = ["review_routing.adapters.evil"]\n',
            trust=DocumentTrust.DEVELOPMENT,
            source="candidate-policy",
        )

        with self.assertRaises(PolicyValidationError):
            TomlConfig().parse_routing(injected)

    def test_parser_rejects_invalid_thresholds_and_missing_matrix_cells(self):
        policy = (ROOT / "core/review-routing.toml").read_text(encoding="utf-8")
        invalid_thresholds = policy.replace("medium = 100", "medium = 0")
        missing_matrix_cell = policy.replace('critical = "qa_sec"\n', "", 1)

        for content in (invalid_thresholds, missing_matrix_cell):
            with self.subTest(content=content):
                with self.assertRaises(PolicyValidationError):
                    TomlConfig().parse_routing(
                        PolicyDocument(content, DocumentTrust.DEVELOPMENT, "candidate-policy")
                    )

    def test_parser_rejects_unknown_route_and_empty_required_checks(self):
        policy = (ROOT / "core/review-routing.toml").read_text(encoding="utf-8")
        invalid_route = policy.replace('medium = "copilot"', 'medium = "fallback"', 1)
        empty_checks = policy.replace(
            '[[gate.required_checks]]\nname = "agent-governance/review-gate"\nsource_app_slug = "agent-governance-review-gate"\n',
            "",
        )

        for content in (invalid_route, empty_checks):
            with self.subTest(content=content):
                with self.assertRaises(PolicyValidationError):
                    TomlConfig().parse_routing(
                        PolicyDocument(content, DocumentTrust.DEVELOPMENT, "candidate-policy")
                    )

    def test_parser_rejects_non_string_route_values_with_a_typed_error(self):
        policy = (ROOT / "core/review-routing.toml").read_text(encoding="utf-8")
        invalid_values = (
            '["qa"]',
            '{ route = "qa" }',
            "true",
            "1",
        )

        for invalid_value in invalid_values:
            with self.subTest(invalid_value=invalid_value):
                candidate = policy.replace('low = "local_checks"', f"low = {invalid_value}", 1)
                with self.assertRaises(PolicyValidationError):
                    TomlConfig().parse_routing(
                        PolicyDocument(candidate, DocumentTrust.DEVELOPMENT, "candidate-policy")
                    )


class RuntimeBootstrapTest(unittest.TestCase):
    """Nur die paketierte Runtime-SSOT darf die Factory-Auswahl steuern."""

    def test_runtime_manifest_has_only_closed_bootstrap_keys(self):
        raw = tomllib.loads(
            (ROOT / "review_routing/runtime.toml").read_text(encoding="utf-8")
        )

        self.assertEqual(set(raw), {"schema_version", "modules"})
        self.assertEqual(raw["schema_version"], 1)
        self.assertEqual(raw["modules"], ["review_routing.adapters.toml_config"])

    def test_bootstrap_resolves_toml_config_from_the_packaged_manifest(self):
        registry = RuntimeRegistry.bootstrap(None)

        self.assertIsInstance(registry.resolve(ConfigPort), TomlConfig)
        self.assertEqual(registry.runtime_provenance.trust.value, "development")

    def test_candidate_policy_cannot_change_the_loaded_factory_set(self):
        policy = (ROOT / "core/review-routing.toml").read_text(encoding="utf-8")
        injected = PolicyDocument(
            policy + '\n[runtime]\nmodules = ["review_routing.adapters.evil"]\n',
            DocumentTrust.DEVELOPMENT,
            "candidate-policy",
        )
        registry = RuntimeRegistry.bootstrap(None)

        with self.assertRaises(PolicyValidationError):
            registry.resolve(ConfigPort).parse_routing(injected)

        self.assertIsInstance(registry.resolve(ConfigPort), TomlConfig)

    def test_missing_external_runtime_pin_is_development(self):
        trust = StaticRuntimeTrust(
            RuntimeTrustConfig(
                expected_runtime_digest=None,
                source=RuntimeTrustSource.INSTALLED_CONFIG,
                observed_at=datetime(2026, 7, 26, tzinfo=timezone.utc),
            )
        )

        registry = RuntimeRegistry.bootstrap(CliDependencies(runtime_trust_port=trust))

        self.assertEqual(registry.runtime_provenance.trust.value, "development")

    def test_matching_trusted_runtime_pin_is_installed(self):
        runtime = (ROOT / "review_routing/runtime.toml").read_bytes()
        digest = "sha256:" + hashlib.sha256(runtime).hexdigest()
        trust = StaticRuntimeTrust(
            RuntimeTrustConfig(
                expected_runtime_digest=digest,
                source=RuntimeTrustSource.PUBLISHER_APP,
                observed_at=datetime(2026, 7, 26, tzinfo=timezone.utc),
            )
        )

        registry = RuntimeRegistry.bootstrap(CliDependencies(runtime_trust_port=trust))

        self.assertEqual(registry.runtime_provenance.trust.value, "installed")

    def test_mismatching_trusted_runtime_pin_is_a_hard_failure(self):
        trust = StaticRuntimeTrust(
            RuntimeTrustConfig(
                expected_runtime_digest="sha256:" + "0" * 64,
                source=RuntimeTrustSource.PUBLISHER_APP,
                observed_at=datetime(2026, 7, 26, tzinfo=timezone.utc),
            )
        )

        with self.assertRaises(RuntimeTrustMismatchError):
            RuntimeRegistry.bootstrap(CliDependencies(runtime_trust_port=trust))

    def test_mismatching_development_runtime_pin_is_a_hard_failure(self):
        trust = StaticRuntimeTrust(
            RuntimeTrustConfig(
                expected_runtime_digest="sha256:" + "0" * 64,
                source=RuntimeTrustSource.DEVELOPMENT,
                observed_at=datetime(2026, 7, 26, tzinfo=timezone.utc),
            )
        )

        with self.assertRaises(RuntimeTrustMismatchError):
            RuntimeRegistry.bootstrap(CliDependencies(runtime_trust_port=trust))


if __name__ == "__main__":
    unittest.main()
