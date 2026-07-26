"""Einziger Vertragsrand für Review-Routing-Ports, Konfiguration und Fehler."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
from types import MappingProxyType
from typing import Mapping, Protocol
import unicodedata


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


class GitSourceError(RuntimeError):
    """Die lokale Git-Quelle kann keine vertrauensgebundene Evidenz liefern."""


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


class DiffMode(str, Enum):
    MERGE_BASE_TO_HEAD = "merge_base_to_head"


class DetectionMode(str, Enum):
    DISABLED = "disabled"


class FileStatus(str, Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"
    COPIED = "copied"


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


def _require_bool(value: object, field_name: str) -> None:
    if type(value) is not bool:
        raise ValueError(f"{field_name} must be a boolean")


def _require_bool_or_none(value: object, field_name: str) -> None:
    if value is not None and type(value) is not bool:
        raise ValueError(f"{field_name} must be a boolean or unknown")


def require_full_sha(value: str, field_name: str) -> None:
    """Akzeptiert ausschließlich vollständige kleingeschriebene SHA-1-Objektkennungen."""
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise ValueError(f"{field_name} must be 40 lowercase hexadecimal characters")


def require_repository(value: str) -> None:
    """Validiert die normalisierte GitHub-Identität OWNER/REPO ohne URL-Semantik."""
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?/"
        r"[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?",
        value,
    ):
        raise ValueError("repository must be a normalized OWNER/REPO identifier")
    if any(part in {".", ".."} for part in value.split("/")):
        raise ValueError("repository must be a normalized OWNER/REPO identifier")


def normalize_repo_path(value: str | PurePosixPath, field_name: str = "path") -> str:
    """Normalisiert einen geschlossenen relativen Repo-Pfad nach Unicode-NFC."""
    if not isinstance(value, (str, PurePosixPath)):
        raise ValueError(f"{field_name} must be a relative POSIX path")
    raw = str(value)
    if (
        not raw
        or raw == "."
        or raw.startswith("/")
        or "\\" in raw
        or "\x00" in raw
        or any(part in {"", ".", ".."} for part in raw.split("/"))
    ):
        raise ValueError(f"{field_name} must be a normalized relative POSIX path")
    return unicodedata.normalize("NFC", raw)


def _freeze_reviewers(reviewers: frozenset[Reviewer] | set[Reviewer]) -> frozenset[Reviewer]:
    frozen = frozenset(reviewers)
    if not all(isinstance(reviewer, Reviewer) for reviewer in frozen):
        raise ValueError("reviewers must be Reviewer values")
    return frozen


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

    @property
    def identity(self) -> tuple[str, str, str, str | None, str | None]:
        """Liefert die stabile Principal-Identität ohne zeitliche Evidenzmetadaten."""
        return (
            self.kind,
            self.identifier,
            self.review_mode,
            self.requester,
            self.pull_request_author,
        )

    def is_valid_at(self, now: datetime) -> bool:
        """Prüft die zeitlich begrenzte Principal-Evidenz fail-closed."""
        return self.observed_at <= now < self.expires_at


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
            and self.principal.identity == principal.identity
            and self.review_mode == review_mode
            and principal.is_valid_at(now)
            and self.observed_at <= now < self.expires_at
            and self.principal.is_valid_at(self.observed_at)
            and self.expires_at <= self.principal.expires_at
        )


@dataclass(frozen=True)
class ProbeSignals:
    billing_status: DiagnosticStatus
    usage_status: DiagnosticStatus
    provider_status: DiagnosticStatus
    permission_status: DiagnosticStatus
    capability: CapabilityEvidence | None
    repository: str
    principal: BillingPrincipal
    review_mode: str
    observed_at: datetime

    def __post_init__(self) -> None:
        _require_non_empty(self.repository, "repository")
        _require_non_empty(self.review_mode, "review_mode")
        if self.review_mode != self.principal.review_mode:
            raise ValueError("review_mode must match the authoritative billing principal")


@dataclass(frozen=True)
class ProbeReport:
    copilot_usable: bool
    routing_status: DiagnosticStatus
    signals: ProbeSignals
    usage: Usage

    def __post_init__(self) -> None:
        _require_bool(self.copilot_usable, "copilot_usable")


@dataclass(frozen=True)
class RiskAssessment:
    level: RiskLevel
    security_relevant: bool
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_bool(self.security_relevant, "security_relevant")
        reasons = tuple(self.reasons)
        if not all(isinstance(reason, str) for reason in reasons):
            raise ValueError("reasons must contain strings")
        object.__setattr__(self, "reasons", reasons)


@dataclass(frozen=True)
class DiffFile:
    path: str
    status: FileStatus
    additions: int
    deletions: int
    binary: bool
    previous_path: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, FileStatus):
            raise ValueError("status must be a FileStatus value")
        path = normalize_repo_path(self.path)
        previous_path = (
            normalize_repo_path(self.previous_path, "previous_path")
            if self.previous_path is not None
            else None
        )
        requires_previous = self.status in {FileStatus.RENAMED, FileStatus.COPIED}
        if requires_previous != (previous_path is not None):
            raise ValueError("previous_path is required exactly for renamed and copied files")
        for field_name in ("additions", "deletions"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        _require_bool(self.binary, "binary")
        if self.binary and (self.additions != 0 or self.deletions != 0):
            raise ValueError("binary files must have zero additions and deletions")
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "previous_path", previous_path)


@dataclass(frozen=True)
class DiffSnapshot:
    schema_version: int
    repository: str
    api_base_sha: str
    merge_base_sha: str
    head_sha: str
    diff_mode: DiffMode
    rename_detection: DetectionMode
    copy_detection: DetectionMode
    files: tuple[DiffFile, ...]
    explicit_risk: RiskLevel | None = None
    security_relevant: bool | None = None
    risk_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != 1 or isinstance(self.schema_version, bool):
            raise ValueError("schema_version must be 1")
        require_repository(self.repository)
        for field_name in ("api_base_sha", "merge_base_sha", "head_sha"):
            require_full_sha(getattr(self, field_name), field_name)
        if self.diff_mode is not DiffMode.MERGE_BASE_TO_HEAD:
            raise ValueError("diff_mode must be merge_base_to_head")
        if self.rename_detection is not DetectionMode.DISABLED:
            raise ValueError("rename_detection must be disabled")
        if self.copy_detection is not DetectionMode.DISABLED:
            raise ValueError("copy_detection must be disabled")
        files = tuple(self.files)
        if not all(isinstance(file, DiffFile) for file in files):
            raise ValueError("files must contain DiffFile values")
        files = tuple(
            sorted(
                files,
                key=lambda file: (file.path, file.status.value, file.previous_path or ""),
            )
        )
        current_paths = [file.path for file in files]
        if len(set(current_paths)) != len(current_paths):
            raise ValueError("diff paths must be unique after NFC normalization")
        previous_paths = {file.previous_path for file in files if file.previous_path is not None}
        if previous_paths & set(current_paths):
            raise ValueError("previous paths must not duplicate current diff paths")
        if self.explicit_risk is not None and not isinstance(self.explicit_risk, RiskLevel):
            raise ValueError("explicit_risk must be a RiskLevel or absent")
        _require_bool_or_none(self.security_relevant, "security_relevant")
        reasons = tuple(self.risk_reasons)
        if any(not isinstance(reason, str) or not reason or "\x00" in reason for reason in reasons):
            raise ValueError("risk_reasons must contain non-empty NUL-free strings")
        object.__setattr__(self, "files", files)
        object.__setattr__(self, "risk_reasons", tuple(sorted(reasons)))

    @property
    def diff_digest(self) -> str:
        """Bindet den vollständigen normalisierten Snapshot an eine kanonische SHA-256-Identität."""
        document = {
            "api_base_sha": self.api_base_sha,
            "copy_detection": self.copy_detection.value,
            "diff_mode": self.diff_mode.value,
            "explicit_risk": self.explicit_risk.value if self.explicit_risk is not None else None,
            "files": [
                {
                    "additions": file.additions,
                    "binary": file.binary,
                    "deletions": file.deletions,
                    "path": file.path,
                    "previous_path": file.previous_path,
                    "status": file.status.value,
                }
                for file in self.files
            ],
            "head_sha": self.head_sha,
            "merge_base_sha": self.merge_base_sha,
            "rename_detection": self.rename_detection.value,
            "repository": self.repository,
            "risk_reasons": list(self.risk_reasons),
            "schema_version": self.schema_version,
            "security_relevant": self.security_relevant,
        }
        canonical = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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
        _require_bool(self.copilot_usable, "copilot_usable")
        _require_bool_or_none(self.copilot_coverage_complete, "copilot_coverage_complete")
        _require_bool(self.qa_available, "qa_available")
        _require_bool(self.sec_available, "sec_available")
        if self.copilot_review_mode not in {"full", "degraded", "unknown"}:
            raise ValueError("copilot_review_mode must be full, degraded or unknown")
        object.__setattr__(self, "prior_reviewers", _freeze_reviewers(self.prior_reviewers))


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
        _require_bool(self.security_relevant, "security_relevant")
        _require_bool(self.copilot_usable, "copilot_usable")
        _require_bool_or_none(self.copilot_coverage_complete, "copilot_coverage_complete")
        _require_bool(self.qa_available, "qa_available")
        _require_bool(self.sec_available, "sec_available")
        object.__setattr__(self, "required_reviewers", _freeze_reviewers(self.required_reviewers))
        object.__setattr__(self, "prior_reviewers", _freeze_reviewers(self.prior_reviewers))


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


class RiskClassifierPort(ABC):
    @abstractmethod
    def assess(self, snapshot: DiffSnapshot, config: RoutingConfig) -> RiskAssessment:
        """Klassifiziert den vollständigen vertrauensgebundenen Diff deterministisch."""


class PolicySourcePort(ABC):
    @abstractmethod
    def read_at_commit(
        self,
        repo_path: Path,
        repository: str,
        commit_sha: str,
        policy_path: PurePosixPath,
    ) -> PolicyDocument:
        """Liest eine Policy ausschließlich aus einem verifizierten Commitobjekt."""


class DiffSourcePort(ABC):
    @abstractmethod
    def load(
        self,
        repo_path: Path,
        repository: str,
        api_base_sha: str,
        head_sha: str,
    ) -> DiffSnapshot:
        """Erhebt den vollständigen Merge-Base→Head-Diff aus lokalen Git-Objekten."""


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
