"""Reine, fail-closed Exact-Head-Evidenzvalidierung ohne I/O oder Publikation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from review_routing.contracts import (
    AdapterFactory,
    BoundEvidenceSource,
    BoundEvidenceSourceKind,
    CheckConclusion,
    CopilotReviewMode,
    CoverageStatus,
    DiffFile,
    DiffSnapshot,
    EvidenceValidatorPort,
    FileCoverage,
    GateEvaluationContext,
    GateResult,
    GateSnapshot,
    PreliminaryRoutePlan,
    Reviewer,
    ReviewRequest,
    ReviewState,
    RiskClassifierPort,
    RoutingConfig,
    RoutingPolicyPort,
    RuntimeProvenance,
)


_CHECK_NAME = "agent-governance/review-gate"
_COPILOT_APP = "copilot-pull-request-reviewer"
_COPILOT_LOGIN = "copilot-pull-request-reviewer[bot]"


def _source_valid(
    source: BoundEvidenceSource,
    context: GateEvaluationContext,
) -> bool:
    state = context.current_pr_state
    return source.is_valid_for(
        state.repository,
        state.pull_request_number,
        state.head_sha,
        context.evaluated_at,
    )


def _diff_key(file: DiffFile | FileCoverage) -> tuple[object, ...]:
    return (file.path, file.status, file.previous_path)


def _context_reasons(
    context: GateEvaluationContext,
    runtime: RuntimeProvenance,
    config: RoutingConfig,
    trusted_diff: DiffSnapshot,
) -> set[str]:
    reasons: set[str] = set()
    plan = context.preliminary_plan
    state = context.current_pr_state
    probe_request = context.probe_request
    probe = context.fresh_probe
    now = context.evaluated_at

    if (
        plan.repository != state.repository
        or plan.pull_request_number != state.pull_request_number
    ):
        reasons.add("preliminary_pr_mismatch")
    if plan.base_ref != state.base_ref:
        reasons.add("base_ref_changed")
    if plan.base_sha != state.api_base_sha:
        reasons.add("base_sha_changed")
    if plan.head_sha != state.head_sha:
        reasons.add("head_sha_changed")
    if plan.pr_state_source is not state.source:
        reasons.add("pr_state_source_mismatch")
    if state.observed_at > now:
        reasons.add("pr_state_observed_in_future")
    if (
        probe_request.repository != state.repository
        or probe_request.pull_request_number != state.pull_request_number
    ):
        reasons.add("probe_request_context_mismatch")
    if (
        probe.repository != probe_request.repository
        or probe.pull_request_number != probe_request.pull_request_number
        or probe.review_mode != probe_request.review_mode
        or probe.request_digest != probe_request.request_digest
        or not probe.observed_at <= now < probe.valid_until
        or not probe.billing_principal.is_valid_at(now)
    ):
        reasons.add("fresh_probe_invalid")
    elif probe_request.review_mode == "manual":
        if (
            probe.requester != probe_request.manual_requester
            or probe.billing_principal.requester != probe_request.manual_requester
            or probe.pull_request_author is not None
        ):
            reasons.add("fresh_probe_principal_mismatch")
    elif (
        probe.requester is not None
        or probe.pull_request_author != state.author
        or probe.billing_principal.pull_request_author != state.author
    ):
        reasons.add("fresh_probe_principal_mismatch")
    if probe.copilot_usable:
        reference = probe_request.capability_reference
        verification = probe.capability_verification
        if (
            reference is None
            or reference.repository != probe_request.repository
            or reference.review_mode != probe_request.review_mode
            or reference.principal_identity != probe.billing_principal.identity
            or verification.source_reference != reference.source_reference
            or verification.evidence is None
            or verification.evidence.repository != probe_request.repository
            or verification.evidence.review_mode != probe_request.review_mode
            or verification.evidence.principal.identity
            != probe.billing_principal.identity
        ):
            reasons.add("fresh_probe_capability_mismatch")
    if plan.runtime_digest != runtime.digest or plan.runtime_trust is not runtime.trust:
        reasons.add("runtime_provenance_mismatch")
    if runtime.trust.value != "installed":
        reasons.add("runtime_not_installed")
    if (
        plan.policy_source_ref != state.api_base_sha
        or plan.policy_source_path != "core/review-routing.toml"
        or plan.policy_digest != config.policy_digest
    ):
        reasons.add("policy_provenance_mismatch")
    if (
        trusted_diff.repository != state.repository
        or trusted_diff.api_base_sha != state.api_base_sha
        or trusted_diff.head_sha != state.head_sha
        or plan.merge_base_sha != trusted_diff.merge_base_sha
        or plan.diff_digest != trusted_diff.diff_digest
    ):
        reasons.add("diff_provenance_mismatch")
    for availability in context.reviewer_availability.evidence:
        if (
            availability.repository != state.repository
            or availability.pull_request_number != state.pull_request_number
            or availability.head_sha != state.head_sha
            or availability.purpose is not plan.purpose
            or not availability.observed_at <= now < availability.expires_at
        ):
            reasons.add("reviewer_availability_invalid")
    return reasons


def _snapshot_reasons(
    context: GateEvaluationContext,
    evidence: GateSnapshot,
) -> set[str]:
    state = context.current_pr_state
    reasons: set[str] = set()
    if (
        evidence.repository != state.repository
        or evidence.pull_request_number != state.pull_request_number
        or evidence.base_sha != state.api_base_sha
        or evidence.head_sha != state.head_sha
    ):
        reasons.add("evidence_context_mismatch")
    if not evidence.observed_at <= context.evaluated_at < evidence.valid_until:
        reasons.add("evidence_stale")
    for review in (*evidence.review_requests, *evidence.reviews):
        if review.submitted_at > context.evaluated_at:
            reasons.add("future_review_timestamp")
    for check in evidence.check_runs:
        if check.completed_at > context.evaluated_at:
            reasons.add("future_check_timestamp")
    return reasons


def _copilot_coverage_complete(
    context: GateEvaluationContext,
    evidence: GateSnapshot,
    trusted_diff: DiffSnapshot,
) -> bool:
    expected = {_diff_key(file) for file in trusted_diff.files}
    actual: dict[tuple[object, ...], FileCoverage] = {}
    for item in evidence.review_file_coverage:
        if item.reviewer is not Reviewer.COPILOT:
            continue
        key = _diff_key(item)
        if key in actual:
            return False
        actual[key] = item
    return (
        set(actual) == expected
        and all(
            item.coverage is CoverageStatus.REVIEWED
            and _source_valid(item.coverage_source, context)
            for item in actual.values()
        )
    )


def _review_mode(
    context: GateEvaluationContext,
    evidence: GateSnapshot,
) -> str:
    if not _source_valid(evidence.review_mode_source, context):
        return CopilotReviewMode.UNKNOWN.value
    return evidence.copilot_review_mode.value


def _validated_reviewers(
    context: GateEvaluationContext,
    evidence: GateSnapshot,
    required: frozenset[Reviewer],
) -> tuple[frozenset[Reviewer], set[str]]:
    state = context.current_pr_state
    valid: set[Reviewer] = set()
    reasons: set[str] = set()
    valid_copilot_reviews = []
    for review in evidence.reviews:
        if (
            review.commit_sha != state.head_sha
            or not _source_valid(review.source, context)
            or not review.source.observed_at
            <= review.submitted_at
            < review.source.valid_until
            or review.submitted_at > context.evaluated_at
            or review.findings_count != 0
        ):
            continue
        if review.reviewer is Reviewer.COPILOT:
            if (
                review.actor_login == _COPILOT_LOGIN
                and review.app_slug == _COPILOT_APP
                and review.state is ReviewState.COMMENTED
                and review.source.kind is BoundEvidenceSourceKind.GITHUB_API
            ):
                valid_copilot_reviews.append(review)
        elif review.reviewer in {Reviewer.QA, Reviewer.SEC}:
            if (
                review.state is ReviewState.APPROVED
                and review.source.kind is BoundEvidenceSourceKind.HARNESS_RUNTIME
            ):
                valid.add(review.reviewer)
    if valid_copilot_reviews:
        latest = max(valid_copilot_reviews, key=lambda review: review.submitted_at)
        newer_incomplete = any(
            request.reviewer is Reviewer.COPILOT
            and request.submitted_at > latest.submitted_at
            and request.state in {ReviewState.PENDING, ReviewState.ERROR}
            for request in evidence.review_requests
        )
        if not newer_incomplete:
            valid.add(Reviewer.COPILOT)
        else:
            reasons.add("newer_copilot_request_incomplete")
    for reviewer in required - valid:
        reasons.add(f"missing_reviewer:{reviewer.value}")
    return frozenset(valid & set(required)), reasons


def _checks_reasons(
    context: GateEvaluationContext,
    evidence: GateSnapshot,
    config: RoutingConfig,
) -> set[str]:
    state = context.current_pr_state
    reasons: set[str] = set()
    if not config.required_checks:
        return {"required_checks_empty"}
    for required in config.required_checks:
        matching = [
            check
            for check in evidence.check_runs
            if check.name == required.name
            and check.source_app_slug == required.source_app_slug
            and check.head_sha == state.head_sha
            and check.source.kind is BoundEvidenceSourceKind.GITHUB_API
            and _source_valid(check.source, context)
            and check.source.observed_at <= check.completed_at < check.source.valid_until
            and check.completed_at <= context.evaluated_at
        ]
        if not matching:
            reasons.add(f"missing_check:{required.name}")
        elif not any(check.conclusion is CheckConclusion.SUCCESS for check in matching):
            reasons.add(f"check_not_successful:{required.name}")
    return reasons


def _coverage_reasons(
    context: GateEvaluationContext,
    evidence: GateSnapshot,
    trusted_diff: DiffSnapshot,
    required_reviewers: frozenset[Reviewer],
) -> set[str]:
    reasons: set[str] = set()
    expected = {_diff_key(file) for file in trusted_diff.files}
    actual = {_diff_key(item) for item in evidence.review_file_coverage}
    if not actual.issubset(expected):
        reasons.add("evidence_diff_mismatch")
    for key in expected:
        covered = any(
            _diff_key(item) == key
            and item.reviewer in required_reviewers
            and item.coverage is CoverageStatus.REVIEWED
            and _source_valid(item.coverage_source, context)
            for item in evidence.review_file_coverage
        )
        if required_reviewers and not covered:
            reasons.add(f"file_not_covered:{key[0]}")
    return reasons


def _prior_reviewers(
    context: GateEvaluationContext,
    evidence: GateSnapshot,
) -> frozenset[Reviewer]:
    if context.preliminary_plan.purpose.value != "correction":
        return frozenset()
    return frozenset(
        review.reviewer
        for review in evidence.reviews
        if review.commit_sha != context.current_pr_state.head_sha
        and review.state in {ReviewState.COMMENTED, ReviewState.APPROVED}
    )


def validate_exact_head(
    context: GateEvaluationContext,
    evidence: GateSnapshot,
    runtime: RuntimeProvenance,
    trusted_config: RoutingConfig,
    trusted_diff: DiffSnapshot,
    risk_classifier: RiskClassifierPort,
    routing_policy: RoutingPolicyPort,
) -> GateResult:
    """Ermittelt Route und Gate ausschließlich aus erneut erhobenen, gebundenen Quellen."""
    reasons = _context_reasons(context, runtime, trusted_config, trusted_diff)
    reasons.update(_snapshot_reasons(context, evidence))
    assessment = risk_classifier.assess(trusted_diff, trusted_config)
    plan = context.preliminary_plan
    if assessment != plan.risk:
        reasons.add("risk_assessment_mismatch")
    coverage_complete = _copilot_coverage_complete(context, evidence, trusted_diff)
    review_mode = _review_mode(context, evidence)
    state = context.current_pr_state
    now = context.evaluated_at
    qa_available = context.reviewer_availability.is_available(
        Reviewer.QA,
        state.repository,
        state.pull_request_number,
        state.head_sha,
        plan.purpose,
        now,
    )
    sec_available = context.reviewer_availability.is_available(
        Reviewer.SEC,
        state.repository,
        state.pull_request_number,
        state.head_sha,
        plan.purpose,
        now,
    )
    prior_reviewers = _prior_reviewers(context, evidence)
    if plan.purpose.value == "correction" and not prior_reviewers:
        reasons.add("correction_prior_review_missing")
        prior_reviewers = frozenset({Reviewer.QA, Reviewer.SEC})
    request = ReviewRequest(
        repository=state.repository,
        base_sha=state.api_base_sha,
        head_sha=state.head_sha,
        purpose=plan.purpose,
        assessment=assessment,
        copilot_usable=context.fresh_probe.copilot_usable,
        copilot_coverage_complete=coverage_complete,
        copilot_review_mode=review_mode,
        qa_available=qa_available,
        sec_available=sec_available,
        policy_source_ref=state.api_base_sha,
        policy_source_path="core/review-routing.toml",
        runtime_digest=runtime.digest,
        runtime_trust=runtime.trust,
        diff_digest=trusted_diff.diff_digest,
        prior_reviewers=prior_reviewers,
    )
    decision = routing_policy.route(request, trusted_config)
    required = decision.required_reviewers
    if decision.route.value == "blocker":
        reasons.add("required_reviewer_unavailable")
    validated, review_reasons = _validated_reviewers(context, evidence, required)
    reasons.update(review_reasons)
    unresolved = sum(1 for thread in evidence.threads if thread.unresolved)
    if unresolved:
        reasons.add("unresolved_review_threads")
    reasons.update(_checks_reasons(context, evidence, trusted_config))
    reasons.update(_coverage_reasons(context, evidence, trusted_diff, required))
    conclusion = "success" if not reasons else "failure"
    return GateResult(
        check_name=_CHECK_NAME,
        conclusion=conclusion,
        repository=state.repository,
        pull_request_number=state.pull_request_number,
        base_ref=state.base_ref,
        base_sha=state.api_base_sha,
        head_sha=state.head_sha,
        pr_state_source=state.source,
        policy_source_ref=state.api_base_sha,
        policy_source_path="core/review-routing.toml",
        policy_digest=trusted_config.policy_digest,
        runtime_digest=runtime.digest,
        runtime_trust=runtime.trust,
        diff_digest=trusted_diff.diff_digest,
        evidence_digest=evidence.evidence_digest,
        required_reviewers=required,
        validated_reviewers=validated,
        unresolved_thread_count=unresolved,
        reasons=tuple(sorted(reasons)),
        observed_at=now,
    )


class EvidenceValidator(EvidenceValidatorPort):
    """Port-Adapter für die reine Evidenzvalidierung."""

    def validate(
        self,
        context: GateEvaluationContext,
        evidence: GateSnapshot,
        runtime: RuntimeProvenance,
        trusted_config: RoutingConfig,
        trusted_diff: DiffSnapshot,
        risk_classifier: RiskClassifierPort,
        routing_policy: RoutingPolicyPort,
    ) -> GateResult:
        return validate_exact_head(
            context,
            evidence,
            runtime,
            trusted_config,
            trusted_diff,
            risk_classifier,
            routing_policy,
        )


@dataclass(frozen=True)
class EvidenceValidatorFactory:
    provided_ports = (EvidenceValidatorPort,)
    required_ports: tuple[type[object], ...] = ()

    def build(self, dependencies: Mapping[type[object], object]) -> Mapping[type[object], object]:
        if dependencies:
            raise ValueError("evidence validator expects no dependencies")
        return {EvidenceValidatorPort: EvidenceValidator()}


def factory() -> AdapterFactory:
    """Meldet den read-only Validator an der Runtime-Registry an."""
    return EvidenceValidatorFactory()
