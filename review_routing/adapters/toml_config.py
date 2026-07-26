"""Strikter TOML-Adapter für die zentrale Routing-Policy."""
from __future__ import annotations

from types import MappingProxyType
from typing import Mapping
import tomllib

from review_routing.contracts import (
    AdapterFactory,
    ConfigPort,
    GatePublisher,
    PathMarker,
    PolicyDocument,
    PolicyValidationError,
    RequiredCheck,
    RoutingConfig,
)


_RISK_LEVELS = ("low", "medium", "high", "critical")
_REVIEW_ROUTES = {
    "local_checks",
    "copilot",
    "copilot_qa",
    "copilot_qa_sec",
    "qa",
    "qa_sec",
    "blocker",
}


class TomlConfig(ConfigPort):
    """Dekodiert nur vollständig bekannte Policy-Schemata."""

    def parse_routing(self, document: PolicyDocument) -> RoutingConfig:
        try:
            raw = tomllib.loads(document.content)
        except tomllib.TOMLDecodeError as error:
            raise PolicyValidationError("Die Routing-Policy ist kein gültiges TOML") from error
        self._require_exact_keys(raw, {"schema_version", "risk", "routing", "gate"}, "Policy")
        if raw["schema_version"] != 1 or isinstance(raw["schema_version"], bool):
            raise PolicyValidationError("Die Routing-Policy verwendet keine unterstützte Schema-Version")
        thresholds, path_markers = self._parse_risk(raw["risk"])
        routes = self._parse_routes(raw["routing"])
        required_checks, publisher = self._parse_gate(raw["gate"])
        return RoutingConfig(
            schema_version=raw["schema_version"],
            thresholds=MappingProxyType(thresholds),
            path_markers=tuple(path_markers),
            routes=MappingProxyType(routes),
            required_checks=tuple(required_checks),
            publisher=publisher,
        )

    def _parse_risk(self, risk: object) -> tuple[dict[str, int], list[PathMarker]]:
        if not isinstance(risk, dict):
            raise PolicyValidationError("Der Risikoabschnitt muss eine Tabelle sein")
        self._require_exact_keys(risk, {"thresholds", "path_markers"}, "Risikoabschnitt")
        thresholds = risk["thresholds"]
        if not isinstance(thresholds, dict):
            raise PolicyValidationError("Die Risikoschwellen müssen eine Tabelle sein")
        self._require_exact_keys(thresholds, {"medium", "high", "critical"}, "Risikoschwellen")
        ordered = [thresholds[level] for level in ("medium", "high", "critical")]
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in ordered):
            raise PolicyValidationError("Die Risikoschwellen müssen positive Ganzzahlen sein")
        if ordered != sorted(ordered) or len(set(ordered)) != len(ordered):
            raise PolicyValidationError("Die Risikoschwellen müssen strikt ansteigen")
        raw_markers = risk["path_markers"]
        if not isinstance(raw_markers, list) or not raw_markers:
            raise PolicyValidationError("Die Risikopolicy benötigt mindestens einen Pfadmarker")
        markers = []
        for marker in raw_markers:
            if not isinstance(marker, dict):
                raise PolicyValidationError("Ein Pfadmarker muss eine Tabelle sein")
            self._require_exact_keys(marker, {"glob", "level", "security_relevant"}, "Pfadmarker")
            if not isinstance(marker["glob"], str) or not marker["glob"]:
                raise PolicyValidationError("Ein Pfadmarker benötigt einen nicht-leeren Glob")
            if marker["level"] not in _RISK_LEVELS:
                raise PolicyValidationError("Ein Pfadmarker enthält eine unbekannte Risikostufe")
            if not isinstance(marker["security_relevant"], bool):
                raise PolicyValidationError("security_relevant eines Pfadmarkers muss boolesch sein")
            markers.append(PathMarker(**marker))
        return dict(thresholds), markers

    def _parse_routes(self, routing: object) -> dict[str, Mapping[bool, Mapping[str, str]]]:
        if not isinstance(routing, dict):
            raise PolicyValidationError("Der Routingabschnitt muss eine Tabelle sein")
        self._require_exact_keys(routing, {"checkpoint", "final_exact_head"}, "Routingabschnitt")
        parsed: dict[str, Mapping[bool, Mapping[str, str]]] = {}
        for purpose, raw_purpose in routing.items():
            if not isinstance(raw_purpose, dict):
                raise PolicyValidationError("Jeder Reviewzweck muss eine Tabelle sein")
            self._require_exact_keys(raw_purpose, {"usable", "unusable"}, "Routingzweck")
            states: dict[bool, Mapping[str, str]] = {}
            for usable, key in ((True, "usable"), (False, "unusable")):
                matrix = raw_purpose[key]
                if not isinstance(matrix, dict):
                    raise PolicyValidationError("Jede Routingmatrix muss eine Tabelle sein")
                self._require_exact_keys(matrix, set(_RISK_LEVELS), "Routingmatrix")
                if any(route not in _REVIEW_ROUTES for route in matrix.values()):
                    raise PolicyValidationError("Die Routingmatrix enthält eine unbekannte Route")
                states[usable] = MappingProxyType(dict(matrix))
            parsed[purpose] = MappingProxyType(states)
        return parsed

    def _parse_gate(self, gate: object) -> tuple[list[RequiredCheck], GatePublisher]:
        if not isinstance(gate, dict):
            raise PolicyValidationError("Der Gateabschnitt muss eine Tabelle sein")
        self._require_exact_keys(gate, {"required_checks", "publisher"}, "Gateabschnitt")
        raw_checks = gate["required_checks"]
        if not isinstance(raw_checks, list) or not raw_checks:
            raise PolicyValidationError("Das Gate benötigt mindestens einen Pflichtcheck")
        checks = []
        names = set()
        for check in raw_checks:
            if not isinstance(check, dict):
                raise PolicyValidationError("Ein Pflichtcheck muss eine Tabelle sein")
            self._require_exact_keys(check, {"name", "source_app_slug"}, "Pflichtcheck")
            if any(not isinstance(check[field], str) or not check[field] for field in check):
                raise PolicyValidationError("Ein Pflichtcheck benötigt nicht-leere Zeichenketten")
            if check["name"] in names:
                raise PolicyValidationError("Pflichtchecknamen müssen eindeutig sein")
            names.add(check["name"])
            checks.append(RequiredCheck(**check))
        publisher = gate["publisher"]
        if not isinstance(publisher, dict):
            raise PolicyValidationError("Der Publisher muss eine Tabelle sein")
        self._require_exact_keys(publisher, {"expected_app_slug"}, "Publisher")
        if not isinstance(publisher["expected_app_slug"], str) or not publisher["expected_app_slug"]:
            raise PolicyValidationError("Der Publisher benötigt einen nicht-leeren App-Slug")
        return checks, GatePublisher(**publisher)

    @staticmethod
    def _require_exact_keys(value: Mapping[str, object], expected: set[str], context: str) -> None:
        if set(value) != expected:
            raise PolicyValidationError(f"{context} enthält unbekannte oder fehlende Schlüssel")


class TomlConfigFactory:
    provided_ports = (ConfigPort,)
    required_ports: tuple[type[object], ...] = ()

    def build(self, dependencies: Mapping[type[object], object]) -> Mapping[type[object], object]:
        if dependencies:
            raise PolicyValidationError("Der TOML-Konfigurationsadapter erwartet keine Abhängigkeiten")
        return {ConfigPort: TomlConfig()}


def factory() -> AdapterFactory:
    """Meldet die deklarative TOML-Policy-Implementierung an der Runtime-Registry an."""
    return TomlConfigFactory()
