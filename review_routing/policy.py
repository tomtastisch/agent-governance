"""Reine, deterministische Verwendbarkeits- und Routing-Policy."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from review_routing.contracts import (
    AdapterFactory,
    DiagnosticStatus,
    ProbeSignals,
    ReviewPurpose,
    ReviewRequest,
    Reviewer,
    ReviewRoute,
    RouteDecision,
    RoutingConfig,
    RoutingPolicyPort,
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

_ROUTE_REVIEWERS = {
    ReviewRoute.LOCAL_CHECKS: frozenset(),
    ReviewRoute.COPILOT: frozenset({Reviewer.COPILOT}),
    ReviewRoute.COPILOT_QA: frozenset({Reviewer.COPILOT, Reviewer.QA}),
    ReviewRoute.COPILOT_QA_SEC: frozenset({Reviewer.COPILOT, Reviewer.QA, Reviewer.SEC}),
    ReviewRoute.QA: frozenset({Reviewer.QA}),
    ReviewRoute.QA_SEC: frozenset({Reviewer.QA, Reviewer.SEC}),
}


def classify_usability(signals: ProbeSignals) -> tuple[bool, DiagnosticStatus]:
    """Erhält die höchste Diagnose und erlaubt Copilot nur bei aktueller Capability-Evidenz."""
    statuses = (
        signals.billing_status,
        signals.usage_status,
        signals.provider_status,
        signals.permission_status,
    )
    status = next(candidate for candidate in _STATUS_PRECEDENCE if candidate in statuses)
    if status not in {DiagnosticStatus.AVAILABLE, DiagnosticStatus.LOW_BUDGET}:
        return False, status
    if signals.capability is None or signals.capability.expires_at <= signals.observed_at:
        return False, DiagnosticStatus.UNKNOWN
    return True, status


def _reviewers_for_route(route: str) -> frozenset[Reviewer]:
    try:
        return _ROUTE_REVIEWERS[ReviewRoute(route)]
    except (KeyError, ValueError) as error:
        raise ValueError("routing matrix must resolve to a non-blocker declared route") from error


def _route_for_reviewers(reviewers: frozenset[Reviewer]) -> ReviewRoute:
    for route, required in _ROUTE_REVIEWERS.items():
        if required == reviewers:
            return route
    raise ValueError("required reviewer set has no declared route")


def _matrix_reviewers(request: ReviewRequest, config: RoutingConfig) -> frozenset[Reviewer]:
    if request.purpose is ReviewPurpose.CORRECTION:
        if not request.prior_reviewers:
            raise ValueError("correction requires a non-empty prior reviewer set")
        reviewers = set(request.prior_reviewers)
        if not request.copilot_usable:
            reviewers.discard(Reviewer.COPILOT)
            reviewers.add(Reviewer.QA)
        return frozenset(reviewers)
    route = config.routes[request.purpose.value][request.copilot_usable][request.assessment.level.value]
    return _reviewers_for_route(route)


def route_review(request: ReviewRequest, config: RoutingConfig) -> RouteDecision:
    """Wendet die zentrale Matrix samt vollständigkeits- und rollenbasiertem Fail-Closed an."""
    reviewers = set(_matrix_reviewers(request, config))
    if request.assessment.security_relevant:
        reviewers.add(Reviewer.SEC)
    if request.copilot_coverage_complete is not True or request.copilot_review_mode != "full":
        reviewers.add(Reviewer.QA)
    if Reviewer.SEC in reviewers:
        reviewers.add(Reviewer.QA)
    required_reviewers = frozenset(reviewers)
    unavailable = (
        (Reviewer.QA in required_reviewers and not request.qa_available)
        or (Reviewer.SEC in required_reviewers and not request.sec_available)
    )
    route = ReviewRoute.BLOCKER if unavailable else _route_for_reviewers(required_reviewers)
    return RouteDecision(
        route=route,
        required_reviewers=required_reviewers,
        repository=request.repository,
        base_sha=request.base_sha,
        head_sha=request.head_sha,
        purpose=request.purpose,
        risk=request.assessment.level,
        security_relevant=request.assessment.security_relevant,
        copilot_usable=request.copilot_usable,
        copilot_coverage_complete=request.copilot_coverage_complete,
        copilot_review_mode=request.copilot_review_mode,
        qa_available=request.qa_available,
        sec_available=request.sec_available,
        policy_source_ref=request.policy_source_ref,
        policy_source_path=request.policy_source_path,
        policy_digest=config.policy_digest,
        runtime_digest=request.runtime_digest,
        runtime_trust=request.runtime_trust,
        diff_digest=request.diff_digest,
        prior_reviewers=request.prior_reviewers,
    )


class RoutingPolicy(RoutingPolicyPort):
    """Port-Adapter für die reine Funktionspolicy."""

    def route(self, request: ReviewRequest, config: RoutingConfig) -> RouteDecision:
        return route_review(request, config)


@dataclass(frozen=True)
class RoutingPolicyFactory:
    provided_ports = (RoutingPolicyPort,)
    required_ports: tuple[type[object], ...] = ()

    def build(self, dependencies: Mapping[type[object], object]) -> Mapping[type[object], object]:
        if dependencies:
            raise ValueError("routing policy expects no dependencies")
        return {RoutingPolicyPort: RoutingPolicy()}


def factory() -> AdapterFactory:
    """Meldet die reine Routing-Policy an der Runtime-Registry an."""
    return RoutingPolicyFactory()
