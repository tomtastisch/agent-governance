#!/usr/bin/env python3
"""Gemeinsamer fail-closed Validator für Manifest und Governance-Kataloge."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tomllib
from typing import Mapping


ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
WORK_ITEM_COLOR_RE = re.compile(r"^[0-9A-Fa-f]{6}$")
WORK_ITEM_MARKER_RE = re.compile(r"^\[[A-Z][A-Z0-9_-]*\]$")


class CatalogValidationError(RuntimeError):
    """Ein geschlossener Katalog-, Pfad- oder Referenzvertrag ist verletzt."""


_CONTRACT_ROOT = Path(__file__).resolve().parents[2]

_CONTRACT_TOP_LEVEL = frozenset({"schema_version", "fields", "domains", "vocabularies"})
_CONTRACT_FIELD_KEYS = frozenset(
    {
        "manifest",
        "routing",
        "ssot_manifest",
        "vocabulary",
        "module",
        "role",
        "tool",
        "command",
        "template",
        "discovery_top_level",
        "discovery_limits",
        "discovery_confidence",
        "discovery_candidate",
        "discovery_family",
        "discovery_signal",
        "work_item_classifications_top_level",
        "work_item_dimension",
        "work_item_classification",
        "work_item_projections_top_level",
        "work_item_projection",
        "work_item_title_marker",
    }
)
_CONTRACT_SSOT_DOMAINS = frozenset({"routing", "commands", "discovery", "work_items"})
_CONTRACT_VOCABULARY_ARRAY_KEYS = frozenset(
    {
        "template_categories",
        "template_formats",
        "command_capabilities",
        "command_effects",
        "discovery_evidence_families",
        "discovery_source_kinds",
        "discovery_strengths",
        "work_item_cardinalities",
    }
)
_CONTRACT_VOCABULARY_MAP_KEYS = frozenset({"discovery_candidate_classes"})


def _closed_keys(data: Mapping[str, object], expected: frozenset[str], context: str) -> None:
    unknown = set(data) - expected
    missing = expected - set(data)
    if unknown:
        raise CatalogValidationError(f"{context} enthält unbekannte Felder: {sorted(unknown)}")
    if missing:
        raise CatalogValidationError(f"{context} enthält fehlende Felder: {sorted(missing)}")


def _load_contract_fixture() -> Mapping[str, object]:
    """Lädt und validiert die gemeinsame sprachneutrale Contract-Fixture (Issue #90).

    Die Fixture ist die einzige Quelle der Strukturdefinitionen (Feldmengen,
    Domain-/Kataloglisten und Vokabulare). TypeScript und Python lesen dieselbe
    Datei; die Validierungslogik bleibt je Sprache unabhängig. Der Loader ist
    fail-closed und validiert ein geschlossenes Schema wie die TS-Seite.
    """
    path = _CONTRACT_ROOT / "contracts" / "governance-contract.json"
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise CatalogValidationError("governance contract fixture fehlt oder ist ungültig") from error
    if not isinstance(data, dict):
        raise CatalogValidationError("governance contract fixture muss eine Tabelle sein")

    _closed_keys(data, _CONTRACT_TOP_LEVEL, "contract fixture Top-Level")
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise CatalogValidationError("contract fixture schema_version muss Integer 1 sein")

    fields = data.get("fields")
    if not isinstance(fields, Mapping):
        raise CatalogValidationError("contract fixture fields muss eine Tabelle sein")
    _closed_keys(fields, _CONTRACT_FIELD_KEYS, "contract fixture fields")
    for name in _CONTRACT_FIELD_KEYS:
        _fieldset(data, name)

    domains = data.get("domains")
    if not isinstance(domains, Mapping):
        raise CatalogValidationError("contract fixture domains muss eine Tabelle sein")
    _closed_keys(domains, frozenset({"ssot", "ssot_catalogs"}), "contract fixture domains")
    ssot = domains.get("ssot")
    if not isinstance(ssot, list) or not ssot or not all(isinstance(item, str) for item in ssot):
        raise CatalogValidationError("contract fixture domains.ssot ist ungültig")
    if frozenset(ssot) != _CONTRACT_SSOT_DOMAINS:
        raise CatalogValidationError("contract fixture domains.ssot ist nicht kanonisch")
    catalogs = domains.get("ssot_catalogs")
    if not isinstance(catalogs, Mapping):
        raise CatalogValidationError("contract fixture domains.ssot_catalogs muss eine Tabelle sein")
    _closed_keys(catalogs, _CONTRACT_SSOT_DOMAINS, "contract fixture domains.ssot_catalogs")
    for domain in _CONTRACT_SSOT_DOMAINS:
        entries = catalogs[domain]
        if not isinstance(entries, list) or not entries or not all(isinstance(item, str) for item in entries):
            raise CatalogValidationError(f"contract fixture domains.ssot_catalogs.{domain} ist ungültig")

    vocabularies = data.get("vocabularies")
    if not isinstance(vocabularies, Mapping):
        raise CatalogValidationError("contract fixture vocabularies muss eine Tabelle sein")
    _closed_keys(
        vocabularies,
        _CONTRACT_VOCABULARY_ARRAY_KEYS | _CONTRACT_VOCABULARY_MAP_KEYS,
        "contract fixture vocabularies",
    )
    for name in _CONTRACT_VOCABULARY_ARRAY_KEYS:
        _vocabulary(data, name)
    _candidate_classes(data)

    return data


def _fieldset(data: Mapping[str, object], name: str) -> frozenset[str]:
    fields = data.get("fields")
    if not isinstance(fields, Mapping):
        raise CatalogValidationError("governance contract fixture fields fehlt")
    value = fields.get(name)
    if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
        raise CatalogValidationError(f"governance contract fixture fields.{name} ist ungültig")
    return frozenset(value)


def _vocabulary(data: Mapping[str, object], name: str) -> frozenset[str]:
    vocabularies = data.get("vocabularies")
    if not isinstance(vocabularies, Mapping):
        raise CatalogValidationError("governance contract fixture vocabularies fehlt")
    value = vocabularies.get(name)
    if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
        raise CatalogValidationError(f"governance contract fixture vocabularies.{name} ist ungültig")
    return frozenset(value)


def _domain_list(data: Mapping[str, object]) -> tuple[str, ...]:
    domains = data.get("domains")
    if not isinstance(domains, Mapping):
        raise CatalogValidationError("governance contract fixture domains fehlt")
    ssot = domains.get("ssot")
    if not isinstance(ssot, list) or not ssot or not all(isinstance(item, str) for item in ssot):
        raise CatalogValidationError("governance contract fixture domains.ssot ist ungültig")
    return tuple(ssot)


def _domain_catalogs(data: Mapping[str, object]) -> Mapping[str, frozenset[str]]:
    domains = data.get("domains")
    if not isinstance(domains, Mapping):
        raise CatalogValidationError("governance contract fixture domains fehlt")
    catalogs = domains.get("ssot_catalogs")
    if not isinstance(catalogs, Mapping):
        raise CatalogValidationError("governance contract fixture domains.ssot_catalogs fehlt")
    result: dict[str, frozenset[str]] = {}
    for domain, entries in catalogs.items():
        if not isinstance(entries, list) or not entries or not all(isinstance(item, str) for item in entries):
            raise CatalogValidationError(f"governance contract fixture domains.ssot_catalogs.{domain} ist ungültig")
        result[domain] = frozenset(entries)
    return result


def _candidate_classes(data: Mapping[str, object]) -> Mapping[str, str]:
    vocabularies = data.get("vocabularies")
    if not isinstance(vocabularies, Mapping):
        raise CatalogValidationError("governance contract fixture vocabularies fehlt")
    classes = vocabularies.get("discovery_candidate_classes")
    if not isinstance(classes, Mapping) or not classes or not all(
        isinstance(value, str) for value in classes.values()
    ):
        raise CatalogValidationError(
            "governance contract fixture vocabularies.discovery_candidate_classes ist ungültig"
        )
    return {str(key): str(value) for key, value in classes.items()}


_CONTRACT = _load_contract_fixture()

MANIFEST_FIELDS = _fieldset(_CONTRACT, "manifest")
SSOT_MANIFEST_FIELDS = _fieldset(_CONTRACT, "ssot_manifest")
SSOT_DOMAINS = _domain_list(_CONTRACT)
SSOT_DOMAIN_CATALOGS = _domain_catalogs(_CONTRACT)
VOCABULARY_FIELDS = _fieldset(_CONTRACT, "vocabulary")
MODULE_FIELDS = _fieldset(_CONTRACT, "module")
ROLE_FIELDS = _fieldset(_CONTRACT, "role")
TOOL_FIELDS = _fieldset(_CONTRACT, "tool")
COMMAND_FIELDS = _fieldset(_CONTRACT, "command")
COMMAND_CAPABILITIES = _vocabulary(_CONTRACT, "command_capabilities")
COMMAND_EFFECTS = _vocabulary(_CONTRACT, "command_effects")
DISCOVERY_TOP_LEVEL_FIELDS = _fieldset(_CONTRACT, "discovery_top_level")
DISCOVERY_LIMIT_FIELDS = _fieldset(_CONTRACT, "discovery_limits")
DISCOVERY_CONFIDENCE_FIELDS = _fieldset(_CONTRACT, "discovery_confidence")
DISCOVERY_CANDIDATE_FIELDS = _fieldset(_CONTRACT, "discovery_candidate")
DISCOVERY_FAMILY_FIELDS = _fieldset(_CONTRACT, "discovery_family")
DISCOVERY_SIGNAL_FIELDS = _fieldset(_CONTRACT, "discovery_signal")
DISCOVERY_FAMILIES = _vocabulary(_CONTRACT, "discovery_evidence_families")
DISCOVERY_SOURCE_KINDS = _vocabulary(_CONTRACT, "discovery_source_kinds")
DISCOVERY_STRENGTHS = _vocabulary(_CONTRACT, "discovery_strengths")
DISCOVERY_CANDIDATE_CLASSES = _candidate_classes(_CONTRACT)
DISCOVERY_CANDIDATE_CLASS_IDS = frozenset(DISCOVERY_CANDIDATE_CLASSES)
TEMPLATE_CATEGORIES = _vocabulary(_CONTRACT, "template_categories")
TEMPLATE_FIELDS = _fieldset(_CONTRACT, "template")
TEMPLATE_FORMATS = _vocabulary(_CONTRACT, "template_formats")
WORK_ITEM_CLASSIFICATIONS_TOP_LEVEL_FIELDS = _fieldset(_CONTRACT, "work_item_classifications_top_level")
WORK_ITEM_DIMENSION_FIELDS = _fieldset(_CONTRACT, "work_item_dimension")
WORK_ITEM_CLASSIFICATION_FIELDS = _fieldset(_CONTRACT, "work_item_classification")
WORK_ITEM_PROJECTIONS_TOP_LEVEL_FIELDS = _fieldset(_CONTRACT, "work_item_projections_top_level")
WORK_ITEM_PROJECTION_FIELDS = _fieldset(_CONTRACT, "work_item_projection")
WORK_ITEM_TITLE_MARKER_FIELDS = _fieldset(_CONTRACT, "work_item_title_marker")
WORK_ITEM_CARDINALITIES = _vocabulary(_CONTRACT, "work_item_cardinalities")


@dataclass(frozen=True)
class CatalogContract:
    manifest: Mapping[str, object]
    catalogs: Mapping[str, Mapping[str, object]]
    catalog_paths: tuple[Path, ...]
    template_paths: tuple[Path, ...]
    triggers: frozenset[str]
    policy_tags: frozenset[str]
    scopes: frozenset[str]
    tools: Mapping[str, Mapping[str, object]]
    commands: tuple[Mapping[str, object], ...]
    discovery: Mapping[str, object]
    work_item_classifications: Mapping[str, object]
    work_item_projections: Mapping[str, object]


def load_catalog_contract(
    manifest_dir: Path, *, manifest: Mapping[str, object] | None = None
) -> CatalogContract:
    """Lädt und validiert Manifest plus alle Kataloge relativ zu einem absoluten Root."""
    root = _manifest_root(Path(manifest_dir))
    manifest_path = root / "manifest.toml"
    if manifest is None:
        manifest_data = _load_toml(_regular_file(root, manifest_path, "Manifest"), "Manifest")
    else:
        if not isinstance(manifest, Mapping):
            raise CatalogValidationError("Manifest muss eine Tabelle sein")
        manifest_data = dict(manifest)

    _exact_fields(manifest_data, MANIFEST_FIELDS, "Manifest Top-Level")
    if type(manifest_data.get("schema_version")) is not int or manifest_data["schema_version"] != 4:
        raise CatalogValidationError("Manifest schema_version muss Integer 4 sein")
    local_rules = manifest_data.get("local_rules")
    if not isinstance(local_rules, str) or not local_rules:
        raise CatalogValidationError("Manifest local_rules muss ein nichtleerer relativer Pfad sein")
    _optional_index_path(root, local_rules, "local_rules")

    routing = manifest_data.get("routing")
    if not isinstance(routing, Mapping):
        raise CatalogValidationError("Manifest routing muss eine Tabelle sein")
    _exact_fields(routing, frozenset({"unknown", "ambiguous"}), "Manifest routing")
    if routing.get("unknown") != "block" or routing.get("ambiguous") != "block":
        raise CatalogValidationError("Manifest routing muss unknown und ambiguous blockieren")

    ssot_index_path = _index_file(root, manifest_data.get("ssot"), "SSOT-Index")
    ssot_data = _load_toml(ssot_index_path, "SSOT-Index")
    _exact_fields(ssot_data, SSOT_MANIFEST_FIELDS, "SSOT-Index Top-Level")
    if type(ssot_data.get("schema_version")) is not int or ssot_data["schema_version"] != 1:
        raise CatalogValidationError("SSOT-Index schema_version muss Integer 1 sein")
    domains = ssot_data.get("domains")
    if not isinstance(domains, Mapping):
        raise CatalogValidationError("SSOT-Index domains muss eine Tabelle sein")
    _exact_fields(domains, frozenset(SSOT_DOMAINS), "SSOT-Index domains")
    ssot_dir = ssot_index_path.parent

    parsed_catalogs: dict[str, Mapping[str, object]] = {}
    catalog_paths: list[Path] = []
    seen_catalog_ids: set[str] = set()
    for domain in SSOT_DOMAINS:
        entries = domains.get(domain)
        if not isinstance(entries, Mapping) or not entries:
            raise CatalogValidationError(f"SSOT-Domain {domain} muss eine nichtleere Tabelle sein")
        _exact_fields(entries, SSOT_DOMAIN_CATALOGS[domain], f"SSOT-Domain {domain}")
        for catalog_id in sorted(entries):
            _validate_id(catalog_id, f"SSOT-Domain {domain}")
            if catalog_id in seen_catalog_ids:
                raise CatalogValidationError("SSOT-Index enthält doppelte Katalog-IDs")
            seen_catalog_ids.add(catalog_id)
            path = _catalog_file(ssot_dir, entries.get(catalog_id))
            parsed_catalogs[catalog_id] = _load_toml(path, f"Katalog {catalog_id}")
            catalog_paths.append(path)

    triggers = _validate_vocabulary(parsed_catalogs["triggers"], "triggers")
    policy_tags = _validate_vocabulary(parsed_catalogs["policy_tags"], "policy_tags")
    scopes = _validate_vocabulary(parsed_catalogs["scopes"], "scopes")
    tools = _validate_tools(parsed_catalogs["tools"], triggers, policy_tags, scopes)
    commands = _validate_commands(parsed_catalogs["commands"])
    discovery = _validate_discovery(parsed_catalogs["discovery_signals"])
    work_item_classifications = _validate_work_item_classifications(
        parsed_catalogs["classifications"]
    )
    work_item_projections = _validate_work_item_projections(
        parsed_catalogs["github_labels"], work_item_classifications
    )
    _validate_manifest_index(root, manifest_data, triggers)
    _validate_tool_routing(manifest_data, tools)
    template_paths = _validate_templates(manifest_data, root)

    return CatalogContract(
        manifest=manifest_data,
        catalogs=parsed_catalogs,
        catalog_paths=tuple(catalog_paths),
        template_paths=template_paths,
        triggers=triggers,
        policy_tags=policy_tags,
        scopes=scopes,
        tools=tools,
        commands=commands,
        discovery=discovery,
        work_item_classifications=work_item_classifications,
        work_item_projections=work_item_projections,
    )


@dataclass(frozen=True)
class RoutingIndex:
    """Minimaler Routingzustand für Klassifikation und Modulauflösung.

    Enthält ausschließlich das Manifest, den Trigger-Katalog und aufgeschobene
    Katalogpfade. Es ist kein vollständiger Katalogvertrag und trifft keine
    fachliche oder Autorisierungsentscheidung.
    """

    manifest: Mapping[str, object]
    triggers: frozenset[str]
    root: Path
    ssot_dir: Path
    catalog_paths: Mapping[str, Path]


def load_routing_index(
    manifest_dir: Path, *, manifest: Mapping[str, object] | None = None
) -> RoutingIndex:
    """Lädt nur Manifest, SSOT-Index und Trigger-Katalog (fail-closed).

    Die übrigen Domänenkataloge (Tools, Policy-Tags, Scopes, Commands, Discovery,
    Work-Items, Templates) werden erst über die passenden Lazy-Loader geladen,
    wenn ein tatsächlich geladenes Modul sie benötigt.
    """
    root = _manifest_root(Path(manifest_dir))
    manifest_path = root / "manifest.toml"
    if manifest is None:
        manifest_data = _load_toml(_regular_file(root, manifest_path, "Manifest"), "Manifest")
    else:
        if not isinstance(manifest, Mapping):
            raise CatalogValidationError("Manifest muss eine Tabelle sein")
        manifest_data = dict(manifest)

    _exact_fields(manifest_data, MANIFEST_FIELDS, "Manifest Top-Level")
    if type(manifest_data.get("schema_version")) is not int or manifest_data["schema_version"] != 4:
        raise CatalogValidationError("Manifest schema_version muss Integer 4 sein")
    local_rules = manifest_data.get("local_rules")
    if not isinstance(local_rules, str) or not local_rules:
        raise CatalogValidationError("Manifest local_rules muss ein nichtleerer relativer Pfad sein")
    _optional_index_path(root, local_rules, "local_rules")

    routing = manifest_data.get("routing")
    if not isinstance(routing, Mapping):
        raise CatalogValidationError("Manifest routing muss eine Tabelle sein")
    _exact_fields(routing, frozenset({"unknown", "ambiguous"}), "Manifest routing")
    if routing.get("unknown") != "block" or routing.get("ambiguous") != "block":
        raise CatalogValidationError("Manifest routing muss unknown und ambiguous blockieren")

    ssot_index_path = _index_file(root, manifest_data.get("ssot"), "SSOT-Index")
    ssot_data = _load_toml(ssot_index_path, "SSOT-Index")
    _exact_fields(ssot_data, SSOT_MANIFEST_FIELDS, "SSOT-Index Top-Level")
    if type(ssot_data.get("schema_version")) is not int or ssot_data["schema_version"] != 1:
        raise CatalogValidationError("SSOT-Index schema_version muss Integer 1 sein")
    domains = ssot_data.get("domains")
    if not isinstance(domains, Mapping):
        raise CatalogValidationError("SSOT-Index domains muss eine Tabelle sein")
    _exact_fields(domains, frozenset(SSOT_DOMAINS), "SSOT-Index domains")
    ssot_dir = ssot_index_path.parent

    catalog_paths: dict[str, Path] = {}
    seen_catalog_ids: set[str] = set()
    for domain in SSOT_DOMAINS:
        entries = domains.get(domain)
        if not isinstance(entries, Mapping) or not entries:
            raise CatalogValidationError(f"SSOT-Domain {domain} muss eine nichtleere Tabelle sein")
        _exact_fields(entries, SSOT_DOMAIN_CATALOGS[domain], f"SSOT-Domain {domain}")
        for catalog_id in sorted(entries):
            _validate_id(catalog_id, f"SSOT-Domain {domain}")
            if catalog_id in seen_catalog_ids:
                raise CatalogValidationError("SSOT-Index enthält doppelte Katalog-IDs")
            seen_catalog_ids.add(catalog_id)
            catalog_paths[catalog_id] = _index_candidate(
                ssot_dir, entries.get(catalog_id), f"Katalog {catalog_id}"
            )

    triggers_path = _regular_file(ssot_dir, catalog_paths["triggers"], "Katalog triggers")
    triggers = _validate_vocabulary(_load_toml(triggers_path, "Katalog triggers"), "triggers")
    _validate_manifest_index(root, manifest_data, triggers)
    return RoutingIndex(
        manifest=manifest_data,
        triggers=triggers,
        root=root,
        ssot_dir=ssot_dir,
        catalog_paths=catalog_paths,
    )


def load_tool_domain(routing_index: RoutingIndex) -> Mapping[str, Mapping[str, object]]:
    """Lädt und validiert Tools-, Policy-Tag- und Scope-Kataloge (fail-closed)."""
    ssot_dir = routing_index.ssot_dir
    paths = routing_index.catalog_paths
    policy_tags = _validate_vocabulary(
        _load_toml(_regular_file(ssot_dir, paths["policy_tags"], "Katalog policy_tags"), "Katalog policy_tags"),
        "policy_tags",
    )
    scopes = _validate_vocabulary(
        _load_toml(_regular_file(ssot_dir, paths["scopes"], "Katalog scopes"), "Katalog scopes"),
        "scopes",
    )
    tools = _validate_tools(
        _load_toml(_regular_file(ssot_dir, paths["tools"], "Katalog tools"), "Katalog tools"),
        routing_index.triggers,
        policy_tags,
        scopes,
    )
    _validate_tool_routing(routing_index.manifest, tools)
    return {"policy_tags": policy_tags, "scopes": scopes, "tools": tools}


def load_template_index(routing_index: RoutingIndex) -> tuple[Path, ...]:
    """Lädt und validiert den Template-Index (fail-closed)."""
    return _validate_templates(routing_index.manifest, routing_index.root)


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
    return _regular_file(root, _index_candidate(root, raw, kind), kind)


def _optional_index_path(root: Path, raw: object, kind: str) -> Path:
    candidate = _index_candidate(root, raw, kind)
    if candidate.exists() or candidate.is_symlink():
        return _regular_file(root, candidate, kind)
    return candidate


def _index_candidate(root: Path, raw: object, kind: str) -> Path:
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
    return candidate


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


def _validate_commands(catalog: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    _exact_fields(catalog, frozenset({"schema_version", "commands"}), "commands Top-Level")
    if type(catalog.get("schema_version")) is not int or catalog["schema_version"] != 1:
        raise CatalogValidationError("commands schema_version muss Integer 1 sein")
    raw_commands = catalog.get("commands")
    if not isinstance(raw_commands, list) or not raw_commands:
        raise CatalogValidationError("commands muss eine nichtleere Liste sein")
    commands: list[Mapping[str, object]] = []
    ids: set[str] = set()
    paths: set[tuple[str, ...]] = set()
    for index, command in enumerate(raw_commands):
        context = f"commands[{index}]"
        if not isinstance(command, Mapping):
            raise CatalogValidationError(f"{context} muss eine Tabelle sein")
        _exact_fields(command, COMMAND_FIELDS, context)
        command_id = _validate_id(command.get("id"), context)
        if command_id in ids:
            raise CatalogValidationError("commands enthält doppelte IDs")
        raw_path = command.get("path")
        if not isinstance(raw_path, list) or not raw_path or any(
            not isinstance(segment, str) or re.fullmatch(r"[a-z][a-z0-9-]*", segment) is None
            for segment in raw_path
        ):
            raise CatalogValidationError(f"{context}.path ist ungültig")
        path = tuple(raw_path)
        if path in paths:
            raise CatalogValidationError("commands enthält doppelte Pfade")
        description = _nonempty_text(command.get("description"), f"{context}.description")
        if re.search(r"[\x00\r\n\x1b]", description):
            raise CatalogValidationError(f"{context}.description enthält Steuerzeichen")
        capability = _nonempty_text(command.get("capability"), f"{context}.capability")
        if capability not in COMMAND_CAPABILITIES:
            raise CatalogValidationError(f"{context}.capability ist unbekannt")
        effect = _nonempty_text(command.get("effect"), f"{context}.effect")
        if effect not in COMMAND_EFFECTS:
            raise CatalogValidationError(f"{context}.effect ist unbekannt")
        for field in ("orchestrates", "interactive"):
            if type(command.get(field)) is not bool:
                raise CatalogValidationError(f"{context}.{field} muss Boolean sein")
        ids.add(command_id)
        paths.add(path)
        commands.append(command)
    return tuple(commands)


def _validate_discovery(catalog: Mapping[str, object]) -> Mapping[str, object]:
    _exact_fields(catalog, DISCOVERY_TOP_LEVEL_FIELDS, "discovery_signals Top-Level")
    if type(catalog.get("schema_version")) is not int or catalog["schema_version"] != 1:
        raise CatalogValidationError("discovery_signals schema_version muss Integer 1 sein")

    limits = catalog.get("limits")
    if not isinstance(limits, Mapping):
        raise CatalogValidationError("discovery_signals limits muss eine Tabelle sein")
    _exact_fields(limits, DISCOVERY_LIMIT_FIELDS, "discovery_signals limits")
    for field, value in limits.items():
        _positive_integer(value, f"discovery_signals limits.{field}")

    confidence = catalog.get("confidence")
    if not isinstance(confidence, Mapping):
        raise CatalogValidationError("discovery_signals confidence muss eine Tabelle sein")
    _exact_fields(confidence, DISCOVERY_CONFIDENCE_FIELDS, "discovery_signals confidence")
    for field in (
        "high_minimum_score",
        "high_minimum_families",
        "high_minimum_independent_sources",
        "uncertain_minimum_score",
    ):
        _positive_integer(confidence.get(field), f"discovery_signals confidence.{field}")
    if type(confidence.get("high_requires_runtime")) is not bool:
        raise CatalogValidationError(
            "discovery_signals confidence.high_requires_runtime muss Boolean sein"
        )
    if confidence["uncertain_minimum_score"] >= confidence["high_minimum_score"]:
        raise CatalogValidationError(
            "discovery_signals uncertain_minimum_score muss kleiner als high_minimum_score sein"
        )

    candidate_classes = catalog.get("candidate_classes")
    if not isinstance(candidate_classes, Mapping):
        raise CatalogValidationError("discovery_signals candidate_classes muss eine Tabelle sein")
    _exact_fields(
        candidate_classes,
        DISCOVERY_CANDIDATE_CLASS_IDS,
        "discovery_signals candidate_classes",
    )
    expected_classes = DISCOVERY_CANDIDATE_CLASSES
    for class_id, expected_class in expected_classes.items():
        entry = candidate_classes[class_id]
        if not isinstance(entry, Mapping):
            raise CatalogValidationError(f"discovery_signals candidate_classes.{class_id} muss eine Tabelle sein")
        _exact_fields(entry, DISCOVERY_CANDIDATE_FIELDS, f"candidate_classes.{class_id}")
        if entry.get("class") != expected_class:
            raise CatalogValidationError(f"candidate_classes.{class_id}.class ist ungültig")
        _nonempty_text(entry.get("label"), f"candidate_classes.{class_id}.label")

    families = catalog.get("evidence_families")
    if not isinstance(families, Mapping):
        raise CatalogValidationError("discovery_signals evidence_families muss eine Tabelle sein")
    _exact_fields(families, DISCOVERY_FAMILIES, "discovery_signals evidence_families")
    for family_id, family in families.items():
        if not isinstance(family, Mapping):
            raise CatalogValidationError(f"evidence_families.{family_id} muss eine Tabelle sein")
        _exact_fields(family, DISCOVERY_FAMILY_FIELDS, f"evidence_families.{family_id}")
        if family.get("default_strength") not in DISCOVERY_STRENGTHS:
            raise CatalogValidationError(f"evidence_families.{family_id}.default_strength ist ungültig")
        _positive_integer(family.get("weight"), f"evidence_families.{family_id}.weight")

    signals = catalog.get("signals")
    if not isinstance(signals, list) or not signals:
        raise CatalogValidationError("discovery_signals signals muss eine nichtleere Liste sein")
    signal_ids: set[str] = set()
    for index, signal in enumerate(signals):
        context = f"discovery_signals signals[{index}]"
        if not isinstance(signal, Mapping):
            raise CatalogValidationError(f"{context} muss eine Tabelle sein")
        _exact_fields(signal, DISCOVERY_SIGNAL_FIELDS, context)
        signal_id = _validate_id(signal.get("id"), context)
        if signal_id in signal_ids:
            raise CatalogValidationError("discovery_signals enthält doppelte IDs")
        signal_ids.add(signal_id)
        if signal.get("family") not in DISCOVERY_FAMILIES:
            raise CatalogValidationError(f"{context}.family ist unbekannt")
        source_kinds = _nonempty_id_list(signal.get("source_kinds"), f"{context}.source_kinds")
        unknown_sources = set(source_kinds) - DISCOVERY_SOURCE_KINDS
        if unknown_sources:
            raise CatalogValidationError(f"{context}.source_kinds ist unbekannt: {sorted(unknown_sources)}")
        keys = _nonempty_id_list(signal.get("keys"), f"{context}.keys")
        minimum_matches = _positive_integer(signal.get("minimum_matches"), f"{context}.minimum_matches")
        if minimum_matches > len(keys):
            raise CatalogValidationError(f"{context}.minimum_matches überschreitet keys")
        if signal.get("strength") not in DISCOVERY_STRENGTHS:
            raise CatalogValidationError(f"{context}.strength ist ungültig")

    return catalog


def _work_item_classification_ids(catalog: Mapping[str, object]) -> frozenset[str]:
    """Liefert die stabilen kanonischen IDs `dimension.value` der Classification-SSOT."""
    classifications = catalog.get("classifications")
    if not isinstance(classifications, Mapping):
        raise CatalogValidationError("work_items classifications muss eine Tabelle sein")
    ids: set[str] = set()
    for dimension_id, values in classifications.items():
        if not isinstance(values, Mapping):
            raise CatalogValidationError(
                f"classifications.{dimension_id} muss eine Tabelle sein"
            )
        for value_id in values:
            ids.add(f"{dimension_id}.{value_id}")
    return frozenset(ids)


def _validate_work_item_classifications(catalog: Mapping[str, object]) -> Mapping[str, object]:
    _exact_fields(
        catalog, WORK_ITEM_CLASSIFICATIONS_TOP_LEVEL_FIELDS,
        "work_items classifications Top-Level",
    )
    if type(catalog.get("schema_version")) is not int or catalog["schema_version"] != 1:
        raise CatalogValidationError("work_items classifications schema_version muss Integer 1 sein")

    dimensions = catalog.get("dimensions")
    if not isinstance(dimensions, Mapping) or not dimensions:
        raise CatalogValidationError("work_items dimensions muss eine nichtleere Tabelle sein")
    for dimension_id, dimension in dimensions.items():
        _validate_id(dimension_id, "work_items dimensions")
        if not isinstance(dimension, Mapping):
            raise CatalogValidationError(f"dimensions.{dimension_id} muss eine Tabelle sein")
        _exact_fields(dimension, WORK_ITEM_DIMENSION_FIELDS, f"dimensions.{dimension_id}")
        _nonempty_text(dimension.get("label"), f"dimensions.{dimension_id}.label")
        if dimension.get("cardinality") not in WORK_ITEM_CARDINALITIES:
            raise CatalogValidationError(f"dimensions.{dimension_id}.cardinality ist unbekannt")
        _nonempty_text(dimension.get("description"), f"dimensions.{dimension_id}.description")

    classifications = catalog.get("classifications")
    if not isinstance(classifications, Mapping) or not classifications:
        raise CatalogValidationError("work_items classifications muss eine nichtleere Tabelle sein")
    known_dimensions = set(dimensions)
    for dimension_id, values in classifications.items():
        _validate_id(dimension_id, "work_items classifications")
        if dimension_id not in known_dimensions:
            raise CatalogValidationError(
                f"classifications.{dimension_id} referenziert eine unbekannte Dimension"
            )
        if not isinstance(values, Mapping) or not values:
            raise CatalogValidationError(
                f"classifications.{dimension_id} muss eine nichtleere Tabelle sein"
            )
        for value_id, value in values.items():
            _validate_id(value_id, f"classifications.{dimension_id}")
            if not isinstance(value, Mapping):
                raise CatalogValidationError(
                    f"classifications.{dimension_id}.{value_id} muss eine Tabelle sein"
                )
            _exact_fields(
                value, WORK_ITEM_CLASSIFICATION_FIELDS,
                f"classifications.{dimension_id}.{value_id}",
            )
            _nonempty_text(value.get("label"), f"classifications.{dimension_id}.{value_id}.label")
            _nonempty_text(
                value.get("description"),
                f"classifications.{dimension_id}.{value_id}.description",
            )
    for dimension_id in known_dimensions:
        if dimension_id not in classifications:
            raise CatalogValidationError(f"dimension {dimension_id} besitzt keine Klassifikationswerte")
    return catalog


def _validate_work_item_projections(
    catalog: Mapping[str, object], classifications: Mapping[str, object]
) -> Mapping[str, object]:
    _exact_fields(
        catalog, WORK_ITEM_PROJECTIONS_TOP_LEVEL_FIELDS,
        "work_items github_labels Top-Level",
    )
    if type(catalog.get("schema_version")) is not int or catalog["schema_version"] != 1:
        raise CatalogValidationError("work_items github_labels schema_version muss Integer 1 sein")

    known_ids = _work_item_classification_ids(classifications)
    projections = catalog.get("projections")
    if not isinstance(projections, Mapping) or not projections:
        raise CatalogValidationError("work_items projections muss eine nichtleere Tabelle sein")
    seen_classifications: set[str] = set()
    occupied_names: set[str] = set()
    for projection_id, projection in projections.items():
        _validate_id(projection_id, "work_items projections")
        if not isinstance(projection, Mapping):
            raise CatalogValidationError(f"projections.{projection_id} muss eine Tabelle sein")
        _exact_fields(projection, WORK_ITEM_PROJECTION_FIELDS, f"projections.{projection_id}")
        classification = projection.get("classification")
        if not isinstance(classification, str) or classification not in known_ids:
            raise CatalogValidationError(
                f"projections.{projection_id}.classification ist eine unbekannte Klassifikations-ID"
            )
        if classification in seen_classifications:
            raise CatalogValidationError(
                f"projections.{projection_id} dupliziert eine Klassifikations-ID"
            )
        seen_classifications.add(classification)
        name = _nonempty_text(projection.get("name"), f"projections.{projection_id}.name")
        if name in occupied_names:
            raise CatalogValidationError(
                f"projections.{projection_id} kollidiert mit einem Labelnamen: {name}"
            )
        occupied_names.add(name)
        _nonempty_text(projection.get("description"), f"projections.{projection_id}.description")
        color = projection.get("color")
        if not isinstance(color, str) or WORK_ITEM_COLOR_RE.fullmatch(color) is None:
            raise CatalogValidationError(f"projections.{projection_id}.color ist ungültig")
        aliases = _alias_list(projection.get("aliases"), f"projections.{projection_id}.aliases")
        for alias in aliases:
            if alias in occupied_names:
                raise CatalogValidationError(
                    f"projections.{projection_id}.aliases kollidiert mit einem Namen: {alias}"
                )
            occupied_names.add(alias)

    title_markers = catalog.get("title_markers")
    if not isinstance(title_markers, Mapping):
        raise CatalogValidationError("work_items title_markers muss eine Tabelle sein")
    seen_markers: set[str] = set()
    for marker_id, marker in title_markers.items():
        _validate_id(marker_id, "work_items title_markers")
        if not isinstance(marker, Mapping):
            raise CatalogValidationError(f"title_markers.{marker_id} muss eine Tabelle sein")
        _exact_fields(marker, WORK_ITEM_TITLE_MARKER_FIELDS, f"title_markers.{marker_id}")
        classification = marker.get("classification")
        if not isinstance(classification, str) or classification not in known_ids:
            raise CatalogValidationError(
                f"title_markers.{marker_id}.classification ist eine unbekannte Klassifikations-ID"
            )
        marker_text = _nonempty_text(marker.get("marker"), f"title_markers.{marker_id}.marker")
        if WORK_ITEM_MARKER_RE.fullmatch(marker_text) is None:
            raise CatalogValidationError(
                f"title_markers.{marker_id}.marker ist kein erkennbarer Bracket-Marker"
            )
        if marker_text in seen_markers:
            raise CatalogValidationError(f"title_markers.{marker_id} kollidiert mit einem Marker")
        seen_markers.add(marker_text)
    return catalog



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


def _validate_tool_routing(
    manifest: Mapping[str, object], tools: Mapping[str, Mapping[str, object]]
) -> None:
    modules = manifest.get("modules")
    tool_routing = modules.get("tool_routing") if isinstance(modules, Mapping) else None
    if not isinstance(tool_routing, Mapping):
        raise CatalogValidationError("Manifest benötigt das Tool-Routing-Modul")
    actual = tool_routing.get("triggers")
    expected = {
        "tool_selection",
        *(trigger for tool in tools.values() for trigger in tool["required_on"]),
    }
    if not isinstance(actual, list) or set(actual) != expected:
        raise CatalogValidationError(
            "Tool-Routing-Trigger müssen tool_selection und alle required_on-Trigger abdecken"
        )


def _validate_templates(manifest: Mapping[str, object], root: Path) -> tuple[Path, ...]:
    raw = manifest.get("templates")
    if not isinstance(raw, str) or raw != "templates/manifest.toml":
        raise CatalogValidationError("Manifest templates muss der kanonische Pfad 'templates/manifest.toml' sein")
    index_path = _index_file(root, raw, "Templates-Index")
    data = _load_toml(index_path, "Templates-Index")
    _exact_fields(data, frozenset({"schema_version", "templates"}), "Templates-Index Top-Level")
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise CatalogValidationError("Templates-Index schema_version muss Integer 1 sein")
    entries = data.get("templates")
    if not isinstance(entries, Mapping) or not entries:
        raise CatalogValidationError("templates muss eine nichtleere Tabelle sein")
    templates_dir = index_path.parent
    seen_paths: set[str] = set()
    resolved: list[Path] = []
    for template_id, entry in entries.items():
        _validate_id(template_id, "templates")
        if not isinstance(entry, Mapping):
            raise CatalogValidationError(f"templates.{template_id} muss eine Tabelle sein")
        _exact_fields(entry, TEMPLATE_FIELDS, f"templates.{template_id}")
        if entry.get("category") not in TEMPLATE_CATEGORIES:
            raise CatalogValidationError(f"templates.{template_id}.category ist unbekannt")
        if entry.get("format") not in TEMPLATE_FORMATS:
            raise CatalogValidationError(f"templates.{template_id}.format ist ungültig")
        raw_path = entry.get("path")
        if not isinstance(raw_path, str) or not raw_path or Path(raw_path).is_absolute() or "\\" in raw_path:
            raise CatalogValidationError(f"templates.{template_id}.path ist ungültig")
        if any(part in {"", ".", "..", "~"} for part in raw_path.split("/")):
            raise CatalogValidationError(f"templates.{template_id}.path enthält Traversal")
        if not raw_path.endswith(".md"):
            raise CatalogValidationError(f"templates.{template_id}.path hat ein ungültiges Format")
        if raw_path in seen_paths:
            raise CatalogValidationError("templates enthält doppelte Pfade")
        seen_paths.add(raw_path)
        candidate = _regular_file(templates_dir, _index_candidate(templates_dir, raw_path, f"templates.{template_id}"), f"templates.{template_id}")
        resolved.append(candidate)
    for candidate in sorted(templates_dir.rglob("*")):
        if candidate.is_symlink():
            raise CatalogValidationError("templates enthält Symlinks")
        if candidate.is_file() and candidate.name.endswith(".md"):
            relative_path = candidate.relative_to(templates_dir).as_posix()
            if relative_path not in seen_paths:
                raise CatalogValidationError("templates enthält nicht registrierte Dateien")
    return tuple(resolved)


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


def _alias_list(value: object, context: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise CatalogValidationError(f"{context} muss eine Liste sein")
    result = tuple(value)
    for alias in result:
        if not isinstance(alias, str) or not alias.strip() or re.search(r"[\x00\r\n\x1b]", alias):
            raise CatalogValidationError(f"{context} enthält einen ungültigen Alias")
    if len(result) != len(set(result)):
        raise CatalogValidationError(f"{context} enthält doppelte Aliase")
    return result


def _positive_integer(value: object, context: str) -> int:
    if type(value) is not int or value <= 0:
        raise CatalogValidationError(f"{context} muss ein positiver Integer sein")
    return value
