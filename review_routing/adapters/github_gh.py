"""Read-only GitHub- und Status-Adapter mit sanitisierten öffentlichen Grenzen."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import math
import subprocess
from typing import Callable, Mapping
from urllib import error as urlerror
from urllib import request as urlrequest

from review_routing.contracts import (
    AdapterFactory,
    BillingContext,
    BillingPrincipal,
    ClockPort,
    CommandPort,
    CommandResult,
    DiagnosticStatus,
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
    UnknownContextError,
    Usage,
    require_repository,
)


API_VERSION = "2026-03-10"
STATUS_URL = "https://www.githubstatus.com/api/v2/components.json"
DEFAULT_TIMEOUT_SECONDS = 10.0
PRINCIPAL_VALIDITY = timedelta(minutes=15)


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
        relevant = []
        for component in document["components"]:
            if not isinstance(component, dict):
                raise IncompleteResponseError("GitHub status response is incomplete")
            name = component.get("name")
            status = component.get("status")
            if not isinstance(name, str) or not isinstance(status, str):
                raise IncompleteResponseError("GitHub status response is incomplete")
            if name.casefold() in {"api requests", "copilot"}:
                relevant.append(status)
        if not relevant:
            raise IncompleteResponseError("GitHub status response is incomplete")
        provider_status = (
            DiagnosticStatus.AVAILABLE
            if all(status == "operational" for status in relevant)
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
    marker = "\n\n"
    if marker not in normalized:
        raise MalformedResponseError("GitHub API response is malformed")
    header_text, body_text = normalized.split(marker, 1)
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


def _status_from_payload(value: object) -> DiagnosticStatus:
    if not isinstance(value, str):
        raise IncompleteResponseError("GitHub billing response is incomplete")
    try:
        status = DiagnosticStatus(value)
    except ValueError as error:
        raise IncompleteResponseError("GitHub billing response is incomplete") from error
    if status not in {
        DiagnosticStatus.AVAILABLE,
        DiagnosticStatus.LOW_BUDGET,
        DiagnosticStatus.QUOTA_EXHAUSTED,
        DiagnosticStatus.BUDGET_BLOCKED,
    }:
        raise IncompleteResponseError("GitHub billing response is incomplete")
    return status


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
    request: ProbeRequest,
    principal: BillingPrincipal,
    observed_at: datetime,
) -> str:
    capability = request.capability_evidence
    if capability is None:
        return "absent"
    if observed_at >= capability.expires_at:
        return "expired"
    if not capability.is_valid_for(
        request.repository,
        principal,
        request.review_mode,
        observed_at,
    ):
        return "invalid"
    return "valid"


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
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        self._command = command
        self._status = status
        self._clock = clock
        self._timeout_seconds = timeout_seconds

    def _request_json(self, endpoint: str) -> _ApiResponse:
        result = self._command.run(
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
            self._timeout_seconds,
        )
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
                return "personal", candidate, ("personal_usage",), None
            except ProbePortError as error:
                return "unknown", "unknown", ("seat_unverified",), error
        return "personal", candidate, ("personal_usage",), None

    def _usage_endpoints(self, kind: str, identifier: str) -> tuple[str, str]:
        if kind == "organization":
            prefix = f"/organizations/{identifier}/settings/billing"
        elif kind == "personal":
            prefix = f"/users/{identifier}/settings/billing"
        else:
            raise UnknownContextError("GitHub billing context is unknown")
        return f"{prefix}/ai_credit/usage", f"{prefix}/premium_request/usage"

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
            quantity = item.get("netQuantity")
            if unit not in expected_units:
                raise IncompleteResponseError("GitHub billing response is incomplete")
            parsed = _number(quantity, "netQuantity")
            assert parsed is not None
            total += parsed
        return total, "credits" if model == "ai_credits" else "requests"

    def _usage(
        self,
        kind: str,
        identifier: str,
    ) -> tuple[Usage, str, DiagnosticStatus]:
        ai_endpoint, legacy_endpoint = self._usage_endpoints(kind, identifier)
        model = "ai_credits"
        try:
            payload = self._request_json(ai_endpoint).payload
        except _NotFoundError:
            payload = self._request_json(legacy_endpoint).payload
            model = "premium_requests"
        used, unit = self._usage_quantity(payload, model)
        limit = _number(payload.get("limit"), "limit", optional=True)
        status_value = payload.get("status", DiagnosticStatus.AVAILABLE.value)
        status = _status_from_payload(status_value)
        return Usage(used=used, limit=limit, unit=unit), model, status

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
        billing_status = DiagnosticStatus.UNKNOWN
        usage_status = DiagnosticStatus.UNKNOWN
        usage_error: Exception | None = None
        if context_error is None and candidate_error is None:
            try:
                usage, billing_model, billing_status = self._usage(context_kind, context_identity)
                usage_status = DiagnosticStatus.AVAILABLE
            except ProbePortError as error:
                usage_error = error
                usage_status = _diagnostic_for_error(error)
                if isinstance(error, PermissionDeniedError):
                    permission_status = DiagnosticStatus.PERMISSION_DENIED

        capability_status = _capability_status(request, principal, observed_at)
        capability = request.capability_evidence
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
        )
        statuses = (
            billing_status,
            usage_status,
            provider_status,
            permission_status,
        )
        routing_status = next(status for status in _STATUS_PRECEDENCE if status in statuses)
        positive_status = routing_status in {
            DiagnosticStatus.AVAILABLE,
            DiagnosticStatus.LOW_BUDGET,
        }
        copilot_usable = positive_status and capability_status == "valid"
        if positive_status and capability_status != "valid":
            routing_status = DiagnosticStatus.UNKNOWN

        errors = tuple(
            error
            for error in (
                auth_error,
                candidate_error,
                context_error,
                usage_error,
                provider_error,
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
            evidence=("github_api", "github_status"),
            warnings=(),
        )


@dataclass(frozen=True)
class GitHubFactory:
    provided_ports = (
        CommandPort,
        StatusPort,
        ClockPort,
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
        probe = GitHubGhProbe(command=command, status=status, clock=clock)
        return {
            CommandPort: command,
            StatusPort: status,
            ClockPort: clock,
            ProbePort: probe,
            PullRequestStatePort: probe,
        }


def factory() -> AdapterFactory:
    """Meldet die read-only GitHub-Ports an der Runtime-Registry an."""
    return GitHubFactory()
