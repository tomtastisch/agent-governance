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


class ExactHeadGateTest(unittest.TestCase):
    """Gate-Evidenz wird ausschließlich aus frischen Exact-Head-Quellen abgeleitet."""

    def setUp(self):
        from pathlib import Path

        from review_routing.adapters.toml_config import TomlConfig
        from review_routing.contracts import (
            DetectionMode,
            DiffFile,
            DiffMode,
            DiffSnapshot,
            DocumentTrust,
            PolicyDocument,
            PullRequestState,
            PullRequestStateSource,
            Reviewer,
            ReviewerAvailabilityEvidence,
            ReviewerAvailabilitySnapshot,
            ReviewerAvailabilitySource,
            ReviewerAvailabilityStatus,
            ReviewPurpose,
            RuntimeProvenance,
            RuntimeTrust,
        )
        from review_routing.registry import RuntimeRegistry
        from tests import test_review_routing_cli as cli_fixtures

        self.base = "a" * 40
        self.head = "b" * 40
        self.merge_base = "c" * 40
        self.repository = REPOSITORY
        self.pr = 5
        self.request = __import__(
            "review_routing.contracts",
            fromlist=["ProbeRequest"],
        ).ProbeRequest(
            repository=self.repository,
            review_mode="manual",
            manual_requester="tom",
            pull_request_number=self.pr,
            capability_reference=CapabilityEvidenceReference(
                schema_version=1,
                source=CapabilityEvidenceSource.OPERATOR_PINNED,
                repository=self.repository,
                review_mode="manual",
                principal_identity=("personal", "tom", "manual", "tom", None),
                source_reference="verified_capability",
                artifact=b"{}",
            ),
        )
        previous_now = cli_fixtures.NOW
        cli_fixtures.NOW = NOW
        try:
            self.probe = cli_fixtures.probe_report(usable=True, request=self.request)
        finally:
            cli_fixtures.NOW = previous_now
        self.state = PullRequestState(
            repository=self.repository,
            pull_request_number=self.pr,
            base_ref="main",
            api_base_sha=self.base,
            head_sha=self.head,
            author="author",
            observed_at=NOW,
            source=PullRequestStateSource.GITHUB_API,
        )
        self.diff = DiffSnapshot(
            schema_version=1,
            repository=self.repository,
            api_base_sha=self.base,
            merge_base_sha=self.merge_base,
            head_sha=self.head,
            diff_mode=DiffMode.MERGE_BASE_TO_HEAD,
            rename_detection=DetectionMode.DISABLED,
            copy_detection=DetectionMode.DISABLED,
            files=(
                DiffFile(
                    path="src/application.py",
                    status=__import__(
                        "review_routing.contracts",
                        fromlist=["FileStatus"],
                    ).FileStatus.MODIFIED,
                    additions=1,
                    deletions=0,
                    binary=False,
                ),
            ),
        )
        root = Path(__file__).resolve().parents[1]
        self.config = TomlConfig().parse_routing(
            PolicyDocument(
                content=(root / "core/review-routing.toml").read_text(encoding="utf-8"),
                trust=DocumentTrust.COMMIT_OBJECT,
                source=f"{self.base}:core/review-routing.toml",
            )
        )
        self.registry = RuntimeRegistry.bootstrap(None)
        self.runtime = RuntimeProvenance(
            digest=self.registry.runtime_provenance.digest,
            trust=RuntimeTrust.INSTALLED,
        )
        self.assessment = self.registry.resolve(
            __import__(
                "review_routing.contracts",
                fromlist=["RiskClassifierPort"],
            ).RiskClassifierPort
        ).assess(self.diff, self.config)
        self.availability = ReviewerAvailabilitySnapshot(
            evidence=tuple(
                ReviewerAvailabilityEvidence(
                    reviewer=reviewer,
                    status=ReviewerAvailabilityStatus.AVAILABLE,
                    repository=self.repository,
                    pull_request_number=self.pr,
                    head_sha=self.head,
                    purpose=ReviewPurpose.FINAL_EXACT_HEAD,
                    observed_at=NOW - timedelta(minutes=1),
                    expires_at=NOW + timedelta(minutes=5),
                    source=ReviewerAvailabilitySource.HARNESS_RUNTIME,
                    reason="harness_role_context",
                )
                for reviewer in (Reviewer.QA, Reviewer.SEC)
            )
        )

    def source(self, *, kind="github_api", repository=None, head=None, valid_until=None):
        from review_routing.contracts import BoundEvidenceSource, BoundEvidenceSourceKind

        return BoundEvidenceSource(
            kind=BoundEvidenceSourceKind(kind),
            source_id="github_graphql",
            repository=repository or self.repository,
            pull_request_number=self.pr,
            head_sha=head or self.head,
            observed_at=NOW - timedelta(seconds=30),
            valid_until=valid_until or NOW + timedelta(minutes=5),
        )

    def plan(self, **changes):
        from review_routing.contracts import (
            CopilotReviewMode,
            PreliminaryRoutePlan,
            PullRequestStateSource,
            Reviewer,
            ReviewPurpose,
            ReviewRoute,
        )

        values = {
            "schema_version": 1,
            "repository": self.repository,
            "pull_request_number": self.pr,
            "purpose": ReviewPurpose.FINAL_EXACT_HEAD,
            "base_ref": "main",
            "base_sha": self.base,
            "merge_base_sha": self.merge_base,
            "head_sha": self.head,
            "pr_state_source": PullRequestStateSource.GITHUB_API,
            "risk": self.assessment,
            "policy_source_ref": self.base,
            "policy_source_path": "core/review-routing.toml",
            "policy_digest": self.config.policy_digest,
            "runtime_digest": self.runtime.digest,
            "runtime_trust": self.runtime.trust,
            "diff_digest": self.diff.diff_digest,
            "copilot_usable": False,
            "copilot_coverage_complete": None,
            "copilot_review_mode": CopilotReviewMode.UNKNOWN,
            "route": ReviewRoute.QA,
            "required_reviewers": frozenset({Reviewer.SEC}),
            "gate_status": "forged_success",
            "gate_eligible": True,
        }
        values.update(changes)
        return PreliminaryRoutePlan(**values)

    def snapshot(self, **changes):
        from review_routing.contracts import (
            CheckConclusion,
            CheckRecord,
            CopilotReviewMode,
            CoverageStatus,
            FileCoverage,
            FileStatus,
            GateSnapshot,
            Reviewer,
            ReviewRecord,
            ReviewState,
        )

        source = self.source()
        values = {
            "schema_version": 1,
            "repository": self.repository,
            "pull_request_number": self.pr,
            "base_sha": self.base,
            "head_sha": self.head,
            "check_runs": tuple(
                CheckRecord(
                    name=required.name,
                    source_app_slug=required.source_app_slug,
                    head_sha=self.head,
                    conclusion=CheckConclusion.SUCCESS,
                    completed_at=NOW - timedelta(minutes=1),
                    source=source,
                )
                for required in self.config.required_checks
            ),
            "review_requests": (),
            "reviews": (
                ReviewRecord(
                    reviewer=Reviewer.COPILOT,
                    event_id="copilot_review_1",
                    actor_login="copilot-pull-request-reviewer[bot]",
                    app_slug="copilot-pull-request-reviewer",
                    state=ReviewState.COMMENTED,
                    commit_sha=self.head,
                    submitted_at=NOW - timedelta(minutes=1),
                    findings_count=0,
                    source=source,
                ),
            ),
            "review_file_coverage": (
                FileCoverage(
                    path="src/application.py",
                    status=FileStatus.MODIFIED,
                    coverage=CoverageStatus.REVIEWED,
                    reviewer=Reviewer.COPILOT,
                    coverage_source=source,
                ),
            ),
            "copilot_review_mode": CopilotReviewMode.FULL,
            "review_mode_source": source,
            "threads": (),
            "observed_at": NOW - timedelta(seconds=20),
            "valid_until": NOW + timedelta(minutes=5),
        }
        values.update(changes)
        return GateSnapshot(**values)

    def context(self, plan=None, **changes):
        from review_routing.contracts import GateEvaluationContext

        values = {
            "preliminary_plan": plan or self.plan(),
            "current_pr_state": self.state,
            "probe_request": self.request,
            "fresh_probe": self.probe,
            "reviewer_availability": self.availability,
            "evaluated_at": NOW,
        }
        values.update(changes)
        return GateEvaluationContext(**values)

    def prior_gate_evidence(self, **changes):
        from dataclasses import replace
        from review_routing.contracts import (
            PriorGateEvidence,
            PublicationReceipt,
            ReviewPurpose,
        )

        current = self.validate()
        prior_result = replace(
            current,
            purpose=ReviewPurpose.FINAL_EXACT_HEAD,
            head_sha="d" * 40,
            observed_at=NOW - timedelta(minutes=10),
        )
        receipt = PublicationReceipt(
            repository=self.repository,
            pull_request_number=self.pr,
            head_sha=prior_result.head_sha,
            check_name=prior_result.check_name,
            publisher_app_slug=self.config.publisher.expected_app_slug,
            publication_id="prior_check_1",
            gate_result_digest=prior_result.gate_result_digest,
            idempotency_key=prior_result.idempotency_key,
            head_revalidated_at=NOW - timedelta(minutes=9),
            published_at=NOW - timedelta(minutes=9) + timedelta(seconds=10),
        )
        values = {
            "schema_version": 1,
            "repository": self.repository,
            "pull_request_number": self.pr,
            "current_head_sha": self.head,
            "prior_gate_result": prior_result,
            "publication_receipt": receipt,
            "source_app_slug": self.config.publisher.expected_app_slug,
            "source_reference": receipt.publication_id,
            "observed_at": NOW - timedelta(minutes=8),
            "valid_until": NOW + timedelta(minutes=5),
        }
        values.update(changes)
        return PriorGateEvidence(**values)

    def correction_context(self, prior_gate_evidence=None):
        from dataclasses import replace
        from review_routing.contracts import (
            ReviewerAvailabilitySnapshot,
            ReviewPurpose,
        )

        availability = ReviewerAvailabilitySnapshot(
            evidence=tuple(
                replace(item, purpose=ReviewPurpose.CORRECTION)
                for item in self.availability.evidence
            )
        )
        return self.context(
            self.plan(purpose=ReviewPurpose.CORRECTION),
            reviewer_availability=availability,
            prior_gate_evidence=prior_gate_evidence,
        )

    def validate(self, *, context=None, snapshot=None, diff=None, config=None):
        from review_routing.contracts import EvidenceValidatorPort, RiskClassifierPort, RoutingPolicyPort

        return self.registry.resolve(EvidenceValidatorPort).validate(
            context or self.context(),
            snapshot or self.snapshot(),
            self.runtime,
            config or self.config,
            diff or self.diff,
            self.registry.resolve(RiskClassifierPort),
            self.registry.resolve(RoutingPolicyPort),
        )

    def test_valid_commented_copilot_exact_head_is_success_without_approved_claim(self):
        result = self.validate()

        self.assertEqual(result.conclusion, "success")
        self.assertEqual(result.check_name, "agent-governance/review-gate")
        self.assertEqual(
            {reviewer.value for reviewer in result.validated_reviewers},
            {"copilot"},
        )
        self.assertNotIn("APPROVED", repr(result))

    def test_preliminary_route_usability_reviewers_and_gate_claims_are_not_authority(self):
        result = self.validate(
            context=self.context(
                self.plan(
                    copilot_usable=False,
                    route=__import__(
                        "review_routing.contracts",
                        fromlist=["ReviewRoute"],
                    ).ReviewRoute.BLOCKER,
                    gate_eligible=True,
                )
            )
        )

        self.assertEqual(result.conclusion, "success")
        self.assertEqual(
            {reviewer.value for reviewer in result.required_reviewers},
            {"copilot"},
        )

    def test_wrong_bot_old_head_open_thread_and_newer_pending_request_fail(self):
        from dataclasses import replace
        from review_routing.contracts import ReviewRecord, Reviewer, ReviewState, ThreadRecord

        base = self.snapshot()
        wrong = replace(base.reviews[0], actor_login="not-copilot")
        pending = ReviewRecord(
            reviewer=Reviewer.COPILOT,
            event_id="copilot_request_2",
            actor_login="copilot-pull-request-reviewer[bot]",
            app_slug="copilot-pull-request-reviewer",
            state=ReviewState.PENDING,
            commit_sha=self.head,
            submitted_at=NOW - timedelta(seconds=45),
            findings_count=0,
            source=self.source(),
        )
        thread = ThreadRecord(
            thread_id="thread_1",
            reviewer=None,
            head_sha=self.head,
            unresolved=True,
            source=self.source(),
        )

        result = self.validate(
            snapshot=replace(
                base,
                reviews=(wrong,),
                review_requests=(pending,),
                threads=(thread,),
            )
        )

        self.assertEqual(result.conclusion, "failure")
        self.assertIn("missing_reviewer:copilot", result.reasons)
        self.assertIn("unresolved_review_threads", result.reasons)

    def test_wrong_app_check_and_stale_coverage_sources_fail_closed(self):
        from dataclasses import replace

        base = self.snapshot()
        wrong_check = replace(base.check_runs[0], source_app_slug="spoofed-app")
        stale_source = self.source(valid_until=NOW)
        stale_coverage = replace(
            base.review_file_coverage[0],
            coverage_source=stale_source,
        )

        result = self.validate(
            snapshot=replace(
                base,
                check_runs=(wrong_check,),
                review_file_coverage=(stale_coverage,),
            )
        )

        self.assertEqual(result.conclusion, "failure")
        self.assertTrue(any(reason.startswith("missing_check:") for reason in result.reasons))
        self.assertIn("file_not_covered:src/application.py", result.reasons)

    def test_foreign_probe_and_coverage_source_cannot_authorize_the_gate(self):
        from dataclasses import replace

        foreign_probe = replace(
            self.probe,
            request_digest="sha256:" + "0" * 64,
        )
        snapshot = self.snapshot()
        foreign_source = replace(
            snapshot.review_file_coverage[0].coverage_source,
            repository="other/repository",
        )
        result = self.validate(
            context=self.context(fresh_probe=foreign_probe),
            snapshot=replace(
                snapshot,
                review_file_coverage=(
                    replace(
                        snapshot.review_file_coverage[0],
                        coverage_source=foreign_source,
                    ),
                ),
            ),
        )

        self.assertIn("fresh_probe_invalid", result.reasons)
        self.assertIn("file_not_covered:src/application.py", result.reasons)

    def test_policy_diff_risk_and_pr_state_provenance_mismatches_fail(self):
        from dataclasses import replace

        result = self.validate(
            context=self.context(self.plan(policy_digest="sha256:" + "0" * 64))
        )
        self.assertIn("policy_provenance_mismatch", result.reasons)

        changed = replace(
            self.diff,
            files=(
                replace(self.diff.files[0], additions=900),
            ),
        )
        result = self.validate(diff=changed)
        self.assertIn("diff_provenance_mismatch", result.reasons)
        self.assertIn("risk_assessment_mismatch", result.reasons)

        empty_checks = replace(self.config, required_checks=())
        result = self.validate(
            context=self.context(
                self.plan(policy_digest=empty_checks.policy_digest)
            ),
            config=empty_checks,
        )
        self.assertIn("required_checks_empty", result.reasons)

    def test_evidence_digest_and_idempotency_key_are_deterministic(self):
        first = self.validate()
        second = self.validate(snapshot=self.snapshot())

        self.assertEqual(first.evidence_digest, second.evidence_digest)
        self.assertEqual(first.idempotency_key, second.idempotency_key)

    def test_copilot_never_accepts_approved_pending_error_or_old_head(self):
        from dataclasses import replace
        from review_routing.contracts import ReviewState

        for state in (
            ReviewState.APPROVED,
            ReviewState.PENDING,
            ReviewState.ERROR,
            ReviewState.CHANGES_REQUESTED,
        ):
            with self.subTest(state=state):
                snapshot = self.snapshot()
                result = self.validate(
                    snapshot=replace(
                        snapshot,
                        reviews=(replace(snapshot.reviews[0], state=state),),
                    )
                )
                self.assertIn("missing_reviewer:copilot", result.reasons)
        snapshot = self.snapshot()
        result = self.validate(
            snapshot=replace(
                snapshot,
                reviews=(replace(snapshot.reviews[0], commit_sha="d" * 40),),
            )
        )
        self.assertIn("missing_reviewer:copilot", result.reasons)

    def test_all_non_successful_or_missing_required_checks_fail(self):
        from dataclasses import replace
        from review_routing.contracts import CheckConclusion

        for conclusion in (
            CheckConclusion.FAILURE,
            CheckConclusion.SKIPPED,
            CheckConclusion.CANCELLED,
            CheckConclusion.PENDING,
        ):
            with self.subTest(conclusion=conclusion):
                snapshot = self.snapshot()
                result = self.validate(
                    snapshot=replace(
                        snapshot,
                        check_runs=(
                            replace(snapshot.check_runs[0], conclusion=conclusion),
                        ),
                    )
                )
                self.assertTrue(
                    any(
                        reason.startswith("check_not_successful:")
                        for reason in result.reasons
                    )
                )
        result = self.validate(
            snapshot=replace(self.snapshot(), check_runs=())
        )
        self.assertTrue(any(reason.startswith("missing_check:") for reason in result.reasons))

    def test_degraded_or_excluded_copilot_coverage_requires_exact_head_qa(self):
        from dataclasses import replace
        from review_routing.contracts import (
            BoundEvidenceSourceKind,
            CopilotReviewMode,
            CoverageStatus,
            FileCoverage,
            Reviewer,
            ReviewRecord,
            ReviewState,
        )

        snapshot = self.snapshot()
        qa_source = replace(
            self.source(),
            kind=BoundEvidenceSourceKind.HARNESS_RUNTIME,
            source_id="qa_exact_head",
        )
        qa_review = ReviewRecord(
            reviewer=Reviewer.QA,
            event_id="qa_review_1",
            actor_login="qa-agent",
            app_slug="codex-qa-agent",
            state=ReviewState.APPROVED,
            commit_sha=self.head,
            submitted_at=NOW - timedelta(minutes=1),
            findings_count=0,
            source=qa_source,
        )
        qa_coverage = FileCoverage(
            path=snapshot.review_file_coverage[0].path,
            status=snapshot.review_file_coverage[0].status,
            coverage=CoverageStatus.REVIEWED,
            reviewer=Reviewer.QA,
            coverage_source=qa_source,
        )
        result = self.validate(
            snapshot=replace(
                snapshot,
                reviews=(*snapshot.reviews, qa_review),
                review_file_coverage=(
                    replace(
                        snapshot.review_file_coverage[0],
                        coverage=CoverageStatus.EXCLUDED,
                    ),
                    qa_coverage,
                ),
                copilot_review_mode=CopilotReviewMode.DEGRADED,
            )
        )

        self.assertEqual(result.conclusion, "success")
        self.assertEqual(
            {reviewer.value for reviewer in result.required_reviewers},
            {"copilot", "qa"},
        )

    def test_missing_or_stale_availability_is_never_inferred(self):
        from dataclasses import replace
        from review_routing.contracts import ReviewerAvailabilitySnapshot

        snapshot = self.snapshot()
        qa_source = replace(
            self.source(),
            kind=__import__(
                "review_routing.contracts",
                fromlist=["BoundEvidenceSourceKind"],
            ).BoundEvidenceSourceKind.HARNESS_RUNTIME,
            source_id="qa_exact_head",
        )
        qa_review = replace(
            snapshot.reviews[0],
            reviewer=__import__(
                "review_routing.contracts",
                fromlist=["Reviewer"],
            ).Reviewer.QA,
            actor_login="qa-agent",
            app_slug="codex-qa-agent",
            state=__import__(
                "review_routing.contracts",
                fromlist=["ReviewState"],
            ).ReviewState.APPROVED,
            source=qa_source,
        )
        qa_coverage = replace(
            snapshot.review_file_coverage[0],
            reviewer=__import__(
                "review_routing.contracts",
                fromlist=["Reviewer"],
            ).Reviewer.QA,
            coverage_source=qa_source,
        )
        fallback_snapshot = replace(
            snapshot,
            reviews=(qa_review,),
            review_file_coverage=(qa_coverage,),
            copilot_review_mode=__import__(
                "review_routing.contracts",
                fromlist=["CopilotReviewMode"],
            ).CopilotReviewMode.UNKNOWN,
            review_mode_source=replace(
                snapshot.review_mode_source,
                kind=__import__(
                    "review_routing.contracts",
                    fromlist=["BoundEvidenceSourceKind"],
                ).BoundEvidenceSourceKind.UNAVAILABLE,
            ),
        )
        result = self.validate(
            context=self.context(
                reviewer_availability=ReviewerAvailabilitySnapshot()
            ),
            snapshot=fallback_snapshot,
        )
        self.assertIn("required_reviewer_unavailable", result.reasons)

        stale = replace(
            self.availability.evidence[0],
            observed_at=NOW - timedelta(minutes=10),
            expires_at=NOW - timedelta(minutes=1),
        )
        result = self.validate(
            context=self.context(
                reviewer_availability=ReviewerAvailabilitySnapshot(
                    evidence=(stale, self.availability.evidence[1])
                )
            ),
            snapshot=fallback_snapshot,
        )
        self.assertIn("reviewer_availability_invalid", result.reasons)

    def test_extra_coverage_future_evidence_and_development_runtime_fail(self):
        from dataclasses import replace
        from review_routing.contracts import FileCoverage, FileStatus, RuntimeTrust

        snapshot = self.snapshot()
        extra = FileCoverage(
            path="not-in-diff.py",
            status=FileStatus.MODIFIED,
            coverage=snapshot.review_file_coverage[0].coverage,
            reviewer=snapshot.review_file_coverage[0].reviewer,
            coverage_source=snapshot.review_file_coverage[0].coverage_source,
        )
        result = self.validate(
            snapshot=replace(
                snapshot,
                review_file_coverage=(*snapshot.review_file_coverage, extra),
                reviews=(
                    replace(
                        snapshot.reviews[0],
                        submitted_at=NOW + timedelta(seconds=1),
                    ),
                ),
            )
        )
        self.assertIn("evidence_diff_mismatch", result.reasons)
        self.assertIn("review_event_source_invalid", result.reasons)

        installed = self.runtime
        self.runtime = replace(self.runtime, trust=RuntimeTrust.DEVELOPMENT)
        try:
            result = self.validate(
                context=self.context(
                    self.plan(runtime_trust=RuntimeTrust.DEVELOPMENT)
                )
            )
        finally:
            self.runtime = installed
        self.assertIn("runtime_not_installed", result.reasons)

    def test_security_diff_cannot_remove_qa_or_sec_from_final_route(self):
        from dataclasses import replace
        from review_routing.contracts import (
            BoundEvidenceSourceKind,
            DiffFile,
            FileCoverage,
            Reviewer,
            ReviewRecord,
            ReviewState,
            RiskClassifierPort,
        )

        security_diff = replace(
            self.diff,
            files=(
                DiffFile(
                    path="src/security/auth/guard.py",
                    status=self.diff.files[0].status,
                    additions=1,
                    deletions=0,
                    binary=False,
                ),
            ),
        )
        assessment = self.registry.resolve(RiskClassifierPort).assess(
            security_diff,
            self.config,
        )
        plan = self.plan(
            risk=assessment,
            diff_digest=security_diff.diff_digest,
        )
        snapshot = self.snapshot()
        copilot_coverage = replace(
            snapshot.review_file_coverage[0],
            path="src/security/auth/guard.py",
        )
        harness_source = replace(
            self.source(),
            kind=BoundEvidenceSourceKind.HARNESS_RUNTIME,
            source_id="independent_roles",
        )
        qa_review = ReviewRecord(
            reviewer=Reviewer.QA,
            event_id="qa_review_1",
            actor_login="qa-agent",
            app_slug="codex-qa-agent",
            state=ReviewState.APPROVED,
            commit_sha=self.head,
            submitted_at=NOW - timedelta(minutes=1),
            findings_count=0,
            source=harness_source,
        )
        qa_coverage = FileCoverage(
            path="src/security/auth/guard.py",
            status=security_diff.files[0].status,
            coverage=copilot_coverage.coverage,
            reviewer=Reviewer.QA,
            coverage_source=harness_source,
        )
        result = self.validate(
            context=self.context(plan),
            diff=security_diff,
            snapshot=replace(
                snapshot,
                reviews=(*snapshot.reviews, qa_review),
                review_file_coverage=(copilot_coverage, qa_coverage),
            ),
        )

        self.assertEqual(
            {reviewer.value for reviewer in result.required_reviewers},
            {"copilot", "qa", "sec"},
        )
        self.assertIn("missing_reviewer:sec", result.reasons)

    def security_gate_inputs(self):
        from dataclasses import replace
        from review_routing.contracts import (
            BoundEvidenceSourceKind,
            DiffFile,
            FileCoverage,
            Reviewer,
            ReviewRecord,
            ReviewState,
            RiskClassifierPort,
        )

        security_diff = replace(
            self.diff,
            files=(
                DiffFile(
                    path="src/security/auth/guard.py",
                    status=self.diff.files[0].status,
                    additions=1,
                    deletions=0,
                    binary=False,
                ),
            ),
        )
        assessment = self.registry.resolve(RiskClassifierPort).assess(
            security_diff,
            self.config,
        )
        plan = self.plan(risk=assessment, diff_digest=security_diff.diff_digest)
        snapshot = self.snapshot()
        copilot_review = replace(snapshot.reviews[0], event_id="copilot_positive")
        copilot_coverage = replace(
            snapshot.review_file_coverage[0],
            path="src/security/auth/guard.py",
        )
        harness_source = replace(
            self.source(),
            kind=BoundEvidenceSourceKind.HARNESS_RUNTIME,
            source_id="independent_roles",
        )
        role_reviews = tuple(
            ReviewRecord(
                reviewer=reviewer,
                event_id=f"{reviewer.value}_positive",
                actor_login=f"{reviewer.value}-agent",
                app_slug=f"codex-{reviewer.value}-agent",
                state=ReviewState.APPROVED,
                commit_sha=self.head,
                submitted_at=NOW - timedelta(minutes=1),
                findings_count=0,
                source=harness_source,
            )
            for reviewer in (Reviewer.QA, Reviewer.SEC)
        )
        qa_coverage = FileCoverage(
            path="src/security/auth/guard.py",
            status=security_diff.files[0].status,
            coverage=copilot_coverage.coverage,
            reviewer=Reviewer.QA,
            coverage_source=harness_source,
        )
        return (
            security_diff,
            plan,
            replace(
                snapshot,
                reviews=(copilot_review, *role_reviews),
                review_file_coverage=(copilot_coverage, qa_coverage),
            ),
        )

    def test_latest_event_wins_for_copilot_qa_and_sec_and_ties_fail_closed(self):
        from dataclasses import replace
        from review_routing.contracts import Reviewer, ReviewRecord, ReviewState

        security_diff, plan, snapshot = self.security_gate_inputs()
        for reviewer in (Reviewer.COPILOT, Reviewer.QA, Reviewer.SEC):
            source = next(
                review.source for review in snapshot.reviews if review.reviewer is reviewer
            )
            for state in (
                ReviewState.PENDING,
                ReviewState.ERROR,
                ReviewState.CHANGES_REQUESTED,
                ReviewState.DISMISSED,
            ):
                with self.subTest(reviewer=reviewer, state=state):
                    newer = ReviewRecord(
                        reviewer=reviewer,
                        event_id=f"{reviewer.value}_{state.value.lower()}",
                        actor_login="request-event",
                        app_slug="request-source",
                        state=state,
                        commit_sha=self.head,
                        submitted_at=NOW - timedelta(seconds=45),
                        findings_count=0,
                        source=source,
                    )
                    result = self.validate(
                        context=self.context(plan),
                        diff=security_diff,
                        snapshot=replace(
                            snapshot,
                            review_requests=(newer,),
                        ),
                    )
                    self.assertIn(
                        f"latest_reviewer_state_invalid:{reviewer.value}",
                        result.reasons,
                    )
                    self.assertIn(
                        f"missing_reviewer:{reviewer.value}",
                        result.reasons,
                    )
            positive = next(
                review for review in snapshot.reviews if review.reviewer is reviewer
            )
            tie = replace(
                positive,
                event_id=f"{reviewer.value}_tie",
                state=ReviewState.PENDING,
            )
            result = self.validate(
                context=self.context(plan),
                diff=security_diff,
                snapshot=replace(snapshot, review_requests=(tie,)),
            )
            self.assertIn(
                f"ambiguous_latest_event:{reviewer.value}",
                result.reasons,
            )

    def test_review_event_input_order_changes_neither_digest_nor_result(self):
        from dataclasses import replace

        security_diff, plan, snapshot = self.security_gate_inputs()
        reversed_snapshot = replace(
            snapshot,
            reviews=tuple(reversed(snapshot.reviews)),
            review_file_coverage=tuple(reversed(snapshot.review_file_coverage)),
        )
        first = self.validate(
            context=self.context(plan),
            diff=security_diff,
            snapshot=snapshot,
        )
        second = self.validate(
            context=self.context(plan),
            diff=security_diff,
            snapshot=reversed_snapshot,
        )

        self.assertEqual(snapshot.evidence_digest, reversed_snapshot.evidence_digest)
        self.assertEqual(first, second)

    def test_event_source_snapshot_and_evaluation_time_order_is_fail_closed(self):
        from dataclasses import replace

        base = self.snapshot()
        self.assertEqual(self.validate(snapshot=base).conclusion, "success")

        after_source_review = replace(
            base.reviews[0],
            submitted_at=base.reviews[0].source.observed_at + timedelta(seconds=1),
        )
        result = self.validate(snapshot=replace(base, reviews=(after_source_review,)))
        self.assertIn("review_event_source_invalid", result.reasons)

        after_source_check = replace(
            base.check_runs[0],
            completed_at=base.check_runs[0].source.observed_at + timedelta(seconds=1),
        )
        result = self.validate(snapshot=replace(base, check_runs=(after_source_check,)))
        self.assertIn("check_event_source_invalid", result.reasons)

        source_after_snapshot = replace(
            base.reviews[0].source,
            observed_at=base.observed_at + timedelta(seconds=1),
        )
        result = self.validate(
            snapshot=replace(
                base,
                reviews=(
                    replace(base.reviews[0], source=source_after_snapshot),
                ),
            )
        )
        self.assertIn("review_event_source_invalid", result.reasons)

        expiring_source = replace(
            base.check_runs[0].source,
            valid_until=NOW,
        )
        result = self.validate(
            snapshot=replace(
                base,
                check_runs=(
                    replace(base.check_runs[0], source=expiring_source),
                ),
            )
        )
        self.assertIn("check_event_source_invalid", result.reasons)

        future_snapshot = replace(
            base,
            observed_at=NOW + timedelta(seconds=1),
            valid_until=NOW + timedelta(minutes=5),
        )
        result = self.validate(snapshot=future_snapshot)
        self.assertIn("evidence_stale", result.reasons)

    def test_publication_receipt_requires_immediate_head_revalidation(self):
        from review_routing.contracts import PublicationReceipt

        with self.assertRaises(ValueError):
            PublicationReceipt(
                repository=self.repository,
                pull_request_number=self.pr,
                head_sha=self.head,
                check_name="agent-governance/review-gate",
                publisher_app_slug="agent-governance-review-gate",
                publication_id="check_1",
                gate_result_digest="sha256:" + "2" * 64,
                idempotency_key="sha256:" + "1" * 64,
                published_at=NOW,
                head_revalidated_at=NOW - timedelta(minutes=1),
            )

    def test_gate_result_exposes_full_digest_and_purpose_bound_idempotency(self):
        result = self.validate()

        self.assertEqual(result.purpose.value, "final_exact_head")
        self.assertRegex(result.gate_result_digest, r"^sha256:[0-9a-f]{64}$")
        self.assertNotEqual(
            result.gate_result_digest,
            __import__("dataclasses").replace(
                result,
                purpose=__import__(
                    "review_routing.contracts",
                    fromlist=["ReviewPurpose"],
                ).ReviewPurpose.CHECKPOINT,
            ).gate_result_digest,
        )

    def test_prior_gate_contract_is_programmatic_only_and_review_rows_are_not_authority(self):
        from review_routing.contracts import PriorGateEvidencePort

        self.assertTrue(hasattr(PriorGateEvidencePort, "load_immediate"))
        result = self.validate(context=self.correction_context(), snapshot=self.snapshot())

        self.assertIn("correction_prior_gate_unavailable", result.reasons)

    def test_correction_accepts_only_fully_bound_injected_prior_gate_evidence(self):
        prior = self.prior_gate_evidence()
        result = self.validate(
            context=self.correction_context(prior),
            snapshot=self.snapshot(),
        )

        self.assertEqual(result.conclusion, "success")
        self.assertNotIn("correction_prior_gate_unavailable", result.reasons)
        self.assertNotIn("correction_prior_gate_invalid", result.reasons)

    def test_correction_rejects_foreign_digest_publisher_and_time_bound_prior_gate(self):
        from dataclasses import replace
        from review_routing.contracts import ReviewPurpose

        valid = self.prior_gate_evidence()
        checkpoint_result = replace(
            valid.prior_gate_result,
            purpose=ReviewPurpose.CHECKPOINT,
        )
        empty_result = replace(
            valid.prior_gate_result,
            required_reviewers=frozenset(),
            validated_reviewers=frozenset(),
        )

        def with_result(result):
            receipt = replace(
                valid.publication_receipt,
                gate_result_digest=result.gate_result_digest,
                idempotency_key=result.idempotency_key,
            )
            return replace(
                valid,
                prior_gate_result=result,
                publication_receipt=receipt,
            )

        cases = {
            "repository": replace(valid, repository="other/repository"),
            "pull_request": replace(valid, pull_request_number=self.pr + 1),
            "current_head": replace(valid, current_head_sha="e" * 40),
            "publisher": replace(valid, source_app_slug="foreign-publisher"),
            "receipt_publisher": replace(
                valid,
                publication_receipt=replace(
                    valid.publication_receipt,
                    publisher_app_slug="foreign-publisher",
                ),
            ),
            "publication": replace(valid, source_reference="another_publication"),
            "receipt_repository": replace(
                valid,
                publication_receipt=replace(
                    valid.publication_receipt,
                    repository="other/repository",
                ),
            ),
            "receipt_pull_request": replace(
                valid,
                publication_receipt=replace(
                    valid.publication_receipt,
                    pull_request_number=self.pr + 1,
                ),
            ),
            "receipt_head": replace(
                valid,
                publication_receipt=replace(
                    valid.publication_receipt,
                    head_sha="e" * 40,
                ),
            ),
            "receipt_check": replace(
                valid,
                publication_receipt=replace(
                    valid.publication_receipt,
                    check_name="foreign/check",
                ),
            ),
            "receipt_digest": replace(
                valid,
                publication_receipt=replace(
                    valid.publication_receipt,
                    gate_result_digest="sha256:" + "0" * 64,
                ),
            ),
            "receipt_idempotency": replace(
                valid,
                publication_receipt=replace(
                    valid.publication_receipt,
                    idempotency_key="sha256:" + "0" * 64,
                ),
            ),
            "time_order": replace(
                valid,
                observed_at=valid.publication_receipt.published_at - timedelta(seconds=1),
            ),
            "expired": replace(
                valid,
                observed_at=NOW - timedelta(minutes=2),
                valid_until=NOW,
            ),
            "prior_failure": replace(
                valid,
                prior_gate_result=replace(
                    valid.prior_gate_result,
                    conclusion="failure",
                    reasons=("prior_gate_failed",),
                ),
            ),
            "prior_checkpoint": with_result(checkpoint_result),
            "prior_empty_reviewers": with_result(empty_result),
        }
        for name, evidence in cases.items():
            with self.subTest(name=name):
                result = self.validate(
                    context=self.correction_context(evidence),
                    snapshot=self.snapshot(),
                )
                self.assertIn("correction_prior_gate_invalid", result.reasons)

    def test_successful_gate_contract_rejects_reviewer_mismatch_reasons_and_threads(self):
        from dataclasses import replace
        from review_routing.contracts import Reviewer

        result = self.validate()
        invalid_successes = (
            {
                "required_reviewers": frozenset({Reviewer.COPILOT, Reviewer.QA}),
            },
            {"reasons": ("unexpected_reason",)},
            {"unresolved_thread_count": 1},
        )
        for changes in invalid_successes:
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    replace(result, **changes)

    def test_gate_result_digest_binds_every_published_decision_dimension(self):
        from dataclasses import replace
        from review_routing.contracts import Reviewer, ReviewPurpose

        result = self.validate()
        mutations = (
            replace(result, purpose=ReviewPurpose.CORRECTION),
            replace(
                result,
                required_reviewers=frozenset({Reviewer.COPILOT, Reviewer.QA}),
                validated_reviewers=frozenset({Reviewer.COPILOT, Reviewer.QA}),
            ),
            replace(
                result,
                conclusion="failure",
                reasons=("changed_reason",),
            ),
            replace(result, policy_digest="sha256:" + "1" * 64),
            replace(result, runtime_digest="sha256:" + "2" * 64),
            replace(result, diff_digest="sha256:" + "3" * 64),
            replace(result, evidence_digest="sha256:" + "4" * 64),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assertNotEqual(result.gate_result_digest, mutation.gate_result_digest)
                self.assertNotEqual(result.idempotency_key, mutation.idempotency_key)

    def test_task_six_contracts_reject_boolean_integer_lookalikes_and_duplicates(self):
        from dataclasses import replace

        with self.assertRaises(ValueError):
            replace(self.plan(), pull_request_number=True)
        with self.assertRaises(ValueError):
            replace(self.snapshot(), schema_version=True)
        with self.assertRaises(ValueError):
            replace(
                self.snapshot(),
                check_runs=(
                    self.snapshot().check_runs[0],
                    self.snapshot().check_runs[0],
                ),
            )
        with self.assertRaises(ValueError):
            replace(
                self.snapshot(),
                reviews=(
                    self.snapshot().reviews[0],
                    self.snapshot().reviews[0],
                ),
            )


if __name__ == "__main__":
    unittest.main()
