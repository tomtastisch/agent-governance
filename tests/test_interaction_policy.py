#!/usr/bin/env python3
"""Verhaltensvertrag für die zentral konfigurierte Ausgabepolitik."""
from dataclasses import FrozenInstanceError
import importlib
import importlib.util
import inspect
from pathlib import Path
import unittest

import review_routing.contracts as contracts
from review_routing.adapters.toml_config import TomlConfig


def contract(name: str):
    value = getattr(contracts, name, None)
    if value is None:
        raise AssertionError(f"Der Vertragsrand {name} fehlt")
    return value


ROOT = Path(__file__).resolve().parents[1]


class InteractionContractTest(unittest.TestCase):
    """Die Ausgabepolitik verwendet geschlossene, unveränderliche Verträge."""

    def test_interaction_config_is_immutable_and_requires_an_exact_boolean(self):
        interaction_config = contract("InteractionConfig")

        config = interaction_config(intermediate_status=False)

        self.assertIs(config.intermediate_status, False)
        with self.assertRaises(FrozenInstanceError):
            config.intermediate_status = True
        for invalid in (0, 1, "false", None):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    interaction_config(intermediate_status=invalid)

    def test_message_kind_is_closed_to_the_approved_message_classes(self):
        message_kind = contract("MessageKind")

        self.assertEqual(
            {kind.value for kind in message_kind},
            {
                "voluntary_intermediate",
                "question",
                "blocker",
                "approval",
                "security_warning",
                "error",
                "material_finding",
                "final_result",
            },
        )

    def test_output_decision_is_immutable_and_requires_closed_values(self):
        message_kind = contract("MessageKind")
        output_decision = contract("OutputDecision")

        decision = output_decision(kind=message_kind.QUESTION, emit=True)

        self.assertIs(decision.kind, message_kind.QUESTION)
        self.assertIs(decision.emit, True)
        with self.assertRaises(FrozenInstanceError):
            decision.emit = False
        with self.assertRaises(ValueError):
            output_decision(kind="question", emit=True)
        with self.assertRaises(ValueError):
            output_decision(kind=message_kind.QUESTION, emit=1)

    def test_configuration_error_is_typed_and_the_config_port_is_closed(self):
        configuration_error = contract("ConfigurationError")
        config_port = contract("ConfigPort")

        self.assertTrue(issubclass(configuration_error, contracts.PolicyValidationError))
        self.assertEqual(
            tuple(inspect.signature(config_port.parse_interaction).parameters),
            ("self", "document"),
        )

    def test_output_policy_port_has_the_closed_decision_signature(self):
        output_policy_port = contract("OutputPolicyPort")

        self.assertEqual(
            tuple(inspect.signature(output_policy_port.decide).parameters),
            ("self", "kind", "config"),
        )


class InteractionConfigParserTest(unittest.TestCase):
    """Der TOML-Adapter akzeptiert ausschließlich das geschlossene Schema."""

    def parse(self, content: str):
        self.assertTrue(
            "parse_interaction" in TomlConfig.__dict__,
            "Der TOML-Adapter implementiert parse_interaction noch nicht",
        )
        document = contracts.PolicyDocument(
            content=content,
            trust=contracts.DocumentTrust.DEVELOPMENT,
            source="interaction-test",
        )
        return TomlConfig().parse_interaction(document)

    def test_checked_in_ssot_has_schema_one_and_default_false(self):
        path = ROOT / "core/interaction.toml"
        self.assertTrue(path.is_file(), "Die zentrale interaction.toml fehlt")

        config = self.parse(path.read_text(encoding="utf-8"))

        self.assertIs(config.intermediate_status, False)

    def test_parser_accepts_explicit_true_without_changing_its_meaning(self):
        config = self.parse(
            "schema_version = 1\n\n[output]\nintermediate_status = true\n"
        )

        self.assertIs(config.intermediate_status, True)

    def test_parser_rejects_missing_or_unknown_root_and_output_keys(self):
        invalid_documents = (
            "[output]\nintermediate_status = false\n",
            "schema_version = 1\n",
            "schema_version = 1\nextra = false\n[output]\nintermediate_status = false\n",
            "schema_version = 1\n[output]\n",
            "schema_version = 1\n[output]\nintermediate_status = false\nextra = false\n",
            "schema_version = 1\n[output]\nintermediate_status = false\n[unknown]\nvalue = 1\n",
        )

        configuration_error = contract("ConfigurationError")
        for content in invalid_documents:
            with self.subTest(content=content):
                with self.assertRaises(configuration_error):
                    self.parse(content)

    def test_parser_rejects_every_non_boolean_intermediate_status(self):
        invalid_values = ('"false"', "0", "1", "[]", "{}", "1979-05-27")
        configuration_error = contract("ConfigurationError")

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(configuration_error):
                    self.parse(
                        f"schema_version = 1\n[output]\nintermediate_status = {value}\n"
                    )

    def test_parser_rejects_unsupported_or_non_integer_schema_versions(self):
        invalid_versions = ("2", "true", '"1"')
        configuration_error = contract("ConfigurationError")

        for version in invalid_versions:
            with self.subTest(version=version):
                with self.assertRaises(configuration_error):
                    self.parse(
                        f"schema_version = {version}\n[output]\n"
                        "intermediate_status = false\n"
                    )

    def test_parser_maps_malformed_toml_to_configuration_error(self):
        configuration_error = contract("ConfigurationError")
        invalid_documents = (
            "schema_version = 1\n[output\nintermediate_status = false\n",
            "schema_version = 1\n[output]\nintermediate_status = null\n",
        )

        for content in invalid_documents:
            with self.subTest(content=content):
                with self.assertRaises(configuration_error):
                    self.parse(content)


class OutputPolicyBehaviorTest(unittest.TestCase):
    """Nur freiwillige Zwischenstände dürfen unterdrückt werden."""

    def output_policy_module(self):
        self.assertIsNotNone(
            importlib.util.find_spec("review_routing.output_policy"),
            "Das reine Ausgabepolicy-Modul fehlt",
        )
        return importlib.import_module("review_routing.output_policy")

    def test_false_suppresses_only_voluntary_intermediate_messages(self):
        module = self.output_policy_module()
        config = contracts.InteractionConfig(intermediate_status=False)

        decisions = {
            kind: module.decide_output(kind, config)
            for kind in contracts.MessageKind
        }

        self.assertIs(
            decisions[contracts.MessageKind.VOLUNTARY_INTERMEDIATE].emit,
            False,
        )
        mandatory = set(contracts.MessageKind) - {
            contracts.MessageKind.VOLUNTARY_INTERMEDIATE
        }
        self.assertTrue(all(decisions[kind].emit is True for kind in mandatory))
        self.assertTrue(all(decisions[kind].kind is kind for kind in contracts.MessageKind))

    def test_true_leaves_every_message_kind_unchanged(self):
        module = self.output_policy_module()
        config = contracts.InteractionConfig(intermediate_status=True)

        decisions = [
            module.decide_output(kind, config)
            for kind in contracts.MessageKind
        ]

        self.assertTrue(all(decision.emit is True for decision in decisions))

    def test_pure_decision_rejects_open_or_wrongly_typed_inputs(self):
        module = self.output_policy_module()
        config = contracts.InteractionConfig(intermediate_status=False)

        with self.assertRaises(ValueError):
            module.decide_output("question", config)
        with self.assertRaises(ValueError):
            module.decide_output(contracts.MessageKind.QUESTION, object())

    def test_port_implementation_delegates_to_the_same_pure_decision(self):
        module = self.output_policy_module()
        config = contracts.InteractionConfig(intermediate_status=False)
        policy = module.OutputPolicy()

        decision = policy.decide(contracts.MessageKind.BLOCKER, config)

        self.assertIsInstance(policy, contracts.OutputPolicyPort)
        self.assertEqual(
            decision,
            contracts.OutputDecision(
                kind=contracts.MessageKind.BLOCKER,
                emit=True,
            ),
        )


if __name__ == "__main__":
    unittest.main()
