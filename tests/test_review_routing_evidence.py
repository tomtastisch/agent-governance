#!/usr/bin/env python3
"""Korrekturregressionen für verifizierte Capability- und Blockadeevidenz."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import unittest

from review_routing.adapters.github_gh import (
    BlockEvidenceVerifier,
    CapabilityEvidenceVerifier,
    GitHubStatus,
)
from review_routing.contracts import (
    BillingPrincipal,
    BlockEvidenceKind,
    BlockEvidenceReference,
    BlockEvidenceSource,
    BlockVerification,
    CapabilityEvidence,
    CapabilityVerification,
    CapabilityEvidenceReference,
    CapabilityEvidenceSource,
    DiagnosticStatus,
    EvidenceTrust,
    EvidenceVerificationStatus,
    OperatorEvidencePin,
    RuntimeTrustSource,
    CommandResult,
    VerifiedBlockEvidence,
)
from review_routing.policy import classify_usability


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc)
REPOSITORY = "tomtastisch/agent-governance"


def canonical(document: dict[str, object]) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def digest(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def principal() -> BillingPrincipal:
    return BillingPrincipal(
        kind="personal",
        identifier="tom",
        review_mode="manual",
        requester="tom",
        pull_request_author=None,
        source="github_api",
        observed_at=NOW - timedelta(minutes=10),
        expires_at=NOW + timedelta(minutes=30),
    )


def operator_capability_document() -> dict[str, object]:
    return {
        "schema_version": 1,
        "repository": REPOSITORY,
        "principal_identity": list(principal().identity),
        "review_mode": "manual",
        "observed_at": "2026-07-26T11:55:00Z",
        "expires_at": "2026-07-26T12:10:00Z",
        "source_reference": "operator_capability_20260726",
    }


class NoCommand:
    def run(self, argv, timeout_seconds):
        raise AssertionError("Operator-Artefakte dürfen keinen GitHub-Aufruf auslösen")


class FixedClock:
    def now(self):
        return NOW


class OperatorEvidenceTrustTest(unittest.TestCase):
    """Callerinhalt wird erst durch einen externen Digest-Pin routingfähig."""

    def reference(self, content: bytes) -> CapabilityEvidenceReference:
        return CapabilityEvidenceReference(
            schema_version=1,
            source=CapabilityEvidenceSource.OPERATOR_PINNED,
            repository=REPOSITORY,
            review_mode="manual",
            principal_identity=principal().identity,
            source_reference="operator_capability_20260726",
            artifact=content,
        )

    def test_unpinned_well_formed_operator_artifact_is_not_routing_capability(self):
        content = canonical(operator_capability_document())
        verifier = CapabilityEvidenceVerifier(command=NoCommand(), operator_pins={})

        result = verifier.verify(
            self.reference(content),
            REPOSITORY,
            principal(),
            "manual",
            NOW,
        )

        self.assertEqual(result.status, EvidenceVerificationStatus.INVALID)
        self.assertEqual(result.trust, EvidenceTrust.DEVELOPMENT)
        self.assertIsNone(result.evidence)

    def test_wrong_external_digest_is_not_routing_capability(self):
        content = canonical(operator_capability_document())
        verifier = CapabilityEvidenceVerifier(
            command=NoCommand(),
            operator_pins={
                "operator_capability_20260726": OperatorEvidencePin(
                    source_reference="operator_capability_20260726",
                    expected_digest="sha256:" + "0" * 64,
                    source=RuntimeTrustSource.INSTALLED_CONFIG,
                )
            },
        )

        result = verifier.verify(
            self.reference(content),
            REPOSITORY,
            principal(),
            "manual",
            NOW,
        )

        self.assertEqual(result.status, EvidenceVerificationStatus.INVALID)
        self.assertIsNone(result.evidence)

    def test_matching_external_digest_produces_current_operator_capability(self):
        content = canonical(operator_capability_document())
        verifier = CapabilityEvidenceVerifier(
            command=NoCommand(),
            operator_pins={
                "operator_capability_20260726": OperatorEvidencePin(
                    source_reference="operator_capability_20260726",
                    expected_digest=digest(content),
                    source=RuntimeTrustSource.PUBLISHER_APP,
                )
            },
        )

        result = verifier.verify(
            self.reference(content),
            REPOSITORY,
            principal(),
            "manual",
            NOW,
        )

        self.assertEqual(result.status, EvidenceVerificationStatus.VERIFIED)
        self.assertEqual(result.trust, EvidenceTrust.VERIFIED)
        self.assertEqual(result.evidence.source, CapabilityEvidenceSource.OPERATOR_PINNED)
        self.assertEqual(result.artifact_digest, digest(content))


class GitHubReviewEvidenceTest(unittest.TestCase):
    class Command:
        def __init__(self, state="COMMENTED", body="finding text is not capability"):
            self.state = state
            self.body = body
            self.calls = []

        def run(self, argv, timeout_seconds):
            self.calls.append(argv)
            payload = {
                "id": 41,
                "user": {"login": "copilot-pull-request-reviewer[bot]"},
                "state": self.state,
                "commit_id": "c" * 40,
                "submitted_at": "2026-07-26T11:59:00Z",
                "body": self.body,
            }
            return CommandResult(
                return_code=0,
                stdout=(
                    b"HTTP/2 200\r\ncontent-type: application/json\r\n\r\n"
                    + json.dumps(payload).encode("utf-8")
                ),
                stderr=b"",
            )

    def reference(self):
        return CapabilityEvidenceReference(
            schema_version=1,
            source=CapabilityEvidenceSource.GITHUB_COMPLETED_REVIEW,
            repository=REPOSITORY,
            review_mode="manual",
            principal_identity=principal().identity,
            source_reference="untrusted_review_reference",
            pull_request_number=17,
            review_id=41,
        )

    def test_completed_copilot_review_is_reconstructed_without_trusting_findings(self):
        command = self.Command(body="SENSITIVE untrusted review prose")
        current_principal = BillingPrincipal(
            kind="personal",
            identifier="tom",
            review_mode="manual",
            requester="tom",
            pull_request_author=None,
            source="github_api",
            observed_at=NOW,
            expires_at=NOW + timedelta(minutes=30),
        )
        reference = CapabilityEvidenceReference(
            **{
                **self.reference().__dict__,
                "principal_identity": current_principal.identity,
            }
        )
        result = CapabilityEvidenceVerifier(command, {}).verify(
            reference,
            REPOSITORY,
            current_principal,
            "manual",
            NOW,
        )

        self.assertEqual(result.status, EvidenceVerificationStatus.VERIFIED)
        self.assertEqual(result.evidence.review_commit_sha, "c" * 40)
        self.assertTrue(
            result.evidence.is_valid_for(
                REPOSITORY,
                current_principal,
                "manual",
                NOW,
            )
        )
        self.assertNotIn("SENSITIVE", result.source_reference)
        self.assertEqual(
            command.calls[0][-1],
            f"/repos/{REPOSITORY}/pulls/17/reviews/41",
        )

    def test_pending_or_failed_review_is_not_capability(self):
        for state in ("PENDING", "DISMISSED"):
            with self.subTest(state=state):
                result = CapabilityEvidenceVerifier(self.Command(state=state), {}).verify(
                    self.reference(),
                    REPOSITORY,
                    principal(),
                    "manual",
                    NOW,
                )
                self.assertEqual(result.status, EvidenceVerificationStatus.INVALID)
                self.assertIsNone(result.evidence)


class ClosedReferenceTest(unittest.TestCase):
    """Referenzen können keine Trust- oder Blockadebehauptung einschmuggeln."""

    def test_capability_reference_has_no_trust_or_expected_digest_field(self):
        fields = CapabilityEvidenceReference.__dataclass_fields__
        self.assertNotIn("trust", fields)
        self.assertNotIn("expected_digest", fields)
        self.assertNotIn("issuer", fields)

    def test_block_reference_carries_only_untrusted_reference_material(self):
        reference = BlockEvidenceReference(
            schema_version=1,
            source=BlockEvidenceSource.OPERATOR_PINNED,
            repository=REPOSITORY,
            review_mode="manual",
            principal_identity=principal().identity,
            source_reference="operator_block_20260726",
            artifact=canonical(
                {
                    "schema_version": 1,
                    "kind": BlockEvidenceKind.BUDGET_BLOCKED.value,
                    "repository": REPOSITORY,
                    "principal_identity": list(principal().identity),
                    "review_mode": "manual",
                    "observed_at": "2026-07-26T11:59:00Z",
                    "expires_at": "2026-07-26T12:10:00Z",
                    "source_reference": "operator_block_20260726",
                }
            ),
        )

        self.assertFalse(hasattr(reference, "trust"))
        self.assertFalse(hasattr(reference, "expected_digest"))

    def test_verified_envelopes_reject_mismatched_provenance(self):
        evidence = CapabilityEvidence(
            repository=REPOSITORY,
            principal=principal(),
            review_mode="manual",
            observed_at=NOW - timedelta(minutes=1),
            expires_at=NOW + timedelta(minutes=5),
            source=CapabilityEvidenceSource.OPERATOR_PINNED,
            source_reference="verified_capability",
            artifact_digest="sha256:" + "a" * 64,
        )
        with self.assertRaises(ValueError):
            CapabilityVerification(
                EvidenceVerificationStatus.VERIFIED,
                EvidenceTrust.VERIFIED,
                CapabilityEvidenceSource.GITHUB_COMPLETED_REVIEW,
                evidence.source_reference,
                evidence.artifact_digest,
                evidence,
            )


class EvidenceOrderingTest(unittest.TestCase):
    def capability(self, observed_at):
        return CapabilityEvidence(
            repository=REPOSITORY,
            principal=principal(),
            review_mode="manual",
            observed_at=observed_at,
            expires_at=NOW + timedelta(minutes=20),
            source=CapabilityEvidenceSource.OPERATOR_PINNED,
            source_reference="verified_capability",
            artifact_digest="sha256:" + "a" * 64,
        )

    def block(self, observed_at):
        return VerifiedBlockEvidence(
            schema_version=1,
            kind=BlockEvidenceKind.BUDGET_BLOCKED,
            repository=REPOSITORY,
            principal_identity=principal().identity,
            review_mode="manual",
            observed_at=observed_at,
            expires_at=NOW + timedelta(minutes=20),
            source=BlockEvidenceSource.OPERATOR_PINNED,
            source_reference="verified_block",
            artifact_digest="sha256:" + "b" * 64,
        )

    def signals(self, capability, block, *, provider=DiagnosticStatus.AVAILABLE):
        from review_routing.contracts import ProbeSignals

        return ProbeSignals(
            billing_status=(
                DiagnosticStatus.BUDGET_BLOCKED if block is not None else None
            ),
            usage_status=DiagnosticStatus.AVAILABLE,
            provider_status=provider,
            permission_status=DiagnosticStatus.AVAILABLE,
            capability=capability,
            repository=REPOSITORY,
            principal=principal(),
            review_mode="manual",
            observed_at=NOW,
            verified_block=block,
        )

    def test_newer_or_equal_verified_block_prevents_use(self):
        capability = self.capability(NOW - timedelta(minutes=5))
        self.assertEqual(
            classify_usability(
                self.signals(capability, self.block(capability.observed_at))
            ),
            (False, DiagnosticStatus.BUDGET_BLOCKED),
        )

    def test_newer_completed_capability_overrides_old_block(self):
        capability = self.capability(NOW - timedelta(minutes=1))
        self.assertEqual(
            classify_usability(
                self.signals(capability, self.block(NOW - timedelta(minutes=2)))
            ),
            (True, DiagnosticStatus.AVAILABLE),
        )

    def test_technical_failure_overrides_verified_cache(self):
        capability = self.capability(NOW - timedelta(minutes=5))
        self.assertEqual(
            classify_usability(
                self.signals(
                    capability,
                    self.block(NOW - timedelta(minutes=1)),
                    provider=DiagnosticStatus.PROVIDER_UNAVAILABLE,
                )
            ),
            (False, DiagnosticStatus.PROVIDER_UNAVAILABLE),
        )


class StatusParserCorrectionTest(unittest.TestCase):
    """Beide erwarteten Statuskomponenten müssen genau einmal vorliegen."""

    class Response:
        def __init__(self, document):
            self._payload = json.dumps(document).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self):
            return self._payload

    def fetch(self, components):
        return GitHubStatus(
            opener=lambda request, timeout: self.Response({"components": components}),
            clock=FixedClock(),
        ).fetch(2.0)

    def test_exact_operational_components_are_available(self):
        snapshot = self.fetch(
            [
                {"name": "API Requests", "status": "operational"},
                {"name": "Copilot", "status": "operational"},
            ]
        )
        self.assertEqual(snapshot.status, DiagnosticStatus.AVAILABLE)

    def test_missing_component_is_incomplete(self):
        with self.assertRaisesRegex(RuntimeError, "incomplete"):
            self.fetch([{"name": "API Requests", "status": "operational"}])

    def test_duplicate_or_conflicting_component_is_incomplete(self):
        with self.assertRaisesRegex(RuntimeError, "incomplete"):
            self.fetch(
                [
                    {"name": "API Requests", "status": "operational"},
                    {"name": "Copilot", "status": "operational"},
                    {"name": "Copilot", "status": "degraded_performance"},
                ]
            )

    def test_degraded_or_incident_component_is_provider_unavailable(self):
        for status in ("degraded_performance", "major_outage"):
            with self.subTest(status=status):
                snapshot = self.fetch(
                    [
                        {"name": "API Requests", "status": "operational"},
                        {"name": "Copilot", "status": status},
                    ]
                )
                self.assertEqual(snapshot.status, DiagnosticStatus.PROVIDER_UNAVAILABLE)


if __name__ == "__main__":
    unittest.main()
