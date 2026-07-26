#!/usr/bin/env python3
"""Verhaltensspezifikation für den read-only Review-Routing-CLI-Vertrag."""
from __future__ import annotations

from contextlib import redirect_stderr
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
from io import StringIO
import json
from pathlib import Path, PurePosixPath
import tempfile
from types import SimpleNamespace
import unittest

from review_routing.contracts import (
    BillingContext,
    BillingPrincipal,
    BlockEvidenceKind,
    BlockEvidenceSource,
    BlockVerification,
    CapabilityArtifactKind,
    CapabilityEvidence,
    CapabilityEvidenceSource,
    CapabilityVerification,
    CliDependencies,
    ClockPort,
    ConfigPort,
    DetectionMode,
    DiagnosticStatus,
    DiffFile,
    DiffMode,
    DiffSnapshot,
    DiffSourcePort,
    DocumentTrust,
    EvidenceTrust,
    EvidenceVerificationStatus,
    FileStatus,
    GitSourceError,
    OperatorEvidencePin,
    OperatorEvidenceTrustPort,
    PolicyDocument,
    PolicySourcePort,
    ProbePort,
    ProbeReport,
    ProbeRequest,
    ProbeSignals,
    ProbeTechnicalError,
    PullRequestState,
    PullRequestStatePort,
    PullRequestStateSource,
    Reviewer,
    ReviewerAvailabilityEvidence,
    ReviewerAvailabilityPort,
    ReviewerAvailabilitySnapshot,
    ReviewerAvailabilitySource,
    ReviewerAvailabilityStatus,
    ReviewPurpose,
    ReviewRoute,
    RuntimeTrustConfig,
    RuntimeTrustPort,
    RuntimeTrustSource,
    Usage,
    VerifiedBlockEvidence,
)


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 7, 27, 9, 0, tzinfo=timezone.utc)
REPOSITORY = "tomtastisch/agent-governance"
BASE_SHA = "a" * 40
MERGE_BASE_SHA = "c" * 40
HEAD_SHA = "b" * 40


class FakeRuntimeTrust(RuntimeTrustPort):
    def __init__(self, installed: bool):
        runtime_bytes = (ROOT / "review_routing/runtime.toml").read_bytes()
        self.config = RuntimeTrustConfig(
            expected_runtime_digest=(
                "sha256:" + hashlib.sha256(runtime_bytes).hexdigest()
                if installed
                else None
            ),
            source=(
                RuntimeTrustSource.INSTALLED_CONFIG
                if installed
                else RuntimeTrustSource.DEVELOPMENT
            ),
            observed_at=NOW,
        )

    def load(self) -> RuntimeTrustConfig:
        return self.config


class FakeOperatorTrust(OperatorEvidenceTrustPort):
    def load(self, source_reference: str) -> OperatorEvidencePin | None:
        return None


class FakeProbe(ProbePort):
    def __init__(self, report: ProbeReport, *, bind_request: bool = True):
        self.report = report
        self.bind_request = bind_request
        self.requests: list[ProbeRequest] = []

    def probe(self, request: ProbeRequest) -> ProbeReport:
        self.requests.append(request)
        if not self.bind_request:
            return self.report
        return replace(
            self.report,
            pull_request_number=request.pull_request_number,
            request_digest=request.request_digest,
        )


class FakePullRequestState(PullRequestStatePort):
    def __init__(self, state: object | None = None):
        self.state = state or PullRequestState(
            repository=REPOSITORY,
            pull_request_number=5,
            base_ref="main",
            api_base_sha=BASE_SHA,
            head_sha=HEAD_SHA,
            author="author",
            observed_at=NOW,
            source=PullRequestStateSource.GITHUB_API,
        )
        self.calls: list[tuple[str, int]] = []

    def load(self, repository: str, pull_request_number: int) -> PullRequestState:
        self.calls.append((repository, pull_request_number))
        return self.state  # type: ignore[return-value]


class FakePolicySource(PolicySourcePort):
    def __init__(self, *, missing: bool = False):
        self.missing = missing
        self.calls: list[tuple[Path, str, str, PurePosixPath]] = []

    def read_at_commit(
        self,
        repo_path: Path,
        repository: str,
        commit_sha: str,
        policy_path: PurePosixPath,
    ) -> PolicyDocument:
        self.calls.append((repo_path, repository, commit_sha, policy_path))
        if self.missing:
            raise GitSourceError("Basispolicy fehlt")
        return PolicyDocument(
            content=(ROOT / "core/review-routing.toml").read_text(encoding="utf-8"),
            trust=DocumentTrust.COMMIT_OBJECT,
            source=f"{commit_sha}:{policy_path}",
        )


class FakeDiffSource(DiffSourcePort):
    def __init__(self, path: str = "src/application.py", changed_lines: int = 1):
        self.path = path
        self.changed_lines = changed_lines
        self.calls: list[tuple[Path, str, str, str]] = []

    def load(
        self,
        repo_path: Path,
        repository: str,
        api_base_sha: str,
        head_sha: str,
    ) -> DiffSnapshot:
        self.calls.append((repo_path, repository, api_base_sha, head_sha))
        return DiffSnapshot(
            schema_version=1,
            repository=repository,
            api_base_sha=api_base_sha,
            merge_base_sha=MERGE_BASE_SHA,
            head_sha=head_sha,
            diff_mode=DiffMode.MERGE_BASE_TO_HEAD,
            rename_detection=DetectionMode.DISABLED,
            copy_detection=DetectionMode.DISABLED,
            files=(
                DiffFile(
                    path=self.path,
                    status=FileStatus.MODIFIED,
                    additions=self.changed_lines,
                    deletions=0,
                    binary=False,
                ),
            ),
        )


class FakeClock(ClockPort):
    def __init__(self, now: datetime = NOW):
        self.current = now

    def now(self) -> datetime:
        return self.current


class FakeReviewerAvailability(ReviewerAvailabilityPort):
    def __init__(
        self,
        *,
        qa: ReviewerAvailabilityStatus = ReviewerAvailabilityStatus.AVAILABLE,
        sec: ReviewerAvailabilityStatus = ReviewerAvailabilityStatus.AVAILABLE,
        repository: str = REPOSITORY,
        head_sha: str = HEAD_SHA,
        observed_at: datetime = NOW,
        expires_at: datetime = NOW + timedelta(minutes=5),
    ):
        self.statuses = {Reviewer.QA: qa, Reviewer.SEC: sec}
        self.repository = repository
        self.head_sha = head_sha
        self.observed_at = observed_at
        self.expires_at = expires_at
        self.calls: list[tuple[str, int, str, ReviewPurpose]] = []

    def load(
        self,
        repository: str,
        pull_request_number: int,
        head_sha: str,
        purpose: ReviewPurpose,
    ) -> ReviewerAvailabilitySnapshot:
        self.calls.append((repository, pull_request_number, head_sha, purpose))
        return ReviewerAvailabilitySnapshot(
            evidence=tuple(
                ReviewerAvailabilityEvidence(
                    reviewer=reviewer,
                    status=status,
                    repository=self.repository,
                    pull_request_number=pull_request_number,
                    head_sha=self.head_sha,
                    purpose=purpose,
                    observed_at=self.observed_at,
                    expires_at=self.expires_at,
                    source=ReviewerAvailabilitySource.HARNESS_RUNTIME,
                    reason="harness_role_context",
                )
                for reviewer, status in self.statuses.items()
            )
        )


def principal(review_mode: str = "manual") -> BillingPrincipal:
    return BillingPrincipal(
        kind="personal",
        identifier="tom" if review_mode == "manual" else "author",
        review_mode=review_mode,
        requester="tom" if review_mode == "manual" else None,
        pull_request_author="author" if review_mode == "automatic" else None,
        source="github_api",
        observed_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(minutes=15),
    )


def probe_report(
    *,
    usable: bool,
    routing_status: DiagnosticStatus | None = None,
    technical_error: ProbeTechnicalError | None = None,
    review_mode: str = "manual",
    request: ProbeRequest | None = None,
) -> ProbeReport:
    request = request or ProbeRequest(
        repository=REPOSITORY,
        review_mode=review_mode,
        manual_requester="tom" if review_mode == "manual" else None,
        pull_request_number=5 if review_mode == "automatic" else None,
    )
    billing_principal = principal(review_mode)
    capability = (
        CapabilityEvidence(
            repository=REPOSITORY,
            principal=billing_principal,
            review_mode=review_mode,
            observed_at=NOW - timedelta(seconds=30),
            expires_at=NOW + timedelta(minutes=10),
            source=CapabilityEvidenceSource.OPERATOR_PINNED,
            artifact_kind=CapabilityArtifactKind.OPERATOR_SETTING,
            source_reference="verified_capability",
            artifact_digest="sha256:" + "d" * 64,
            pin_source=RuntimeTrustSource.INSTALLED_CONFIG,
        )
        if usable
        else None
    )
    verification = CapabilityVerification(
        status=(
            EvidenceVerificationStatus.VERIFIED
            if capability is not None
            else EvidenceVerificationStatus.ABSENT
        ),
        trust=(
            EvidenceTrust.VERIFIED
            if capability is not None
            else EvidenceTrust.UNVERIFIED
        ),
        source=capability.source if capability is not None else None,
        artifact_kind=capability.artifact_kind if capability is not None else None,
        source_reference=capability.source_reference if capability is not None else None,
        artifact_digest=capability.artifact_digest if capability is not None else None,
        pin_source=capability.pin_source if capability is not None else None,
        evidence=capability,
    )
    technical_status = {
        ProbeTechnicalError.PERMISSION_DENIED: DiagnosticStatus.PERMISSION_DENIED,
        ProbeTechnicalError.RATE_LIMITED: DiagnosticStatus.RATE_LIMITED,
        ProbeTechnicalError.PROVIDER_UNAVAILABLE: DiagnosticStatus.PROVIDER_UNAVAILABLE,
        ProbeTechnicalError.TIMEOUT: DiagnosticStatus.PROVIDER_UNAVAILABLE,
        ProbeTechnicalError.UNKNOWN_CONTEXT: DiagnosticStatus.UNKNOWN,
        ProbeTechnicalError.INCOMPLETE_RESPONSE: DiagnosticStatus.UNKNOWN,
    }.get(technical_error, DiagnosticStatus.AVAILABLE)
    status = routing_status or (
        DiagnosticStatus.AVAILABLE
        if usable
        else (
            technical_status
            if technical_status is not DiagnosticStatus.AVAILABLE
            else DiagnosticStatus.UNKNOWN
        )
    )
    signals = ProbeSignals(
        billing_status=None,
        usage_status=(
            DiagnosticStatus.AVAILABLE
            if technical_status is DiagnosticStatus.AVAILABLE
            else technical_status
        ),
        provider_status=(
            technical_status
            if technical_status
            in {DiagnosticStatus.RATE_LIMITED, DiagnosticStatus.PROVIDER_UNAVAILABLE}
            else DiagnosticStatus.AVAILABLE
        ),
        permission_status=(
            DiagnosticStatus.PERMISSION_DENIED
            if technical_status is DiagnosticStatus.PERMISSION_DENIED
            else DiagnosticStatus.AVAILABLE
        ),
        capability=capability,
        repository=REPOSITORY,
        principal=billing_principal,
        review_mode=review_mode,
        observed_at=NOW,
        verified_block=(
            VerifiedBlockEvidence(
                schema_version=1,
                kind=BlockEvidenceKind.BUDGET_BLOCKED,
                repository=REPOSITORY,
                principal_identity=billing_principal.identity,
                review_mode=review_mode,
                observed_at=NOW - timedelta(seconds=15),
                expires_at=NOW + timedelta(minutes=10),
                source=BlockEvidenceSource.OPERATOR_PINNED,
                source_reference="verified_block",
                artifact_digest="sha256:" + "e" * 64,
                pin_source=RuntimeTrustSource.INSTALLED_CONFIG,
            )
            if routing_status is DiagnosticStatus.BUDGET_BLOCKED
            else None
        ),
    )
    block_verification = (
        BlockVerification(
            status=EvidenceVerificationStatus.VERIFIED,
            trust=EvidenceTrust.VERIFIED,
            source=signals.verified_block.source,
            source_reference=signals.verified_block.source_reference,
            artifact_digest=signals.verified_block.artifact_digest,
            pin_source=signals.verified_block.pin_source,
            evidence=signals.verified_block,
        )
        if signals.verified_block is not None
        else None
    )
    return ProbeReport(
        copilot_usable=usable,
        routing_status=status,
        signals=signals,
        usage=Usage(used=1, limit=None, unit="credits"),
        repository=REPOSITORY,
        review_mode=review_mode,
        requester="tom" if review_mode == "manual" else None,
        pull_request_author="author" if review_mode == "automatic" else None,
        billing_principal=billing_principal,
        billing_context=BillingContext(
            kind="personal",
            identity="tom",
            evidence=("github_api",),
        ),
        billing_model="ai_credits",
        technical_status=technical_status,
        technical_error=technical_error,
        capability_verification=verification,
        block_verification=block_verification,
        evidence=("github_api",),
        pull_request_number=request.pull_request_number,
        request_digest=request.request_digest,
        valid_until=NOW + timedelta(minutes=5),
    )


def dependencies(
    report: ProbeReport,
    *,
    installed: bool = False,
    diff_source: DiffSourcePort | None = None,
    policy_source: PolicySourcePort | None = None,
    pull_request_state: PullRequestStatePort | None = None,
    reviewer_availability: ReviewerAvailabilityPort | None = None,
    probe: ProbePort | None = None,
    clock: ClockPort | None = None,
) -> CliDependencies:
    from review_routing.adapters.toml_config import TomlConfig

    return CliDependencies(
        runtime_trust_port=FakeRuntimeTrust(installed),
        operator_evidence_trust_port=FakeOperatorTrust(),
        probe=probe or FakeProbe(report),
        pull_request_state=pull_request_state or FakePullRequestState(),
        config=TomlConfig(),
        policy_source=policy_source or FakePolicySource(),
        diff_source=diff_source or FakeDiffSource(),
        clock=clock or FakeClock(),
        reviewer_availability=reviewer_availability,
    )


def invoke(
    arguments: list[str],
    cli_dependencies: CliDependencies,
) -> tuple[int, dict[str, object], str, str]:
    from review_routing.__main__ import main

    stdout = StringIO()
    stderr = StringIO()
    with redirect_stderr(stderr):
        exit_code = main(arguments, dependencies=cli_dependencies, stdout=stdout)
    lines = stdout.getvalue().splitlines()
    if len(lines) != 1:
        raise AssertionError(f"stdout must contain exactly one line, got {lines!r}")
    return exit_code, json.loads(lines[0]), stdout.getvalue(), stderr.getvalue()


class ProbeCliTest(unittest.TestCase):
    """Probe gibt technische Zustände stabil und ohne Nebenkanal aus."""

    def test_valid_manual_probe_reads_untrusted_capability_reference(self):
        report = probe_report(usable=True)
        cli_dependencies = dependencies(report)
        artifact = {
            "schema_version": 1,
            "kind": "operator_setting",
            "repository": REPOSITORY,
            "principal_identity": ["personal", "tom", "manual", "tom", None],
            "review_mode": "manual",
            "observed_at": "2026-07-27T08:59:30Z",
            "expires_at": "2026-07-27T09:10:00Z",
            "source_reference": "verified_capability",
        }
        with tempfile.TemporaryDirectory() as directory:
            artifact_path = Path(directory) / "capability.json"
            artifact_path.write_text(json.dumps(artifact), encoding="utf-8")
            exit_code, payload, stdout, stderr = invoke(
                [
                    "probe",
                    "--repo",
                    REPOSITORY,
                    "--review-mode",
                    "manual",
                    "--requester",
                    "tom",
                    "--capability-reference",
                    str(artifact_path),
                    "--json",
                ],
                cli_dependencies,
            )

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["copilot_usable"])
        self.assertEqual(stderr, "")
        self.assertEqual(stdout.count("\n"), 1)
        request = cli_dependencies.probe.requests[0]  # type: ignore[union-attr]
        self.assertEqual(request.capability_reference.artifact, json.dumps(artifact).encode())
        self.assertEqual(request.capability_reference.source_reference, "verified_capability")

    def test_probe_exitcodes_cover_all_declared_technical_failures(self):
        cases = (
            (ProbeTechnicalError.PERMISSION_DENIED, 20),
            (ProbeTechnicalError.RATE_LIMITED, 21),
            (ProbeTechnicalError.PROVIDER_UNAVAILABLE, 22),
            (ProbeTechnicalError.TIMEOUT, 22),
            (ProbeTechnicalError.UNKNOWN_CONTEXT, 23),
            (ProbeTechnicalError.INCOMPLETE_RESPONSE, 24),
        )
        for technical_error, expected_exit in cases:
            with self.subTest(technical_error=technical_error):
                report = probe_report(usable=False, technical_error=technical_error)
                exit_code, payload, _stdout, stderr = invoke(
                    [
                        "probe",
                        "--repo",
                        REPOSITORY,
                        "--review-mode",
                        "manual",
                        "--requester",
                        "tom",
                        "--json",
                    ],
                    dependencies(report),
                )
                self.assertEqual(exit_code, expected_exit)
                self.assertEqual(payload["technical_error"], technical_error.value)
                self.assertEqual(stderr, "")

    def test_valid_automatic_probe_is_bound_to_the_requested_pr_context(self):
        report = probe_report(usable=False, review_mode="automatic")
        cli_dependencies = dependencies(report)

        exit_code, payload, _stdout, _stderr = invoke(
            [
                "probe",
                "--repo",
                REPOSITORY,
                "--review-mode",
                "automatic",
                "--pull-request",
                "5",
                "--json",
            ],
            cli_dependencies,
        )

        self.assertEqual(exit_code, 23)
        self.assertEqual(payload["review_mode"], "automatic")
        self.assertEqual(payload["pull_request_author"], "author")
        request = cli_dependencies.probe.requests[0]  # type: ignore[union-attr]
        self.assertEqual(request.pull_request_number, 5)
        self.assertIsNone(request.manual_requester)

    def test_probe_rejects_a_report_from_another_requested_context(self):
        exit_code, payload, _stdout, _stderr = invoke(
            [
                "probe",
                "--repo",
                REPOSITORY,
                "--review-mode",
                "automatic",
                "--pull-request",
                "5",
                "--json",
            ],
            dependencies(probe_report(usable=False, review_mode="manual")),
        )

        self.assertEqual(exit_code, 31)
        self.assertEqual(payload["error"], "invalid_input")

    def test_verified_budget_block_is_a_complete_probe_not_a_technical_error(self):
        report = probe_report(
            usable=False,
            routing_status=DiagnosticStatus.BUDGET_BLOCKED,
        )
        exit_code, payload, _stdout, _stderr = invoke(
            [
                "probe",
                "--repo",
                REPOSITORY,
                "--review-mode",
                "manual",
                "--requester",
                "tom",
                "--json",
            ],
            dependencies(report),
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["routing_status"], "budget_blocked")

    def test_invalid_arguments_and_json_are_sanitized_exit_31(self):
        cli_dependencies = dependencies(probe_report(usable=False))
        cases = (
            ["probe", "--repo", REPOSITORY, "--review-mode", "manual", "--json"],
            [
                "probe",
                "--repo",
                REPOSITORY,
                "--review-mode",
                "automatic",
                "--requester",
                "tom",
                "--pull-request",
                "5",
                "--json",
            ],
            ["probe", "--repo", REPOSITORY, "--review-mode", "manual", "--requester", "tom"],
            ["probe", "--repo", REPOSITORY, "--review-mode", "manual", "--requester", "tom", "--billing", "blocked", "--json"],
            ["dispatch", "--repo", REPOSITORY, "--json"],
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                exit_code, payload, _stdout, stderr = invoke(arguments, cli_dependencies)
                self.assertEqual(exit_code, 31)
                self.assertEqual(payload["error"], "invalid_input")
                self.assertEqual(stderr, "")

        with tempfile.TemporaryDirectory() as directory:
            artifact_path = Path(directory) / "invalid.json"
            artifact_path.write_text("{", encoding="utf-8")
            exit_code, payload, _stdout, _stderr = invoke(
                [
                    "probe",
                    "--repo",
                    REPOSITORY,
                    "--review-mode",
                    "manual",
                    "--requester",
                    "tom",
                    "--capability-reference",
                    str(artifact_path),
                    "--json",
                ],
                cli_dependencies,
            )
        self.assertEqual(exit_code, 31)
        self.assertEqual(payload["error"], "invalid_input")

    def test_cli_exposes_no_trust_or_provider_assertion_flags(self):
        forbidden = (
            "--runtime-trust",
            "--runtime-digest",
            "--expected-digest",
            "--issuer",
            "--source",
            "--pin-source",
            "--billing-status",
            "--quota-exhausted",
        )
        for flag in forbidden:
            with self.subTest(flag=flag):
                exit_code, payload, _stdout, _stderr = invoke(
                    [
                        "probe",
                        "--repo",
                        REPOSITORY,
                        "--review-mode",
                        "manual",
                        "--requester",
                        "tom",
                        flag,
                        "forged",
                        "--json",
                    ],
                    dependencies(probe_report(usable=False)),
                )
                self.assertEqual(exit_code, 31)
                self.assertEqual(payload["error"], "invalid_input")


class CliDependencyContractTest(unittest.TestCase):
    """Programmatic-only Injektionen müssen exakt den deklarierten Ports entsprechen."""

    def test_each_injected_dependency_rejects_non_port_objects(self):
        fields = (
            "runtime_trust_port",
            "operator_evidence_trust_port",
            "probe",
            "pull_request_state",
            "config",
            "policy_source",
            "diff_source",
            "clock",
            "reviewer_availability",
        )

        for field_name in fields:
            with self.subTest(field_name=field_name):
                with self.assertRaises(ValueError):
                    CliDependencies(**{field_name: object()})

    def test_probe_request_digest_binds_every_routing_context_field(self):
        base = ProbeRequest(
            repository=REPOSITORY,
            review_mode="manual",
            manual_requester="tom",
            pull_request_number=5,
        )
        changed = (
            replace(base, manual_requester="other"),
            replace(base, pull_request_number=6),
            replace(base, organization="organization"),
        )

        self.assertRegex(base.request_digest, r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(base.request_digest, replace(base).request_digest)
        self.assertEqual(len({base.request_digest, *(item.request_digest for item in changed)}), 4)

    def test_probe_report_rejects_digest_time_status_and_usability_mismatches(self):
        request = ProbeRequest(
            repository=REPOSITORY,
            review_mode="manual",
            manual_requester="tom",
            pull_request_number=5,
        )
        report = probe_report(usable=False, request=request)

        with self.assertRaises(ValueError):
            replace(report, request_digest="forged")
        with self.assertRaises(ValueError):
            replace(report, valid_until=report.observed_at)
        with self.assertRaises(ValueError):
            replace(report, copilot_usable=True)
        unbound_manual_principal = replace(report.billing_principal, requester=None)
        with self.assertRaises(ValueError):
            replace(
                report,
                requester=None,
                billing_principal=unbound_manual_principal,
                signals=replace(
                    report.signals,
                    principal=unbound_manual_principal,
                ),
            )
        with self.assertRaises(ValueError):
            replace(
                probe_report(usable=True, request=request),
                technical_error=ProbeTechnicalError.PERMISSION_DENIED,
                technical_status=DiagnosticStatus.PERMISSION_DENIED,
            )
        with self.assertRaises(ValueError):
            replace(
                report,
                technical_error=ProbeTechnicalError.PERMISSION_DENIED,
                technical_status=DiagnosticStatus.PERMISSION_DENIED,
            )
        with self.assertRaises(ValueError):
            replace(
                probe_report(
                    usable=False,
                    request=request,
                    technical_error=ProbeTechnicalError.PERMISSION_DENIED,
                ),
                technical_error=None,
            )

    def test_reviewer_availability_is_exactly_context_and_time_bound(self):
        current = ReviewerAvailabilityEvidence(
            reviewer=Reviewer.QA,
            status=ReviewerAvailabilityStatus.AVAILABLE,
            repository=REPOSITORY,
            pull_request_number=5,
            head_sha=HEAD_SHA,
            purpose=ReviewPurpose.CHECKPOINT,
            observed_at=NOW,
            expires_at=NOW + timedelta(minutes=5),
            source=ReviewerAvailabilitySource.HARNESS_RUNTIME,
            reason="harness_role_context",
        )
        snapshot = ReviewerAvailabilitySnapshot(evidence=(current,))

        self.assertTrue(
            snapshot.is_available(
                Reviewer.QA,
                REPOSITORY,
                5,
                HEAD_SHA,
                ReviewPurpose.CHECKPOINT,
                NOW,
            )
        )
        self.assertFalse(
            snapshot.is_available(
                Reviewer.QA,
                REPOSITORY,
                5,
                "f" * 40,
                ReviewPurpose.CHECKPOINT,
                NOW,
            )
        )
        self.assertFalse(
            snapshot.is_available(
                Reviewer.SEC,
                REPOSITORY,
                5,
                HEAD_SHA,
                ReviewPurpose.CHECKPOINT,
                NOW,
            )
        )
        self.assertFalse(
            snapshot.is_available(
                Reviewer.QA,
                REPOSITORY,
                5,
                HEAD_SHA,
                ReviewPurpose.CHECKPOINT,
                current.expires_at,
            )
        )


class RouteCliTest(unittest.TestCase):
    """Route erhebt Probe und Reviewer-Verfügbarkeit frisch und programmgesteuert."""

    def _route(
        self,
        *,
        usable: bool,
        purpose: str,
        review_mode: str = "manual",
        path: str = "src/application.py",
        changed_lines: int = 1,
        installed: bool = False,
        extra: tuple[str, ...] = (),
        policy_source: PolicySourcePort | None = None,
        pull_request_state: PullRequestStatePort | None = None,
        reviewer_availability: ReviewerAvailabilityPort | None | bool = True,
        probe: ProbePort | None = None,
        clock: ClockPort | None = None,
    ):
        report = probe_report(usable=usable, review_mode=review_mode)
        availability = (
            FakeReviewerAvailability()
            if reviewer_availability is True
            else reviewer_availability
        )
        cli_dependencies = dependencies(
            report,
            installed=installed,
            diff_source=FakeDiffSource(path, changed_lines),
            policy_source=policy_source,
            pull_request_state=pull_request_state,
            reviewer_availability=availability,
            probe=probe,
            clock=clock,
        )
        with tempfile.TemporaryDirectory() as directory:
            capability_arguments: list[str] = []
            if usable:
                identity = (
                    ["personal", "tom", "manual", "tom", None]
                    if review_mode == "manual"
                    else ["personal", "author", "automatic", None, "author"]
                )
                artifact = {
                    "schema_version": 1,
                    "kind": "operator_setting",
                    "repository": REPOSITORY,
                    "principal_identity": identity,
                    "review_mode": review_mode,
                    "observed_at": "2026-07-27T08:59:30Z",
                    "expires_at": "2026-07-27T09:10:00Z",
                    "source_reference": "verified_capability",
                }
                artifact_path = Path(directory) / "capability.json"
                artifact_path.write_text(json.dumps(artifact), encoding="utf-8")
                capability_arguments = [
                    "--capability-reference",
                    str(artifact_path),
                ]
            result = invoke(
                [
                    "route",
                    "--repo",
                    REPOSITORY,
                    "--pull-request",
                    "5",
                    "--review-mode",
                    review_mode,
                    *(
                        ["--requester", "tom"]
                        if review_mode == "manual"
                        else []
                    ),
                    "--purpose",
                    purpose,
                    "--repo-path",
                    str(ROOT),
                    *capability_arguments,
                    *extra,
                    "--json",
                ],
                cli_dependencies,
            )
        return (*result, cli_dependencies)

    def test_automatic_route_binds_fresh_probe_to_api_pr_author(self):
        exit_code, payload, _stdout, _stderr, cli_dependencies = self._route(
            usable=False,
            purpose="checkpoint",
            review_mode="automatic",
        )

        self.assertEqual(exit_code, 0)
        request = cli_dependencies.probe.requests[0]  # type: ignore[union-attr]
        self.assertEqual(request.review_mode, "automatic")
        self.assertEqual(request.pull_request_number, 5)
        self.assertIsNone(request.manual_requester)
        self.assertEqual(payload["pull_request_author"], "author")

    def test_preliminary_routes_always_include_qa_for_unknown_coverage_and_mode(self):
        cases = (
            (True, "checkpoint", "src/a.py", 1, ReviewRoute.QA),
            (True, "final_exact_head", "src/a.py", 300, ReviewRoute.COPILOT_QA),
            (True, "final_exact_head", "core/core.md", 1, ReviewRoute.COPILOT_QA_SEC),
            (False, "checkpoint", "src/a.py", 1, ReviewRoute.QA),
            (False, "final_exact_head", "core/core.md", 1, ReviewRoute.QA_SEC),
        )
        for usable, purpose, path, changed_lines, expected in cases:
            with self.subTest(route=expected):
                exit_code, payload, _stdout, stderr, _dependencies = self._route(
                    usable=usable,
                    purpose=purpose,
                    path=path,
                    changed_lines=changed_lines,
                )
                self.assertEqual(exit_code, 0)
                self.assertEqual(payload["route"], expected.value)
                self.assertIsNone(payload["copilot_coverage_complete"])
                self.assertEqual(payload["copilot_review_mode"], "unknown")
                self.assertEqual(payload["decision_stage"], "preliminary")
                self.assertEqual(payload["gate_status"], "evidence_validation_pending")
                self.assertFalse(payload["gate_eligible"])
                self.assertEqual(stderr, "")

    def test_route_uses_only_api_state_base_policy_and_complete_diff_ports(self):
        exit_code, payload, _stdout, _stderr, cli_dependencies = self._route(
            usable=True,
            purpose="final_exact_head",
            installed=True,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            cli_dependencies.pull_request_state.calls,  # type: ignore[union-attr]
            [(REPOSITORY, 5)],
        )
        self.assertEqual(
            cli_dependencies.policy_source.calls,  # type: ignore[union-attr]
            [(ROOT, REPOSITORY, BASE_SHA, PurePosixPath("core/review-routing.toml"))],
        )
        self.assertEqual(
            cli_dependencies.diff_source.calls,  # type: ignore[union-attr]
            [(ROOT, REPOSITORY, BASE_SHA, HEAD_SHA)],
        )
        self.assertEqual(len(cli_dependencies.probe.requests), 1)  # type: ignore[union-attr]
        fresh_request = cli_dependencies.probe.requests[0]  # type: ignore[union-attr]
        self.assertEqual(fresh_request.repository, REPOSITORY)
        self.assertEqual(fresh_request.pull_request_number, 5)
        self.assertEqual(fresh_request.review_mode, "manual")
        self.assertEqual(payload["probe_request_digest"], fresh_request.request_digest)
        self.assertEqual(payload["base_ref"], "main")
        self.assertEqual(payload["base_sha"], BASE_SHA)
        self.assertEqual(payload["merge_base_sha"], MERGE_BASE_SHA)
        self.assertEqual(payload["head_sha"], HEAD_SHA)
        self.assertEqual(payload["pull_request_author"], "author")
        self.assertEqual(payload["pr_state_source"], "github_api")
        self.assertEqual(payload["policy_source_ref"], BASE_SHA)
        self.assertEqual(payload["policy_source_path"], "core/review-routing.toml")
        self.assertEqual(payload["diff_mode"], "merge_base_to_head")
        self.assertEqual(payload["rename_detection"], "disabled")
        self.assertEqual(payload["copy_detection"], "disabled")
        self.assertEqual(payload["runtime_trust"], "installed")
        self.assertFalse(payload["gate_eligible"])
        self.assertFalse(payload["dispatch_permitted"])

    def test_development_runtime_cannot_claim_gate_eligibility(self):
        exit_code, payload, _stdout, _stderr, _dependencies = self._route(
            usable=True,
            purpose="final_exact_head",
            installed=False,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["runtime_trust"], "development")
        self.assertFalse(payload["gate_eligible"])

    def test_missing_reviewer_availability_port_is_fail_closed_blocker(self):
        exit_code, payload, _stdout, _stderr, _dependencies = self._route(
            usable=False,
            purpose="checkpoint",
            reviewer_availability=None,
        )

        self.assertEqual(exit_code, 30)
        self.assertEqual(payload["route"], "blocker")
        self.assertEqual(payload["required_reviewers"], ["qa"])

    def test_invalid_policy_pr_state_and_caller_authority_fail_exit_31(self):
        exit_code, payload, _stdout, _stderr, _dependencies = self._route(
            usable=False,
            purpose="checkpoint",
            policy_source=FakePolicySource(missing=True),
        )
        self.assertEqual(exit_code, 31)
        self.assertEqual(payload["error"], "invalid_input")

        invalid_state = SimpleNamespace(
            repository=REPOSITORY,
            pull_request_number=5,
            base_ref="main",
            api_base_sha="short",
            head_sha=HEAD_SHA,
            author="author",
            observed_at=NOW,
            source=PullRequestStateSource.GITHUB_API,
        )
        exit_code, payload, _stdout, _stderr, _dependencies = self._route(
            usable=False,
            purpose="checkpoint",
            pull_request_state=FakePullRequestState(invalid_state),
        )
        self.assertEqual(exit_code, 31)
        self.assertEqual(payload["error"], "invalid_input")

        for forbidden in (
            "--probe-file",
            "--base-sha",
            "--head-sha",
            "--files",
            "--policy-file",
            "--dispatch",
            "--qa-available",
            "--sec-available",
        ):
            with self.subTest(forbidden=forbidden):
                exit_code, payload, _stdout, _stderr, _dependencies = self._route(
                    usable=False,
                    purpose="checkpoint",
                    extra=(forbidden, BASE_SHA),
                )
                self.assertEqual(exit_code, 31)
                self.assertEqual(payload["error"], "invalid_input")

    def test_route_rejects_stale_or_request_digest_mismatched_probe_reports(self):
        stale_exit, stale_payload, _stdout, _stderr, _dependencies = self._route(
            usable=False,
            purpose="checkpoint",
            clock=FakeClock(NOW + timedelta(minutes=6)),
        )
        self.assertEqual(stale_exit, 31)
        self.assertEqual(stale_payload["error"], "invalid_input")

        fixed_report = probe_report(usable=False)
        mismatch_exit, mismatch_payload, _stdout, _stderr, _dependencies = self._route(
            usable=False,
            purpose="checkpoint",
            probe=FakeProbe(fixed_report, bind_request=False),
        )
        self.assertEqual(mismatch_exit, 31)
        self.assertEqual(mismatch_payload["error"], "invalid_input")

    def test_available_reviewer_evidence_must_match_context_and_time(self):
        foreign = FakeReviewerAvailability(repository="other/repository")
        expired = FakeReviewerAvailability(
            observed_at=NOW - timedelta(minutes=10),
            expires_at=NOW - timedelta(minutes=1),
        )
        for availability in (foreign, expired):
            with self.subTest(availability=availability):
                exit_code, payload, _stdout, _stderr, _dependencies = self._route(
                    usable=False,
                    purpose="checkpoint",
                    reviewer_availability=availability,
                )
                self.assertEqual(exit_code, 30)
                self.assertEqual(payload["route"], "blocker")

    def test_argparse_rejects_abbreviated_long_options_without_stderr(self):
        abbreviations = (
            "--rep",
            "--rep=value",
            "--review-m",
            "--review-m=value",
            "--req",
            "--req=value",
            "--qa-av",
            "--sec-av",
        )
        for abbreviation in abbreviations:
            with self.subTest(abbreviation=abbreviation):
                exit_code, payload, _stdout, stderr, _dependencies = self._route(
                    usable=False,
                    purpose="checkpoint",
                    extra=(abbreviation,),
                )
                self.assertEqual(exit_code, 31)
                self.assertEqual(payload["error"], "invalid_input")
                self.assertEqual(stderr, "")


if __name__ == "__main__":
    unittest.main()
