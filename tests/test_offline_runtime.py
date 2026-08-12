#!/usr/bin/env python3
"""Offlinebetrieb nach vollständiger lokaler Materialisierung."""

from __future__ import annotations

import json
import socket
import unittest
from unittest import mock

from tests.test_local_rules_runtime import NeutralRuntimeCase


class OfflineRuntime(NeutralRuntimeCase):
    def test_discovery_routing_provider_and_audit_work_with_network_guard(self):
        def network_forbidden(*_args, **_kwargs):
            raise AssertionError("network access attempted after bootstrap")

        with mock.patch.object(socket, "socket", side_effect=network_forbidden):
            allowed = self.harness.new_session(
                task="offline allowed read",
                triggers=("analysis", "external_effect", "role_security_review"),
                action_envelope=self.envelope(action_id="offline-allow"),
            )
            denied = self.harness.new_session(
                task="offline denied write",
                triggers=("external_effect",),
                action_envelope=self.envelope(
                    action_id="offline-deny", effect="external_write"
                ),
            )

        self.assertEqual(allowed.decision, "allow")
        self.assertTrue(allowed.continued)
        self.assertEqual(allowed.marker, "SYNTHETIC_LOCAL_RULE_ACTIVE")
        self.assertIn("roles/security-review.md", allowed.role_paths)
        self.assertEqual(denied.decision, "deny")
        self.assertFalse(denied.continued)
        records = [
            json.loads(line) for line in self.audit.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual([record["decision"] for record in records], ["allow", "deny"])
        for record in records:
            self.assertEqual(
                set(record), {"action_id", "decision", "evidence_id", "provider_reached"}
            )


if __name__ == "__main__":
    unittest.main()
