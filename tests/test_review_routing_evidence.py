#!/usr/bin/env python3
"""Revision-2-Regressionsvertrag für ausschließlich operator-gepinnte Evidenz."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
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
    CapabilityArtifactKind,
    CapabilityEvidence,
    CapabilityEvidenceReference,
    CapabilityEvidenceSource,
    CapabilityVerification,
    CommandResult,
    DiagnosticStatus,
    EvidenceTrust,
    EvidenceVerificationStatus,
    IncompleteResponseError,
    OperatorEvidencePin,
    OperatorEvidenceTrustPort,
    ProbeSignals,
    RuntimeTrustSource,
    VerifiedBlockEvidence,
)
from review_routing.policy import classify_usability


NOW = datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc)
REPOSITORY = "tomtastisch/agent-governance"
HEAD_SHA = "c" * 40


def canonical(document: dict[str, object]) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def digest(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def principal(*, review_mode: str = "manual", identifier: str = "tom") -> BillingPrincipal:
    return BillingPrincipal(
        kind="personal",
        identifier=identifier,
        review_mode=review_mode,
        requester="tom" if review_mode == "manual" else None,
        pull_request_author="author" if review_mode == "automatic" else None,
        source="github_api",
        observed_at=NOW - timedelta(minutes=10),
        expires_at=NOW + timedelta(minutes=30),
    )


def common_document(
    kind: CapabilityArtifactKind,
    *,
    review_mode: str = "manual",
    identity=None,
    observed_at: str = "2026-07-26T11:59:00Z",
    expires_at: str = "2026-07-26T12:10:00Z",
    schema_version: object = 1,
) -> dict[str, object]:
    return {
        "schema_version": schema_version,
        "kind": kind.value,
        "repository": REPOSITORY,
        "principal_identity": list(identity or principal(review_mode=review_mode).identity),
        "review_mode": review_mode,
        "observed_at": observed_at,
        "expires_at": expires_at,
        "source_reference": "operator_capability_20260726",
    }


def completed_review_document(**changes: object) -> dict[str, object]:
    document = {
        **common_document(CapabilityArtifactKind.COMPLETED_REVIEW_CONTEXT),
        "pull_request_number": 17,
        "review_id": 41,
        "review_commit_sha": HEAD_SHA,
    }
    document.update(changes)
    return document


def block_document(**changes: object) -> dict[str, object]:
    document = {
        "schema_version": 1,
        "kind": BlockEvidenceKind.BUDGET_BLOCKED.value,
        "repository": REPOSITORY,
        "principal_identity": list(principal().identity),
        "review_mode": "manual",
        "observed_at": "2026-07-26T11:59:00Z",
        "expires_at": "2026-07-26T12:10:00Z",
        "source_reference": "operator_block_20260726",
    }
    document.update(changes)
    return document


class FixedTrust(OperatorEvidenceTrustPort):
    def __init__(self, pins=None, error=None):
        self.pins = dict(pins or {})
        self.error = error

    def load(self, source_reference):
        if self.error is not None:
            raise self.error
        return self.pins.get(source_reference)


def pin_for(
    source_reference: str,
    content: bytes,
    source: RuntimeTrustSource = RuntimeTrustSource.PUBLISHER_APP,
) -> OperatorEvidencePin:
    return OperatorEvidencePin(
        source_reference=source_reference,
        expected_digest=digest(content),
        pin_source=source,
    )


def capability_reference(
    content: bytes,
    *,
    review_mode: str = "manual",
    identity=None,
) -> CapabilityEvidenceReference:
    return CapabilityEvidenceReference(
        schema_version=1,
        source=CapabilityEvidenceSource.OPERATOR_PINNED,
        repository=REPOSITORY,
        review_mode=review_mode,
        principal_identity=identity or principal(review_mode=review_mode).identity,
        source_reference="operator_capability_20260726",
        artifact=content,
    )


class NoCommand:
    def __init__(self):
        self.calls = []

    def run(self, argv, timeout_seconds):
        self.calls.append(argv)
        raise AssertionError("operator_setting must not call GitHub")


class ReviewCommand:
    def __init__(
        self,
        *,
        state: str = "COMMENTED",
        commit_id: str = HEAD_SHA,
        submitted_at: str = "2026-07-26T11:59:00Z",
        review_id: object = 41,
    ):
        self.state = state
        self.commit_id = commit_id
        self.submitted_at = submitted_at
        self.review_id = review_id
        self.calls = []

    def run(self, argv, timeout_seconds):
        self.calls.append(argv)
        payload = {
            "id": self.review_id,
            "user": {"login": "copilot-pull-request-reviewer[bot]"},
            "state": self.state,
            "commit_id": self.commit_id,
            "submitted_at": self.submitted_at,
            "body": "untrusted findings do not define availability",
        }
        return CommandResult(
            return_code=0,
            stdout=(
                b"HTTP/2 200\r\ncontent-type: application/json\r\n\r\n"
                + json.dumps(payload).encode("utf-8")
            ),
            stderr=b"",
        )


class OperatorCapabilityTrustTest(unittest.TestCase):
    def verifier(self, document, *, pinned=True, command=None, wrong_digest=False):
        content = canonical(document)
        pins = {}
        if pinned:
            expected = "sha256:" + "0" * 64 if wrong_digest else digest(content)
            pins["operator_capability_20260726"] = OperatorEvidencePin(
                source_reference="operator_capability_20260726",
                expected_digest=expected,
                pin_source=RuntimeTrustSource.PUBLISHER_APP,
            )
        return (
            CapabilityEvidenceVerifier(
                command or NoCommand(),
                FixedTrust(pins),
            ),
            content,
        )

    def test_only_operator_pinned_is_a_declared_capability_source(self):
        self.assertEqual(
            tuple(source.value for source in CapabilityEvidenceSource),
            ("operator_pinned",),
        )

    def test_unpinned_or_wrong_digest_operator_setting_is_unusable(self):
        document = common_document(CapabilityArtifactKind.OPERATOR_SETTING)
        for pinned, wrong_digest in ((False, False), (True, True)):
            with self.subTest(pinned=pinned, wrong_digest=wrong_digest):
                verifier, content = self.verifier(
                    document,
                    pinned=pinned,
                    wrong_digest=wrong_digest,
                )
                result = verifier.verify(
                    capability_reference(content),
                    REPOSITORY,
                    principal(),
                    "manual",
                    NOW,
                )
                self.assertEqual(result.status, EvidenceVerificationStatus.INVALID)
                self.assertEqual(result.trust, EvidenceTrust.UNVERIFIED)
                self.assertIsNone(result.evidence)

    def test_pinned_operator_setting_is_verified_with_sanitized_pin_source(self):
        verifier, content = self.verifier(
            common_document(CapabilityArtifactKind.OPERATOR_SETTING)
        )
        result = verifier.verify(
            capability_reference(content),
            REPOSITORY,
            principal(),
            "manual",
            NOW,
        )

        self.assertEqual(result.status, EvidenceVerificationStatus.VERIFIED)
        self.assertEqual(result.trust, EvidenceTrust.VERIFIED)
        self.assertEqual(result.artifact_kind, CapabilityArtifactKind.OPERATOR_SETTING)
        self.assertEqual(result.pin_source, RuntimeTrustSource.PUBLISHER_APP)
        self.assertEqual(result.artifact_digest, digest(content))

    def test_absent_invalid_and_expired_never_carry_verified_trust(self):
        absent = CapabilityEvidenceVerifier(NoCommand(), FixedTrust()).verify(
            None,
            REPOSITORY,
            principal(),
            "manual",
            NOW,
        )
        expired_document = common_document(
            CapabilityArtifactKind.OPERATOR_SETTING,
            observed_at="2026-07-26T11:30:00Z",
            expires_at="2026-07-26T11:59:00Z",
        )
        verifier, content = self.verifier(expired_document)
        expired = verifier.verify(
            capability_reference(content),
            REPOSITORY,
            principal(),
            "manual",
            NOW,
        )

        self.assertEqual(absent.status, EvidenceVerificationStatus.ABSENT)
        self.assertEqual(expired.status, EvidenceVerificationStatus.EXPIRED)
        self.assertIs(absent.trust, EvidenceTrust.UNVERIFIED)
        self.assertIs(expired.trust, EvidenceTrust.UNVERIFIED)
        with self.assertRaises(ValueError):
            CapabilityVerification(
                status=EvidenceVerificationStatus.INVALID,
                trust=EvidenceTrust.VERIFIED,
                source=CapabilityEvidenceSource.OPERATOR_PINNED,
                artifact_kind=None,
                source_reference="operator_capability_20260726",
                artifact_digest=None,
                pin_source=None,
                evidence=None,
            )

    def test_boolean_schema_version_is_invalid_not_version_one(self):
        verifier, content = self.verifier(
            common_document(
                CapabilityArtifactKind.OPERATOR_SETTING,
                schema_version=True,
            )
        )
        result = verifier.verify(
            capability_reference(content),
            REPOSITORY,
            principal(),
            "manual",
            NOW,
        )
        self.assertEqual(result.status, EvidenceVerificationStatus.INVALID)


class CompletedReviewContextTest(unittest.TestCase):
    def verify(self, document=None, *, command=None, current_principal=None, mode="manual"):
        content = canonical(document or completed_review_document())
        trust = FixedTrust(
            {
                "operator_capability_20260726": pin_for(
                    "operator_capability_20260726",
                    content,
                    RuntimeTrustSource.INSTALLED_CONFIG,
                )
            }
        )
        verifier = CapabilityEvidenceVerifier(command or ReviewCommand(), trust)
        selected_principal = current_principal or principal(review_mode=mode)
        return verifier.verify(
            capability_reference(
                content,
                review_mode=mode,
                identity=selected_principal.identity,
            ),
            REPOSITORY,
            selected_principal,
            mode,
            NOW,
        )

    def test_pinned_context_revalidates_completed_review_before_capability(self):
        command = ReviewCommand()
        result = self.verify(command=command)

        self.assertEqual(result.status, EvidenceVerificationStatus.VERIFIED)
        self.assertEqual(
            result.artifact_kind,
            CapabilityArtifactKind.COMPLETED_REVIEW_CONTEXT,
        )
        self.assertEqual(result.evidence.review_commit_sha, HEAD_SHA)
        self.assertEqual(result.pin_source, RuntimeTrustSource.INSTALLED_CONFIG)
        self.assertEqual(
            command.calls[0][-1],
            f"/repos/{REPOSITORY}/pulls/17/reviews/41",
        )

    def test_same_api_review_cannot_cross_principal_or_review_mode(self):
        content = canonical(completed_review_document())
        command = ReviewCommand()
        trust = FixedTrust(
            {
                "operator_capability_20260726": pin_for(
                    "operator_capability_20260726",
                    content,
                )
            }
        )
        verifier = CapabilityEvidenceVerifier(command, trust)
        cases = (
            (principal(identifier="other"), "manual"),
            (principal(review_mode="automatic"), "automatic"),
        )
        for foreign_principal, mode in cases:
            with self.subTest(principal=foreign_principal.identity, mode=mode):
                result = verifier.verify(
                    capability_reference(content),
                    REPOSITORY,
                    foreign_principal,
                    mode,
                    NOW,
                )
                self.assertEqual(result.status, EvidenceVerificationStatus.INVALID)
        self.assertEqual(command.calls, [])

    def test_pending_wrong_commit_or_wrong_time_is_invalid(self):
        cases = (
            ReviewCommand(state="PENDING"),
            ReviewCommand(commit_id="d" * 40),
            ReviewCommand(submitted_at="2026-07-26T11:58:00Z"),
        )
        for command in cases:
            with self.subTest(command=command.__dict__):
                result = self.verify(command=command)
                self.assertEqual(result.status, EvidenceVerificationStatus.INVALID)
                self.assertIsNone(result.evidence)

    def test_boolean_review_or_pr_id_is_invalid_without_api_call(self):
        for field_name in ("review_id", "pull_request_number"):
            with self.subTest(field_name=field_name):
                command = ReviewCommand()
                result = self.verify(
                    completed_review_document(**{field_name: True}),
                    command=command,
                )
                self.assertEqual(result.status, EvidenceVerificationStatus.INVALID)
                self.assertEqual(command.calls, [])

    def test_api_review_id_requires_the_exact_integer_type(self):
        for api_review_id in (True, False, 41.0, "41", None, [], {}):
            with self.subTest(api_review_id=api_review_id):
                document = completed_review_document()
                content = canonical(document)
                command = ReviewCommand(review_id=api_review_id)
                verifier = CapabilityEvidenceVerifier(
                    command,
                    FixedTrust(
                        {
                            "operator_capability_20260726": pin_for(
                                "operator_capability_20260726",
                                content,
                            )
                        }
                    ),
                )

                result = verifier.verify(
                    capability_reference(content),
                    REPOSITORY,
                    principal(),
                    "manual",
                    NOW,
                )

                self.assertEqual(result.status, EvidenceVerificationStatus.INVALID)
                self.assertEqual(result.trust, EvidenceTrust.UNVERIFIED)
                self.assertIsNone(result.evidence)


class OperatorBlockTrustTest(unittest.TestCase):
    def test_only_operator_pinned_is_a_declared_block_source(self):
        self.assertEqual(
            tuple(source.value for source in BlockEvidenceSource),
            ("operator_pinned",),
        )

    def test_pinned_block_is_verified_and_boolean_schema_is_invalid(self):
        for schema_version, expected in (
            (1, EvidenceVerificationStatus.VERIFIED),
            (True, EvidenceVerificationStatus.INVALID),
        ):
            with self.subTest(schema_version=schema_version):
                content = canonical(block_document(schema_version=schema_version))
                verifier = BlockEvidenceVerifier(
                    FixedTrust(
                        {
                            "operator_block_20260726": pin_for(
                                "operator_block_20260726",
                                content,
                            )
                        }
                    )
                )
                reference = BlockEvidenceReference(
                    schema_version=1,
                    source=BlockEvidenceSource.OPERATOR_PINNED,
                    repository=REPOSITORY,
                    review_mode="manual",
                    principal_identity=principal().identity,
                    source_reference="operator_block_20260726",
                    artifact=content,
                )
                result = verifier.verify(
                    reference,
                    REPOSITORY,
                    principal(),
                    "manual",
                    NOW,
                )
                self.assertEqual(result.status, expected)
                if expected is EvidenceVerificationStatus.VERIFIED:
                    self.assertEqual(
                        result.pin_source,
                        RuntimeTrustSource.PUBLISHER_APP,
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
            artifact_kind=CapabilityArtifactKind.COMPLETED_REVIEW_CONTEXT,
            source_reference="verified_capability",
            artifact_digest="sha256:" + "a" * 64,
            pin_source=RuntimeTrustSource.PUBLISHER_APP,
            pull_request_number=17,
            review_id=41,
            review_commit_sha=HEAD_SHA,
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
            pin_source=RuntimeTrustSource.INSTALLED_CONFIG,
        )

    def signals(self, capability, block, *, provider=DiagnosticStatus.AVAILABLE):
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

    def test_missing_block_with_valid_capability_is_usable(self):
        self.assertEqual(
            classify_usability(
                self.signals(self.capability(NOW - timedelta(minutes=1)), None)
            ),
            (True, DiagnosticStatus.AVAILABLE),
        )

    def test_missing_block_without_capability_is_unknown(self):
        self.assertEqual(
            classify_usability(self.signals(None, None)),
            (False, DiagnosticStatus.UNKNOWN),
        )

    def test_newer_or_equal_block_wins_and_newer_review_overrides_old_block(self):
        old_capability = self.capability(NOW - timedelta(minutes=5))
        self.assertEqual(
            classify_usability(
                self.signals(old_capability, self.block(old_capability.observed_at))
            ),
            (False, DiagnosticStatus.BUDGET_BLOCKED),
        )
        new_capability = self.capability(NOW - timedelta(minutes=1))
        self.assertEqual(
            classify_usability(
                self.signals(new_capability, self.block(NOW - timedelta(minutes=2)))
            ),
            (True, DiagnosticStatus.AVAILABLE),
        )

    def test_technical_failure_overrides_verified_cache(self):
        self.assertEqual(
            classify_usability(
                self.signals(
                    self.capability(NOW - timedelta(minutes=5)),
                    self.block(NOW - timedelta(minutes=1)),
                    provider=DiagnosticStatus.PROVIDER_UNAVAILABLE,
                )
            ),
            (False, DiagnosticStatus.PROVIDER_UNAVAILABLE),
        )


class StatusParserCorrectionTest(unittest.TestCase):
    class Response:
        def __init__(self, document):
            self._payload = json.dumps(document).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self):
            return self._payload

    class Clock:
        def now(self):
            return NOW

    def fetch(self, components):
        return GitHubStatus(
            opener=lambda request, timeout: self.Response({"components": components}),
            clock=self.Clock(),
        ).fetch(2.0)

    def test_exact_operational_components_are_available(self):
        snapshot = self.fetch(
            [
                {"name": "API Requests", "status": "operational"},
                {"name": "Copilot", "status": "operational"},
            ]
        )
        self.assertEqual(snapshot.status, DiagnosticStatus.AVAILABLE)

    def test_missing_or_duplicate_component_is_incomplete(self):
        cases = (
            [{"name": "API Requests", "status": "operational"}],
            [
                {"name": "API Requests", "status": "operational"},
                {"name": "Copilot", "status": "operational"},
                {"name": "Copilot", "status": "degraded_performance"},
            ],
        )
        for components in cases:
            with self.subTest(components=components):
                with self.assertRaises(IncompleteResponseError):
                    self.fetch(components)

    def test_degraded_or_incident_component_is_provider_unavailable(self):
        for status in ("degraded_performance", "major_outage"):
            with self.subTest(status=status):
                snapshot = self.fetch(
                    [
                        {"name": "API Requests", "status": "operational"},
                        {"name": "Copilot", "status": status},
                    ]
                )
                self.assertEqual(
                    snapshot.status,
                    DiagnosticStatus.PROVIDER_UNAVAILABLE,
                )


if __name__ == "__main__":
    unittest.main()
