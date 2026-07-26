"""Importblinder, ausschließlich read-only arbeitender Review-Routing-CLI."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path, PurePosixPath
import sys
from typing import Mapping, Sequence, TextIO, TypeVar

from review_routing.contracts import (
    CapabilityEvidenceReference,
    CapabilityEvidenceSource,
    CliDependencies,
    ClockPort,
    ConfigPort,
    DiagnosticStatus,
    DiffSnapshot,
    DiffSourcePort,
    DocumentTrust,
    PolicySourcePort,
    ProbePort,
    ProbeReport,
    ProbeRequest,
    ProbeTechnicalError,
    PullRequestState,
    PullRequestStatePort,
    PullRequestStateSource,
    RiskAssessment,
    ReviewPurpose,
    ReviewRequest,
    ReviewRoute,
    RiskClassifierPort,
    RouteDecision,
    RoutingPolicyPort,
    RuntimeTrust,
    require_full_sha,
    require_repository,
)
from review_routing.registry import RuntimeRegistry


POLICY_PATH = PurePosixPath("core/review-routing.toml")
MAX_INPUT_BYTES = 1024 * 1024
T = TypeVar("T")


class CliInputError(ValueError):
    """Ein externer CLI-Wert verletzt den geschlossenen Eingabevertrag."""


class JsonArgumentParser(argparse.ArgumentParser):
    """Unterbindet argparse-Prosa auf stderr zugunsten des JSON-Vertrags."""

    def error(self, message: str) -> None:
        raise CliInputError("invalid command line")


def _parser() -> JsonArgumentParser:
    parser = JsonArgumentParser(prog="review-routing", add_help=False)
    commands = parser.add_subparsers(dest="command", required=True)

    probe = commands.add_parser("probe", add_help=False)
    probe.add_argument("--repo", required=True)
    probe.add_argument("--review-mode", choices=("manual", "automatic"), required=True)
    probe.add_argument("--requester")
    probe.add_argument("--pull-request", type=int)
    probe.add_argument("--organization")
    probe.add_argument("--enterprise")
    probe.add_argument("--cost-center")
    probe.add_argument("--capability-reference")
    probe.add_argument("--json", action="store_true", required=True)

    route = commands.add_parser("route", add_help=False)
    route.add_argument("--probe-file", required=True)
    route.add_argument("--repo", required=True)
    route.add_argument("--pull-request", type=int, required=True)
    route.add_argument(
        "--purpose",
        choices=(
            ReviewPurpose.CHECKPOINT.value,
            ReviewPurpose.FINAL_EXACT_HEAD.value,
            ReviewPurpose.CORRECTION.value,
        ),
        required=True,
    )
    route.add_argument("--repo-path", required=True)
    route.add_argument("--qa-available", choices=("true", "false"), default="true")
    route.add_argument("--sec-available", choices=("true", "false"), default="true")
    route.add_argument("--json", action="store_true", required=True)
    return parser


def _write_json(stdout: TextIO, payload: Mapping[str, object]) -> None:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    stdout.write(serialized + "\n")


def _invalid(stdout: TextIO) -> int:
    _write_json(
        stdout,
        {
            "schema_version": 1,
            "error": "invalid_input",
        },
    )
    return 31


def _read_bytes(path_value: str) -> bytes:
    try:
        path = Path(path_value)
        with path.open("rb") as stream:
            content = stream.read(MAX_INPUT_BYTES + 1)
        if len(content) > MAX_INPUT_BYTES:
            raise CliInputError("input is too large")
    except (OSError, ValueError) as error:
        raise CliInputError("input cannot be read") from error
    if not content:
        raise CliInputError("input is empty")
    return content


def _read_json(path_value: str) -> tuple[dict[str, object], bytes]:
    content = _read_bytes(path_value)
    try:
        decoded = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CliInputError("input is not valid JSON") from error
    if not isinstance(decoded, dict):
        raise CliInputError("JSON input must be an object")
    return decoded, content


def _capability_reference(path_value: str | None) -> CapabilityEvidenceReference | None:
    if path_value is None:
        return None
    document, artifact = _read_json(path_value)
    required = {
        "schema_version",
        "repository",
        "principal_identity",
        "review_mode",
        "source_reference",
    }
    if not required.issubset(document):
        raise CliInputError("capability reference is incomplete")
    identity = document["principal_identity"]
    if not isinstance(identity, list):
        raise CliInputError("principal identity must be a list")
    try:
        return CapabilityEvidenceReference(
            schema_version=document["schema_version"],  # type: ignore[arg-type]
            source=CapabilityEvidenceSource.OPERATOR_PINNED,
            repository=document["repository"],  # type: ignore[arg-type]
            review_mode=document["review_mode"],  # type: ignore[arg-type]
            principal_identity=tuple(identity),  # type: ignore[arg-type]
            source_reference=document["source_reference"],  # type: ignore[arg-type]
            artifact=artifact,
        )
    except (TypeError, ValueError) as error:
        raise CliInputError("capability reference is invalid") from error


def _probe_request(arguments: argparse.Namespace) -> ProbeRequest:
    if arguments.review_mode == "manual":
        if arguments.requester is None or arguments.pull_request is not None:
            raise CliInputError("manual mode requires only a requester")
    elif arguments.requester is not None or arguments.pull_request is None:
        raise CliInputError("automatic mode requires only a pull request")
    try:
        return ProbeRequest(
            repository=arguments.repo,
            review_mode=arguments.review_mode,
            manual_requester=arguments.requester,
            pull_request_number=arguments.pull_request,
            organization=arguments.organization,
            enterprise=arguments.enterprise,
            cost_center=arguments.cost_center,
            capability_reference=_capability_reference(arguments.capability_reference),
        )
    except (TypeError, ValueError) as error:
        raise CliInputError("probe request is invalid") from error


def _probe_exit(report: ProbeReport) -> int:
    technical_error = report.technical_error
    if technical_error is ProbeTechnicalError.PERMISSION_DENIED:
        return 20
    if technical_error is ProbeTechnicalError.RATE_LIMITED:
        return 21
    if technical_error in {
        ProbeTechnicalError.PROVIDER_UNAVAILABLE,
        ProbeTechnicalError.TIMEOUT,
    }:
        return 22
    if technical_error is ProbeTechnicalError.UNKNOWN_CONTEXT:
        return 23
    if technical_error is ProbeTechnicalError.INCOMPLETE_RESPONSE:
        return 24
    if technical_error is not None:
        return 24
    if report.routing_status is DiagnosticStatus.UNKNOWN:
        return 23
    return 0


def _resolve(
    explicit: T | None,
    registry: RuntimeRegistry,
    port: type[T],
) -> T:
    return explicit if explicit is not None else registry.resolve(port)


def _run_probe(
    arguments: argparse.Namespace,
    dependencies: CliDependencies,
    registry: RuntimeRegistry,
    stdout: TextIO,
) -> int:
    probe = _resolve(dependencies.probe, registry, ProbePort)
    request = _probe_request(arguments)
    report = probe.probe(request)
    if (
        not isinstance(report, ProbeReport)
        or report.repository != request.repository
        or report.review_mode != request.review_mode
        or (
            request.review_mode == "manual"
            and (
                report.requester != request.manual_requester
                or report.pull_request_author is not None
            )
        )
        or (
            request.review_mode == "automatic"
            and (
                report.requester is not None
                or not isinstance(report.pull_request_author, str)
                or not report.pull_request_author
            )
        )
    ):
        raise CliInputError("probe returned an invalid report")
    payload = report.to_dict()
    if not isinstance(payload, dict):
        raise CliInputError("probe returned an invalid report")
    _write_json(stdout, payload)
    return _probe_exit(report)


_PROBE_KEYS = {
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
}


def _probe_usability(path_value: str, repository: str) -> bool:
    document, _raw = _read_json(path_value)
    if (
        set(document) != _PROBE_KEYS
        or type(document.get("schema_version")) is not int
        or document.get("schema_version") != 1
    ):
        raise CliInputError("probe document has an unsupported schema")
    if document.get("repository") != repository:
        raise CliInputError("probe repository does not match")
    usable = document.get("copilot_usable")
    if type(usable) is not bool:
        raise CliInputError("probe usability must be boolean")
    try:
        routing_status = DiagnosticStatus(document["routing_status"])  # type: ignore[arg-type]
    except (KeyError, TypeError, ValueError) as error:
        raise CliInputError("probe routing status is invalid") from error
    capability = document.get("capability_evidence")
    signals = document.get("signals")
    if not isinstance(capability, dict) or not isinstance(signals, dict):
        raise CliInputError("probe evidence is incomplete")
    if usable:
        if (
            routing_status not in {
                DiagnosticStatus.AVAILABLE,
                DiagnosticStatus.LOW_BUDGET,
            }
            or document.get("technical_error") is not None
            or capability.get("status") != "valid"
            or capability.get("trust") != "verified"
            or signals.get("provider_status") != DiagnosticStatus.AVAILABLE.value
            or signals.get("api_status") != DiagnosticStatus.AVAILABLE.value
            or signals.get("usage_status")
            not in {
                DiagnosticStatus.AVAILABLE.value,
                DiagnosticStatus.LOW_BUDGET.value,
            }
        ):
            raise CliInputError("positive probe evidence is inconsistent")
    return usable


def _validated_pr_state(value: object, repository: str, pull_request_number: int) -> PullRequestState:
    if not isinstance(value, PullRequestState):
        raise CliInputError("pull request state has an invalid type")
    if (
        value.repository != repository
        or value.pull_request_number != pull_request_number
        or value.source is not PullRequestStateSource.GITHUB_API
    ):
        raise CliInputError("pull request state does not match the request")
    try:
        require_repository(value.repository)
        require_full_sha(value.api_base_sha, "api_base_sha")
        require_full_sha(value.head_sha, "head_sha")
    except ValueError as error:
        raise CliInputError("pull request state is invalid") from error
    return value


def _iso_z(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CliInputError("clock must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _route_payload(
    *,
    arguments: argparse.Namespace,
    state: PullRequestState,
    snapshot: DiffSnapshot,
    assessment: RiskAssessment,
    decision: RouteDecision,
    observed_at: datetime,
    gate_eligible: bool,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "observed_at": _iso_z(observed_at),
        "repository": state.repository,
        "pull_request_number": state.pull_request_number,
        "pull_request_author": state.author,
        "purpose": decision.purpose.value,
        "base_ref": state.base_ref,
        "base_sha": state.api_base_sha,
        "merge_base_sha": snapshot.merge_base_sha,
        "head_sha": state.head_sha,
        "pr_state_source": state.source.value,
        "risk": {
            "level": assessment.level.value,
            "security_relevant": assessment.security_relevant,
            "reasons": list(assessment.reasons),
        },
        "copilot_usable": decision.copilot_usable,
        "required_reviewers": sorted(
            reviewer.value for reviewer in decision.required_reviewers
        ),
        "route": decision.route.value,
        "policy_source_ref": decision.policy_source_ref,
        "policy_source_path": decision.policy_source_path,
        "policy_digest": decision.policy_digest,
        "runtime_digest": decision.runtime_digest,
        "runtime_trust": decision.runtime_trust.value,
        "diff_digest": decision.diff_digest,
        "diff_mode": snapshot.diff_mode.value,
        "rename_detection": snapshot.rename_detection.value,
        "copy_detection": snapshot.copy_detection.value,
        "gate_eligible": gate_eligible,
        "merge_evidence_required": arguments.purpose != ReviewPurpose.CHECKPOINT.value,
        "dispatch_permitted": False,
    }


def _run_route(
    arguments: argparse.Namespace,
    dependencies: CliDependencies,
    registry: RuntimeRegistry,
    stdout: TextIO,
) -> int:
    try:
        require_repository(arguments.repo)
        if (
            isinstance(arguments.pull_request, bool)
            or not isinstance(arguments.pull_request, int)
            or arguments.pull_request <= 0
        ):
            raise ValueError("invalid pull request")
        repository_path = Path(arguments.repo_path)
        if not repository_path.is_absolute():
            raise ValueError("repo path must be absolute")
        purpose = ReviewPurpose(arguments.purpose)
        if purpose is ReviewPurpose.CORRECTION:
            raise ValueError("correction requires prior exact-head evidence")
    except (TypeError, ValueError) as error:
        raise CliInputError("route request is invalid") from error

    copilot_usable = _probe_usability(arguments.probe_file, arguments.repo)
    pull_request_state = _resolve(
        dependencies.pull_request_state,
        registry,
        PullRequestStatePort,
    )
    state = _validated_pr_state(
        pull_request_state.load(arguments.repo, arguments.pull_request),
        arguments.repo,
        arguments.pull_request,
    )
    policy_source = _resolve(dependencies.policy_source, registry, PolicySourcePort)
    document = policy_source.read_at_commit(
        repository_path,
        arguments.repo,
        state.api_base_sha,
        POLICY_PATH,
    )
    if (
        document.trust is not DocumentTrust.COMMIT_OBJECT
        or document.source != f"{state.api_base_sha}:{POLICY_PATH}"
    ):
        raise CliInputError("base policy provenance is invalid")
    config_port = _resolve(dependencies.config, registry, ConfigPort)
    config = config_port.parse_routing(document)
    diff_source = _resolve(dependencies.diff_source, registry, DiffSourcePort)
    snapshot = diff_source.load(
        repository_path,
        arguments.repo,
        state.api_base_sha,
        state.head_sha,
    )
    if (
        not isinstance(snapshot, DiffSnapshot)
        or snapshot.repository != state.repository
        or snapshot.api_base_sha != state.api_base_sha
        or snapshot.head_sha != state.head_sha
    ):
        raise CliInputError("diff source does not match pull request state")
    risk_classifier = registry.resolve(RiskClassifierPort)
    assessment = risk_classifier.assess(snapshot, config)
    runtime = registry.runtime_provenance
    request = ReviewRequest(
        repository=state.repository,
        base_sha=state.api_base_sha,
        head_sha=state.head_sha,
        purpose=purpose,
        assessment=assessment,
        copilot_usable=copilot_usable,
        copilot_coverage_complete=True,
        copilot_review_mode="full",
        qa_available=arguments.qa_available == "true",
        sec_available=arguments.sec_available == "true",
        policy_source_ref=state.api_base_sha,
        policy_source_path=str(POLICY_PATH),
        runtime_digest=runtime.digest,
        runtime_trust=runtime.trust,
        diff_digest=snapshot.diff_digest,
        prior_reviewers=frozenset(),
    )
    decision = registry.resolve(RoutingPolicyPort).route(request, config)
    gate_eligible = (
        runtime.trust is RuntimeTrust.INSTALLED
        and document.trust is DocumentTrust.COMMIT_OBJECT
        and decision.route is not ReviewRoute.BLOCKER
    )
    clock = _resolve(dependencies.clock, registry, ClockPort)
    payload = _route_payload(
        arguments=arguments,
        state=state,
        snapshot=snapshot,
        assessment=assessment,
        decision=decision,
        observed_at=clock.now(),
        gate_eligible=gate_eligible,
    )
    _write_json(stdout, payload)
    return 30 if decision.route is ReviewRoute.BLOCKER else 0


def main(
    argv: Sequence[str] | None = None,
    *,
    dependencies: CliDependencies | None = None,
    stdout: TextIO | None = None,
) -> int:
    """Führt genau einen read-only CLI-Befehl aus und schreibt genau ein JSON-Objekt."""
    output = stdout or sys.stdout
    injected = dependencies or CliDependencies()
    try:
        arguments = _parser().parse_args(list(argv) if argv is not None else None)
        registry = RuntimeRegistry.bootstrap(injected)
        if arguments.command == "probe":
            return _run_probe(arguments, injected, registry, output)
        if arguments.command == "route":
            return _run_route(arguments, injected, registry, output)
        raise CliInputError("unknown command")
    except Exception:
        return _invalid(output)


if __name__ == "__main__":
    raise SystemExit(main())
