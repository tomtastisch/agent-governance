"""Read-only GitHub- und Status-Adapter mit sanitisierten öffentlichen Grenzen."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import re
import subprocess
from typing import Callable, Mapping
from urllib import error as urlerror
from urllib.parse import urlencode
from urllib import request as urlrequest

from review_routing.contracts import (
    AdapterFactory,
    BillingContext,
    BillingPrincipal,
    BlockEvidenceKind,
    BlockEvidenceReference,
    BlockEvidenceSource,
    BlockEvidenceVerifierPort,
    BlockVerification,
    CapabilityEvidence,
    CapabilityEvidenceReference,
    CapabilityEvidenceSource,
    CapabilityEvidenceVerifierPort,
    CapabilityVerification,
    ClockPort,
    CommandPort,
    CommandResult,
    DiagnosticStatus,
    EvidenceTrust,
    EvidenceVerificationStatus,
    IncompleteResponseError,
    MalformedResponseError,
    PermissionDeniedError,
    PortTimeoutError,
    ProbePort,
    ProbePortError,
    ProbeReport,
    ProbeRequest,
    ProbeSignals,
    ProbeTechnicalError,
    ProviderUnavailableError,
    PullRequestState,
    PullRequestStatePort,
    PullRequestStateSource,
    RateLimitedError,
    StatusPort,
    StatusSnapshot,
    OperatorEvidencePin,
    UnknownContextError,
    Usage,
    VerifiedBlockEvidence,
    require_repository,
)


API_VERSION = "2026-03-10"
STATUS_URL = "https://www.githubstatus.com/api/v2/components.json"
DEFAULT_TIMEOUT_SECONDS = 10.0
PRINCIPAL_VALIDITY = timedelta(minutes=15)
CAPABILITY_VALIDITY = timedelta(minutes=15)
COPILOT_REVIEWERS = {
    "copilot-pull-request-reviewer[bot]",
    "github-copilot[bot]",
}


class _NotFoundError(UnknownContextError):
    """Interner Fallback-Marker; wird nie nach außen serialisiert."""


@dataclass(frozen=True)
class _ApiResponse:
    payload: Mapping[str, object]
    safe_headers: Mapping[str, str]


class SubprocessCommand(CommandPort):
    """Führt `gh` ausschließlich als argv-Prozess ohne Shell aus."""

    def __init__(self, runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run):
        self._runner = runner

    def run(self, argv: tuple[str, ...], timeout_seconds: float) -> CommandResult:
        if (
            not isinstance(argv, tuple)
            or not argv
            or any(not isinstance(item, str) or not item or "\x00" in item for item in argv)
        ):
            raise ValueError("argv must be a non-empty tuple of NUL-free strings")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be finite and positive")
        try:
            result = self._runner(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=float(timeout_seconds),
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired as error:
            raise PortTimeoutError("GitHub command timed out") from error
        except OSError as error:
            raise ProviderUnavailableError("GitHub command is unavailable") from error
        return CommandResult(
            return_code=result.returncode,
            stdout=bytes(result.stdout),
            stderr=bytes(result.stderr),
        )


class SystemClock(ClockPort):
    """Timezone-aware Produktionsuhr."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class GitHubStatus(StatusPort):
    """Öffentlicher, injizierbarer Statuspage-Client ohne Authentifizierung."""

    def __init__(
        self,
        opener: Callable[..., object] = urlrequest.urlopen,
        clock: ClockPort | None = None,
    ):
        self._opener = opener
        self._clock = clock or SystemClock()

    def fetch(self, timeout_seconds: float) -> StatusSnapshot:
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be finite and positive")
        request = urlrequest.Request(
            STATUS_URL,
            headers={"Accept": "application/json", "User-Agent": "agent-governance-review-routing"},
            method="GET",
        )
        try:
            with self._opener(request, timeout=float(timeout_seconds)) as response:
                body = response.read()
        except TimeoutError as error:
            raise PortTimeoutError("GitHub status request timed out") from error
        except (urlerror.URLError, OSError) as error:
            raise ProviderUnavailableError("GitHub status is unavailable") from error
        try:
            document = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as error:
            raise MalformedResponseError("GitHub status response is malformed") from error
        if not isinstance(document, dict) or not isinstance(document.get("components"), list):
            raise IncompleteResponseError("GitHub status response is incomplete")
        relevant: dict[str, str] = {}
        for component in document["components"]:
            if not isinstance(component, dict):
                raise IncompleteResponseError("GitHub status response is incomplete")
            name = component.get("name")
            status = component.get("status")
            if not isinstance(name, str) or not isinstance(status, str):
                raise IncompleteResponseError("GitHub status response is incomplete")
            normalized_name = name.casefold()
            if normalized_name in {"api requests", "copilot"}:
                if normalized_name in relevant:
                    raise IncompleteResponseError("GitHub status response is incomplete")
                relevant[normalized_name] = status
        if set(relevant) != {"api requests", "copilot"}:
            raise IncompleteResponseError("GitHub status response is incomplete")
        provider_status = (
            DiagnosticStatus.AVAILABLE
            if all(status == "operational" for status in relevant.values())
            else DiagnosticStatus.PROVIDER_UNAVAILABLE
        )
        return StatusSnapshot(
            status=provider_status,
            source="github_status",
            observed_at=self._clock.now(),
        )


def _parse_include_output(output: bytes) -> tuple[int, dict[str, str], bytes]:
    try:
        text = output.decode("utf-8")
    except UnicodeDecodeError as error:
        raise MalformedResponseError("GitHub API response is malformed") from error
    normalized = text.replace("\r\n", "\n")
    starts = [match.start() for match in re.finditer(r"(?m)^HTTP/\S+ [0-9]{3}(?: .*)?$", normalized)]
    if not starts:
        raise MalformedResponseError("GitHub API response is malformed")
    block_start = starts[-1]
    marker_index = normalized.find("\n\n", block_start)
    if marker_index < 0:
        raise MalformedResponseError("GitHub API response is malformed")
    header_text = normalized[block_start:marker_index]
    body_text = normalized[marker_index + 2 :]
    lines = header_text.splitlines()
    if not lines or not lines[0].startswith("HTTP/"):
        raise MalformedResponseError("GitHub API response is malformed")
    status_parts = lines[0].split()
    if len(status_parts) < 2 or not status_parts[1].isdigit():
        raise MalformedResponseError("GitHub API response is malformed")
    headers: dict[str, str] = {}
    safe_names = {"content-type", "retry-after", "x-ratelimit-remaining"}
    for line in lines[1:]:
        if ":" not in line:
            raise MalformedResponseError("GitHub API response is malformed")
        name, value = line.split(":", 1)
        normalized_name = name.strip().casefold()
        if normalized_name in safe_names:
            headers[normalized_name] = value.strip()
    return int(status_parts[1]), headers, body_text.encode("utf-8")


def _error_for_failed_command(result: CommandResult) -> ProbePortError:
    """Klassifiziert ausschließlich bekannte Statusmarker, nie rohe stderr-Inhalte."""
    diagnostic = result.stderr.decode("utf-8", errors="replace")
    match = re.search(r"(?:HTTP(?:/[\d.]+)?\s+|status(?:\s+code)?[=: ]+)(\d{3})\b", diagnostic, re.I)
    if match is None:
        return UnknownContextError("GitHub API command failed without a complete response")
    return _error_for_http(int(match.group(1)), {})


def _error_for_http(status: int, headers: Mapping[str, str]) -> ProbePortError:
    if status == 429 or headers.get("x-ratelimit-remaining") == "0":
        return RateLimitedError("GitHub API rate limit reached")
    if status in {401, 403}:
        return PermissionDeniedError("GitHub API permission denied")
    if status in {500, 502, 503, 504}:
        return ProviderUnavailableError("GitHub API is unavailable")
    if status == 404:
        return _NotFoundError("GitHub API resource not found")
    return UnknownContextError("GitHub API response status is unknown")


def _request_json(
    command: CommandPort,
    timeout_seconds: float,
    endpoint: str,
) -> _ApiResponse:
    result = command.run(
        (
            "gh",
            "api",
            "--include",
            "--header",
            f"X-GitHub-Api-Version: {API_VERSION}",
            "--header",
            "Accept: application/vnd.github+json",
            "--method",
            "GET",
            endpoint,
        ),
        timeout_seconds,
    )
    if not result.stdout.strip() and result.return_code != 0:
        raise _error_for_failed_command(result)
    status, headers, body = _parse_include_output(result.stdout)
    if status < 200 or status >= 300 or result.return_code != 0:
        raise _error_for_http(status, headers)
    if not body.strip():
        raise IncompleteResponseError("GitHub API response is incomplete")
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MalformedResponseError("GitHub API response is malformed") from error
    if not isinstance(payload, dict):
        raise IncompleteResponseError("GitHub API response is incomplete")
    return _ApiResponse(payload=payload, safe_headers=headers)


def _diagnostic_for_error(error: Exception) -> DiagnosticStatus:
    if isinstance(error, PermissionDeniedError):
        return DiagnosticStatus.PERMISSION_DENIED
    if isinstance(error, RateLimitedError):
        return DiagnosticStatus.RATE_LIMITED
    if isinstance(error, (ProviderUnavailableError, PortTimeoutError)):
        return DiagnosticStatus.PROVIDER_UNAVAILABLE
    return DiagnosticStatus.UNKNOWN


def _technical_error_code(error: Exception) -> ProbeTechnicalError:
    if isinstance(error, PermissionDeniedError):
        return ProbeTechnicalError.PERMISSION_DENIED
    if isinstance(error, RateLimitedError):
        return ProbeTechnicalError.RATE_LIMITED
    if isinstance(error, PortTimeoutError):
        return ProbeTechnicalError.TIMEOUT
    if isinstance(error, ProviderUnavailableError):
        return ProbeTechnicalError.PROVIDER_UNAVAILABLE
    if isinstance(error, UnknownContextError):
        return ProbeTechnicalError.UNKNOWN_CONTEXT
    return ProbeTechnicalError.INCOMPLETE_RESPONSE


def _number(value: object, field_name: str, *, optional: bool = False) -> float | None:
    if value is None and optional:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise IncompleteResponseError(f"GitHub billing field '{field_name}' is incomplete")
    return float(value)


def _capability_status(
    verification: CapabilityVerification,
) -> str:
    if verification.status is EvidenceVerificationStatus.ABSENT:
        return "absent"
    if verification.status is EvidenceVerificationStatus.EXPIRED:
        return "expired"
    if verification.status is EvidenceVerificationStatus.INVALID:
        return "invalid"
    return "valid"


def _canonical_digest(document: Mapping[str, object]) -> str:
    canonical = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _parse_artifact(artifact: bytes) -> Mapping[str, object]:
    try:
        document = json.loads(artifact)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as error:
        raise MalformedResponseError("Operator evidence artifact is malformed") from error
    if not isinstance(document, dict):
        raise IncompleteResponseError("Operator evidence artifact is incomplete")
    return document


def _parse_utc(value: object, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise IncompleteResponseError(f"Evidence field '{field_name}' is incomplete")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise IncompleteResponseError(f"Evidence field '{field_name}' is incomplete") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise IncompleteResponseError(f"Evidence field '{field_name}' is incomplete")
    return parsed.astimezone(timezone.utc)


def _absent_capability() -> CapabilityVerification:
    return CapabilityVerification(
        status=EvidenceVerificationStatus.ABSENT,
        trust=EvidenceTrust.DEVELOPMENT,
        source=None,
        source_reference=None,
        artifact_digest=None,
        evidence=None,
    )


def _invalid_capability(
    reference: CapabilityEvidenceReference,
    artifact_digest: str | None = None,
    *,
    expired: bool = False,
) -> CapabilityVerification:
    return CapabilityVerification(
        status=(
            EvidenceVerificationStatus.EXPIRED
            if expired
            else EvidenceVerificationStatus.INVALID
        ),
        trust=EvidenceTrust.DEVELOPMENT,
        source=reference.source,
        source_reference=reference.source_reference,
        artifact_digest=artifact_digest,
        evidence=None,
    )


class CapabilityEvidenceVerifier(CapabilityEvidenceVerifierPort):
    """Verifiziert GitHub-Review- oder extern gepinnte Operator-Capabilities."""

    def __init__(
        self,
        command: CommandPort,
        operator_pins: Mapping[str, OperatorEvidencePin],
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        self._command = command
        self._operator_pins = dict(operator_pins)
        self._timeout_seconds = timeout_seconds

    def verify(
        self,
        reference: CapabilityEvidenceReference | None,
        repository: str,
        principal: BillingPrincipal,
        review_mode: str,
        observed_at: datetime,
    ) -> CapabilityVerification:
        if reference is None:
            return _absent_capability()
        if (
            reference.repository != repository
            or reference.principal_identity != principal.identity
            or reference.review_mode != review_mode
        ):
            return _invalid_capability(reference)
        if reference.source is CapabilityEvidenceSource.GITHUB_COMPLETED_REVIEW:
            return self._verify_github(reference, principal, observed_at)
        return self._verify_operator(reference, principal, observed_at)

    def _verify_github(
        self,
        reference: CapabilityEvidenceReference,
        principal: BillingPrincipal,
        observed_at: datetime,
    ) -> CapabilityVerification:
        assert reference.pull_request_number is not None
        assert reference.review_id is not None
        response = _request_json(
            self._command,
            self._timeout_seconds,
            (
                f"/repos/{reference.repository}/pulls/"
                f"{reference.pull_request_number}/reviews/{reference.review_id}"
            ),
        ).payload
        expected_keys = {"id", "user", "state", "commit_id", "submitted_at"}
        if not expected_keys.issubset(response):
            return _invalid_capability(reference)
        user = response["user"]
        if (
            response["id"] != reference.review_id
            or not isinstance(user, dict)
            or user.get("login") not in COPILOT_REVIEWERS
            or response["state"] != "COMMENTED"
            or not isinstance(response["commit_id"], str)
        ):
            return _invalid_capability(reference)
        try:
            submitted_at = _parse_utc(response["submitted_at"], "submitted_at")
            review_commit_sha = response["commit_id"]
            if len(review_commit_sha) != 40 or any(
                character not in "0123456789abcdef" for character in review_commit_sha
            ):
                raise ValueError
        except (IncompleteResponseError, ValueError):
            return _invalid_capability(reference)
        selected = {
            "commit_id": review_commit_sha,
            "id": reference.review_id,
            "pull_request_number": reference.pull_request_number,
            "repository": reference.repository,
            "reviewer": user["login"],
            "state": response["state"],
            "submitted_at": submitted_at.isoformat().replace("+00:00", "Z"),
        }
        artifact_digest = _canonical_digest(selected)
        expires_at = min(submitted_at + CAPABILITY_VALIDITY, principal.expires_at)
        if not submitted_at <= observed_at < expires_at:
            return _invalid_capability(reference, artifact_digest, expired=True)
        evidence = CapabilityEvidence(
            repository=reference.repository,
            principal=principal,
            review_mode=reference.review_mode,
            observed_at=submitted_at,
            expires_at=expires_at,
            source=CapabilityEvidenceSource.GITHUB_COMPLETED_REVIEW,
            source_reference=f"github_review_{reference.review_id}",
            artifact_digest=artifact_digest,
            pull_request_number=reference.pull_request_number,
            review_id=reference.review_id,
            review_commit_sha=review_commit_sha,
        )
        return CapabilityVerification(
            status=EvidenceVerificationStatus.VERIFIED,
            trust=EvidenceTrust.VERIFIED,
            source=evidence.source,
            source_reference=evidence.source_reference,
            artifact_digest=artifact_digest,
            evidence=evidence,
        )

    def _verify_operator(
        self,
        reference: CapabilityEvidenceReference,
        principal: BillingPrincipal,
        observed_at: datetime,
    ) -> CapabilityVerification:
        assert reference.artifact is not None
        document = _parse_artifact(reference.artifact)
        artifact_digest = _canonical_digest(document)
        pin = self._operator_pins.get(reference.source_reference)
        if pin is None or pin.expected_digest != artifact_digest:
            return _invalid_capability(reference, artifact_digest)
        expected_keys = {
            "schema_version",
            "repository",
            "principal_identity",
            "review_mode",
            "observed_at",
            "expires_at",
            "source_reference",
        }
        if set(document) != expected_keys:
            return _invalid_capability(reference, artifact_digest)
        try:
            identity = tuple(document["principal_identity"])
            artifact_observed_at = _parse_utc(document["observed_at"], "observed_at")
            expires_at = _parse_utc(document["expires_at"], "expires_at")
        except (TypeError, IncompleteResponseError):
            return _invalid_capability(reference, artifact_digest)
        if (
            document["schema_version"] != 1
            or document["repository"] != reference.repository
            or identity != principal.identity
            or document["review_mode"] != reference.review_mode
            or document["source_reference"] != reference.source_reference
            or expires_at > principal.expires_at
        ):
            return _invalid_capability(reference, artifact_digest)
        if not artifact_observed_at <= observed_at < expires_at:
            return _invalid_capability(reference, artifact_digest, expired=True)
        evidence = CapabilityEvidence(
            repository=reference.repository,
            principal=principal,
            review_mode=reference.review_mode,
            observed_at=artifact_observed_at,
            expires_at=expires_at,
            source=CapabilityEvidenceSource.OPERATOR_PINNED,
            source_reference=reference.source_reference,
            artifact_digest=artifact_digest,
        )
        return CapabilityVerification(
            status=EvidenceVerificationStatus.VERIFIED,
            trust=EvidenceTrust.VERIFIED,
            source=evidence.source,
            source_reference=evidence.source_reference,
            artifact_digest=artifact_digest,
            evidence=evidence,
        )


def _absent_block() -> BlockVerification:
    return BlockVerification(
        status=EvidenceVerificationStatus.ABSENT,
        trust=EvidenceTrust.DEVELOPMENT,
        source=None,
        source_reference=None,
        artifact_digest=None,
        evidence=None,
    )


class BlockEvidenceVerifier(BlockEvidenceVerifierPort):
    """Verifiziert Blockaden; Caller-Artefakte greifen nur mit externem Digest-Pin."""

    def __init__(self, operator_pins: Mapping[str, OperatorEvidencePin]):
        self._operator_pins = dict(operator_pins)

    def _invalid(
        self,
        reference: BlockEvidenceReference,
        artifact_digest: str | None = None,
        *,
        expired: bool = False,
    ) -> BlockVerification:
        return BlockVerification(
            status=(
                EvidenceVerificationStatus.EXPIRED
                if expired
                else EvidenceVerificationStatus.INVALID
            ),
            trust=EvidenceTrust.DEVELOPMENT,
            source=reference.source,
            source_reference=reference.source_reference,
            artifact_digest=artifact_digest,
            evidence=None,
        )

    def verify(
        self,
        reference: BlockEvidenceReference | None,
        repository: str,
        principal: BillingPrincipal,
        review_mode: str,
        observed_at: datetime,
    ) -> BlockVerification:
        if reference is None:
            return _absent_block()
        if (
            reference.repository != repository
            or reference.principal_identity != principal.identity
            or reference.review_mode != review_mode
            or reference.source is not BlockEvidenceSource.OPERATOR_PINNED
            or reference.artifact is None
        ):
            return self._invalid(reference)
        document = _parse_artifact(reference.artifact)
        artifact_digest = _canonical_digest(document)
        pin = self._operator_pins.get(reference.source_reference)
        if pin is None or pin.expected_digest != artifact_digest:
            return self._invalid(reference, artifact_digest)
        expected_keys = {
            "schema_version",
            "kind",
            "repository",
            "principal_identity",
            "review_mode",
            "observed_at",
            "expires_at",
            "source_reference",
        }
        if set(document) != expected_keys:
            return self._invalid(reference, artifact_digest)
        try:
            kind = BlockEvidenceKind(document["kind"])
            identity = tuple(document["principal_identity"])
            artifact_observed_at = _parse_utc(document["observed_at"], "observed_at")
            expires_at = _parse_utc(document["expires_at"], "expires_at")
        except (ValueError, TypeError, IncompleteResponseError):
            return self._invalid(reference, artifact_digest)
        if (
            document["schema_version"] != 1
            or document["repository"] != repository
            or identity != principal.identity
            or document["review_mode"] != review_mode
            or document["source_reference"] != reference.source_reference
            or expires_at > principal.expires_at
        ):
            return self._invalid(reference, artifact_digest)
        if not artifact_observed_at <= observed_at < expires_at:
            return self._invalid(reference, artifact_digest, expired=True)
        evidence = VerifiedBlockEvidence(
            schema_version=1,
            kind=kind,
            repository=repository,
            principal_identity=principal.identity,
            review_mode=review_mode,
            observed_at=artifact_observed_at,
            expires_at=expires_at,
            source=BlockEvidenceSource.OPERATOR_PINNED,
            source_reference=reference.source_reference,
            artifact_digest=artifact_digest,
        )
        return BlockVerification(
            status=EvidenceVerificationStatus.VERIFIED,
            trust=EvidenceTrust.VERIFIED,
            source=evidence.source,
            source_reference=evidence.source_reference,
            artifact_digest=artifact_digest,
            evidence=evidence,
        )


_STATUS_PRECEDENCE = (
    DiagnosticStatus.BUDGET_BLOCKED,
    DiagnosticStatus.QUOTA_EXHAUSTED,
    DiagnosticStatus.RATE_LIMITED,
    DiagnosticStatus.PROVIDER_UNAVAILABLE,
    DiagnosticStatus.PERMISSION_DENIED,
    DiagnosticStatus.UNKNOWN,
    DiagnosticStatus.LOW_BUDGET,
    DiagnosticStatus.AVAILABLE,
)


class GitHubGhProbe(ProbePort, PullRequestStatePort):
    """Sammelt GitHub-Evidenz read-only und lässt unklare Kontexte geschlossen."""

    def __init__(
        self,
        command: CommandPort,
        status: StatusPort,
        clock: ClockPort,
        capability_verifier: CapabilityEvidenceVerifierPort,
        block_verifier: BlockEvidenceVerifierPort,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        self._command = command
        self._status = status
        self._clock = clock
        self._capability_verifier = capability_verifier
        self._block_verifier = block_verifier
        self._timeout_seconds = timeout_seconds

    def _request_json(self, endpoint: str) -> _ApiResponse:
        return _request_json(self._command, self._timeout_seconds, endpoint)

    def load(self, repository: str, pull_request_number: int) -> PullRequestState:
        require_repository(repository)
        if (
            isinstance(pull_request_number, bool)
            or not isinstance(pull_request_number, int)
            or pull_request_number <= 0
        ):
            raise ValueError("pull_request_number must be a positive integer")
        response = self._request_json(f"/repos/{repository}/pulls/{pull_request_number}")
        payload = response.payload
        try:
            number = payload["number"]
            base = payload["base"]
            head = payload["head"]
            user = payload["user"]
            if (
                isinstance(number, bool)
                or not isinstance(number, int)
                or number != pull_request_number
                or not isinstance(base, dict)
                or not isinstance(head, dict)
                or not isinstance(user, dict)
            ):
                raise TypeError
            base_ref = base["ref"]
            base_sha = base["sha"]
            head_sha = head["sha"]
            author = user["login"]
            if not all(isinstance(value, str) for value in (base_ref, base_sha, head_sha, author)):
                raise TypeError
            return PullRequestState(
                repository=repository,
                pull_request_number=pull_request_number,
                base_ref=base_ref,
                api_base_sha=base_sha,
                head_sha=head_sha,
                author=author,
                observed_at=self._clock.now(),
                source=PullRequestStateSource.GITHUB_API,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise IncompleteResponseError("GitHub pull request response is incomplete") from error

    def _provider_status(self) -> tuple[DiagnosticStatus, Exception | None]:
        try:
            return self._status.fetch(self._timeout_seconds).status, None
        except ProbePortError as error:
            return _diagnostic_for_error(error), error

    def _authenticated_user(self) -> tuple[str | None, DiagnosticStatus, Exception | None]:
        try:
            payload = self._request_json("/user").payload
            login = payload.get("login")
            if not isinstance(login, str) or not login:
                raise IncompleteResponseError("GitHub user response is incomplete")
            return login, DiagnosticStatus.AVAILABLE, None
        except ProbePortError as error:
            return None, _diagnostic_for_error(error), error

    def _candidate(
        self,
        request: ProbeRequest,
    ) -> tuple[str, str | None, PullRequestState | None, Exception | None]:
        if request.review_mode == "manual":
            assert request.manual_requester is not None
            return request.manual_requester, None, None, None
        assert request.pull_request_number is not None
        try:
            state = self.load(request.repository, request.pull_request_number)
            return state.author, state.author, state, None
        except ProbePortError as error:
            return "unknown", None, None, error

    def _context(
        self,
        request: ProbeRequest,
        candidate: str,
    ) -> tuple[str, str, tuple[str, ...], Exception | None]:
        selectors = tuple(
            selector
            for selector in (request.organization, request.enterprise, request.cost_center)
            if selector is not None
        )
        if len(selectors) > 1:
            return "unknown", "unknown", ("ambiguous_selector",), UnknownContextError(
                "GitHub billing context is ambiguous"
            )
        if request.enterprise is not None or request.cost_center is not None:
            return "unknown", "unknown", ("unverified_selector",), UnknownContextError(
                "GitHub billing context is not API-backed"
            )
        if request.organization is not None:
            try:
                payload = self._request_json(
                    f"/orgs/{request.organization}/members/{candidate}/copilot"
                ).payload
                assignee = payload.get("assignee")
                if (
                    not isinstance(assignee, dict)
                    or assignee.get("login") != candidate
                ):
                    raise IncompleteResponseError("GitHub Copilot seat response is incomplete")
                return (
                    "organization",
                    request.organization,
                    ("copilot_seat",),
                    None,
                )
            except _NotFoundError:
                return "unknown", "unknown", ("seat_unverified",), UnknownContextError(
                    "GitHub Copilot organization seat is not proven"
                )
            except ProbePortError as error:
                return "unknown", "unknown", ("seat_unverified",), error
        return "personal", candidate, ("personal_usage",), None

    def _usage_endpoints(
        self,
        kind: str,
        identifier: str,
        candidate: str,
        observed_at: datetime,
    ) -> tuple[str, str]:
        if kind == "organization":
            prefix = f"/organizations/{identifier}/settings/billing"
            query = urlencode(
                (
                    ("year", observed_at.year),
                    ("month", observed_at.month),
                    ("user", candidate),
                )
            )
        elif kind == "personal":
            prefix = f"/users/{identifier}/settings/billing"
            query = urlencode((("year", observed_at.year), ("month", observed_at.month)))
        else:
            raise UnknownContextError("GitHub billing context is unknown")
        return (
            f"{prefix}/ai_credit/usage?{query}",
            f"{prefix}/premium_request/usage?{query}",
        )

    def _usage_quantity(self, payload: Mapping[str, object], model: str) -> tuple[float, str]:
        items = payload.get("usageItems")
        if not isinstance(items, list):
            raise IncompleteResponseError("GitHub billing response is incomplete")
        expected_units = {"credits", "ai-credits"} if model == "ai_credits" else {"requests"}
        total = 0.0
        for item in items:
            if not isinstance(item, dict):
                raise IncompleteResponseError("GitHub billing response is incomplete")
            unit = item.get("unitType")
            quantity = item.get("grossQuantity")
            if unit not in expected_units:
                raise IncompleteResponseError("GitHub billing response is incomplete")
            parsed = _number(quantity, "grossQuantity")
            assert parsed is not None
            total += parsed
        return total, "credits" if model == "ai_credits" else "requests"

    def _usage(
        self,
        kind: str,
        identifier: str,
        candidate: str,
        observed_at: datetime,
    ) -> tuple[Usage, str]:
        ai_endpoint, legacy_endpoint = self._usage_endpoints(
            kind,
            identifier,
            candidate,
            observed_at,
        )
        model = "ai_credits"
        try:
            payload = self._request_json(ai_endpoint).payload
        except _NotFoundError:
            payload = self._request_json(legacy_endpoint).payload
            model = "premium_requests"
        used, unit = self._usage_quantity(payload, model)
        return Usage(used=used, limit=None, unit=unit), model

    def probe(self, request: ProbeRequest) -> ProbeReport:
        observed_at = self._clock.now()
        provider_status, provider_error = self._provider_status()
        authenticated_user, permission_status, auth_error = self._authenticated_user()
        candidate, pull_request_author, _state, candidate_error = self._candidate(request)
        context_kind, context_identity, context_evidence, context_error = self._context(
            request,
            candidate,
        )
        if (
            authenticated_user is not None
            and request.review_mode == "manual"
            and authenticated_user != candidate
        ):
            context_kind = "unknown"
            context_identity = "unknown"
            context_evidence = ("requester_mismatch",)
            context_error = UnknownContextError("GitHub requester context is not authenticated")

        principal = BillingPrincipal(
            kind=context_kind,
            identifier=context_identity,
            review_mode=request.review_mode,
            requester=request.manual_requester,
            pull_request_author=pull_request_author,
            source="github_api" if context_error is None else "unverified",
            observed_at=observed_at,
            expires_at=observed_at + PRINCIPAL_VALIDITY,
        )
        usage = Usage(used=None, limit=None)
        billing_model = "unknown"
        billing_status: DiagnosticStatus | None = None
        usage_status = DiagnosticStatus.UNKNOWN
        usage_error: Exception | None = None
        if context_error is None and candidate_error is None:
            try:
                usage, billing_model = self._usage(
                    context_kind,
                    context_identity,
                    candidate,
                    observed_at,
                )
                usage_status = DiagnosticStatus.AVAILABLE
            except ProbePortError as error:
                usage_error = error
                usage_status = _diagnostic_for_error(error)
                if isinstance(error, PermissionDeniedError):
                    permission_status = DiagnosticStatus.PERMISSION_DENIED

        capability_error: Exception | None = None
        block_error: Exception | None = None
        try:
            capability_verification = self._capability_verifier.verify(
                request.capability_reference,
                request.repository,
                principal,
                request.review_mode,
                observed_at,
            )
        except ProbePortError as error:
            capability_error = error
            capability_verification = (
                _absent_capability()
                if request.capability_reference is None
                else _invalid_capability(request.capability_reference)
            )
        try:
            block_verification = self._block_verifier.verify(
                request.block_reference,
                request.repository,
                principal,
                request.review_mode,
                observed_at,
            )
        except ProbePortError as error:
            block_error = error
            block_verification = (
                _absent_block()
                if request.block_reference is None
                else BlockVerification(
                    status=EvidenceVerificationStatus.INVALID,
                    trust=EvidenceTrust.DEVELOPMENT,
                    source=request.block_reference.source,
                    source_reference=request.block_reference.source_reference,
                    artifact_digest=None,
                    evidence=None,
                )
            )
        capability_status = _capability_status(capability_verification)
        capability = capability_verification.evidence
        verified_block = block_verification.evidence
        if verified_block is not None:
            billing_status = (
                DiagnosticStatus.QUOTA_EXHAUSTED
                if verified_block.kind is BlockEvidenceKind.QUOTA_EXHAUSTED
                else DiagnosticStatus.BUDGET_BLOCKED
            )
        signals = ProbeSignals(
            billing_status=billing_status,
            usage_status=usage_status,
            provider_status=provider_status,
            permission_status=permission_status,
            capability=capability,
            repository=request.repository,
            principal=principal,
            review_mode=request.review_mode,
            observed_at=observed_at,
            verified_block=verified_block,
        )
        technical_statuses = (
            usage_status,
            provider_status,
            permission_status,
        )
        routing_status = next(
            status for status in _STATUS_PRECEDENCE if status in technical_statuses
        )
        copilot_usable = False
        if routing_status in {DiagnosticStatus.AVAILABLE, DiagnosticStatus.LOW_BUDGET}:
            if capability is None or not capability.is_valid_for(
                request.repository,
                principal,
                request.review_mode,
                observed_at,
            ):
                routing_status = DiagnosticStatus.UNKNOWN
            elif (
                verified_block is not None
                and verified_block.observed_at >= capability.observed_at
            ):
                assert billing_status is not None
                routing_status = billing_status
            else:
                copilot_usable = True

        errors = tuple(
            error
            for error in (
                auth_error,
                candidate_error,
                context_error,
                usage_error,
                provider_error,
                capability_error,
                block_error,
            )
            if error is not None
        )
        errors_by_status = {
            status: next(
                (error for error in errors if _diagnostic_for_error(error) is status),
                None,
            )
            for status in (
                DiagnosticStatus.RATE_LIMITED,
                DiagnosticStatus.PROVIDER_UNAVAILABLE,
                DiagnosticStatus.PERMISSION_DENIED,
                DiagnosticStatus.UNKNOWN,
            )
        }
        technical_status = next(
            (
                status
                for status in (
                    DiagnosticStatus.RATE_LIMITED,
                    DiagnosticStatus.PROVIDER_UNAVAILABLE,
                    DiagnosticStatus.PERMISSION_DENIED,
                    DiagnosticStatus.UNKNOWN,
                )
                if errors_by_status[status] is not None
                or (
                    status
                    in {
                        DiagnosticStatus.PROVIDER_UNAVAILABLE,
                        DiagnosticStatus.UNKNOWN,
                    }
                    and provider_status is status
                )
            ),
            DiagnosticStatus.AVAILABLE,
        )
        technical_error = errors_by_status.get(technical_status)
        if technical_error is not None:
            technical_error_code = _technical_error_code(technical_error)
        elif technical_status is DiagnosticStatus.PROVIDER_UNAVAILABLE:
            technical_error_code = ProbeTechnicalError.PROVIDER_UNAVAILABLE
        elif technical_status is DiagnosticStatus.UNKNOWN:
            technical_error_code = ProbeTechnicalError.UNKNOWN_CONTEXT
        else:
            technical_error_code = None
        return ProbeReport(
            copilot_usable=copilot_usable,
            routing_status=routing_status,
            signals=signals,
            usage=usage,
            repository=request.repository,
            review_mode=request.review_mode,
            requester=request.manual_requester,
            pull_request_author=pull_request_author,
            billing_principal=principal,
            billing_context=BillingContext(
                kind=context_kind,
                identity=context_identity,
                evidence=context_evidence,
            ),
            billing_model=billing_model,
            technical_status=technical_status,
            technical_error=technical_error_code,
            capability_status=capability_status,
            capability_verification=capability_verification,
            block_verification=block_verification,
            evidence=("github_api", "github_status"),
            warnings=(),
        )


@dataclass(frozen=True)
class GitHubFactory:
    provided_ports = (
        CommandPort,
        StatusPort,
        ClockPort,
        CapabilityEvidenceVerifierPort,
        BlockEvidenceVerifierPort,
        ProbePort,
        PullRequestStatePort,
    )
    required_ports: tuple[type[object], ...] = ()

    def build(self, dependencies: Mapping[type[object], object]) -> Mapping[type[object], object]:
        if dependencies:
            raise ValueError("GitHub factory expects no dependencies")
        command = SubprocessCommand()
        clock = SystemClock()
        status = GitHubStatus(clock=clock)
        capability_verifier = CapabilityEvidenceVerifier(command=command, operator_pins={})
        block_verifier = BlockEvidenceVerifier(operator_pins={})
        probe = GitHubGhProbe(
            command=command,
            status=status,
            clock=clock,
            capability_verifier=capability_verifier,
            block_verifier=block_verifier,
        )
        return {
            CommandPort: command,
            StatusPort: status,
            ClockPort: clock,
            CapabilityEvidenceVerifierPort: capability_verifier,
            BlockEvidenceVerifierPort: block_verifier,
            ProbePort: probe,
            PullRequestStatePort: probe,
        }


def factory() -> AdapterFactory:
    """Meldet die read-only GitHub-Ports an der Runtime-Registry an."""
    return GitHubFactory()
