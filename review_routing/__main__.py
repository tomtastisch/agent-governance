"""Importblinder, ausschließlich read-only arbeitender Review-Routing-CLI."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Mapping, Sequence, TextIO, TypeVar

from review_routing.contracts import (
    BoundEvidenceSource,
    BoundEvidenceSourceKind,
    CapabilityEvidenceReference,
    CapabilityEvidenceSource,
    CheckConclusion,
    CheckRecord,
    CliDependencies,
    ClockPort,
    CopilotReviewMode,
    ConfigPort,
    CoverageStatus,
    DiagnosticStatus,
    DiffSnapshot,
    DiffSourcePort,
    DocumentTrust,
    EvidenceValidatorPort,
    FileCoverage,
    FileStatus,
    GateEvaluationContext,
    GateResult,
    GateSnapshot,
    PreliminaryRoutePlan,
    PolicySourcePort,
    ProbePort,
    ProbeReport,
    ProbeRequest,
    ProbeTechnicalError,
    PullRequestState,
    PullRequestStatePort,
    PullRequestStateSource,
    RiskAssessment,
    Reviewer,
    ReviewerAvailabilitySnapshot,
    ReviewRecord,
    ReviewState,
    ReviewPurpose,
    ReviewRequest,
    ReviewRoute,
    RiskClassifierPort,
    RiskLevel,
    RouteDecision,
    RoutingPolicyPort,
    RuntimeTrust,
    ThreadRecord,
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
    parser = JsonArgumentParser(
        prog="review-routing",
        add_help=False,
        allow_abbrev=False,
    )
    commands = parser.add_subparsers(dest="command", required=True)

    probe = commands.add_parser("probe", add_help=False, allow_abbrev=False)
    probe.add_argument("--repo", required=True)
    probe.add_argument("--review-mode", choices=("manual", "automatic"), required=True)
    probe.add_argument("--requester")
    probe.add_argument("--pull-request", type=int)
    probe.add_argument("--organization")
    probe.add_argument("--enterprise")
    probe.add_argument("--cost-center")
    probe.add_argument("--capability-reference")
    probe.add_argument("--json", action="store_true", required=True)

    route = commands.add_parser("route", add_help=False, allow_abbrev=False)
    route.add_argument("--repo", required=True)
    route.add_argument("--pull-request", type=int, required=True)
    route.add_argument("--review-mode", choices=("manual", "automatic"), required=True)
    route.add_argument("--requester")
    route.add_argument("--organization")
    route.add_argument("--enterprise")
    route.add_argument("--cost-center")
    route.add_argument("--capability-reference")
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
    route.add_argument("--json", action="store_true", required=True)

    validate = commands.add_parser("validate", add_help=False, allow_abbrev=False)
    validate.add_argument("--route-file", required=True)
    validate.add_argument("--evidence-file", required=True)
    validate.add_argument("--repo", required=True)
    validate.add_argument("--pull-request", type=int, required=True)
    validate.add_argument("--review-mode", choices=("manual", "automatic"), required=True)
    validate.add_argument("--requester")
    validate.add_argument("--organization")
    validate.add_argument("--enterprise")
    validate.add_argument("--cost-center")
    validate.add_argument("--capability-reference")
    validate.add_argument("--repo-path", required=True)
    validate.add_argument("--json", action="store_true", required=True)
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
    def closed_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise CliInputError("JSON input contains duplicate fields")
            result[key] = value
        return result
    try:
        decoded = json.loads(content, object_pairs_hook=closed_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CliInputError("input is not valid JSON") from error
    if not isinstance(decoded, dict):
        raise CliInputError("JSON input must be an object")
    return decoded, content


def _exact_keys(document: Mapping[str, object], expected: set[str], label: str) -> None:
    if set(document) != expected:
        raise CliInputError(f"{label} has unknown or missing fields")


def _parse_time(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise CliInputError(f"{label} must be an ISO UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as error:
        raise CliInputError(f"{label} must be an ISO UTC timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CliInputError(f"{label} must be timezone-aware")
    return parsed


def _parse_bound_source(value: object, label: str) -> BoundEvidenceSource:
    if not isinstance(value, dict):
        raise CliInputError(f"{label} must be an object")
    _exact_keys(
        value,
        {
            "kind",
            "source_id",
            "repository",
            "pull_request_number",
            "head_sha",
            "observed_at",
            "valid_until",
        },
        label,
    )
    try:
        return BoundEvidenceSource(
            kind=BoundEvidenceSourceKind(value["kind"]),
            source_id=value["source_id"],  # type: ignore[arg-type]
            repository=value["repository"],  # type: ignore[arg-type]
            pull_request_number=value["pull_request_number"],  # type: ignore[arg-type]
            head_sha=value["head_sha"],  # type: ignore[arg-type]
            observed_at=_parse_time(value["observed_at"], f"{label}.observed_at"),
            valid_until=_parse_time(value["valid_until"], f"{label}.valid_until"),
        )
    except (TypeError, ValueError) as error:
        raise CliInputError(f"{label} is invalid") from error


def _parse_review(value: object, label: str) -> ReviewRecord:
    if not isinstance(value, dict):
        raise CliInputError(f"{label} must be an object")
    _exact_keys(
        value,
        {
            "reviewer",
            "actor_login",
            "app_slug",
            "state",
            "commit_sha",
            "submitted_at",
            "findings_count",
            "source",
        },
        label,
    )
    try:
        return ReviewRecord(
            reviewer=Reviewer(value["reviewer"]),
            actor_login=value["actor_login"],  # type: ignore[arg-type]
            app_slug=value["app_slug"],  # type: ignore[arg-type]
            state=ReviewState(value["state"]),
            commit_sha=value["commit_sha"],  # type: ignore[arg-type]
            submitted_at=_parse_time(value["submitted_at"], f"{label}.submitted_at"),
            findings_count=value["findings_count"],  # type: ignore[arg-type]
            source=_parse_bound_source(value["source"], f"{label}.source"),
        )
    except (TypeError, ValueError) as error:
        raise CliInputError(f"{label} is invalid") from error


def _parse_gate_snapshot(document: Mapping[str, object]) -> GateSnapshot:
    _exact_keys(
        document,
        {
            "schema_version",
            "repository",
            "pull_request_number",
            "base_sha",
            "head_sha",
            "check_runs",
            "review_requests",
            "reviews",
            "review_file_coverage",
            "copilot_review_mode",
            "review_mode_source",
            "threads",
            "observed_at",
            "valid_until",
        },
        "evidence",
    )
    for field_name in (
        "check_runs",
        "review_requests",
        "reviews",
        "review_file_coverage",
        "threads",
    ):
        if not isinstance(document[field_name], list):
            raise CliInputError(f"evidence.{field_name} must be a list")
    checks = []
    for index, value in enumerate(document["check_runs"]):  # type: ignore[union-attr]
        label = f"evidence.check_runs[{index}]"
        if not isinstance(value, dict):
            raise CliInputError(f"{label} must be an object")
        _exact_keys(
            value,
            {"name", "source_app_slug", "head_sha", "conclusion", "completed_at", "source"},
            label,
        )
        try:
            checks.append(
                CheckRecord(
                    name=value["name"],  # type: ignore[arg-type]
                    source_app_slug=value["source_app_slug"],  # type: ignore[arg-type]
                    head_sha=value["head_sha"],  # type: ignore[arg-type]
                    conclusion=CheckConclusion(value["conclusion"]),
                    completed_at=_parse_time(value["completed_at"], f"{label}.completed_at"),
                    source=_parse_bound_source(value["source"], f"{label}.source"),
                )
            )
        except (TypeError, ValueError) as error:
            raise CliInputError(f"{label} is invalid") from error
    coverage = []
    for index, value in enumerate(document["review_file_coverage"]):  # type: ignore[union-attr]
        label = f"evidence.review_file_coverage[{index}]"
        if not isinstance(value, dict):
            raise CliInputError(f"{label} must be an object")
        _exact_keys(
            value,
            {
                "path",
                "status",
                "previous_path",
                "coverage",
                "reviewer",
                "coverage_source",
            },
            label,
        )
        try:
            coverage.append(
                FileCoverage(
                    path=value["path"],  # type: ignore[arg-type]
                    status=FileStatus(value["status"]),
                    previous_path=value["previous_path"],  # type: ignore[arg-type]
                    coverage=CoverageStatus(value["coverage"]),
                    reviewer=Reviewer(value["reviewer"]),
                    coverage_source=_parse_bound_source(
                        value["coverage_source"],
                        f"{label}.coverage_source",
                    ),
                )
            )
        except (TypeError, ValueError) as error:
            raise CliInputError(f"{label} is invalid") from error
    threads = []
    for index, value in enumerate(document["threads"]):  # type: ignore[union-attr]
        label = f"evidence.threads[{index}]"
        if not isinstance(value, dict):
            raise CliInputError(f"{label} must be an object")
        _exact_keys(value, {"thread_id", "reviewer", "head_sha", "unresolved", "source"}, label)
        reviewer_value = value["reviewer"]
        try:
            threads.append(
                ThreadRecord(
                    thread_id=value["thread_id"],  # type: ignore[arg-type]
                    reviewer=Reviewer(reviewer_value) if reviewer_value is not None else None,
                    head_sha=value["head_sha"],  # type: ignore[arg-type]
                    unresolved=value["unresolved"],  # type: ignore[arg-type]
                    source=_parse_bound_source(value["source"], f"{label}.source"),
                )
            )
        except (TypeError, ValueError) as error:
            raise CliInputError(f"{label} is invalid") from error
    try:
        return GateSnapshot(
            schema_version=document["schema_version"],  # type: ignore[arg-type]
            repository=document["repository"],  # type: ignore[arg-type]
            pull_request_number=document["pull_request_number"],  # type: ignore[arg-type]
            base_sha=document["base_sha"],  # type: ignore[arg-type]
            head_sha=document["head_sha"],  # type: ignore[arg-type]
            check_runs=tuple(checks),
            review_requests=tuple(
                _parse_review(value, f"evidence.review_requests[{index}]")
                for index, value in enumerate(document["review_requests"])  # type: ignore[arg-type]
            ),
            reviews=tuple(
                _parse_review(value, f"evidence.reviews[{index}]")
                for index, value in enumerate(document["reviews"])  # type: ignore[arg-type]
            ),
            review_file_coverage=tuple(coverage),
            copilot_review_mode=CopilotReviewMode(document["copilot_review_mode"]),
            review_mode_source=_parse_bound_source(
                document["review_mode_source"],
                "evidence.review_mode_source",
            ),
            threads=tuple(threads),
            observed_at=_parse_time(document["observed_at"], "evidence.observed_at"),
            valid_until=_parse_time(document["valid_until"], "evidence.valid_until"),
        )
    except (TypeError, ValueError) as error:
        raise CliInputError("evidence is invalid") from error


def _parse_preliminary_plan(document: Mapping[str, object]) -> PreliminaryRoutePlan:
    expected = {
        "schema_version",
        "observed_at",
        "repository",
        "pull_request_number",
        "pull_request_author",
        "purpose",
        "base_ref",
        "base_sha",
        "merge_base_sha",
        "head_sha",
        "pr_state_source",
        "risk",
        "copilot_usable",
        "copilot_coverage_complete",
        "copilot_review_mode",
        "probe_request_digest",
        "probe_observed_at",
        "probe_valid_until",
        "required_reviewers",
        "route",
        "policy_source_ref",
        "policy_source_path",
        "policy_digest",
        "runtime_digest",
        "runtime_trust",
        "diff_digest",
        "diff_mode",
        "rename_detection",
        "copy_detection",
        "decision_stage",
        "gate_status",
        "gate_eligible",
        "merge_evidence_required",
        "dispatch_permitted",
    }
    _exact_keys(document, expected, "route")
    risk = document["risk"]
    if not isinstance(risk, dict):
        raise CliInputError("route.risk must be an object")
    _exact_keys(risk, {"level", "security_relevant", "reasons"}, "route.risk")
    if not isinstance(risk["reasons"], list) or not isinstance(
        document["required_reviewers"],
        list,
    ):
        raise CliInputError("route lists are invalid")
    if (
        not isinstance(document["pull_request_author"], str)
        or not document["pull_request_author"]
        or not isinstance(document["probe_request_digest"], str)
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", document["probe_request_digest"])
        or len(document["required_reviewers"])
        != len(set(document["required_reviewers"]))  # type: ignore[arg-type]
    ):
        raise CliInputError("route context is invalid")
    if (
        document["decision_stage"] != "preliminary"
        or document["diff_mode"] != "merge_base_to_head"
        or document["rename_detection"] != "disabled"
        or document["copy_detection"] != "disabled"
        or type(document["merge_evidence_required"]) is not bool
        or type(document["dispatch_permitted"]) is not bool
        or document["dispatch_permitted"] is not False
    ):
        raise CliInputError("route invariants are invalid")
    observed_at = _parse_time(document["observed_at"], "route.observed_at")
    probe_observed_at = _parse_time(
        document["probe_observed_at"],
        "route.probe_observed_at",
    )
    probe_valid_until = _parse_time(
        document["probe_valid_until"],
        "route.probe_valid_until",
    )
    if probe_valid_until <= probe_observed_at or observed_at < probe_observed_at:
        raise CliInputError("route probe timestamps are invalid")
    try:
        return PreliminaryRoutePlan(
            schema_version=document["schema_version"],  # type: ignore[arg-type]
            repository=document["repository"],  # type: ignore[arg-type]
            pull_request_number=document["pull_request_number"],  # type: ignore[arg-type]
            purpose=ReviewPurpose(document["purpose"]),
            base_ref=document["base_ref"],  # type: ignore[arg-type]
            base_sha=document["base_sha"],  # type: ignore[arg-type]
            merge_base_sha=document["merge_base_sha"],  # type: ignore[arg-type]
            head_sha=document["head_sha"],  # type: ignore[arg-type]
            pr_state_source=PullRequestStateSource(document["pr_state_source"]),
            risk=RiskAssessment(
                level=RiskLevel(risk["level"]),
                security_relevant=risk["security_relevant"],  # type: ignore[arg-type]
                reasons=tuple(risk["reasons"]),  # type: ignore[arg-type]
            ),
            policy_source_ref=document["policy_source_ref"],  # type: ignore[arg-type]
            policy_source_path=document["policy_source_path"],  # type: ignore[arg-type]
            policy_digest=document["policy_digest"],  # type: ignore[arg-type]
            runtime_digest=document["runtime_digest"],  # type: ignore[arg-type]
            runtime_trust=RuntimeTrust(document["runtime_trust"]),
            diff_digest=document["diff_digest"],  # type: ignore[arg-type]
            copilot_usable=document["copilot_usable"],  # type: ignore[arg-type]
            copilot_coverage_complete=document["copilot_coverage_complete"],  # type: ignore[arg-type]
            copilot_review_mode=CopilotReviewMode(document["copilot_review_mode"]),
            route=ReviewRoute(document["route"]),
            required_reviewers=frozenset(
                Reviewer(value) for value in document["required_reviewers"]  # type: ignore[union-attr]
            ),
            gate_status=document["gate_status"],  # type: ignore[arg-type]
            gate_eligible=document["gate_eligible"],  # type: ignore[arg-type]
        )
    except (TypeError, ValueError) as error:
        raise CliInputError("route is invalid") from error


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
    clock = _resolve(dependencies.clock, registry, ClockPort)
    request = _probe_request(arguments)
    report = probe.probe(request)
    _validate_probe_report(report, request, clock.now())
    payload = report.to_dict()
    if not isinstance(payload, dict):
        raise CliInputError("probe returned an invalid report")
    _write_json(stdout, payload)
    return _probe_exit(report)


def _validate_probe_report(
    report: object,
    request: ProbeRequest,
    now: datetime,
    state: PullRequestState | None = None,
) -> ProbeReport:
    """Bindet einen frischen Portbericht an Request, Uhr und optionalen API-PR-State."""
    if (
        not isinstance(report, ProbeReport)
        or report.repository != request.repository
        or report.review_mode != request.review_mode
        or report.pull_request_number != request.pull_request_number
        or report.request_digest != request.request_digest
        or not report.observed_at <= now < report.valid_until
        or not report.billing_principal.is_valid_at(now)
    ):
        raise CliInputError("probe returned an invalid report")
    if request.review_mode == "manual":
        if (
            report.requester != request.manual_requester
            or report.billing_principal.requester != request.manual_requester
            or report.pull_request_author is not None
        ):
            raise CliInputError("probe returned an invalid manual principal")
    elif (
        report.requester is not None
        or not report.pull_request_author
        or state is not None
        and (
            report.pull_request_author != state.author
            or report.billing_principal.pull_request_author != state.author
        )
    ):
        raise CliInputError("probe returned an invalid automatic principal")
    if report.copilot_usable:
        reference = request.capability_reference
        verification = report.capability_verification
        if (
            reference is None
            or reference.repository != request.repository
            or reference.review_mode != request.review_mode
            or reference.principal_identity != report.billing_principal.identity
            or verification.source_reference != reference.source_reference
            or verification.evidence is None
            or verification.evidence.repository != request.repository
            or verification.evidence.review_mode != request.review_mode
            or verification.evidence.principal.identity
            != report.billing_principal.identity
        ):
            raise CliInputError("positive probe evidence is not request-bound")
    return report


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
    report: ProbeReport,
    observed_at: datetime,
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
        "copilot_coverage_complete": None,
        "copilot_review_mode": "unknown",
        "probe_request_digest": report.request_digest,
        "probe_observed_at": _iso_z(report.observed_at),
        "probe_valid_until": _iso_z(report.valid_until),
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
        "decision_stage": "preliminary",
        "gate_status": "evidence_validation_pending",
        "gate_eligible": False,
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
        if arguments.review_mode == "manual":
            if not arguments.requester:
                raise ValueError("manual route requires requester")
        elif arguments.requester is not None:
            raise ValueError("automatic route forbids requester")
    except (TypeError, ValueError) as error:
        raise CliInputError("route request is invalid") from error

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
    try:
        probe_request = ProbeRequest(
            repository=state.repository,
            review_mode=arguments.review_mode,
            manual_requester=arguments.requester,
            pull_request_number=state.pull_request_number,
            organization=arguments.organization,
            enterprise=arguments.enterprise,
            cost_center=arguments.cost_center,
            capability_reference=_capability_reference(
                arguments.capability_reference,
            ),
        )
    except (TypeError, ValueError) as error:
        raise CliInputError("route probe request is invalid") from error
    probe = _resolve(dependencies.probe, registry, ProbePort)
    report = probe.probe(probe_request)
    clock = _resolve(dependencies.clock, registry, ClockPort)
    observed_at = clock.now()
    report = _validate_probe_report(
        report,
        probe_request,
        observed_at,
        state,
    )
    availability_snapshot = ReviewerAvailabilitySnapshot()
    if dependencies.reviewer_availability is not None:
        availability_snapshot = dependencies.reviewer_availability.load(
            state.repository,
            state.pull_request_number,
            state.head_sha,
            purpose,
        )
        if not isinstance(availability_snapshot, ReviewerAvailabilitySnapshot):
            raise CliInputError("reviewer availability has an invalid type")
    qa_available = availability_snapshot.is_available(
        Reviewer.QA,
        state.repository,
        state.pull_request_number,
        state.head_sha,
        purpose,
        observed_at,
    )
    sec_available = availability_snapshot.is_available(
        Reviewer.SEC,
        state.repository,
        state.pull_request_number,
        state.head_sha,
        purpose,
        observed_at,
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
        copilot_usable=report.copilot_usable,
        copilot_coverage_complete=None,
        copilot_review_mode="unknown",
        qa_available=qa_available,
        sec_available=sec_available,
        policy_source_ref=state.api_base_sha,
        policy_source_path=str(POLICY_PATH),
        runtime_digest=runtime.digest,
        runtime_trust=runtime.trust,
        diff_digest=snapshot.diff_digest,
        prior_reviewers=frozenset(),
    )
    decision = registry.resolve(RoutingPolicyPort).route(request, config)
    payload = _route_payload(
        arguments=arguments,
        state=state,
        snapshot=snapshot,
        assessment=assessment,
        decision=decision,
        report=report,
        observed_at=observed_at,
    )
    _write_json(stdout, payload)
    return 30 if decision.route is ReviewRoute.BLOCKER else 0


def _gate_result_payload(result: GateResult) -> dict[str, object]:
    return {
        "schema_version": 1,
        "check_name": result.check_name,
        "conclusion": result.conclusion,
        "repository": result.repository,
        "pull_request_number": result.pull_request_number,
        "base_ref": result.base_ref,
        "base_sha": result.base_sha,
        "head_sha": result.head_sha,
        "pr_state_source": result.pr_state_source.value,
        "policy_source_ref": result.policy_source_ref,
        "policy_source_path": result.policy_source_path,
        "policy_digest": result.policy_digest,
        "runtime_digest": result.runtime_digest,
        "runtime_trust": result.runtime_trust.value,
        "diff_digest": result.diff_digest,
        "evidence_digest": result.evidence_digest,
        "required_reviewers": sorted(value.value for value in result.required_reviewers),
        "validated_reviewers": sorted(value.value for value in result.validated_reviewers),
        "unresolved_thread_count": result.unresolved_thread_count,
        "reasons": list(result.reasons),
        "observed_at": _iso_z(result.observed_at),
        "published": False,
    }


def _run_validate(
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
        if arguments.review_mode == "manual":
            if not arguments.requester:
                raise ValueError("manual validate requires requester")
        elif arguments.requester is not None:
            raise ValueError("automatic validate forbids requester")
    except (TypeError, ValueError) as error:
        raise CliInputError("validate request is invalid") from error
    state_port = _resolve(
        dependencies.pull_request_state,
        registry,
        PullRequestStatePort,
    )
    state = _validated_pr_state(
        state_port.load(arguments.repo, arguments.pull_request),
        arguments.repo,
        arguments.pull_request,
    )
    route_document, _ = _read_json(arguments.route_file)
    evidence_document, _ = _read_json(arguments.evidence_file)
    plan = _parse_preliminary_plan(route_document)
    evidence = _parse_gate_snapshot(evidence_document)
    if (
        plan.repository != arguments.repo
        or plan.pull_request_number != arguments.pull_request
    ):
        raise CliInputError("route does not match validate request")
    try:
        probe_request = ProbeRequest(
            repository=state.repository,
            review_mode=arguments.review_mode,
            manual_requester=arguments.requester,
            pull_request_number=state.pull_request_number,
            organization=arguments.organization,
            enterprise=arguments.enterprise,
            cost_center=arguments.cost_center,
            capability_reference=_capability_reference(arguments.capability_reference),
        )
    except (TypeError, ValueError) as error:
        raise CliInputError("validate probe request is invalid") from error
    probe = _resolve(dependencies.probe, registry, ProbePort)
    fresh_report = probe.probe(probe_request)
    clock = _resolve(dependencies.clock, registry, ClockPort)
    evaluated_at = clock.now()
    fresh_probe = _validate_probe_report(
        fresh_report,
        probe_request,
        evaluated_at,
        state,
    )
    availability = ReviewerAvailabilitySnapshot()
    if dependencies.reviewer_availability is not None:
        availability = dependencies.reviewer_availability.load(
            state.repository,
            state.pull_request_number,
            state.head_sha,
            plan.purpose,
        )
        if not isinstance(availability, ReviewerAvailabilitySnapshot):
            raise CliInputError("reviewer availability has an invalid type")

    policy_source = _resolve(dependencies.policy_source, registry, PolicySourcePort)
    try:
        document = policy_source.read_at_commit(
            repository_path,
            state.repository,
            state.api_base_sha,
            POLICY_PATH,
        )
    except Exception as error:
        raise CliInputError("trusted base policy is unavailable") from error
    if (
        document.trust is not DocumentTrust.COMMIT_OBJECT
        or document.source != f"{state.api_base_sha}:{POLICY_PATH}"
    ):
        raise CliInputError("base policy provenance is invalid")
    config = _resolve(dependencies.config, registry, ConfigPort).parse_routing(document)
    snapshot = _resolve(dependencies.diff_source, registry, DiffSourcePort).load(
        repository_path,
        state.repository,
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
    context = GateEvaluationContext(
        preliminary_plan=plan,
        current_pr_state=state,
        probe_request=probe_request,
        fresh_probe=fresh_probe,
        reviewer_availability=availability,
        evaluated_at=evaluated_at,
    )
    result = registry.resolve(EvidenceValidatorPort).validate(
        context,
        evidence,
        registry.runtime_provenance,
        config,
        snapshot,
        registry.resolve(RiskClassifierPort),
        registry.resolve(RoutingPolicyPort),
    )
    _write_json(stdout, _gate_result_payload(result))
    return 0 if result.conclusion == "success" else 32


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
        if arguments.command == "validate":
            return _run_validate(arguments, injected, registry, output)
        raise CliInputError("unknown command")
    except Exception:
        return _invalid(output)


if __name__ == "__main__":
    raise SystemExit(main())
