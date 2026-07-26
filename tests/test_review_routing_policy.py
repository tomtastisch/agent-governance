#!/usr/bin/env python3
"""Verhaltensspezifikation für die deterministische Review-Route."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from review_routing.policy import classify_usability, route_review
from review_routing.adapters.toml_config import TomlConfig
from review_routing.contracts import (
    BillingPrincipal,
    CapabilityEvidence,
    DiagnosticStatus,
    PolicyDocument,
    ProbeSignals,
    ReviewPurpose,
    ReviewRequest,
    Reviewer,
    ReviewRoute,
    RiskAssessment,
    RiskLevel,
    RuntimeTrust,
    Usage,
)


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 7, 26, tzinfo=timezone.utc)
SHA_A = "a" * 40
SHA_B = "b" * 40


def principal(*, identifier: str = "tom", review_mode: str = "manual") -> BillingPrincipal:
    return BillingPrincipal(
        kind="personal",
        identifier=identifier,
        review_mode=review_mode,
        requester="tom",
        pull_request_author="tom",
        source="operator_evidence",
        observed_at=NOW,
        expires_at=NOW + timedelta(hours=1),
    )


def capability(
    *,
    repository: str = "tomtastisch/agent-governance",
    billing_principal: BillingPrincipal | None = None,
    review_mode: str = "manual",
    observed_at: datetime = NOW,
    expires_at: datetime | None = None,
) -> CapabilityEvidence:
    return CapabilityEvidence(
        repository=repository,
        principal=billing_principal or principal(review_mode=review_mode),
        review_mode=review_mode,
        observed_at=observed_at,
        expires_at=expires_at or observed_at + timedelta(hours=1),
        source="completed_review",
    )


def signals(status: DiagnosticStatus) -> ProbeSignals:
    return ProbeSignals(
        billing_status=status,
        usage_status=DiagnosticStatus.AVAILABLE,
        provider_status=DiagnosticStatus.AVAILABLE,
        permission_status=DiagnosticStatus.AVAILABLE,
        capability=capability(),
        repository="tomtastisch/agent-governance",
        principal=principal(),
        review_mode="manual",
        observed_at=NOW,
    )


def request(
    *,
    purpose: ReviewPurpose = ReviewPurpose.CHECKPOINT,
    risk: RiskLevel = RiskLevel.LOW,
    copilot_usable: bool = True,
    security_relevant: bool = False,
    coverage_complete: bool | None = True,
    copilot_review_mode: str = "full",
    qa_available: bool = True,
    sec_available: bool = True,
    prior_reviewers: frozenset[Reviewer] = frozenset(),
    usage: Usage | None = None,
) -> ReviewRequest:
    return ReviewRequest(
        repository="tomtastisch/agent-governance",
        base_sha=SHA_A,
        head_sha=SHA_B,
        purpose=purpose,
        assessment=RiskAssessment(risk, security_relevant),
        copilot_usable=copilot_usable,
        copilot_coverage_complete=coverage_complete,
        copilot_review_mode=copilot_review_mode,
        qa_available=qa_available,
        sec_available=sec_available,
        policy_source_ref=SHA_A,
        policy_source_path="core/review-routing.toml",
        runtime_digest="sha256:" + "c" * 64,
        runtime_trust=RuntimeTrust.DEVELOPMENT,
        diff_digest="sha256:" + "d" * 64,
        prior_reviewers=prior_reviewers,
        usage=usage,
    )


class UsabilityClassificationTest(unittest.TestCase):
    """Die Diagnose bleibt erhalten, während nur positive Evidenz nutzbar macht."""

    def test_every_required_status_has_the_declared_usability(self):
        cases = {
            DiagnosticStatus.AVAILABLE: True,
            DiagnosticStatus.LOW_BUDGET: True,
            DiagnosticStatus.QUOTA_EXHAUSTED: False,
            DiagnosticStatus.BUDGET_BLOCKED: False,
            DiagnosticStatus.RATE_LIMITED: False,
            DiagnosticStatus.PROVIDER_UNAVAILABLE: False,
            DiagnosticStatus.PERMISSION_DENIED: False,
            DiagnosticStatus.UNKNOWN: False,
        }

        for status, expected_usable in cases.items():
            with self.subTest(status=status):
                self.assertEqual(classify_usability(signals(status)), (expected_usable, status))

    def test_highest_precedence_signal_wins(self):
        result = classify_usability(
            ProbeSignals(
                billing_status=DiagnosticStatus.QUOTA_EXHAUSTED,
                usage_status=DiagnosticStatus.LOW_BUDGET,
                provider_status=DiagnosticStatus.BUDGET_BLOCKED,
                permission_status=DiagnosticStatus.AVAILABLE,
                capability=capability(),
                repository="tomtastisch/agent-governance",
                principal=principal(),
                review_mode="manual",
                observed_at=NOW,
            )
        )

        self.assertEqual(result, (False, DiagnosticStatus.BUDGET_BLOCKED))

    def test_historical_usage_without_current_capability_is_not_usable(self):
        usable, status = classify_usability(
            ProbeSignals(
                billing_status=DiagnosticStatus.AVAILABLE,
                usage_status=DiagnosticStatus.AVAILABLE,
                provider_status=DiagnosticStatus.AVAILABLE,
                permission_status=DiagnosticStatus.AVAILABLE,
                capability=None,
                repository="tomtastisch/agent-governance",
                principal=principal(),
                review_mode="manual",
                observed_at=NOW,
            )
        )

        self.assertFalse(usable)
        self.assertEqual(status, DiagnosticStatus.UNKNOWN)

    def test_capability_must_match_the_authoritative_probe_context(self):
        cases = {
            "foreign_repository": capability(repository="tomtastisch/other"),
            "foreign_principal": capability(billing_principal=principal(identifier="other")),
            "foreign_review_mode": capability(
                billing_principal=principal(review_mode="automatic"),
                review_mode="automatic",
            ),
            "future": capability(observed_at=NOW + timedelta(minutes=1)),
            "expired": capability(
                observed_at=NOW - timedelta(hours=2),
                expires_at=NOW - timedelta(hours=1),
            ),
        }

        for name, evidence in cases.items():
            with self.subTest(name=name):
                usable, status = classify_usability(
                    ProbeSignals(
                        billing_status=DiagnosticStatus.AVAILABLE,
                        usage_status=DiagnosticStatus.AVAILABLE,
                        provider_status=DiagnosticStatus.AVAILABLE,
                        permission_status=DiagnosticStatus.AVAILABLE,
                        capability=evidence,
                        repository="tomtastisch/agent-governance",
                        principal=principal(),
                        review_mode="manual",
                        observed_at=NOW,
                    )
                )
                self.assertEqual((usable, status), (False, DiagnosticStatus.UNKNOWN))

    def test_current_capability_for_the_authoritative_context_is_usable(self):
        self.assertEqual(
            classify_usability(signals(DiagnosticStatus.AVAILABLE)),
            (True, DiagnosticStatus.AVAILABLE),
        )


class ContractValidationTest(unittest.TestCase):
    """Geschlossene Werttypen und Collections bleiben gegen Python-Sonderfälle robust."""

    def test_boolean_fields_reject_strings_and_integer_lookalikes(self):
        for invalid in ("true", 0, 1):
            with self.subTest(target="risk", invalid=invalid):
                with self.assertRaises(ValueError):
                    RiskAssessment(RiskLevel.LOW, invalid)
            for field_name in (
                "copilot_usable",
                "coverage_complete",
                "qa_available",
                "sec_available",
            ):
                with self.subTest(target=field_name, invalid=invalid):
                    with self.assertRaises(ValueError):
                        request(**{field_name: invalid})

        decision = route_review(request(), TomlConfig().parse_routing(
            PolicyDocument(
                content=(ROOT / "core/review-routing.toml").read_text(encoding="utf-8"),
                trust="development",
                source="core/review-routing.toml",
            )
        ))
        for field_name in (
            "security_relevant",
            "copilot_usable",
            "copilot_coverage_complete",
            "qa_available",
            "sec_available",
        ):
            for invalid in ("true", 0, 1):
                with self.subTest(target=field_name, invalid=invalid):
                    with self.assertRaises(ValueError):
                        replace(decision, **{field_name: invalid})

    def test_task_two_collections_are_defensively_frozen(self):
        reasons = ["path marker"]
        prior_reviewers = {Reviewer.COPILOT}
        assessment = RiskAssessment(RiskLevel.LOW, False, reasons)
        review_request = request(prior_reviewers=prior_reviewers)
        decision = route_review(review_request, TomlConfig().parse_routing(
            PolicyDocument(
                content=(ROOT / "core/review-routing.toml").read_text(encoding="utf-8"),
                trust="development",
                source="core/review-routing.toml",
            )
        ))
        reasons.append("late mutation")
        prior_reviewers.add(Reviewer.QA)

        self.assertEqual(assessment.reasons, ("path marker",))
        self.assertEqual(review_request.prior_reviewers, frozenset({Reviewer.COPILOT}))
        self.assertIsInstance(decision.required_reviewers, frozenset)
        self.assertIsInstance(decision.prior_reviewers, frozenset)
        with self.assertRaises(AttributeError):
            decision.required_reviewers.add(Reviewer.QA)


class RoutePolicyTest(unittest.TestCase):
    """Die TOML-Matrix und ihre fail-closed Überlagerungen sind ausführbar."""

    @classmethod
    def setUpClass(cls):
        cls.config = TomlConfig().parse_routing(
            PolicyDocument(
                content=(ROOT / "core/review-routing.toml").read_text(encoding="utf-8"),
                trust="development",
                source="core/review-routing.toml",
            )
        )

    def test_all_checkpoint_and_final_matrix_cells_match_the_toml_route(self):
        for purpose in (ReviewPurpose.CHECKPOINT, ReviewPurpose.FINAL_EXACT_HEAD):
            for copilot_usable in (True, False):
                for risk in RiskLevel:
                    with self.subTest(purpose=purpose, usable=copilot_usable, risk=risk):
                        decision = route_review(
                            request(purpose=purpose, risk=risk, copilot_usable=copilot_usable),
                            self.config,
                        )
                        expected = self.config.routes[purpose.value][copilot_usable][risk.value]
                        self.assertEqual(decision.route.value, expected)
                        if not copilot_usable and purpose is ReviewPurpose.CHECKPOINT:
                            self.assertIn(Reviewer.QA, decision.required_reviewers)

    def test_remaining_budget_never_changes_an_otherwise_identical_route(self):
        known = route_review(
            request(usage=Usage(used=2, limit=10)),
            self.config,
        )
        unknown = route_review(
            request(usage=Usage(used=None, limit=10)),
            self.config,
        )

        self.assertEqual(known.route, unknown.route)
        self.assertEqual(known.required_reviewers, unknown.required_reviewers)

    def test_unavailable_required_qa_becomes_a_blocker_without_dropping_reviewers(self):
        decision = route_review(
            request(risk=RiskLevel.HIGH, qa_available=False),
            self.config,
        )

        self.assertEqual(decision.route, ReviewRoute.BLOCKER)
        self.assertEqual(decision.required_reviewers, frozenset({Reviewer.COPILOT, Reviewer.QA}))

    def test_unavailable_required_sec_becomes_a_blocker_without_dropping_reviewers(self):
        decision = route_review(
            request(risk=RiskLevel.CRITICAL, sec_available=False),
            self.config,
        )

        self.assertEqual(decision.route, ReviewRoute.BLOCKER)
        self.assertEqual(
            decision.required_reviewers,
            frozenset({Reviewer.COPILOT, Reviewer.QA, Reviewer.SEC}),
        )

    def test_security_relevance_adds_sec_and_a_route_representable_qa(self):
        decision = route_review(
            request(security_relevant=True),
            self.config,
        )

        self.assertEqual(decision.route, ReviewRoute.QA_SEC)
        self.assertTrue({Reviewer.QA, Reviewer.SEC} <= decision.required_reviewers)

    def test_partial_or_unknown_coverage_adds_qa_at_any_risk(self):
        for coverage in (False, None):
            with self.subTest(coverage=coverage):
                decision = route_review(
                    request(risk=RiskLevel.LOW, coverage_complete=coverage),
                    self.config,
                )
                self.assertIn(Reviewer.QA, decision.required_reviewers)

    def test_degraded_or_unknown_copilot_mode_adds_qa_at_any_risk(self):
        for mode in ("degraded", "unknown"):
            with self.subTest(mode=mode):
                decision = route_review(
                    request(risk=RiskLevel.LOW, copilot_review_mode=mode),
                    self.config,
                )
                self.assertIn(Reviewer.QA, decision.required_reviewers)

    def test_correction_replaces_unusable_copilot_and_binds_the_new_head(self):
        decision = route_review(
            request(
                purpose=ReviewPurpose.CORRECTION,
                copilot_usable=False,
                prior_reviewers=frozenset({Reviewer.COPILOT, Reviewer.SEC}),
            ),
            self.config,
        )

        self.assertEqual(decision.route, ReviewRoute.QA_SEC)
        self.assertEqual(decision.head_sha, SHA_B)
        self.assertEqual(decision.required_reviewers, frozenset({Reviewer.QA, Reviewer.SEC}))

    def test_correction_requires_previous_reviewer_evidence(self):
        with self.assertRaises(ValueError):
            route_review(request(purpose=ReviewPurpose.CORRECTION), self.config)

    def test_decision_copies_policy_digest_and_deterministic_provenance(self):
        decision = route_review(request(), self.config)

        self.assertEqual(decision.policy_digest, self.config.policy_digest)
        self.assertEqual(decision.policy_source_ref, SHA_A)
        self.assertEqual(decision.diff_digest, "sha256:" + "d" * 64)


if __name__ == "__main__":
    unittest.main()
