#!/usr/bin/env python3
"""Produktneutralität, Routing und Enforcement des synthetischen Harnesses."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest import mock

from tests.test_local_rules_runtime import NeutralRuntimeCase


class NeutralHarnessContract(unittest.TestCase):
    def test_harness_source_contains_no_product_default(self):
        source = (
            Path(__file__).parent / "support" / "neutral_harness.py"
        ).read_text(encoding="utf-8")
        for forbidden in ("CODEX_HOME", ".codex", ".claude", "opencode", "gemini"):
            self.assertNotIn(forbidden, source.lower() if forbidden.islower() else source)
        self.assertNotRegex(source, r"(?m)/(?:Users|home)/")


class NeutralHarnessRouting(NeutralRuntimeCase):
    def test_every_required_tool_trigger_loads_tool_routing_semantics(self):
        tools_path = self.root / "agent-governance" / "catalogs" / "tools.toml"
        tools = tomllib.loads(tools_path.read_text(encoding="utf-8"))["tools"]
        required_triggers = {
            trigger
            for tool in tools.values()
            for trigger in tool["required_on"]
        }

        missing = []
        for trigger in sorted(required_triggers):
            result = self.harness.new_session(
                task=f"required tool route for {trigger}",
                triggers=(trigger,),
            )
            if "modules/tool-routing.md" not in result.module_paths:
                missing.append(trigger)
        self.assertEqual(missing, [])

    def test_absolute_interface_works_without_product_environment_or_known_cwd(self):
        environment = os.environ.copy()
        for name in tuple(environment):
            if "CODEX" in name or "CLAUDE" in name or "GEMINI" in name:
                environment.pop(name)
        previous = Path.cwd()
        with tempfile.TemporaryDirectory(prefix="foreign neutral cwd ") as foreign:
            with mock.patch.dict(os.environ, environment, clear=True):
                os.chdir(foreign)
                try:
                    result = self.harness.new_session(
                        task="neutral read", triggers=("analysis", "role_quality_assurance")
                    )
                finally:
                    os.chdir(previous)
        self.assertIn("modules/evidence.md", result.module_paths)
        self.assertIn("roles/quality-assurance.md", result.role_paths)

    def test_relative_interface_paths_fail_closed(self):
        for field in ("global_instruction_path", "config_path", "enforcement_command"):
            values = {
                "global_instruction_path": self.global_instruction,
                "config_path": self.config,
                "enforcement_command": self.provider,
                "provider_environment": {},
            }
            values[field] = Path("relative/path")
            with self.subTest(field=field):
                with self.assertRaises(self.neutral.NeutralHarnessError):
                    self.neutral.NeutralHarness(**values)

    def test_enforcement_is_fail_closed_and_only_allow_continues(self):
        cases = (
            (self.envelope(), "allow", True, None),
            (self.envelope(effect="external_write"), "deny", False, None),
            (
                self.envelope(risk_context={"requires_approval": True}),
                "require_approval",
                False,
                None,
            ),
            (self.envelope(), "error", False, "error"),
            (self.envelope(), "unknown", False, "unknown"),
        )
        for envelope, decision, continued, provider_mode in cases:
            with self.subTest(decision=decision):
                with mock.patch.dict(
                    self.harness.provider_environment,
                    {"SYNTHETIC_PROVIDER_MODE": provider_mode} if provider_mode else {},
                    clear=False,
                ):
                    result = self.harness.new_session(
                        task="enforced action",
                        triggers=("external_effect",),
                        action_envelope=envelope,
                    )
                self.assertEqual(result.decision, decision)
                self.assertEqual(result.continued, continued)
        call_lines = self.provider_calls.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(call_lines), 5)

    def test_governance_deny_never_reaches_provider(self):
        result = self.harness.new_session(
            task="denied action",
            triggers=("external_effect",),
            action_envelope=self.envelope(semantic_authorization="deny"),
        )

        self.assertEqual(result.decision, "deny")
        self.assertFalse(result.provider_reached)
        self.assertFalse(result.continued)
        self.assertFalse(self.provider_calls.exists())

    def test_envelope_with_additional_fields_fails_before_provider(self):
        envelope = self.envelope()
        envelope["secret_extra"] = "synthetic-data-that-must-not-reach-provider"

        result = self.harness.new_session(
            task="overbroad action envelope",
            triggers=("external_effect",),
            action_envelope=envelope,
        )

        self.assertEqual(result.decision, "error")
        self.assertFalse(result.provider_reached)
        self.assertFalse(result.continued)
        self.assertFalse(self.provider_calls.exists())

    def test_envelope_with_additional_approval_field_fails_before_provider(self):
        envelope = self.envelope(
            approval_context={
                "valid": False,
                "private_extra": "synthetic-data-that-must-not-reach-provider",
            }
        )

        result = self.harness.new_session(
            task="overbroad nested action envelope",
            triggers=("external_effect",),
            action_envelope=envelope,
        )

        self.assertEqual(result.decision, "error")
        self.assertFalse(result.provider_reached)
        self.assertFalse(result.continued)
        self.assertFalse(self.provider_calls.exists())

    def test_envelope_with_additional_risk_field_fails_before_provider(self):
        envelope = self.envelope(
            risk_context={
                "requires_approval": False,
                "private_extra": "synthetic-data-that-must-not-reach-provider",
            }
        )

        result = self.harness.new_session(
            task="overbroad nested action envelope",
            triggers=("external_effect",),
            action_envelope=envelope,
        )

        self.assertEqual(result.decision, "error")
        self.assertFalse(result.provider_reached)
        self.assertFalse(result.continued)
        self.assertFalse(self.provider_calls.exists())


if __name__ == "__main__":
    unittest.main()
