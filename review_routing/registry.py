"""Importblinde Registry für die paketierte Runtime-Bootstrap-SSOT."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib
from importlib import resources
from typing import Mapping
import tomllib

from review_routing.contracts import (
    AdapterFactory,
    CliDependencies,
    CyclicProviderError,
    DuplicateProviderError,
    InvalidFactoryError,
    MissingProviderError,
    RuntimeProvenance,
    RuntimeTrust,
    RuntimeTrustConfig,
    RuntimeTrustMismatchError,
    RuntimeTrustSource,
)


class RuntimeRegistry:
    """Löst Port-Implementierungen ausschließlich aus der paketierten Runtime-SSOT auf."""

    def __init__(self, runtime_provenance: RuntimeProvenance | None = None):
        self._providers: dict[type[object], AdapterFactory] = {}
        self._resolved: dict[type[object], object] = {}
        self._resolving: set[type[object]] = set()
        self._runtime_provenance = runtime_provenance

    @property
    def runtime_provenance(self) -> RuntimeProvenance:
        if self._runtime_provenance is None:
            raise InvalidFactoryError("Die Runtime-Provenienz ist vor dem Bootstrap nicht verfügbar")
        return self._runtime_provenance

    @classmethod
    def bootstrap(cls, dependencies: CliDependencies | None) -> RuntimeRegistry:
        runtime_bytes = resources.files("review_routing").joinpath("runtime.toml").read_bytes()
        manifest = cls._parse_manifest(runtime_bytes)
        provenance = cls._runtime_provenance(runtime_bytes, dependencies)
        registry = cls(provenance)
        for module_name in manifest["modules"]:
            module = importlib.import_module(module_name)
            factory_builder = getattr(module, "factory", None)
            if not callable(factory_builder):
                raise InvalidFactoryError(f"Runtime-Modul '{module_name}' stellt keine Factory bereit")
            registry.register(factory_builder())
        return registry

    @staticmethod
    def _parse_manifest(runtime_bytes: bytes) -> Mapping[str, object]:
        try:
            raw = tomllib.loads(runtime_bytes.decode("utf-8"))
        except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
            raise InvalidFactoryError("Das Runtime-Manifest ist nicht gültiges UTF-8-TOML") from error
        if set(raw) != {"schema_version", "modules"}:
            raise InvalidFactoryError("Das Runtime-Manifest enthält unbekannte oder fehlende Schlüssel")
        if raw["schema_version"] != 1 or isinstance(raw["schema_version"], bool):
            raise InvalidFactoryError("Das Runtime-Manifest verwendet keine unterstützte Schema-Version")
        modules = raw["modules"]
        if (
            not isinstance(modules, list)
            or not modules
            or any(not isinstance(module, str) or not module for module in modules)
            or len(set(modules)) != len(modules)
        ):
            raise InvalidFactoryError("Das Runtime-Manifest enthält keine geschlossene Modulliste")
        return raw

    @staticmethod
    def _runtime_provenance(
        runtime_bytes: bytes,
        dependencies: CliDependencies | None,
    ) -> RuntimeProvenance:
        trust_config = (
            dependencies.runtime_trust_port.load()
            if dependencies is not None and dependencies.runtime_trust_port is not None
            else RuntimeTrustConfig(
                expected_runtime_digest=None,
                source=RuntimeTrustSource.DEVELOPMENT,
                observed_at=datetime.now(timezone.utc),
            )
        )
        digest = "sha256:" + hashlib.sha256(runtime_bytes).hexdigest()
        trusted_sources = {
            RuntimeTrustSource.PUBLISHER_APP,
            RuntimeTrustSource.INSTALLED_CONFIG,
        }
        if trust_config.expected_runtime_digest is None:
            return RuntimeProvenance(digest=digest, trust=RuntimeTrust.DEVELOPMENT)
        if trust_config.source in trusted_sources:
            if trust_config.expected_runtime_digest != digest:
                raise RuntimeTrustMismatchError("Der externe Runtime-Pin stimmt nicht mit dem Manifest überein")
            return RuntimeProvenance(digest=digest, trust=RuntimeTrust.INSTALLED)
        return RuntimeProvenance(digest=digest, trust=RuntimeTrust.DEVELOPMENT)

    def register(self, factory: AdapterFactory) -> None:
        provided_ports = factory.provided_ports
        if not provided_ports or len(set(provided_ports)) != len(provided_ports):
            raise InvalidFactoryError("Eine Factory muss eindeutige angebotene Ports deklarieren")
        for port in provided_ports:
            if port in self._providers:
                raise DuplicateProviderError(f"Mehrere Factories bieten den Port '{port.__name__}' an")
        for port in provided_ports:
            self._providers[port] = factory

    def resolve(self, port: type[object]) -> object:
        if port in self._resolved:
            return self._resolved[port]
        if port in self._resolving:
            raise CyclicProviderError(f"Zyklische Abhängigkeit am Port '{port.__name__}'")
        factory = self._providers.get(port)
        if factory is None:
            raise MissingProviderError(f"Für den Port '{port.__name__}' fehlt ein Provider")
        self._resolving.add(port)
        try:
            dependencies = {required: self.resolve(required) for required in factory.required_ports}
            implementations = factory.build(dependencies)
            if set(implementations) != set(factory.provided_ports):
                raise InvalidFactoryError("Eine Factory liefert nicht genau ihre deklarierten Ports")
            self._resolved.update(implementations)
        finally:
            self._resolving.remove(port)
        return self._resolved[port]
