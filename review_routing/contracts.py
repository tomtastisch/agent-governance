"""Einziger Vertragsrand für Review-Routing-Ports, Konfiguration und Fehler."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Mapping, Protocol


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
