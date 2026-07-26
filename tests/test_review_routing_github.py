#!/usr/bin/env python3
"""Verhaltensspezifikation für den read-only GitHub-Probe-Adapter."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import unittest

from review_routing.adapters.github_gh import (
    API_VERSION,
    BlockEvidenceVerifier,
    CapabilityEvidenceVerifier,
    GitHubGhProbe,
    GitHubStatus,
    SubprocessCommand,
)
from review_routing.contracts import (
    BillingPrincipal,
    BlockEvidenceKind,
    BlockEvidenceReference,
    BlockEvidenceSource,
    BlockVerification,
    CapabilityEvidence,
    CapabilityEvidenceReference,
    CapabilityEvidenceSource,
    CapabilityVerification,
    ClockPort,
    CommandPort,
    CommandResult,
    DiagnosticStatus,
    EvidenceTrust,
    EvidenceVerificationStatus,
    MalformedResponseError,
    PermissionDeniedError,
    PortTimeoutError,
    ProbeRequest,
    PullRequestState,
    PullRequestStateSource,
    StatusPort,
    StatusSnapshot,
    VerifiedBlockEvidence,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/review-routing"
NOW = datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc)
REPOSITORY = "tomtastisch/agent-governance"
BASE_SHA = "a" * 40
HEAD_SHA = "b" * 40


def fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def response(
    status: int,
    payload: object,
    *,
    headers: dict[str, str] | None = None,
    stderr: bytes = b"",
    returncode: int | None = None,
) -> CommandResult:
    fields = {"content-type": "application/json", **(headers or {})}
    header_lines = [f"HTTP/2 {status}", *(f"{name}: {value}" for name, value in fields.items())]
    body = json.dumps(payload).encode("utf-8") if payload is not None else b""
    stdout = "\r\n".join(header_lines).encode("ascii") + b"\r\n\r\n" + body
    return CommandResult(
        return_code=(0 if 200 <= status < 300 else 1) if returncode is None else returncode,
        stdout=stdout,
        stderr=stderr,
    )


def pr_response(*, author: str = "author") -> CommandResult:
    return response(
        200,
        {
            "number": 5,
            "base": {"ref": "main", "sha": BASE_SHA},
            "head": {"sha": HEAD_SHA},
            "user": {"login": author},
        },
    )


class FakeCommand(CommandPort):
    def __init__(self, replies: dict[str, CommandResult | Exception]):
        self.replies = replies
        self.calls: list[tuple[tuple[str, ...], float]] = []

    def run(self, argv: tuple[str, ...], timeout_seconds: float) -> CommandResult:
        self.calls.append((argv, timeout_seconds))
        endpoint = argv[-1]
        result = self.replies.get(endpoint)
        if result is None:
            raise AssertionError(f"Unerwarteter Endpoint: {endpoint}")
        if isinstance(result, Exception):
            raise result
        return result


class FakeStatus(StatusPort):
    def __init__(
        self,
        snapshot: StatusSnapshot | None = None,
        error: Exception | None = None,
    ):
        self.snapshot = snapshot or StatusSnapshot(
            status=DiagnosticStatus.AVAILABLE,
            source="github_status",
            observed_at=NOW,
        )
        self.error = error
        self.calls: list[float] = []

    def fetch(self, timeout_seconds: float) -> StatusSnapshot:
        self.calls.append(timeout_seconds)
        if self.error is not None:
            raise self.error
        return self.snapshot


class FakeClock(ClockPort):
    def now(self) -> datetime:
        return NOW


def user_response(login: str = "tom") -> CommandResult:
    return response(200, {"login": login})


def personal_replies(
    usage: CommandResult | Exception | None = None,
    *,
    user: CommandResult | Exception | None = None,
) -> dict[str, CommandResult | Exception]:
    return {
        "/user": user or user_response(),
        "/users/tom/settings/billing/ai_credit/usage?year=2026&month=7": usage
        or response(200, fixture("ai-credits.json")),
    }


def request(**changes: object) -> ProbeRequest:
    values: dict[str, object] = {
        "repository": REPOSITORY,
        "review_mode": "manual",
        "manual_requester": "tom",
        "capability_reference": None,
        "block_reference": None,
    }
    values.update(changes)
    return ProbeRequest(**values)


def capability_reference(
    *,
    kind: str = "personal",
    identifier: str = "tom",
    repository: str = REPOSITORY,
    review_mode: str = "manual",
    observed_at: datetime = NOW - timedelta(minutes=5),
    expires_at: datetime = NOW + timedelta(minutes=10),
) -> CapabilityEvidenceReference:
    billing_principal = BillingPrincipal(
        kind=kind,
        identifier=identifier,
        review_mode=review_mode,
        requester="tom" if review_mode == "manual" else None,
        pull_request_author="author" if review_mode == "automatic" else None,
        source="github_api",
        observed_at=NOW - timedelta(minutes=10),
        expires_at=NOW + timedelta(minutes=15),
    )
    return CapabilityEvidenceReference(
        schema_version=1,
        source=CapabilityEvidenceSource.GITHUB_COMPLETED_REVIEW,
        repository=repository,
        review_mode=review_mode,
        principal_identity=billing_principal.identity,
        source_reference=(
            "expired_capability" if expires_at <= NOW else "verified_capability"
        ),
        pull_request_number=5,
        review_id=7,
    )


class FakeCapabilityVerifier:
    def verify(self, reference, repository, principal, review_mode, observed_at):
        if reference is None:
            return CapabilityVerification(
                EvidenceVerificationStatus.ABSENT,
                EvidenceTrust.DEVELOPMENT,
                None,
                None,
                None,
                None,
            )
        if (
            reference.repository != repository
            or reference.principal_identity != principal.identity
            or reference.review_mode != review_mode
        ):
            return CapabilityVerification(
                EvidenceVerificationStatus.INVALID,
                EvidenceTrust.DEVELOPMENT,
                reference.source,
                reference.source_reference,
                None,
                None,
            )
        if reference.source_reference == "expired_capability":
            return CapabilityVerification(
                EvidenceVerificationStatus.EXPIRED,
                EvidenceTrust.DEVELOPMENT,
                reference.source,
                reference.source_reference,
                "sha256:" + "a" * 64,
                None,
            )
        evidence = CapabilityEvidence(
            repository=repository,
            principal=principal,
            review_mode=review_mode,
            observed_at=observed_at - timedelta(minutes=5),
            expires_at=min(observed_at + timedelta(minutes=10), principal.expires_at),
            source=CapabilityEvidenceSource.GITHUB_COMPLETED_REVIEW,
            source_reference=reference.source_reference,
            artifact_digest="sha256:" + "a" * 64,
            pull_request_number=reference.pull_request_number,
            review_id=reference.review_id,
            review_commit_sha=HEAD_SHA,
        )
        return CapabilityVerification(
            EvidenceVerificationStatus.VERIFIED,
            EvidenceTrust.VERIFIED,
            evidence.source,
            evidence.source_reference,
            evidence.artifact_digest,
            evidence,
        )


class FakeBlockVerifier:
    def verify(self, reference, repository, principal, review_mode, observed_at):
        if reference is None:
            return BlockVerification(
                EvidenceVerificationStatus.ABSENT,
                EvidenceTrust.DEVELOPMENT,
                None,
                None,
                None,
                None,
            )
        kind = (
            BlockEvidenceKind.QUOTA_EXHAUSTED
            if reference.source_reference == "quota_exhausted"
            else BlockEvidenceKind.BUDGET_BLOCKED
        )
        evidence = VerifiedBlockEvidence(
            schema_version=1,
            kind=kind,
            repository=repository,
            principal_identity=principal.identity,
            review_mode=review_mode,
            observed_at=observed_at - timedelta(minutes=1),
            expires_at=observed_at + timedelta(minutes=10),
            source=BlockEvidenceSource.PROVIDER_API,
            source_reference=reference.source_reference,
            artifact_digest="sha256:" + "b" * 64,
        )
        return BlockVerification(
            EvidenceVerificationStatus.VERIFIED,
            EvidenceTrust.VERIFIED,
            evidence.source,
            evidence.source_reference,
            evidence.artifact_digest,
            evidence,
        )


def block_reference(kind: str) -> BlockEvidenceReference:
    return BlockEvidenceReference(
        schema_version=1,
        source=BlockEvidenceSource.PROVIDER_API,
        repository=REPOSITORY,
        review_mode="manual",
        principal_identity=capability_reference().principal_identity,
        source_reference=kind,
    )


def adapter(command: CommandPort, status: StatusPort | None = None) -> GitHubGhProbe:
    return GitHubGhProbe(
        command=command,
        status=status or FakeStatus(),
        clock=FakeClock(),
        capability_verifier=FakeCapabilityVerifier(),
        block_verifier=FakeBlockVerifier(),
    )


class GitHubProbeTest(unittest.TestCase):
    """Probe-Signale bleiben vollständig, principalgebunden und fail-closed."""

    def probe(
        self,
        replies: dict[str, CommandResult | Exception],
        probe_request: ProbeRequest | None = None,
        status: FakeStatus | None = None,
    ):
        command = FakeCommand(replies)
        probe_adapter = adapter(command, status)
        return probe_adapter.probe(probe_request or request()), command

    def test_personal_ai_credits_use_valid_capability_without_routing_on_remaining(self):
        report, command = self.probe(
            personal_replies(),
            request(capability_reference=capability_reference()),
        )

        self.assertTrue(report.copilot_usable)
        self.assertEqual(report.billing_model, "ai_credits")
        self.assertEqual(report.usage.used, 37)
        self.assertIsNone(report.usage.limit)
        self.assertIsNone(report.usage.remaining)
        self.assertEqual(report.usage.unit, "credits")
        self.assertEqual(report.billing_principal.kind, "personal")
        self.assertEqual(report.billing_principal.identifier, "tom")
        self.assertIn(
            "/users/tom/settings/billing/ai_credit/usage?year=2026&month=7",
            [call[0][-1] for call in command.calls],
        )

    def test_ai_credits_without_limit_preserve_unknown_remaining(self):
        payload = fixture("ai-credits.json")
        report, _ = self.probe(
            personal_replies(response(200, payload)),
            request(capability_reference=capability_reference()),
        )

        self.assertTrue(report.copilot_usable)
        self.assertIsNone(report.usage.limit)
        self.assertIsNone(report.usage.remaining)

    def test_legacy_premium_requests_are_used_only_after_ai_endpoint_is_absent(self):
        replies = personal_replies(response(404, {"message": "Not Found"}))
        replies["/users/tom/settings/billing/premium_request/usage?year=2026&month=7"] = response(
            200,
            fixture("legacy-premium.json"),
        )

        report, command = self.probe(replies, request(capability_reference=capability_reference()))

        self.assertEqual(report.billing_model, "premium_requests")
        self.assertEqual(report.usage.used, 7)
        self.assertIsNone(report.usage.remaining)
        self.assertEqual(
            [call[0][-1] for call in command.calls][-2:],
            [
                "/users/tom/settings/billing/ai_credit/usage?year=2026&month=7",
                "/users/tom/settings/billing/premium_request/usage?year=2026&month=7",
            ],
        )

    def test_confirmed_organization_seat_uses_organization_billing(self):
        replies = {
            "/user": user_response(),
            "/orgs/acme/members/tom/copilot": response(
                200,
                {"assignee": {"login": "tom"}, "assigning_team": {"slug": "engineering"}},
            ),
            "/organizations/acme/settings/billing/ai_credit/usage?year=2026&month=7&user=tom": response(
                200,
                fixture("ai-credits.json"),
            ),
        }

        report, _ = self.probe(
            replies,
            request(
                organization="acme",
                capability_reference=capability_reference(kind="organization", identifier="acme"),
            ),
        )

        self.assertEqual(report.billing_principal.kind, "organization")
        self.assertEqual(report.billing_principal.identifier, "acme")
        self.assertEqual(report.billing_context.kind, "organization")
        self.assertTrue(report.copilot_usable)

    def test_organization_seat_404_is_unknown_and_never_personal_fallback(self):
        replies = {
            **personal_replies(),
            "/orgs/acme/members/tom/copilot": response(404, {"message": "Not Found"}),
        }

        report, _ = self.probe(replies, request(organization="acme"))

        self.assertEqual(report.billing_principal.kind, "unknown")
        self.assertEqual(report.billing_context.kind, "unknown")
        self.assertEqual(report.billing_model, "unknown")
        self.assertFalse(report.copilot_usable)

    def test_manual_requester_and_automatic_pr_author_are_distinct_candidates(self):
        manual, _ = self.probe(personal_replies())
        automatic_replies = {
            "/user": user_response(),
            f"/repos/{REPOSITORY}/pulls/5": pr_response(author="author"),
            "/users/author/settings/billing/ai_credit/usage?year=2026&month=7": response(
                200,
                fixture("ai-credits.json"),
            ),
        }
        automatic, _ = self.probe(
            automatic_replies,
            request(
                review_mode="automatic",
                manual_requester=None,
                pull_request_number=5,
            ),
        )

        self.assertEqual(manual.requester, "tom")
        self.assertIsNone(manual.pull_request_author)
        self.assertEqual(manual.billing_principal.identifier, "tom")
        self.assertIsNone(automatic.requester)
        self.assertEqual(automatic.pull_request_author, "author")
        self.assertEqual(automatic.billing_principal.identifier, "author")

    def test_ambiguous_selectors_fail_closed_without_billing_guess(self):
        report, command = self.probe(
            {"/user": user_response()},
            request(organization="acme", enterprise="enterprise"),
        )

        self.assertEqual(report.routing_status, DiagnosticStatus.UNKNOWN)
        self.assertFalse(report.copilot_usable)
        self.assertEqual(report.billing_principal.kind, "unknown")
        self.assertEqual(len(command.calls), 1)

    def test_unknown_enterprise_and_cost_center_contexts_fail_closed(self):
        cases = (
            request(enterprise="enterprise"),
            request(cost_center="cost-center"),
        )
        for probe_request in cases:
            with self.subTest(probe_request=probe_request):
                report, _ = self.probe({"/user": user_response()}, probe_request)
                self.assertEqual(report.routing_status, DiagnosticStatus.UNKNOWN)
                self.assertEqual(report.billing_model, "unknown")
                self.assertFalse(report.copilot_usable)

    def test_usage_payload_cannot_claim_quota_or_budget_block(self):
        for status in ("quota_exhausted", "budget_blocked"):
            with self.subTest(status=status):
                payload = {**fixture("ai-credits.json"), "status": status}
                report, _ = self.probe(
                    personal_replies(response(200, payload)),
                    request(capability_reference=capability_reference()),
                )
                self.assertTrue(report.copilot_usable)
                self.assertIsNone(report.signals.billing_status)

    def test_permission_rate_and_provider_failures_are_sanitized(self):
        cases = (
            (403, {}, DiagnosticStatus.PERMISSION_DENIED),
            (429, {}, DiagnosticStatus.RATE_LIMITED),
            (503, {}, DiagnosticStatus.PROVIDER_UNAVAILABLE),
            (
                403,
                {"x-ratelimit-remaining": "0"},
                DiagnosticStatus.RATE_LIMITED,
            ),
        )
        secret = b"authorization: SENSITIVE_VALUE"
        for status_code, headers, expected in cases:
            with self.subTest(status_code=status_code, headers=headers):
                report, _ = self.probe(
                    personal_replies(
                        response(status_code, {"message": "failure"}, headers=headers, stderr=secret)
                    )
                )
                serialized = json.dumps(report.to_dict(), sort_keys=True)
                self.assertEqual(report.technical_status, expected)
                self.assertFalse(report.copilot_usable)
                self.assertNotIn("sensitive_value", serialized.lower())
                self.assertNotIn("authorization", serialized.lower())

    def test_public_status_incident_is_a_provider_failure_even_when_billing_api_works(self):
        status = FakeStatus(
            StatusSnapshot(
                status=DiagnosticStatus.PROVIDER_UNAVAILABLE,
                source="github_status",
                observed_at=NOW,
            )
        )

        report, _ = self.probe(
            personal_replies(),
            request(capability_reference=capability_reference()),
            status=status,
        )

        self.assertEqual(report.signals.provider_status, DiagnosticStatus.PROVIDER_UNAVAILABLE)
        self.assertEqual(report.routing_status, DiagnosticStatus.PROVIDER_UNAVAILABLE)
        self.assertEqual(report.technical_status, DiagnosticStatus.PROVIDER_UNAVAILABLE)
        self.assertEqual(report.technical_error, "provider_unavailable")
        self.assertFalse(report.copilot_usable)

    def test_empty_malformed_and_incomplete_payloads_are_unknown_and_incomplete(self):
        malformed = CommandResult(
            return_code=0,
            stdout=b"HTTP/2 200\r\ncontent-type: application/json\r\n\r\n{",
            stderr=b"",
        )
        cases = (
            response(200, None),
            malformed,
            response(200, {"billing_model": "ai_credits", "status": "available"}),
        )
        for result in cases:
            with self.subTest(result=result.stdout[-20:]):
                report, _ = self.probe(personal_replies(result))
                self.assertEqual(report.technical_status, DiagnosticStatus.UNKNOWN)
                self.assertEqual(report.technical_error, "incomplete_response")
                self.assertFalse(report.copilot_usable)

    def test_technical_permission_failure_overrides_verified_block_cache(self):
        report, _ = self.probe(
            personal_replies(
                response(
                    200,
                    fixture("ai-credits.json"),
                ),
                user=response(403, {"message": "Resource not accessible"}),
            ),
            request(
                capability_reference=capability_reference(),
                block_reference=block_reference("budget_blocked"),
            ),
        )

        self.assertEqual(report.routing_status, DiagnosticStatus.PERMISSION_DENIED)
        self.assertEqual(report.technical_status, DiagnosticStatus.PERMISSION_DENIED)
        self.assertFalse(report.copilot_usable)

    def test_rate_limit_has_precedence_over_an_independent_permission_failure(self):
        report, _ = self.probe(
            personal_replies(
                response(429, {"message": "rate limited"}),
                user=response(403, {"message": "Resource not accessible"}),
            )
        )

        self.assertEqual(report.routing_status, DiagnosticStatus.RATE_LIMITED)
        self.assertEqual(report.technical_status, DiagnosticStatus.RATE_LIMITED)
        self.assertEqual(report.technical_error, "rate_limited")

    def test_capability_must_be_present_current_and_bound_to_principal(self):
        cases = (
            None,
            capability_reference(expires_at=NOW),
            capability_reference(identifier="other"),
            capability_reference(repository="tomtastisch/other"),
        )
        for evidence in cases:
            with self.subTest(evidence=evidence):
                report, _ = self.probe(
                    personal_replies(),
                    request(capability_reference=evidence),
                )
                self.assertFalse(report.copilot_usable)
                self.assertEqual(report.routing_status, DiagnosticStatus.UNKNOWN)

        valid, _ = self.probe(
            personal_replies(),
            request(capability_reference=capability_reference()),
        )
        self.assertTrue(valid.copilot_usable)
        self.assertEqual(valid.capability_status, "valid")

    def test_every_gh_call_uses_documented_version_header_and_no_secret_argument(self):
        report, command = self.probe(personal_replies())
        self.assertFalse(report.copilot_usable)

        for argv, timeout in command.calls:
            self.assertEqual(argv[:4], ("gh", "api", "--include", "--header"))
            self.assertEqual(argv[4], f"X-GitHub-Api-Version: {API_VERSION}")
            self.assertIn(("--method", "GET"), tuple(zip(argv, argv[1:])))
            self.assertGreater(timeout, 0)
            flattened = " ".join(argv).lower()
            self.assertNotIn("authorization", flattened)
            self.assertNotIn("token", flattened)

    def test_report_serialization_contains_only_closed_sanitized_fields(self):
        report, _ = self.probe(
            personal_replies(),
            request(capability_reference=capability_reference()),
        )

        document = report.to_dict()

        self.assertEqual(
            set(document),
            {
                "schema_version",
                "observed_at",
                "repository",
                "review_mode",
                "requester",
                "pull_request_author",
                "billing_principal",
                "billing_context",
                "billing_model",
                "usage",
                "signals",
                "routing_status",
                "technical_status",
                "technical_error",
                "copilot_usable",
                "capability_evidence",
                "block_evidence",
                "evidence",
                "warnings",
            },
        )
        serialized = json.dumps(document, sort_keys=True)
        for forbidden in ("stderr", "stdout", "authorization", "cookie", "token"):
            self.assertNotIn(forbidden, serialized.lower())


class PullRequestStateTest(unittest.TestCase):
    """PR-Metadaten werden vollständig aus der GitHub-API gebunden."""

    def test_exact_pr_state_is_loaded_from_api(self):
        command = FakeCommand({f"/repos/{REPOSITORY}/pulls/5": pr_response(author="author")})
        probe_adapter = adapter(command)

        state = probe_adapter.load(REPOSITORY, 5)

        self.assertEqual(
            state,
            PullRequestState(
                repository=REPOSITORY,
                pull_request_number=5,
                base_ref="main",
                api_base_sha=BASE_SHA,
                head_sha=HEAD_SHA,
                author="author",
                observed_at=NOW,
                source=PullRequestStateSource.GITHUB_API,
            ),
        )

    def test_invalid_or_incomplete_pr_metadata_is_typed_and_sanitized(self):
        secret = b"cookie: session=SENSITIVE_VALUE"
        cases = (
            response(200, {"number": 5}),
            response(503, {}, stderr=secret),
        )
        for result in cases:
            with self.subTest(result=result.return_code):
                probe_adapter = adapter(
                    FakeCommand({f"/repos/{REPOSITORY}/pulls/5": result})
                )
                with self.assertRaisesRegex(
                    (MalformedResponseError, PortTimeoutError, RuntimeError),
                    r"^(?!.*(?:cookie|session)).*$",
                ):
                    probe_adapter.load(REPOSITORY, 5)


class ProductionClientBoundaryTest(unittest.TestCase):
    """Produktive Clients bleiben argv-/timeoutgebunden und ohne Shell-Ausführung."""

    def test_subprocess_client_uses_argv_without_shell(self):
        calls = []

        def runner(argv, **kwargs):
            calls.append((argv, kwargs))
            return subprocess.CompletedProcess(argv, 0, stdout=b"{}", stderr=b"")

        result = SubprocessCommand(runner=runner).run(("gh", "api", "/user"), 3.0)

        self.assertEqual(result.return_code, 0)
        self.assertEqual(calls[0][0], ("gh", "api", "/user"))
        self.assertIs(calls[0][1]["shell"], False)
        self.assertEqual(calls[0][1]["timeout"], 3.0)

    def test_subprocess_timeout_is_typed_without_raw_command_output(self):
        def runner(argv, **kwargs):
            raise subprocess.TimeoutExpired(
                argv,
                kwargs["timeout"],
                stderr=b"credential-material=SENSITIVE_VALUE",
            )

        with self.assertRaisesRegex(PortTimeoutError, "^GitHub command timed out$"):
            SubprocessCommand(runner=runner).run(("gh", "api", "/user"), 1.0)

    def test_include_parser_uses_the_last_complete_http_response_block(self):
        final = pr_response(author="author").stdout
        combined = CommandResult(
            return_code=0,
            stdout=b"HTTP/1.1 100 Continue\r\ncontent-length: 0\r\n\r\n" + final,
            stderr=b"",
        )
        probe_adapter = adapter(
            FakeCommand({f"/repos/{REPOSITORY}/pulls/5": combined})
        )

        state = probe_adapter.load(REPOSITORY, 5)

        self.assertEqual(state.head_sha, HEAD_SHA)

    def test_empty_stdout_uses_only_known_stderr_http_diagnostic(self):
        secret = b"authorization=SENSITIVE_VALUE request failed: HTTP 403"
        probe_adapter = adapter(
            FakeCommand(
                {
                    f"/repos/{REPOSITORY}/pulls/5": CommandResult(
                        return_code=1,
                        stdout=b"",
                        stderr=secret,
                    )
                }
            )
        )

        with self.assertRaisesRegex(
            PermissionDeniedError,
            r"^GitHub API permission denied$",
        ):
            probe_adapter.load(REPOSITORY, 5)

    def test_public_status_client_parses_only_operational_components(self):
        payload = json.dumps(fixture("status-operational.json")).encode("utf-8")

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def read(self):
                return payload

        calls = []

        def opener(request_object, timeout):
            calls.append((request_object, timeout))
            return Response()

        snapshot = GitHubStatus(opener=opener, clock=FakeClock()).fetch(2.0)

        self.assertEqual(snapshot.status, DiagnosticStatus.AVAILABLE)
        self.assertEqual(snapshot.observed_at, NOW)
        self.assertEqual(calls[0][1], 2.0)
        self.assertEqual(
            calls[0][0].full_url,
            "https://www.githubstatus.com/api/v2/components.json",
        )


class ClosedContractTest(unittest.TestCase):
    """Ungültige Werte werden an der Portgrenze abgelehnt."""

    def test_request_rejects_wrong_mode_and_ambiguous_manual_fields(self):
        with self.assertRaises(ValueError):
            request(review_mode="maybe")
        with self.assertRaises(ValueError):
            request(manual_requester=None)
        with self.assertRaises(ValueError):
            request(review_mode="automatic", manual_requester="tom", pull_request_number=5)

    def test_command_result_requires_bytes_and_non_boolean_return_code(self):
        with self.assertRaises(ValueError):
            CommandResult(return_code=True, stdout=b"", stderr=b"")
        with self.assertRaises(ValueError):
            CommandResult(return_code=0, stdout="{}", stderr=b"")

    def test_principal_and_capability_reject_naive_evidence_timestamps(self):
        naive = datetime(2026, 7, 26, 12, 0)
        with self.assertRaises(ValueError):
            BillingPrincipal(
                kind="personal",
                identifier="tom",
                review_mode="manual",
                requester="tom",
                pull_request_author=None,
                source="github_api",
                observed_at=naive,
                expires_at=naive + timedelta(minutes=15),
            )


if __name__ == "__main__":
    unittest.main()
