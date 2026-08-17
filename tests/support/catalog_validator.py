#!/usr/bin/env python3
"""Gemeinsamer fail-closed Validator für Manifest und Governance-Kataloge."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tomllib
from typing import Mapping


ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
MANIFEST_FIELDS = frozenset(
    {"schema_version", "local_rules", "catalogs", "routing", "modules", "roles"}
)
CATALOG_NAMES = ("triggers", "policy_tags", "scopes", "tools")
VOCABULARY_FIELDS = frozenset({"label", "description"})
MODULE_FIELDS = frozenset({"path", "triggers", "dependencies"})
ROLE_FIELDS = frozenset({"path", "triggers", "modules"})
TOOL_FIELDS = frozenset(
    {
        "name",
        "purpose",
        "required_on",
        "useful_on",
        "policy_tags",
        "scopes",
        "evidence",
        "fallback",
        "constraints",
    }
)


class CatalogValidationError(RuntimeError):
    """Ein geschlossener Katalog-, Pfad- oder Referenzvertrag ist verletzt."""


@dataclass(frozen=True)
class CatalogContract:
    manifest: Mapping[str, object]
    catalogs: Mapping[str, Mapping[str, object]]
    catalog_paths: tuple[Path, ...]
    triggers: frozenset[str]
    policy_tags: frozenset[str]
    scopes: frozenset[str]
    tools: Mapping[str, Mapping[str, object]]


def load_catalog_contract(
    manifest_dir: Path, *, manifest: Mapping[str, object] | None = None
) -> CatalogContract:
    """Lädt und validiert Manifest plus vier Kataloge relativ zu einem absoluten Root."""
    root = _manifest_root(Path(manifest_dir))
    manifest_path = root / "manifest.toml"
    if manifest is None:
        manifest_data = _load_toml(_regular_file(root, manifest_path, "Manifest"), "Manifest")
    else:
        if not isinstance(manifest, Mapping):
            raise CatalogValidationError("Manifest muss eine Tabelle sein")
        manifest_data = dict(manifest)

    _exact_fields(manifest_data, MANIFEST_FIELDS, "Manifest Top-Level")
    if type(manifest_data.get("schema_version")) is not int or manifest_data["schema_version"] != 2:
        raise CatalogValidationError("Manifest schema_version muss Integer 2 sein")
    local_rules = manifest_data.get("local_rules")
    if not isinstance(local_rules, str) or not local_rules:
        raise CatalogValidationError("Manifest local_rules muss ein nichtleerer relativer Pfad sein")

    routing = manifest_data.get("routing")
    if not isinstance(routing, Mapping):
        raise CatalogValidationError("Manifest routing muss eine Tabelle sein")
    _exact_fields(routing, frozenset({"unknown", "ambiguous"}), "Manifest routing")
    if routing.get("unknown") != "block" or routing.get("ambiguous") != "block":
        raise CatalogValidationError("Manifest routing muss unknown und ambiguous blockieren")

    catalog_index = manifest_data.get("catalogs")
    if not isinstance(catalog_index, Mapping):
        raise CatalogValidationError("Manifest catalogs muss eine Tabelle sein")
    _exact_fields(catalog_index, frozenset(CATALOG_NAMES), "Manifest catalogs")

    parsed_catalogs: dict[str, Mapping[str, object]] = {}
    catalog_paths: list[Path] = []
    for name in CATALOG_NAMES:
        path = _catalog_file(root, catalog_index.get(name))
        parsed_catalogs[name] = _load_toml(path, f"Katalog {name}")
        catalog_paths.append(path)

    triggers = _validate_vocabulary(parsed_catalogs["triggers"], "triggers")
    policy_tags = _validate_vocabulary(parsed_catalogs["policy_tags"], "policy_tags")
    scopes = _validate_vocabulary(parsed_catalogs["scopes"], "scopes")
    tools = _validate_tools(parsed_catalogs["tools"], triggers, policy_tags, scopes)
    _validate_manifest_index(root, manifest_data, triggers)

    return CatalogContract(
        manifest=manifest_data,
        catalogs=parsed_catalogs,
        catalog_paths=tuple(catalog_paths),
        triggers=triggers,
        policy_tags=policy_tags,
        scopes=scopes,
        tools=tools,
    )


def _manifest_root(path: Path) -> Path:
    if not path.is_absolute() or path.is_symlink() or not path.is_dir():
        raise CatalogValidationError("Manifestverzeichnis muss absolut, vorhanden und linkfrei sein")
    try:
        return path.resolve(strict=True)
    except OSError as error:
        raise CatalogValidationError("Manifestverzeichnis ist nicht sicher auflösbar") from error


def _catalog_file(root: Path, raw: object) -> Path:
    return _index_file(root, raw, "Katalog")


def _index_file(root: Path, raw: object, kind: str) -> Path:
    if not isinstance(raw, str) or not raw or Path(raw).is_absolute() or "\\" in raw:
        raise CatalogValidationError(f"{kind}pfad ist ungültig")
    raw_parts = raw.split("/")
    if any(part in {"", ".", "..", "~"} for part in raw_parts):
        raise CatalogValidationError(f"{kind}pfad enthält Traversal")
    pure = PurePosixPath(raw)
    candidate = root.joinpath(*pure.parts)
    current = root
    for part in pure.parts:
        current = current / part
        if current.is_symlink():
            raise CatalogValidationError(f"Symlink im {kind}pfad")
    return _regular_file(root, candidate, kind)


def _regular_file(root: Path, candidate: Path, kind: str) -> Path:
    try:
        file_stat = os.lstat(candidate)
    except OSError as error:
        raise CatalogValidationError(f"{kind} muss eine reguläre Nicht-Symlink-Datei sein") from error
    if stat.S_ISLNK(file_stat.st_mode):
        raise CatalogValidationError(f"Symlink im {kind}pfad")
    if not stat.S_ISREG(file_stat.st_mode):
        raise CatalogValidationError(f"{kind} muss eine reguläre Nicht-Symlink-Datei sein")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as error:
        raise CatalogValidationError(f"{kind} verlässt das Manifestverzeichnis") from error
    return resolved


def _load_toml(path: Path, kind: str) -> Mapping[str, object]:
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise CatalogValidationError(f"{kind} ist kein gültiges TOML") from error
    if not isinstance(data, dict):
        raise CatalogValidationError(f"{kind} muss eine TOML-Tabelle sein")
    return data


def _exact_fields(
    data: Mapping[str, object], expected: frozenset[str], context: str
) -> None:
    present = set(data)
    unknown = present - expected
    missing = expected - present
    if unknown:
        raise CatalogValidationError(f"{context} enthält unbekannte Felder: {sorted(unknown)}")
    if missing:
        raise CatalogValidationError(f"{context} enthält fehlende Felder: {sorted(missing)}")


def _validate_vocabulary(catalog: Mapping[str, object], table_name: str) -> frozenset[str]:
    _exact_fields(catalog, frozenset({"schema_version", table_name}), f"{table_name} Top-Level")
    if type(catalog.get("schema_version")) is not int or catalog["schema_version"] != 1:
        raise CatalogValidationError(f"{table_name} schema_version muss Integer 1 sein")
    entries = catalog.get(table_name)
    if not isinstance(entries, Mapping) or not entries:
        raise CatalogValidationError(f"{table_name} muss eine nichtleere Tabelle sein")
    for item_id, item in entries.items():
        _validate_id(item_id, table_name)
        if not isinstance(item, Mapping):
            raise CatalogValidationError(f"{table_name}.{item_id} muss eine Tabelle sein")
        _exact_fields(item, VOCABULARY_FIELDS, f"{table_name}.{item_id}")
        _nonempty_text(item.get("label"), f"{table_name}.{item_id}.label")
        _nonempty_text(item.get("description"), f"{table_name}.{item_id}.description")
    return frozenset(entries)


def _validate_tools(
    catalog: Mapping[str, object],
    triggers: frozenset[str],
    policy_tags: frozenset[str],
    scopes: frozenset[str],
) -> Mapping[str, Mapping[str, object]]:
    _exact_fields(catalog, frozenset({"schema_version", "tools"}), "tools Top-Level")
    if type(catalog.get("schema_version")) is not int or catalog["schema_version"] != 1:
        raise CatalogValidationError("tools schema_version muss Integer 1 sein")
    tools = catalog.get("tools")
    if not isinstance(tools, Mapping) or not tools:
        raise CatalogValidationError("tools muss eine nichtleere Tabelle sein")
    for tool_id, tool in tools.items():
        _validate_id(tool_id, "tools")
        if not isinstance(tool, Mapping):
            raise CatalogValidationError(f"tools.{tool_id} muss eine Tabelle sein")
        _exact_fields(tool, TOOL_FIELDS, f"tools.{tool_id}")
        for field in ("name", "purpose", "evidence", "fallback", "constraints"):
            _nonempty_text(tool.get(field), f"tools.{tool_id}.{field}")
        required_on = _id_list(tool.get("required_on"), f"tools.{tool_id}.required_on")
        useful_on = _id_list(tool.get("useful_on"), f"tools.{tool_id}.useful_on")
        tool_policy_tags = _id_list(tool.get("policy_tags"), f"tools.{tool_id}.policy_tags")
        tool_scopes = _id_list(tool.get("scopes"), f"tools.{tool_id}.scopes")
        _known_references(required_on, triggers, "unbekannten Trigger", tool_id)
        _known_references(useful_on, triggers, "unbekannten Trigger", tool_id)
        _known_references(tool_policy_tags, policy_tags, "unbekannten Policy-Tag", tool_id)
        _known_references(tool_scopes, scopes, "unbekannten Scope", tool_id)
    return tools


def _validate_manifest_index(
    root: Path,
    manifest: Mapping[str, object],
    triggers: frozenset[str],
) -> None:
    modules = manifest.get("modules")
    if not isinstance(modules, Mapping) or not modules:
        raise CatalogValidationError("Manifest modules muss eine nichtleere Tabelle sein")
    module_ids = frozenset(_validate_id(module_id, "Manifest modules") for module_id in modules)
    module_dependencies: dict[str, tuple[str, ...]] = {}
    for module_id, module in modules.items():
        context = f"Manifest modules.{module_id}"
        if not isinstance(module, Mapping):
            raise CatalogValidationError(f"{context} muss eine Tabelle sein")
        _exact_fields(module, MODULE_FIELDS, context)
        _index_file(root, module.get("path"), "Modul")
        module_triggers = _nonempty_id_list(module.get("triggers"), f"{context}.triggers")
        _known_references(module_triggers, triggers, "unbekannten Trigger", context)
        module_dependencies[module_id] = _id_list(
            module.get("dependencies"), f"{context}.dependencies"
        )

    for module_id, dependencies in module_dependencies.items():
        _known_references(dependencies, module_ids, "unbekannte Module", f"modules.{module_id}")
    _validate_module_graph(module_dependencies)

    roles = manifest.get("roles")
    if not isinstance(roles, Mapping) or not roles:
        raise CatalogValidationError("Manifest roles muss eine nichtleere Tabelle sein")
    for role_id, role in roles.items():
        _validate_id(role_id, "Manifest roles")
        context = f"Manifest roles.{role_id}"
        if not isinstance(role, Mapping):
            raise CatalogValidationError(f"{context} muss eine Tabelle sein")
        _exact_fields(role, ROLE_FIELDS, context)
        _index_file(root, role.get("path"), "Rollen")
        role_triggers = _nonempty_id_list(role.get("triggers"), f"{context}.triggers")
        _known_references(role_triggers, triggers, "unbekannten Trigger", context)
        role_modules = _nonempty_id_list(role.get("modules"), f"{context}.modules")
        _known_references(role_modules, module_ids, "unbekannte Module", context)


def _validate_module_graph(dependencies: Mapping[str, tuple[str, ...]]) -> None:
    visited: set[str] = set()
    visiting: list[str] = []

    def visit(module_id: str) -> None:
        if module_id in visited:
            return
        if module_id in visiting:
            cycle = " -> ".join([*visiting[visiting.index(module_id):], module_id])
            raise CatalogValidationError(f"Modulabhängigkeiten sind zyklisch: {cycle}")
        visiting.append(module_id)
        for dependency in dependencies[module_id]:
            visit(dependency)
        visiting.pop()
        visited.add(module_id)

    for module_id in dependencies:
        visit(module_id)


def _validate_id(value: object, context: str) -> str:
    if not isinstance(value, str) or ID_RE.fullmatch(value) is None:
        raise CatalogValidationError(f"{context} enthält ungültige ID: {value!r}")
    return value


def _id_list(value: object, context: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise CatalogValidationError(f"{context} muss eine Liste sein")
    result = tuple(_validate_id(item, context) for item in value)
    if len(result) != len(set(result)):
        raise CatalogValidationError(f"{context} enthält doppelte IDs")
    return result


def _nonempty_id_list(value: object, context: str) -> tuple[str, ...]:
    result = _id_list(value, context)
    if not result:
        raise CatalogValidationError(f"{context} muss mindestens eine ID enthalten")
    return result


def _known_references(
    references: tuple[str, ...], known: frozenset[str], label: str, context: str
) -> None:
    unknown = set(references) - known
    if unknown:
        raise CatalogValidationError(f"{context} enthält {label}: {sorted(unknown)}")


def _nonempty_text(value: object, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CatalogValidationError(f"{context} muss ein nichtleerer String sein")
    return value
