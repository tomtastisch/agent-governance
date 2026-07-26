"""Einziger Vertragsrand für Review-Routing-Ports, Konfiguration und Fehler."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import Mapping, Protocol


SHA_RE = re.compile(r"[0-9a-f]{40}")
DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")


class PolicyError(ValueError):
    """Basisfehler für eine nicht verwendbare Routing-Policy."""


class PolicyValidationError(PolicyError):
    """Die Policy verletzt den geschlossenen Konfigurationsvertrag."""


class RegistryError(RuntimeError):
    """Basisfehler für eine unvollständige oder widersprüchliche Laufzeitbindung."""


class MissingProviderError(RegistryError):
    """Für einen benötigten Port ist kein Provider registriert."""


class DuplicateProviderError(RegistryError):
    """Mehrere Factories bieten denselben Port an."""


class CyclicProviderError(RegistryError):
    """Die Port-Abhängigkeiten der Factories bilden einen Zyklus."""


class InvalidFactoryError(RegistryError):
    """Eine Factory hält ihren deklarierten Port-Vertrag nicht ein."""


class RuntimeTrustMismatchError(RegistryError):
    """Ein externer, vertrauenswürdiger Runtime-Pin passt nicht zum Manifest."""


class DocumentTrust(str, Enum):
    DEVELOPMENT = "development"
    COMMIT_OBJECT = "commit_object"


class RuntimeTrustSource(str, Enum):
    PUBLISHER_APP = "publisher_app"
    INSTALLED_CONFIG = "installed_config"
    DEVELOPMENT = "development"


class RuntimeTrust(str, Enum):
    INSTALLED = "installed"
    DEVELOPMENT = "development"


class DiagnosticStatus(str, Enum):
    AVAILABLE = "available"
    LOW_BUDGET = "low_budget"
    QUOTA_EXHAUSTED = "quota_exhausted"
    BUDGET_BLOCKED = "budget_blocked"
    RATE_LIMITED = "rate_limited"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PERMISSION_DENIED = "permission_denied"
    UNKNOWN = "unknown"


class ReviewPurpose(str, Enum):
    CHECKPOINT = "checkpoint"
    FINAL_EXACT_HEAD = "final_exact_head"
    CORRECTION = "correction"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReviewRoute(str, Enum):
    LOCAL_CHECKS = "local_checks"
    COPILOT = "copilot"
    COPILOT_QA = "copilot_qa"
    COPILOT_QA_SEC = "copilot_qa_sec"
    QA = "qa"
    QA_SEC = "qa_sec"
    BLOCKER = "blocker"


class Reviewer(str, Enum):
    COPILOT = "copilot"
    QA = "qa"
    SEC = "sec"


def _require_digest(value: str, field_name: str) -> None:
    if not DIGEST_RE.fullmatch(value):
        raise ValueError(f"{field_name} must be a sha256 digest")


def _require_non_empty(value: str, field_name: str) -> None:
    if not value:
        raise ValueError(f"{field_name} must be non-empty")


def _require_finite_non_negative(value: float | None, field_name: str) -> None:
    if value is not None and (not math.isfinite(value) or value < 0):
        raise ValueError(f"{field_name} must be finite and non-negative")


def canonical_policy_digest(policy: Mapping[str, object]) -> str:
    """Bindet die vollständig validierte TOML-Struktur an eine kanonische SHA-256-Identität."""
    canonical = json.dumps(policy, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PolicyDocument:
    content: str
    trust: DocumentTrust
    source: str


@dataclass(frozen=True)
class PathMarker:
    glob: str
    level: str
    security_relevant: bool


@dataclass(frozen=True)
class RequiredCheck:
    name: str
    source_app_slug: str


@dataclass(frozen=True)
class GatePublisher:
    expected_app_slug: str


@dataclass(frozen=True)
class RoutingConfig:
    schema_version: int
    thresholds: Mapping[str, int]
    path_markers: tuple[PathMarker, ...]
    routes: Mapping[str, Mapping[bool, Mapping[str, str]]]
    required_checks: tuple[RequiredCheck, ...]
    publisher: GatePublisher
    policy_digest: str

    def __post_init__(self) -> None:
        _require_digest(self.policy_digest, "policy_digest")
        object.__setattr__(self, "thresholds", MappingProxyType(dict(self.thresholds)))
        object.__setattr__(
            self,
            "routes",
            MappingProxyType(
                {
                    purpose: MappingProxyType(
                        {usable: MappingProxyType(dict(levels)) for usable, levels in states.items()}
                    )
                    for purpose, states in self.routes.items()
                }
            ),
        )


@dataclass(frozen=True)
class Usage:
    used: float | None
    limit: float | None

    def __post_init__(self) -> None:
        _require_finite_non_negative(self.used, "used")
        _require_finite_non_negative(self.limit, "limit")

    @property
    def remaining(self) -> float | None:
        if self.used is None or self.limit is None:
            return None
        return self.limit - self.used


@dataclass(frozen=True)
class BillingPrincipal:
    kind: str
    identifier: str
    review_mode: str
    requester: str | None
    pull_request_author: str | None
    source: str
    observed_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        for field_name in ("kind", "identifier", "review_mode", "source"):
            _require_non_empty(getattr(self, field_name), field_name)
        if self.expires_at <= self.observed_at:
            raise ValueError("expires_at must be after observed_at")


@dataclass(frozen=True)
class CapabilityEvidence:
    repository: str
    principal: BillingPrincipal
    review_mode: str
    observed_at: datetime
    expires_at: datetime
    source: str

    def __post_init__(self) -> None:
        for field_name in ("repository", "review_mode", "source"):
            _require_non_empty(getattr(self, field_name), field_name)
        if self.review_mode != self.principal.review_mode:
            raise ValueError("review_mode must match the billing principal")
        if self.expires_at <= self.observed_at:
            raise ValueError("expires_at must be after observed_at")

    def is_valid_for(self, repository: str, principal: BillingPrincipal, review_mode: str, now: datetime) -> bool:
        return (
            self.repository == repository
            and self.principal == principal
            and self.review_mode == review_mode
            and self.observed_at <= now < self.expires_at
        )


@dataclass(frozen=True)
class ProbeSignals:
    billing_status: DiagnosticStatus
    usage_status: DiagnosticStatus
    provider_status: DiagnosticStatus
    permission_status: DiagnosticStatus
    capability: CapabilityEvidence | None
    observed_at: datetime


@dataclass(frozen=True)
class ProbeReport:
    copilot_usable: bool
    routing_status: DiagnosticStatus
    signals: ProbeSignals
    usage: Usage


@dataclass(frozen=True)
class RiskAssessment:
    level: RiskLevel
    security_relevant: bool
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class QaCostEstimate:
    model: str | None = None
    estimated_input_tokens: int | None = None
    estimated_output_tokens: int | None = None
    actual_input_tokens: int | None = None
    actual_output_tokens: int | None = None
    price_source: str | None = None
    estimated_cost: float | None = None
    actual_cost: float | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "estimated_input_tokens",
            "estimated_output_tokens",
            "actual_input_tokens",
            "actual_output_tokens",
        ):
            value = getattr(self, field_name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise ValueError(f"{field_name} must be a non-negative integer")
        _require_finite_non_negative(self.estimated_cost, "estimated_cost")
        _require_finite_non_negative(self.actual_cost, "actual_cost")


@dataclass(frozen=True)
class ReviewRequest:
    repository: str
    base_sha: str
    head_sha: str
    purpose: ReviewPurpose
    assessment: RiskAssessment
    copilot_usable: bool
    copilot_coverage_complete: bool | None
    copilot_review_mode: str
    qa_available: bool
    sec_available: bool
    policy_source_ref: str
    policy_source_path: str
    runtime_digest: str
    runtime_trust: RuntimeTrust
    diff_digest: str
    prior_reviewers: frozenset[Reviewer] = field(default_factory=frozenset)
    usage: Usage | None = None

    def __post_init__(self) -> None:
        if not SHA_RE.fullmatch(self.base_sha) or not SHA_RE.fullmatch(self.head_sha):
            raise ValueError("base_sha and head_sha must be 40 lowercase hexadecimal characters")
        for field_name in ("repository", "policy_source_ref", "policy_source_path", "copilot_review_mode"):
            _require_non_empty(getattr(self, field_name), field_name)
        _require_digest(self.runtime_digest, "runtime_digest")
        _require_digest(self.diff_digest, "diff_digest")
        if self.copilot_coverage_complete not in (True, False, None):
            raise ValueError("copilot_coverage_complete must be true, false or unknown")
        if self.copilot_review_mode not in {"full", "degraded", "unknown"}:
            raise ValueError("copilot_review_mode must be full, degraded or unknown")
        object.__setattr__(self, "prior_reviewers", frozenset(self.prior_reviewers))


@dataclass(frozen=True)
class RouteDecision:
    route: ReviewRoute
    required_reviewers: frozenset[Reviewer]
    repository: str
    base_sha: str
    head_sha: str
    purpose: ReviewPurpose
    risk: RiskLevel
    security_relevant: bool
    copilot_usable: bool
    copilot_coverage_complete: bool | None
    copilot_review_mode: str
    qa_available: bool
    sec_available: bool
    policy_source_ref: str
    policy_source_path: str
    policy_digest: str
    runtime_digest: str
    runtime_trust: RuntimeTrust
    diff_digest: str
    prior_reviewers: frozenset[Reviewer]

    def __post_init__(self) -> None:
        if not SHA_RE.fullmatch(self.base_sha) or not SHA_RE.fullmatch(self.head_sha):
            raise ValueError("base_sha and head_sha must be 40 lowercase hexadecimal characters")
        for field_name in ("repository", "policy_source_ref", "policy_source_path", "copilot_review_mode"):
            _require_non_empty(getattr(self, field_name), field_name)
        for field_name in ("policy_digest", "runtime_digest", "diff_digest"):
            _require_digest(getattr(self, field_name), field_name)
        object.__setattr__(self, "required_reviewers", frozenset(self.required_reviewers))
        object.__setattr__(self, "prior_reviewers", frozenset(self.prior_reviewers))


@dataclass(frozen=True)
class RuntimeTrustConfig:
    expected_runtime_digest: str | None
    source: RuntimeTrustSource
    observed_at: datetime


@dataclass(frozen=True)
class RuntimeProvenance:
    digest: str
    trust: RuntimeTrust


class ConfigPort(ABC):
    @abstractmethod
    def parse_routing(self, document: PolicyDocument) -> RoutingConfig:
        """Validiert und dekodiert eine Routing-Policy aus ihrer vertrauensgebundenen Quelle."""


class RuntimeTrustPort(ABC):
    @abstractmethod
    def load(self) -> RuntimeTrustConfig:
        """Lädt den extern bestimmten Runtime-Pin ohne Einfluss der Kandidatenpolicy."""


class RoutingPolicyPort(ABC):
    @abstractmethod
    def route(self, request: ReviewRequest, config: RoutingConfig) -> RouteDecision:
        """Leitet read-only die erforderliche Review-Route aus der normativen Matrix ab."""


@dataclass(frozen=True)
class CliDependencies:
    """Programmatic-only Grenze für externe, vertrauenswürdige Abhängigkeiten."""

    runtime_trust_port: RuntimeTrustPort | None = None


class AdapterFactory(Protocol):
    """Deklariert Ports und erzeugt ihre Implementierungen aus aufgelösten Abhängigkeiten."""

    provided_ports: tuple[type[object], ...]
    required_ports: tuple[type[object], ...]

    def build(self, dependencies: Mapping[type[object], object]) -> Mapping[type[object], object]:
        """Erzeugt genau die für diese Factory deklarierten Port-Implementierungen."""
