"""Einziger Vertragsrand für Review-Routing-Ports, Konfiguration und Fehler."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
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


class ProbePortError(RuntimeError):
    """Basisfehler für einen sanitisierten externen Probe-Port."""


class PermissionDeniedError(ProbePortError):
    """Die dokumentierte API hat den read-only Zugriff abgelehnt."""


class RateLimitedError(ProbePortError):
    """Die dokumentierte API hat den read-only Zugriff gedrosselt."""


class ProviderUnavailableError(ProbePortError):
    """GitHub oder der öffentliche Statusdienst ist nicht verfügbar."""


class PortTimeoutError(ProbePortError):
    """Ein externer read-only Port hat sein Zeitlimit überschritten."""


class MalformedResponseError(ProbePortError):
    """Eine externe Antwort ist syntaktisch nicht auswertbar."""


class IncompleteResponseError(ProbePortError):
    """Eine externe Antwort verletzt ihren geschlossenen Pflichtfeldvertrag."""


class UnknownContextError(ProbePortError):
    """Der Billing- oder Principal-Kontext ist nicht eindeutig belegbar."""


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


class ReviewerAvailabilityStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class ReviewerAvailabilitySource(str, Enum):
    HARNESS_RUNTIME = "harness_runtime"


class CoverageStatus(str, Enum):
    REVIEWED = "reviewed"
    EXCLUDED = "excluded"
    UNVERIFIED = "unverified"


class BoundEvidenceSourceKind(str, Enum):
    GITHUB_API = "github_api"
    HARNESS_RUNTIME = "harness_runtime"
    UNAVAILABLE = "unavailable"


class CopilotReviewMode(str, Enum):
    FULL = "full"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class ReviewState(str, Enum):
    COMMENTED = "COMMENTED"
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    DISMISSED = "DISMISSED"
    PENDING = "PENDING"
    ERROR = "ERROR"


class CheckConclusion(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    PENDING = "pending"


class PullRequestStateSource(str, Enum):
    GITHUB_API = "github_api"


class ProbeTechnicalError(str, Enum):
    PERMISSION_DENIED = "permission_denied"
    RATE_LIMITED = "rate_limited"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    TIMEOUT = "timeout"
    UNKNOWN_CONTEXT = "unknown_context"
    INCOMPLETE_RESPONSE = "incomplete_response"


class CapabilityEvidenceSource(str, Enum):
    OPERATOR_PINNED = "operator_pinned"


class BlockEvidenceSource(str, Enum):
    OPERATOR_PINNED = "operator_pinned"


class CapabilityArtifactKind(str, Enum):
    OPERATOR_SETTING = "operator_setting"
    COMPLETED_REVIEW_CONTEXT = "completed_review_context"


class BlockEvidenceKind(str, Enum):
    BUDGET_BLOCKED = "budget_blocked"
    QUOTA_EXHAUSTED = "quota_exhausted"
    ACCOUNT_LOCKED = "account_locked"


class EvidenceVerificationStatus(str, Enum):
    ABSENT = "absent"
    INVALID = "invalid"
    EXPIRED = "expired"
    VERIFIED = "verified"


class EvidenceTrust(str, Enum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"


def _require_digest(value: str, field_name: str) -> None:
    if not DIGEST_RE.fullmatch(value):
        raise ValueError(f"{field_name} must be a sha256 digest")


def _require_non_empty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be non-empty")


def _require_code(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", value):
        raise ValueError(f"{field_name} must be a normalized evidence code")


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


def _require_principal_identity(
    value: tuple[str, str, str, str | None, str | None],
) -> tuple[str, str, str, str | None, str | None]:
    identity = tuple(value)
    if len(identity) != 5:
        raise ValueError("principal_identity must contain exactly five fields")
    if any(item is not None and not isinstance(item, str) for item in identity):
        raise ValueError("principal_identity fields must be strings or absent")
    if not all(identity[index] for index in (0, 1, 2)):
        raise ValueError("principal_identity kind, identifier and review mode are required")
    return identity  # type: ignore[return-value]


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
    unit: str | None = None

    def __post_init__(self) -> None:
        _require_finite_non_negative(self.used, "used")
        _require_finite_non_negative(self.limit, "limit")
        if self.unit not in {None, "credits", "requests"}:
            raise ValueError("unit must be credits, requests or unknown")

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
        if self.kind not in {"personal", "organization", "enterprise", "cost_center", "unknown"}:
            raise ValueError("kind is not supported")
        if self.review_mode not in {"manual", "automatic"}:
            raise ValueError("review_mode must be manual or automatic")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", self.identifier):
            raise ValueError("identifier must be normalized")
        for field_name in ("requester", "pull_request_author"):
            value = getattr(self, field_name)
            if value is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value):
                raise ValueError(f"{field_name} must be normalized")
        _require_code(self.source, "source")
        _iso_z(self.observed_at)
        _iso_z(self.expires_at)
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
class OperatorEvidencePin:
    source_reference: str
    expected_digest: str
    pin_source: RuntimeTrustSource

    def __post_init__(self) -> None:
        _require_code(self.source_reference, "source_reference")
        _require_digest(self.expected_digest, "expected_digest")
        if self.pin_source not in {
            RuntimeTrustSource.PUBLISHER_APP,
            RuntimeTrustSource.INSTALLED_CONFIG,
        }:
            raise ValueError("operator evidence pin requires an external trusted source")


@dataclass(frozen=True)
class CapabilityEvidenceReference:
    schema_version: int
    source: CapabilityEvidenceSource
    repository: str
    review_mode: str
    principal_identity: tuple[str, str, str, str | None, str | None]
    source_reference: str
    artifact: bytes

    def __post_init__(self) -> None:
        if self.schema_version != 1 or isinstance(self.schema_version, bool):
            raise ValueError("schema_version must be 1")
        if not isinstance(self.source, CapabilityEvidenceSource):
            raise ValueError("source must be a CapabilityEvidenceSource")
        require_repository(self.repository)
        if self.review_mode not in {"manual", "automatic"}:
            raise ValueError("review_mode must be manual or automatic")
        object.__setattr__(
            self,
            "principal_identity",
            _require_principal_identity(self.principal_identity),
        )
        _require_code(self.source_reference, "source_reference")
        if self.source is not CapabilityEvidenceSource.OPERATOR_PINNED:
            raise ValueError("capability source must be operator_pinned")
        if not isinstance(self.artifact, bytes) or not self.artifact:
            raise ValueError("operator references require untrusted artifact bytes")


@dataclass(frozen=True)
class BlockEvidenceReference:
    schema_version: int
    source: BlockEvidenceSource
    repository: str
    review_mode: str
    principal_identity: tuple[str, str, str, str | None, str | None]
    source_reference: str
    artifact: bytes

    def __post_init__(self) -> None:
        if self.schema_version != 1 or isinstance(self.schema_version, bool):
            raise ValueError("schema_version must be 1")
        if not isinstance(self.source, BlockEvidenceSource):
            raise ValueError("source must be a BlockEvidenceSource")
        require_repository(self.repository)
        if self.review_mode not in {"manual", "automatic"}:
            raise ValueError("review_mode must be manual or automatic")
        object.__setattr__(
            self,
            "principal_identity",
            _require_principal_identity(self.principal_identity),
        )
        _require_code(self.source_reference, "source_reference")
        if self.source is not BlockEvidenceSource.OPERATOR_PINNED:
            raise ValueError("block source must be operator_pinned")
        if not isinstance(self.artifact, bytes) or not self.artifact:
            raise ValueError("operator references require untrusted artifact bytes")


@dataclass(frozen=True)
class CapabilityEvidence:
    repository: str
    principal: BillingPrincipal
    review_mode: str
    observed_at: datetime
    expires_at: datetime
    source: CapabilityEvidenceSource
    artifact_kind: CapabilityArtifactKind
    source_reference: str
    artifact_digest: str
    pin_source: RuntimeTrustSource
    pull_request_number: int | None = None
    review_id: int | None = None
    review_commit_sha: str | None = None

    def __post_init__(self) -> None:
        require_repository(self.repository)
        _require_non_empty(self.review_mode, "review_mode")
        if self.review_mode not in {"manual", "automatic"}:
            raise ValueError("review_mode must be manual or automatic")
        if not isinstance(self.source, CapabilityEvidenceSource):
            raise ValueError("source must be a CapabilityEvidenceSource")
        if self.source is not CapabilityEvidenceSource.OPERATOR_PINNED:
            raise ValueError("capability source must be operator_pinned")
        if not isinstance(self.artifact_kind, CapabilityArtifactKind):
            raise ValueError("artifact_kind must be a CapabilityArtifactKind")
        if self.pin_source not in {
            RuntimeTrustSource.PUBLISHER_APP,
            RuntimeTrustSource.INSTALLED_CONFIG,
        }:
            raise ValueError("pin_source must be an external trusted source")
        _require_code(self.source_reference, "source_reference")
        _require_digest(self.artifact_digest, "artifact_digest")
        _iso_z(self.observed_at)
        _iso_z(self.expires_at)
        if self.review_mode != self.principal.review_mode:
            raise ValueError("review_mode must match the billing principal")
        if self.expires_at <= self.observed_at:
            raise ValueError("expires_at must be after observed_at")
        if self.artifact_kind is CapabilityArtifactKind.COMPLETED_REVIEW_CONTEXT:
            for field_name in ("pull_request_number", "review_id"):
                value = getattr(self, field_name)
                if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                    raise ValueError(f"{field_name} must be a positive integer")
            if self.review_commit_sha is None:
                raise ValueError("GitHub review evidence requires review_commit_sha")
            require_full_sha(self.review_commit_sha, "review_commit_sha")
        elif any(
            value is not None
            for value in (self.pull_request_number, self.review_id, self.review_commit_sha)
        ):
            raise ValueError("operator evidence forbids GitHub review fields")

    def is_valid_for(self, repository: str, principal: BillingPrincipal, review_mode: str, now: datetime) -> bool:
        return (
            self.repository == repository
            and self.principal.identity == principal.identity
            and self.review_mode == review_mode
            and principal.is_valid_at(now)
            and self.observed_at <= now < self.expires_at
            and self.expires_at <= self.principal.expires_at
        )


@dataclass(frozen=True)
class CapabilityVerification:
    status: EvidenceVerificationStatus
    trust: EvidenceTrust
    source: CapabilityEvidenceSource | None
    artifact_kind: CapabilityArtifactKind | None
    source_reference: str | None
    artifact_digest: str | None
    pin_source: RuntimeTrustSource | None
    evidence: CapabilityEvidence | None

    def __post_init__(self) -> None:
        if not isinstance(self.status, EvidenceVerificationStatus):
            raise ValueError("status must be an EvidenceVerificationStatus")
        if not isinstance(self.trust, EvidenceTrust):
            raise ValueError("trust must be an EvidenceTrust")
        if self.status is EvidenceVerificationStatus.VERIFIED:
            if (
                self.trust is not EvidenceTrust.VERIFIED
                or self.source is None
                or self.artifact_kind is None
                or self.source_reference is None
                or self.artifact_digest is None
                or self.pin_source not in {
                    RuntimeTrustSource.PUBLISHER_APP,
                    RuntimeTrustSource.INSTALLED_CONFIG,
                }
                or self.evidence is None
            ):
                raise ValueError("verified capability must carry complete trusted provenance")
            if (
                self.evidence.source is not self.source
                or self.evidence.artifact_kind is not self.artifact_kind
                or self.evidence.source_reference != self.source_reference
                or self.evidence.artifact_digest != self.artifact_digest
                or self.evidence.pin_source is not self.pin_source
            ):
                raise ValueError("verified capability provenance must match its evidence")
        elif self.evidence is not None or self.trust is EvidenceTrust.VERIFIED:
            raise ValueError("non-verified capability must not carry verified trust or evidence")


@dataclass(frozen=True)
class VerifiedBlockEvidence:
    schema_version: int
    kind: BlockEvidenceKind
    repository: str
    principal_identity: tuple[str, str, str, str | None, str | None]
    review_mode: str
    observed_at: datetime
    expires_at: datetime
    source: BlockEvidenceSource
    source_reference: str
    artifact_digest: str
    pin_source: RuntimeTrustSource

    def __post_init__(self) -> None:
        if self.schema_version != 1 or isinstance(self.schema_version, bool):
            raise ValueError("schema_version must be 1")
        if not isinstance(self.kind, BlockEvidenceKind):
            raise ValueError("kind must be a BlockEvidenceKind")
        require_repository(self.repository)
        object.__setattr__(
            self,
            "principal_identity",
            _require_principal_identity(self.principal_identity),
        )
        if self.review_mode not in {"manual", "automatic"}:
            raise ValueError("review_mode must be manual or automatic")
        _iso_z(self.observed_at)
        _iso_z(self.expires_at)
        if self.expires_at <= self.observed_at:
            raise ValueError("expires_at must be after observed_at")
        if not isinstance(self.source, BlockEvidenceSource):
            raise ValueError("source must be a BlockEvidenceSource")
        _require_code(self.source_reference, "source_reference")
        _require_digest(self.artifact_digest, "artifact_digest")
        if self.pin_source not in {
            RuntimeTrustSource.PUBLISHER_APP,
            RuntimeTrustSource.INSTALLED_CONFIG,
        }:
            raise ValueError("pin_source must be an external trusted source")

    def is_valid_for(
        self,
        repository: str,
        principal: BillingPrincipal,
        review_mode: str,
        now: datetime,
    ) -> bool:
        return (
            self.repository == repository
            and self.principal_identity == principal.identity
            and self.review_mode == review_mode
            and self.observed_at <= now < self.expires_at
        )


@dataclass(frozen=True)
class BlockVerification:
    status: EvidenceVerificationStatus
    trust: EvidenceTrust
    source: BlockEvidenceSource | None
    source_reference: str | None
    artifact_digest: str | None
    pin_source: RuntimeTrustSource | None
    evidence: VerifiedBlockEvidence | None

    def __post_init__(self) -> None:
        if not isinstance(self.status, EvidenceVerificationStatus):
            raise ValueError("status must be an EvidenceVerificationStatus")
        if not isinstance(self.trust, EvidenceTrust):
            raise ValueError("trust must be an EvidenceTrust")
        if self.status is EvidenceVerificationStatus.VERIFIED:
            if (
                self.trust is not EvidenceTrust.VERIFIED
                or self.source is None
                or self.source_reference is None
                or self.artifact_digest is None
                or self.pin_source not in {
                    RuntimeTrustSource.PUBLISHER_APP,
                    RuntimeTrustSource.INSTALLED_CONFIG,
                }
                or self.evidence is None
            ):
                raise ValueError("verified block must carry complete trusted provenance")
            if (
                self.evidence.source is not self.source
                or self.evidence.source_reference != self.source_reference
                or self.evidence.artifact_digest != self.artifact_digest
                or self.evidence.pin_source is not self.pin_source
            ):
                raise ValueError("verified block provenance must match its evidence")
        elif self.evidence is not None or self.trust is EvidenceTrust.VERIFIED:
            raise ValueError("non-verified block must not carry verified trust or evidence")


@dataclass(frozen=True)
class ProbeSignals:
    billing_status: DiagnosticStatus | None
    usage_status: DiagnosticStatus
    provider_status: DiagnosticStatus
    permission_status: DiagnosticStatus
    capability: CapabilityEvidence | None
    repository: str
    principal: BillingPrincipal
    review_mode: str
    observed_at: datetime
    verified_block: VerifiedBlockEvidence | None = None

    def __post_init__(self) -> None:
        for field_name in ("usage_status", "provider_status", "permission_status"):
            if not isinstance(getattr(self, field_name), DiagnosticStatus):
                raise ValueError(f"{field_name} must be a DiagnosticStatus")
        if self.billing_status is not None and not isinstance(
            self.billing_status,
            DiagnosticStatus,
        ):
            raise ValueError("billing_status must be a DiagnosticStatus or absent")
        require_repository(self.repository)
        if self.review_mode not in {"manual", "automatic"}:
            raise ValueError("review_mode must be manual or automatic")
        _iso_z(self.observed_at)
        if self.review_mode != self.principal.review_mode:
            raise ValueError("review_mode must match the authoritative billing principal")
        if self.verified_block is not None and not self.verified_block.is_valid_for(
            self.repository,
            self.principal,
            self.review_mode,
            self.observed_at,
        ):
            raise ValueError("verified_block must match the authoritative probe context")

    def classify_usability(self) -> tuple[bool, DiagnosticStatus]:
        """Leitet die einzige zulässige Verwendbarkeitsentscheidung aus den Signalen ab."""
        precedence = (
            DiagnosticStatus.BUDGET_BLOCKED,
            DiagnosticStatus.QUOTA_EXHAUSTED,
            DiagnosticStatus.RATE_LIMITED,
            DiagnosticStatus.PROVIDER_UNAVAILABLE,
            DiagnosticStatus.PERMISSION_DENIED,
            DiagnosticStatus.UNKNOWN,
            DiagnosticStatus.LOW_BUDGET,
            DiagnosticStatus.AVAILABLE,
        )
        technical_statuses = (
            self.usage_status,
            self.provider_status,
            self.permission_status,
        )
        status = next(candidate for candidate in precedence if candidate in technical_statuses)
        if status not in {DiagnosticStatus.AVAILABLE, DiagnosticStatus.LOW_BUDGET}:
            return False, status
        block = self.verified_block
        if block is not None and (
            self.capability is None
            or block.observed_at >= self.capability.observed_at
        ):
            if block.kind is BlockEvidenceKind.QUOTA_EXHAUSTED:
                return False, DiagnosticStatus.QUOTA_EXHAUSTED
            return False, DiagnosticStatus.BUDGET_BLOCKED
        if self.capability is None or not self.capability.is_valid_for(
            self.repository,
            self.principal,
            self.review_mode,
            self.observed_at,
        ):
            return False, DiagnosticStatus.UNKNOWN
        return True, status


@dataclass(frozen=True)
class BillingContext:
    kind: str
    identity: str
    evidence: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in ("kind", "identity"):
            _require_non_empty(getattr(self, field_name), field_name)
        if self.kind not in {"personal", "organization", "enterprise", "cost_center", "unknown"}:
            raise ValueError("kind is not supported")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", self.identity):
            raise ValueError("identity must be normalized")
        evidence = tuple(self.evidence)
        for item in evidence:
            _require_code(item, "evidence")
        object.__setattr__(self, "evidence", evidence)


def _iso_z(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime values must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class ProbeReport:
    copilot_usable: bool
    routing_status: DiagnosticStatus
    signals: ProbeSignals
    usage: Usage
    repository: str
    review_mode: str
    requester: str | None
    pull_request_author: str | None
    billing_principal: BillingPrincipal
    billing_context: BillingContext
    billing_model: str
    technical_status: DiagnosticStatus
    technical_error: ProbeTechnicalError | None
    capability_verification: CapabilityVerification
    pull_request_number: int | None
    request_digest: str
    valid_until: datetime
    block_verification: BlockVerification | None = None
    evidence: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1 or isinstance(self.schema_version, bool):
            raise ValueError("schema_version must be 1")
        _require_bool(self.copilot_usable, "copilot_usable")
        require_repository(self.repository)
        if self.review_mode not in {"manual", "automatic"}:
            raise ValueError("review_mode must be manual or automatic")
        if self.billing_model not in {"ai_credits", "premium_requests", "unknown"}:
            raise ValueError("billing_model is not supported")
        if self.pull_request_number is not None and (
            isinstance(self.pull_request_number, bool)
            or not isinstance(self.pull_request_number, int)
            or self.pull_request_number <= 0
        ):
            raise ValueError("pull_request_number must be a positive integer or absent")
        _require_digest(self.request_digest, "request_digest")
        _iso_z(self.valid_until)
        if not self.observed_at < self.valid_until <= self.billing_principal.expires_at:
            raise ValueError("valid_until must follow observation within principal validity")
        if not isinstance(self.capability_verification, CapabilityVerification):
            raise ValueError("capability_verification must be a CapabilityVerification")
        if self.capability_verification.evidence != self.signals.capability:
            raise ValueError("capability verification must match probe signals")
        if (
            self.copilot_usable
            and self.capability_verification.status
            is not EvidenceVerificationStatus.VERIFIED
        ):
            raise ValueError("copilot_usable requires a verified capability")
        expected_usable, expected_status = self.signals.classify_usability()
        if self.copilot_usable is not expected_usable or self.routing_status is not expected_status:
            raise ValueError("probe result must match the deterministic signal classification")
        if (
            self.block_verification is not None
            and self.block_verification.evidence != self.signals.verified_block
        ):
            raise ValueError("block verification must match probe signals")
        if self.technical_error is not None and not isinstance(
            self.technical_error,
            ProbeTechnicalError,
        ):
            raise ValueError("technical_error must be a ProbeTechnicalError or absent")
        expected_technical_status = {
            None: DiagnosticStatus.AVAILABLE,
            ProbeTechnicalError.PERMISSION_DENIED: DiagnosticStatus.PERMISSION_DENIED,
            ProbeTechnicalError.RATE_LIMITED: DiagnosticStatus.RATE_LIMITED,
            ProbeTechnicalError.PROVIDER_UNAVAILABLE: DiagnosticStatus.PROVIDER_UNAVAILABLE,
            ProbeTechnicalError.TIMEOUT: DiagnosticStatus.PROVIDER_UNAVAILABLE,
            ProbeTechnicalError.UNKNOWN_CONTEXT: DiagnosticStatus.UNKNOWN,
            ProbeTechnicalError.INCOMPLETE_RESPONSE: DiagnosticStatus.UNKNOWN,
        }[self.technical_error]
        if self.technical_status is not expected_technical_status:
            raise ValueError("technical_status must match technical_error")
        if self.copilot_usable and (
            self.technical_error is not None
            or self.technical_status is not DiagnosticStatus.AVAILABLE
        ):
            raise ValueError("copilot_usable requires a fully positive technical result")
        if (
            self.technical_error is not None
            and self.routing_status is not expected_technical_status
        ):
            raise ValueError("technical failures must control the routing status")
        if self.signals.principal.identity != self.billing_principal.identity:
            raise ValueError("signals and report must use the same billing principal")
        if self.signals.repository != self.repository or self.signals.review_mode != self.review_mode:
            raise ValueError("signals must be bound to the report context")
        if self.review_mode == "manual":
            if (
                self.requester != self.billing_principal.requester
                or not self.requester
                or self.pull_request_author is not None
            ):
                raise ValueError("manual report must bind the authoritative requester")
        elif (
            self.pull_request_number is None
            or self.requester is not None
            or self.pull_request_author != self.billing_principal.pull_request_author
            or (
                self.technical_error is None
                and not self.pull_request_author
            )
        ):
            raise ValueError("automatic report must bind pull request and author")
        capability = self.capability_verification.evidence
        if capability is not None and self.valid_until > capability.expires_at:
            raise ValueError("report validity must not outlive capability evidence")
        verified_block = (
            self.block_verification.evidence
            if self.block_verification is not None
            else None
        )
        if verified_block is not None and self.valid_until > verified_block.expires_at:
            raise ValueError("report validity must not outlive block evidence")
        for field_name in ("evidence", "warnings"):
            values = tuple(getattr(self, field_name))
            for item in values:
                _require_code(item, field_name)
            object.__setattr__(self, field_name, values)

    @property
    def observed_at(self) -> datetime:
        return self.signals.observed_at

    @property
    def capability_status(self) -> str:
        return {
            EvidenceVerificationStatus.ABSENT: "absent",
            EvidenceVerificationStatus.INVALID: "invalid",
            EvidenceVerificationStatus.EXPIRED: "expired",
            EvidenceVerificationStatus.VERIFIED: "valid",
        }[self.capability_verification.status]

    def to_dict(self) -> dict[str, object]:
        """Serialisiert ausschließlich den geschlossenen, sanitisierten Probe-Vertrag."""
        capability = self.signals.capability
        capability_verification = self.capability_verification
        block_verification = self.block_verification
        return {
            "schema_version": self.schema_version,
            "observed_at": _iso_z(self.observed_at),
            "repository": self.repository,
            "pull_request_number": self.pull_request_number,
            "review_mode": self.review_mode,
            "requester": self.requester,
            "pull_request_author": self.pull_request_author,
            "billing_principal": {
                "kind": self.billing_principal.kind,
                "identifier": self.billing_principal.identifier,
                "review_mode": self.billing_principal.review_mode,
                "requester": self.billing_principal.requester,
                "pull_request_author": self.billing_principal.pull_request_author,
                "source": self.billing_principal.source,
                "observed_at": _iso_z(self.billing_principal.observed_at),
                "expires_at": _iso_z(self.billing_principal.expires_at),
            },
            "billing_context": {
                "kind": self.billing_context.kind,
                "identity": self.billing_context.identity,
                "evidence": list(self.billing_context.evidence),
            },
            "billing_model": self.billing_model,
            "usage": {
                "used": self.usage.used,
                "limit": self.usage.limit,
                "remaining": self.usage.remaining,
                "unit": self.usage.unit,
            },
            "signals": {
                "billing_status": (
                    self.signals.billing_status.value
                    if self.signals.billing_status is not None
                    else None
                ),
                "usage_status": self.signals.usage_status.value,
                "provider_status": self.signals.provider_status.value,
                "api_status": self.signals.permission_status.value,
            },
            "routing_status": self.routing_status.value,
            "request_digest": self.request_digest,
            "valid_until": _iso_z(self.valid_until),
            "technical_status": self.technical_status.value,
            "technical_error": self.technical_error.value if self.technical_error is not None else None,
            "copilot_usable": self.copilot_usable,
            "capability_evidence": {
                "status": self.capability_status,
                "expires_at": _iso_z(capability.expires_at) if capability is not None else None,
                "source": (
                    capability_verification.source.value
                    if capability_verification is not None
                    and capability_verification.source is not None
                    else None
                ),
                "source_reference": (
                    capability_verification.source_reference
                    if capability_verification is not None
                    else None
                ),
                "artifact_digest": (
                    capability_verification.artifact_digest
                    if capability_verification is not None
                    else None
                ),
                "artifact_kind": (
                    capability_verification.artifact_kind.value
                    if capability_verification is not None
                    and capability_verification.artifact_kind is not None
                    else None
                ),
                "pin_source": (
                    capability_verification.pin_source.value
                    if capability_verification is not None
                    and capability_verification.pin_source is not None
                    else None
                ),
                "trust": (
                    capability_verification.trust.value
                    if capability_verification is not None
                    else EvidenceTrust.UNVERIFIED.value
                ),
            },
            "block_evidence": {
                "status": (
                    block_verification.status.value
                    if block_verification is not None
                    else EvidenceVerificationStatus.ABSENT.value
                ),
                "kind": (
                    block_verification.evidence.kind.value
                    if block_verification is not None
                    and block_verification.evidence is not None
                    else None
                ),
                "source": (
                    block_verification.source.value
                    if block_verification is not None
                    and block_verification.source is not None
                    else None
                ),
                "source_reference": (
                    block_verification.source_reference
                    if block_verification is not None
                    else None
                ),
                "artifact_digest": (
                    block_verification.artifact_digest
                    if block_verification is not None
                    else None
                ),
                "pin_source": (
                    block_verification.pin_source.value
                    if block_verification is not None
                    and block_verification.pin_source is not None
                    else None
                ),
                "trust": (
                    block_verification.trust.value
                    if block_verification is not None
                    else EvidenceTrust.UNVERIFIED.value
                ),
            },
            "evidence": list(self.evidence),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class CommandResult:
    """Rohe Prozessbytes, die ausschließlich innerhalb des Adapters verarbeitet werden."""

    return_code: int
    stdout: bytes
    stderr: bytes

    def __post_init__(self) -> None:
        if isinstance(self.return_code, bool) or not isinstance(self.return_code, int):
            raise ValueError("return_code must be an integer")
        if not isinstance(self.stdout, bytes) or not isinstance(self.stderr, bytes):
            raise ValueError("stdout and stderr must be bytes")


@dataclass(frozen=True)
class StatusSnapshot:
    status: DiagnosticStatus
    source: str
    observed_at: datetime

    def __post_init__(self) -> None:
        if self.status not in {
            DiagnosticStatus.AVAILABLE,
            DiagnosticStatus.PROVIDER_UNAVAILABLE,
            DiagnosticStatus.UNKNOWN,
        }:
            raise ValueError("status snapshot has an unsupported diagnostic status")
        _require_code(self.source, "source")
        _iso_z(self.observed_at)


@dataclass(frozen=True)
class PullRequestState:
    repository: str
    pull_request_number: int
    base_ref: str
    api_base_sha: str
    head_sha: str
    author: str
    observed_at: datetime
    source: PullRequestStateSource

    def __post_init__(self) -> None:
        require_repository(self.repository)
        if (
            isinstance(self.pull_request_number, bool)
            or not isinstance(self.pull_request_number, int)
            or self.pull_request_number <= 0
        ):
            raise ValueError("pull_request_number must be a positive integer")
        for field_name in ("base_ref", "author"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value or "\x00" in value:
                raise ValueError(f"{field_name} must be a non-empty NUL-free string")
        for field_name in ("api_base_sha", "head_sha"):
            require_full_sha(getattr(self, field_name), field_name)
        if self.source is not PullRequestStateSource.GITHUB_API:
            raise ValueError("source must be github_api")
        _iso_z(self.observed_at)


@dataclass(frozen=True)
class ProbeRequest:
    repository: str
    review_mode: str
    manual_requester: str | None = None
    pull_request_number: int | None = None
    organization: str | None = None
    enterprise: str | None = None
    cost_center: str | None = None
    capability_reference: CapabilityEvidenceReference | None = None
    block_reference: BlockEvidenceReference | None = None

    def __post_init__(self) -> None:
        require_repository(self.repository)
        if self.review_mode not in {"manual", "automatic"}:
            raise ValueError("review_mode must be manual or automatic")
        if self.review_mode == "manual":
            if not isinstance(self.manual_requester, str) or not self.manual_requester:
                raise ValueError("manual mode requires manual_requester")
        elif self.manual_requester is not None:
            raise ValueError("automatic mode forbids manual_requester")
        if self.review_mode == "automatic" and (
            isinstance(self.pull_request_number, bool)
            or not isinstance(self.pull_request_number, int)
            or self.pull_request_number <= 0
        ):
            raise ValueError("automatic mode requires a positive pull_request_number")
        if self.pull_request_number is not None and (
            isinstance(self.pull_request_number, bool)
            or not isinstance(self.pull_request_number, int)
            or self.pull_request_number <= 0
        ):
            raise ValueError("pull_request_number must be a positive integer")
        for field_name in ("manual_requester", "organization", "enterprise", "cost_center"):
            value = getattr(self, field_name)
            if value is not None and (
                not isinstance(value, str)
                or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?", value)
            ):
                raise ValueError(f"{field_name} must be a normalized identifier")
        if self.capability_reference is not None and not isinstance(
            self.capability_reference,
            CapabilityEvidenceReference,
        ):
            raise ValueError("capability_reference must be a CapabilityEvidenceReference")
        if self.block_reference is not None and not isinstance(
            self.block_reference,
            BlockEvidenceReference,
        ):
            raise ValueError("block_reference must be a BlockEvidenceReference")

    @property
    def request_digest(self) -> str:
        """Bindet den vollständigen Probe-Kontext einschließlich untrusted Artefaktbytes."""

        def reference_document(
            reference: CapabilityEvidenceReference | BlockEvidenceReference | None,
        ) -> object:
            if reference is None:
                return None
            return {
                "artifact_digest": "sha256:"
                + hashlib.sha256(reference.artifact).hexdigest(),
                "principal_identity": list(reference.principal_identity),
                "repository": reference.repository,
                "review_mode": reference.review_mode,
                "schema_version": reference.schema_version,
                "source": reference.source.value,
                "source_reference": reference.source_reference,
            }

        document = {
            "block_reference": reference_document(self.block_reference),
            "capability_reference": reference_document(self.capability_reference),
            "cost_center": self.cost_center,
            "enterprise": self.enterprise,
            "manual_requester": self.manual_requester,
            "organization": self.organization,
            "pull_request_number": self.pull_request_number,
            "repository": self.repository,
            "review_mode": self.review_mode,
            "schema_version": 1,
        }
        canonical = json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ReviewerAvailabilityEvidence:
    """Zeitlich und kontextuell gebundene Harness-Evidenz für genau einen Reviewer."""

    reviewer: Reviewer
    status: ReviewerAvailabilityStatus
    repository: str
    pull_request_number: int
    head_sha: str
    purpose: ReviewPurpose
    observed_at: datetime
    expires_at: datetime
    source: ReviewerAvailabilitySource
    reason: str

    def __post_init__(self) -> None:
        if self.reviewer not in {Reviewer.QA, Reviewer.SEC}:
            raise ValueError("reviewer availability is supported only for qa and sec")
        if not isinstance(self.status, ReviewerAvailabilityStatus):
            raise ValueError("status must be a ReviewerAvailabilityStatus")
        require_repository(self.repository)
        if (
            isinstance(self.pull_request_number, bool)
            or not isinstance(self.pull_request_number, int)
            or self.pull_request_number <= 0
        ):
            raise ValueError("pull_request_number must be a positive integer")
        require_full_sha(self.head_sha, "head_sha")
        if not isinstance(self.purpose, ReviewPurpose):
            raise ValueError("purpose must be a ReviewPurpose")
        _iso_z(self.observed_at)
        _iso_z(self.expires_at)
        if self.expires_at <= self.observed_at:
            raise ValueError("expires_at must be after observed_at")
        if self.source is not ReviewerAvailabilitySource.HARNESS_RUNTIME:
            raise ValueError("reviewer availability source must be harness_runtime")
        _require_code(self.reason, "reason")

    def is_available_for(
        self,
        repository: str,
        pull_request_number: int,
        head_sha: str,
        purpose: ReviewPurpose,
        now: datetime,
    ) -> bool:
        """Akzeptiert ausschließlich aktuelle Exact-Context-Evidenz mit Status available."""
        _iso_z(now)
        return (
            self.status is ReviewerAvailabilityStatus.AVAILABLE
            and self.repository == repository
            and self.pull_request_number == pull_request_number
            and self.head_sha == head_sha
            and self.purpose is purpose
            and self.observed_at <= now < self.expires_at
        )


@dataclass(frozen=True)
class ReviewerAvailabilitySnapshot:
    """Geschlossener, programmatic-only Snapshot ohne CLI-Überschreibungen."""

    evidence: tuple[ReviewerAvailabilityEvidence, ...] = ()

    def __post_init__(self) -> None:
        evidence = tuple(self.evidence)
        if not all(isinstance(item, ReviewerAvailabilityEvidence) for item in evidence):
            raise ValueError("evidence must contain ReviewerAvailabilityEvidence values")
        reviewers = tuple(item.reviewer for item in evidence)
        if len(set(reviewers)) != len(reviewers):
            raise ValueError("reviewer availability evidence must be unique per reviewer")
        object.__setattr__(self, "evidence", evidence)

    def is_available(
        self,
        reviewer: Reviewer,
        repository: str,
        pull_request_number: int,
        head_sha: str,
        purpose: ReviewPurpose,
        now: datetime,
    ) -> bool:
        if reviewer not in {Reviewer.QA, Reviewer.SEC}:
            return False
        return any(
            item.reviewer is reviewer
            and item.is_available_for(
                repository,
                pull_request_number,
                head_sha,
                purpose,
                now,
            )
            for item in self.evidence
        )


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
class BoundEvidenceSource:
    """Maschinenlesbare Quelle, gebunden an einen zeitlich gültigen Exact-Head-Kontext."""

    kind: BoundEvidenceSourceKind
    source_id: str
    repository: str
    pull_request_number: int
    head_sha: str
    observed_at: datetime
    valid_until: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.kind, BoundEvidenceSourceKind):
            raise ValueError("kind must be a BoundEvidenceSourceKind")
        _require_code(self.source_id, "source_id")
        require_repository(self.repository)
        if (
            isinstance(self.pull_request_number, bool)
            or not isinstance(self.pull_request_number, int)
            or self.pull_request_number <= 0
        ):
            raise ValueError("pull_request_number must be a positive integer")
        require_full_sha(self.head_sha, "head_sha")
        _iso_z(self.observed_at)
        _iso_z(self.valid_until)
        if self.valid_until <= self.observed_at:
            raise ValueError("valid_until must be after observed_at")

    def is_valid_for(
        self,
        repository: str,
        pull_request_number: int,
        head_sha: str,
        evaluated_at: datetime,
    ) -> bool:
        _iso_z(evaluated_at)
        return (
            self.kind is not BoundEvidenceSourceKind.UNAVAILABLE
            and self.repository == repository
            and self.pull_request_number == pull_request_number
            and self.head_sha == head_sha
            and self.observed_at <= evaluated_at < self.valid_until
        )


@dataclass(frozen=True)
class ReviewRecord:
    reviewer: Reviewer
    event_id: str
    actor_login: str
    app_slug: str
    state: ReviewState
    commit_sha: str
    submitted_at: datetime
    findings_count: int
    source: BoundEvidenceSource

    def __post_init__(self) -> None:
        if not isinstance(self.reviewer, Reviewer):
            raise ValueError("reviewer must be a Reviewer")
        _require_code(self.event_id, "event_id")
        for field_name in ("actor_login", "app_slug"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value or "\x00" in value:
                raise ValueError(f"{field_name} must be a non-empty NUL-free string")
        if not isinstance(self.state, ReviewState):
            raise ValueError("state must be a ReviewState")
        require_full_sha(self.commit_sha, "commit_sha")
        _iso_z(self.submitted_at)
        if (
            isinstance(self.findings_count, bool)
            or not isinstance(self.findings_count, int)
            or self.findings_count < 0
        ):
            raise ValueError("findings_count must be a non-negative integer")
        if not isinstance(self.source, BoundEvidenceSource):
            raise ValueError("source must be a BoundEvidenceSource")


@dataclass(frozen=True)
class ThreadRecord:
    thread_id: str
    reviewer: Reviewer | None
    head_sha: str
    unresolved: bool
    source: BoundEvidenceSource

    def __post_init__(self) -> None:
        _require_non_empty(self.thread_id, "thread_id")
        if self.reviewer is not None and not isinstance(self.reviewer, Reviewer):
            raise ValueError("reviewer must be a Reviewer or absent")
        require_full_sha(self.head_sha, "head_sha")
        _require_bool(self.unresolved, "unresolved")
        if not isinstance(self.source, BoundEvidenceSource):
            raise ValueError("source must be a BoundEvidenceSource")


@dataclass(frozen=True)
class CheckRecord:
    name: str
    source_app_slug: str
    head_sha: str
    conclusion: CheckConclusion
    completed_at: datetime
    source: BoundEvidenceSource

    def __post_init__(self) -> None:
        for field_name in ("name", "source_app_slug"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value or "\x00" in value:
                raise ValueError(f"{field_name} must be a non-empty NUL-free string")
        require_full_sha(self.head_sha, "head_sha")
        if not isinstance(self.conclusion, CheckConclusion):
            raise ValueError("conclusion must be a CheckConclusion")
        _iso_z(self.completed_at)
        if not isinstance(self.source, BoundEvidenceSource):
            raise ValueError("source must be a BoundEvidenceSource")


@dataclass(frozen=True)
class FileCoverage:
    path: str
    status: FileStatus
    coverage: CoverageStatus
    reviewer: Reviewer
    coverage_source: BoundEvidenceSource
    previous_path: str | None = None

    def __post_init__(self) -> None:
        path = normalize_repo_path(self.path)
        previous_path = (
            normalize_repo_path(self.previous_path, "previous_path")
            if self.previous_path is not None
            else None
        )
        if not isinstance(self.status, FileStatus):
            raise ValueError("status must be a FileStatus")
        requires_previous = self.status in {FileStatus.RENAMED, FileStatus.COPIED}
        if requires_previous != (previous_path is not None):
            raise ValueError("previous_path is required exactly for renamed and copied files")
        if not isinstance(self.coverage, CoverageStatus):
            raise ValueError("coverage must be a CoverageStatus")
        if not isinstance(self.reviewer, Reviewer):
            raise ValueError("reviewer must be a Reviewer")
        if not isinstance(self.coverage_source, BoundEvidenceSource):
            raise ValueError("coverage_source must be a BoundEvidenceSource")
        if (
            self.coverage_source.kind is BoundEvidenceSourceKind.UNAVAILABLE
            and self.coverage is not CoverageStatus.UNVERIFIED
        ):
            raise ValueError("unavailable coverage source can only be unverified")
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "previous_path", previous_path)


@dataclass(frozen=True)
class GateSnapshot:
    schema_version: int
    repository: str
    pull_request_number: int
    base_sha: str
    head_sha: str
    check_runs: tuple[CheckRecord, ...]
    review_requests: tuple[ReviewRecord, ...]
    reviews: tuple[ReviewRecord, ...]
    review_file_coverage: tuple[FileCoverage, ...]
    copilot_review_mode: CopilotReviewMode
    review_mode_source: BoundEvidenceSource
    threads: tuple[ThreadRecord, ...]
    observed_at: datetime
    valid_until: datetime

    def __post_init__(self) -> None:
        if self.schema_version != 1 or isinstance(self.schema_version, bool):
            raise ValueError("schema_version must be 1")
        require_repository(self.repository)
        if (
            isinstance(self.pull_request_number, bool)
            or not isinstance(self.pull_request_number, int)
            or self.pull_request_number <= 0
        ):
            raise ValueError("pull_request_number must be a positive integer")
        require_full_sha(self.base_sha, "base_sha")
        require_full_sha(self.head_sha, "head_sha")
        collections = {
            "check_runs": (self.check_runs, CheckRecord),
            "review_requests": (self.review_requests, ReviewRecord),
            "reviews": (self.reviews, ReviewRecord),
            "review_file_coverage": (self.review_file_coverage, FileCoverage),
            "threads": (self.threads, ThreadRecord),
        }
        for field_name, (values, expected_type) in collections.items():
            frozen = tuple(values)
            if not all(isinstance(value, expected_type) for value in frozen):
                raise ValueError(f"{field_name} contains an invalid record")
            object.__setattr__(self, field_name, frozen)
        if not isinstance(self.copilot_review_mode, CopilotReviewMode):
            raise ValueError("copilot_review_mode must be a CopilotReviewMode")
        if not isinstance(self.review_mode_source, BoundEvidenceSource):
            raise ValueError("review_mode_source must be a BoundEvidenceSource")
        _iso_z(self.observed_at)
        _iso_z(self.valid_until)
        if self.valid_until <= self.observed_at:
            raise ValueError("valid_until must be after observed_at")
        check_keys = tuple(
            (check.name, check.source_app_slug, check.head_sha) for check in self.check_runs
        )
        if len(check_keys) != len(set(check_keys)):
            raise ValueError("check records must be unique by name, source and head")
        for field_name in ("review_requests", "reviews"):
            review_keys = tuple(
                (
                    review.reviewer,
                    review.event_id,
                    review.actor_login,
                    review.app_slug,
                    review.state,
                    review.commit_sha,
                    review.submitted_at,
                )
                for review in getattr(self, field_name)
            )
            if len(review_keys) != len(set(review_keys)):
                raise ValueError(f"{field_name} must not contain duplicate records")
        event_ids = tuple(
            review.event_id for review in (*self.review_requests, *self.reviews)
        )
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("review event identifiers must be unique across all collections")
        coverage_keys = tuple(
            (
                coverage.path,
                coverage.status,
                coverage.previous_path,
                coverage.reviewer,
            )
            for coverage in self.review_file_coverage
        )
        if len(coverage_keys) != len(set(coverage_keys)):
            raise ValueError("file coverage records must be unique per reviewer and diff entry")
        thread_ids = tuple(thread.thread_id for thread in self.threads)
        if len(thread_ids) != len(set(thread_ids)):
            raise ValueError("thread records must have unique identifiers")
        object.__setattr__(
            self,
            "check_runs",
            tuple(
                sorted(
                    self.check_runs,
                    key=lambda value: (
                        value.name,
                        value.source_app_slug,
                        value.head_sha,
                        value.completed_at,
                    ),
                )
            ),
        )
        for field_name in ("review_requests", "reviews"):
            object.__setattr__(
                self,
                field_name,
                tuple(
                    sorted(
                        getattr(self, field_name),
                        key=lambda value: (
                            value.reviewer.value,
                            value.event_id,
                            value.commit_sha,
                            value.submitted_at,
                            value.actor_login,
                        ),
                    )
                ),
            )
        object.__setattr__(
            self,
            "review_file_coverage",
            tuple(
                sorted(
                    self.review_file_coverage,
                    key=lambda value: (
                        value.path,
                        value.status.value,
                        value.previous_path or "",
                        value.reviewer.value,
                    ),
                )
            ),
        )
        object.__setattr__(
            self,
            "threads",
            tuple(sorted(self.threads, key=lambda value: value.thread_id)),
        )

    @property
    def evidence_digest(self) -> str:
        def source_document(source: BoundEvidenceSource) -> dict[str, object]:
            return {
                "head_sha": source.head_sha,
                "kind": source.kind.value,
                "observed_at": _iso_z(source.observed_at),
                "pull_request_number": source.pull_request_number,
                "repository": source.repository,
                "source_id": source.source_id,
                "valid_until": _iso_z(source.valid_until),
            }

        document = {
            "base_sha": self.base_sha,
            "check_runs": [
                {
                    "completed_at": _iso_z(check.completed_at),
                    "conclusion": check.conclusion.value,
                    "head_sha": check.head_sha,
                    "name": check.name,
                    "source": source_document(check.source),
                    "source_app_slug": check.source_app_slug,
                }
                for check in self.check_runs
            ],
            "copilot_review_mode": self.copilot_review_mode.value,
            "head_sha": self.head_sha,
            "observed_at": _iso_z(self.observed_at),
            "pull_request_number": self.pull_request_number,
            "repository": self.repository,
            "review_file_coverage": [
                {
                    "coverage": item.coverage.value,
                    "coverage_source": source_document(item.coverage_source),
                    "path": item.path,
                    "previous_path": item.previous_path,
                    "reviewer": item.reviewer.value,
                    "status": item.status.value,
                }
                for item in self.review_file_coverage
            ],
            "review_mode_source": source_document(self.review_mode_source),
            "review_requests": [
                {
                    "actor_login": review.actor_login,
                    "app_slug": review.app_slug,
                    "commit_sha": review.commit_sha,
                    "event_id": review.event_id,
                    "findings_count": review.findings_count,
                    "reviewer": review.reviewer.value,
                    "source": source_document(review.source),
                    "state": review.state.value,
                    "submitted_at": _iso_z(review.submitted_at),
                }
                for review in self.review_requests
            ],
            "reviews": [
                {
                    "actor_login": review.actor_login,
                    "app_slug": review.app_slug,
                    "commit_sha": review.commit_sha,
                    "event_id": review.event_id,
                    "findings_count": review.findings_count,
                    "reviewer": review.reviewer.value,
                    "source": source_document(review.source),
                    "state": review.state.value,
                    "submitted_at": _iso_z(review.submitted_at),
                }
                for review in self.reviews
            ],
            "schema_version": self.schema_version,
            "threads": [
                {
                    "head_sha": thread.head_sha,
                    "reviewer": thread.reviewer.value if thread.reviewer else None,
                    "source": source_document(thread.source),
                    "thread_id": thread.thread_id,
                    "unresolved": thread.unresolved,
                }
                for thread in self.threads
            ],
            "valid_until": _iso_z(self.valid_until),
        }
        canonical = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PreliminaryRoutePlan:
    schema_version: int
    repository: str
    pull_request_number: int
    purpose: ReviewPurpose
    base_ref: str
    base_sha: str
    merge_base_sha: str
    head_sha: str
    pr_state_source: PullRequestStateSource
    risk: RiskAssessment
    policy_source_ref: str
    policy_source_path: str
    policy_digest: str
    runtime_digest: str
    runtime_trust: RuntimeTrust
    diff_digest: str
    copilot_usable: bool
    copilot_coverage_complete: bool | None
    copilot_review_mode: CopilotReviewMode
    route: ReviewRoute
    required_reviewers: frozenset[Reviewer]
    gate_status: str
    gate_eligible: bool

    def __post_init__(self) -> None:
        if self.schema_version != 1 or isinstance(self.schema_version, bool):
            raise ValueError("schema_version must be 1")
        require_repository(self.repository)
        if (
            isinstance(self.pull_request_number, bool)
            or not isinstance(self.pull_request_number, int)
            or self.pull_request_number <= 0
        ):
            raise ValueError("pull_request_number must be a positive integer")
        if not isinstance(self.purpose, ReviewPurpose):
            raise ValueError("purpose must be a ReviewPurpose")
        for field_name in ("base_ref", "policy_source_ref", "policy_source_path", "gate_status"):
            _require_non_empty(getattr(self, field_name), field_name)
        for field_name in ("base_sha", "merge_base_sha", "head_sha"):
            require_full_sha(getattr(self, field_name), field_name)
        if self.pr_state_source is not PullRequestStateSource.GITHUB_API:
            raise ValueError("pr_state_source must be github_api")
        if not isinstance(self.risk, RiskAssessment):
            raise ValueError("risk must be a RiskAssessment")
        for field_name in ("policy_digest", "runtime_digest", "diff_digest"):
            _require_digest(getattr(self, field_name), field_name)
        if not isinstance(self.runtime_trust, RuntimeTrust):
            raise ValueError("runtime_trust must be a RuntimeTrust")
        _require_bool(self.copilot_usable, "copilot_usable")
        _require_bool_or_none(self.copilot_coverage_complete, "copilot_coverage_complete")
        if not isinstance(self.copilot_review_mode, CopilotReviewMode):
            raise ValueError("copilot_review_mode must be a CopilotReviewMode")
        if not isinstance(self.route, ReviewRoute):
            raise ValueError("route must be a ReviewRoute")
        object.__setattr__(self, "required_reviewers", _freeze_reviewers(self.required_reviewers))
        _require_bool(self.gate_eligible, "gate_eligible")


@dataclass(frozen=True)
class GateEvaluationContext:
    preliminary_plan: PreliminaryRoutePlan
    current_pr_state: PullRequestState
    probe_request: ProbeRequest
    fresh_probe: ProbeReport
    reviewer_availability: ReviewerAvailabilitySnapshot
    evaluated_at: datetime
    prior_gate_evidence: PriorGateEvidence | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.preliminary_plan, PreliminaryRoutePlan):
            raise ValueError("preliminary_plan must be a PreliminaryRoutePlan")
        if not isinstance(self.current_pr_state, PullRequestState):
            raise ValueError("current_pr_state must be a PullRequestState")
        if not isinstance(self.probe_request, ProbeRequest):
            raise ValueError("probe_request must be a ProbeRequest")
        if not isinstance(self.fresh_probe, ProbeReport):
            raise ValueError("fresh_probe must be a ProbeReport")
        if not isinstance(self.reviewer_availability, ReviewerAvailabilitySnapshot):
            raise ValueError("reviewer_availability must be a ReviewerAvailabilitySnapshot")
        if self.prior_gate_evidence is not None and not isinstance(
            self.prior_gate_evidence,
            PriorGateEvidence,
        ):
            raise ValueError("prior_gate_evidence must be PriorGateEvidence or absent")
        _iso_z(self.evaluated_at)


@dataclass(frozen=True)
class GateResult:
    check_name: str
    conclusion: str
    repository: str
    pull_request_number: int
    purpose: ReviewPurpose
    base_ref: str
    base_sha: str
    head_sha: str
    pr_state_source: PullRequestStateSource
    policy_source_ref: str
    policy_source_path: str
    policy_digest: str
    runtime_digest: str
    runtime_trust: RuntimeTrust
    diff_digest: str
    evidence_digest: str
    required_reviewers: frozenset[Reviewer]
    validated_reviewers: frozenset[Reviewer]
    unresolved_thread_count: int
    reasons: tuple[str, ...]
    observed_at: datetime

    def __post_init__(self) -> None:
        if self.check_name != "agent-governance/review-gate":
            raise ValueError("check_name must be the stable governance gate name")
        if self.conclusion not in {"success", "failure"}:
            raise ValueError("conclusion must be success or failure")
        require_repository(self.repository)
        if (
            isinstance(self.pull_request_number, bool)
            or not isinstance(self.pull_request_number, int)
            or self.pull_request_number <= 0
        ):
            raise ValueError("pull_request_number must be a positive integer")
        if not isinstance(self.purpose, ReviewPurpose):
            raise ValueError("purpose must be a ReviewPurpose")
        _require_non_empty(self.base_ref, "base_ref")
        for field_name in ("base_sha", "head_sha"):
            require_full_sha(getattr(self, field_name), field_name)
        if self.pr_state_source is not PullRequestStateSource.GITHUB_API:
            raise ValueError("pr_state_source must be github_api")
        for field_name in ("policy_source_ref", "policy_source_path"):
            _require_non_empty(getattr(self, field_name), field_name)
        for field_name in ("policy_digest", "runtime_digest", "diff_digest", "evidence_digest"):
            _require_digest(getattr(self, field_name), field_name)
        if not isinstance(self.runtime_trust, RuntimeTrust):
            raise ValueError("runtime_trust must be a RuntimeTrust")
        object.__setattr__(self, "required_reviewers", _freeze_reviewers(self.required_reviewers))
        object.__setattr__(self, "validated_reviewers", _freeze_reviewers(self.validated_reviewers))
        if (
            isinstance(self.unresolved_thread_count, bool)
            or not isinstance(self.unresolved_thread_count, int)
            or self.unresolved_thread_count < 0
        ):
            raise ValueError("unresolved_thread_count must be a non-negative integer")
        reasons = tuple(self.reasons)
        for reason in reasons:
            if (
                not isinstance(reason, str)
                or not reason
                or len(reason) > 240
                or not re.fullmatch(r"[a-z0-9][a-z0-9_./:-]*", reason)
            ):
                raise ValueError("reason must be a sanitized evidence code")
        object.__setattr__(self, "reasons", tuple(sorted(set(reasons))))
        _iso_z(self.observed_at)
        if self.conclusion == "success" and (
            self.reasons
            or self.unresolved_thread_count
            or self.required_reviewers != self.validated_reviewers
        ):
            raise ValueError("successful gate result must be complete and reason-free")
        if self.conclusion == "failure" and not self.reasons:
            raise ValueError("failed gate result must name at least one sanitized reason")

    @property
    def gate_result_digest(self) -> str:
        document = {
            "base_ref": self.base_ref,
            "base_sha": self.base_sha,
            "check_name": self.check_name,
            "conclusion": self.conclusion,
            "diff_digest": self.diff_digest,
            "evidence_digest": self.evidence_digest,
            "head_sha": self.head_sha,
            "observed_at": _iso_z(self.observed_at),
            "policy_digest": self.policy_digest,
            "policy_source_path": self.policy_source_path,
            "policy_source_ref": self.policy_source_ref,
            "pr_state_source": self.pr_state_source.value,
            "pull_request_number": self.pull_request_number,
            "purpose": self.purpose.value,
            "reasons": list(self.reasons),
            "repository": self.repository,
            "required_reviewers": sorted(value.value for value in self.required_reviewers),
            "runtime_digest": self.runtime_digest,
            "runtime_trust": self.runtime_trust.value,
            "unresolved_thread_count": self.unresolved_thread_count,
            "validated_reviewers": sorted(value.value for value in self.validated_reviewers),
        }
        canonical = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @property
    def idempotency_key(self) -> str:
        document = {
            "check_name": self.check_name,
            "gate_result_digest": self.gate_result_digest,
            "head_sha": self.head_sha,
            "pull_request_number": self.pull_request_number,
            "repository": self.repository,
        }
        canonical = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PublicationReceipt:
    repository: str
    pull_request_number: int
    head_sha: str
    check_name: str
    publisher_app_slug: str
    publication_id: str
    gate_result_digest: str
    idempotency_key: str
    published_at: datetime
    head_revalidated_at: datetime

    def __post_init__(self) -> None:
        require_repository(self.repository)
        if (
            isinstance(self.pull_request_number, bool)
            or not isinstance(self.pull_request_number, int)
            or self.pull_request_number <= 0
        ):
            raise ValueError("pull_request_number must be a positive integer")
        require_full_sha(self.head_sha, "head_sha")
        for field_name in ("check_name", "publisher_app_slug", "publication_id"):
            _require_non_empty(getattr(self, field_name), field_name)
        _require_digest(self.gate_result_digest, "gate_result_digest")
        _require_digest(self.idempotency_key, "idempotency_key")
        _iso_z(self.published_at)
        _iso_z(self.head_revalidated_at)
        if (
            self.head_revalidated_at > self.published_at
            or (self.published_at - self.head_revalidated_at).total_seconds() > 30
        ):
            raise ValueError("head must be revalidated immediately before publication")


@dataclass(frozen=True)
class PriorGateEvidence:
    """Programmatic-only Beleg eines unmittelbar vorausgehenden publizierten Gate-Ergebnisses."""

    schema_version: int
    repository: str
    pull_request_number: int
    current_head_sha: str
    prior_gate_result: GateResult
    publication_receipt: PublicationReceipt
    source_app_slug: str
    source_reference: str
    observed_at: datetime
    valid_until: datetime

    def __post_init__(self) -> None:
        if self.schema_version != 1 or isinstance(self.schema_version, bool):
            raise ValueError("schema_version must be 1")
        require_repository(self.repository)
        if (
            isinstance(self.pull_request_number, bool)
            or not isinstance(self.pull_request_number, int)
            or self.pull_request_number <= 0
        ):
            raise ValueError("pull_request_number must be a positive integer")
        require_full_sha(self.current_head_sha, "current_head_sha")
        if not isinstance(self.prior_gate_result, GateResult):
            raise ValueError("prior_gate_result must be a GateResult")
        if not isinstance(self.publication_receipt, PublicationReceipt):
            raise ValueError("publication_receipt must be a PublicationReceipt")
        for field_name in ("source_app_slug", "source_reference"):
            _require_non_empty(getattr(self, field_name), field_name)
        _iso_z(self.observed_at)
        _iso_z(self.valid_until)
        if self.valid_until <= self.observed_at:
            raise ValueError("valid_until must be after observed_at")


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


class CommandPort(ABC):
    @abstractmethod
    def run(self, argv: tuple[str, ...], timeout_seconds: float) -> CommandResult:
        """Führt einen read-only Prozess mit geschlossenem argv- und Zeitlimitvertrag aus."""


class StatusPort(ABC):
    @abstractmethod
    def fetch(self, timeout_seconds: float) -> StatusSnapshot:
        """Liest den öffentlichen Providerzustand ohne Authentifizierungsdaten."""


class ClockPort(ABC):
    @abstractmethod
    def now(self) -> datetime:
        """Liefert einen timezone-aware Zeitpunkt für Evidenzbindungen."""


class ProbePort(ABC):
    @abstractmethod
    def probe(self, request: ProbeRequest) -> ProbeReport:
        """Erhebt die read-only Copilot-Verwendbarkeit für den gebundenen Kontext."""


class OperatorEvidenceTrustPort(ABC):
    @abstractmethod
    def load(self, source_reference: str) -> OperatorEvidencePin | None:
        """Lädt einen programmatic-only externen Digest-Pin oder meldet ihn als fehlend."""


class CapabilityEvidenceVerifierPort(ABC):
    @abstractmethod
    def verify(
        self,
        reference: CapabilityEvidenceReference | None,
        repository: str,
        principal: BillingPrincipal,
        review_mode: str,
        observed_at: datetime,
    ) -> CapabilityVerification:
        """Rekonstruiert routingfähige Capability ausschließlich aus verifizierter Evidenz."""


class BlockEvidenceVerifierPort(ABC):
    @abstractmethod
    def verify(
        self,
        reference: BlockEvidenceReference | None,
        repository: str,
        principal: BillingPrincipal,
        review_mode: str,
        observed_at: datetime,
    ) -> BlockVerification:
        """Rekonstruiert eine aktuelle Blockade ausschließlich aus verifizierter Evidenz."""


class PullRequestStatePort(ABC):
    @abstractmethod
    def load(self, repository: str, pull_request_number: int) -> PullRequestState:
        """Lädt Base-Ref sowie vollständige Base-/Head-SHAs aus der GitHub-API."""


class ReviewerAvailabilityPort(ABC):
    @abstractmethod
    def load(
        self,
        repository: str,
        pull_request_number: int,
        head_sha: str,
        purpose: ReviewPurpose,
    ) -> ReviewerAvailabilitySnapshot:
        """Lädt die programmatic-only QA-/SEC-Verfügbarkeit für den Exact-Head-Kontext."""


class PriorGateEvidencePort(ABC):
    @abstractmethod
    def load_immediate(
        self,
        repository: str,
        pull_request_number: int,
        current_head_sha: str,
    ) -> PriorGateEvidence | None:
        """Lädt ausschließlich das unmittelbar vorausgehende publizierte Gate aus dem Ledger."""


class EvidenceValidatorPort(ABC):
    @abstractmethod
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
        """Validiert vollständige Exact-Head-Evidenz gegen erneut erhobene Vertrauensquellen."""


class GatePublisherPort(ABC):
    @abstractmethod
    def publish(self, result: GateResult) -> PublicationReceipt:
        """Publiziert nach erneuter Head-Prüfung idempotent; in diesem PR ohne Implementierung."""


@dataclass(frozen=True)
class CliDependencies:
    """Programmatic-only Grenze für externe, vertrauenswürdige Abhängigkeiten."""

    runtime_trust_port: RuntimeTrustPort | None = None
    operator_evidence_trust_port: OperatorEvidenceTrustPort | None = None
    probe: ProbePort | None = None
    pull_request_state: PullRequestStatePort | None = None
    reviewer_availability: ReviewerAvailabilityPort | None = None
    prior_gate_evidence: PriorGateEvidencePort | None = None
    config: ConfigPort | None = None
    policy_source: PolicySourcePort | None = None
    diff_source: DiffSourcePort | None = None
    clock: ClockPort | None = None

    def __post_init__(self) -> None:
        expected_ports = {
            "runtime_trust_port": RuntimeTrustPort,
            "operator_evidence_trust_port": OperatorEvidenceTrustPort,
            "probe": ProbePort,
            "pull_request_state": PullRequestStatePort,
            "reviewer_availability": ReviewerAvailabilityPort,
            "prior_gate_evidence": PriorGateEvidencePort,
            "config": ConfigPort,
            "policy_source": PolicySourcePort,
            "diff_source": DiffSourcePort,
            "clock": ClockPort,
        }
        for field_name, port in expected_ports.items():
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, port):
                raise ValueError(f"{field_name} must implement {port.__name__}")


class AdapterFactory(Protocol):
    """Deklariert Ports und erzeugt ihre Implementierungen aus aufgelösten Abhängigkeiten."""

    provided_ports: tuple[type[object], ...]
    required_ports: tuple[type[object], ...]

    def build(self, dependencies: Mapping[type[object], object]) -> Mapping[type[object], object]:
        """Erzeugt genau die für diese Factory deklarierten Port-Implementierungen."""
