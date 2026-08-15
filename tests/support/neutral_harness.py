#!/usr/bin/env python3
"""Deterministischer produktneutraler Testharness für Governance und Enforcement."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tomllib
from typing import Mapping, Sequence


class NeutralHarnessError(RuntimeError):
    """Fail-closed Fehler des synthetischen Harnesses."""


@dataclass(frozen=True)
class SessionResult:
    chain: tuple[str, ...]
    governance_loaded: bool
    manifest_loaded: bool
    local_rules_loaded: bool
    synthetic_rule_effect: bool
    marker: str | None
    used_legacy_source: bool
    module_paths: tuple[str, ...]
    role_paths: tuple[str, ...]
    read_paths: tuple[Path, ...]
    decision: str | None
    provider_reached: bool
    continued: bool
    audit_written: bool


class NeutralHarness:
    """Lädt nur die explizite absolute Instruktions-, Konfigurations- und Providerschnittstelle."""

    _DECISIONS = {"allow", "deny", "require_approval", "error", "unknown"}
    _REQUIRED_ENVELOPE = {
        "action_id",
        "evidence_id",
        "action",
        "resource",
        "effect",
        "semantic_authorization",
        "approval_context",
        "risk_context",
    }

    def __init__(
        self,
        *,
        global_instruction_path: Path,
        config_path: Path,
        enforcement_command: Path,
        provider_environment: Mapping[str, str] | None = None,
    ):
        self.global_instruction = self._absolute_file(
            Path(global_instruction_path), "globale Instruktion"
        )
        self.config_path = self._absolute_file(Path(config_path), "Harnesskonfiguration")
        self.enforcement_command = self._absolute_file(
            Path(enforcement_command), "Enforcementcommand"
        )
        if not os.access(self.enforcement_command, os.X_OK):
            raise NeutralHarnessError("Enforcementcommand ist nicht ausführbar")
        self.provider_environment = dict(provider_environment or {})
        if any(not isinstance(key, str) or not isinstance(value, str) for key, value in self.provider_environment.items()):
            raise NeutralHarnessError("Providerumgebung muss ausschließlich Strings enthalten")

        try:
            config = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise NeutralHarnessError("Harnesskonfiguration ist nicht lesbar") from error
        if not isinstance(config, dict):
            raise NeutralHarnessError("Harnesskonfiguration muss ein Objekt sein")
        if config.get("global_instruction_path") != str(self.global_instruction):
            raise NeutralHarnessError("Globale Instruktionsbindung ist widersprüchlich")
        self.root = self._absolute_directory_value(config.get("governance_root"), "Governance-Root")
        self.evidence = self._absolute_output_value(
            config.get("evidence_log_path"), "Evidence-Log"
        )
        self.manifest_dir = self.root / "agent-governance"
        self.manifest = self._absolute_file(
            self.manifest_dir / "manifest.toml", "Governance-Manifest"
        )

    def new_session(
        self,
        *,
        task: str,
        triggers: Sequence[str],
        action_envelope: Mapping[str, object] | None = None,
    ) -> SessionResult:
        if not isinstance(task, str) or not task.strip():
            raise NeutralHarnessError("Runtimeauftrag fehlt")
        if not triggers:
            raise NeutralHarnessError("Mindestens ein geschlossener Trigger ist erforderlich")

        read_paths: list[Path] = [self.global_instruction]
        entrypoint = self._absolute_file(self.root / "GOVERNANCE.md", "Governance-Einstieg")
        if self.global_instruction.read_bytes() != entrypoint.read_bytes():
            raise NeutralHarnessError("Globale Instruktion ist nicht byte-identisch zum Einstieg")

        read_paths.append(self.manifest)
        try:
            manifest = tomllib.loads(self.manifest.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as error:
            raise NeutralHarnessError("Governance-Manifest ist ungültig") from error

        chain = ["bootstrap", "manifest"]
        local_path = self._local_rules_path(manifest)
        local_rules_loaded = local_path.is_file() and not local_path.is_symlink()
        marker = None
        if local_rules_loaded:
            read_paths.append(local_path)
            local_text = local_path.read_text(encoding="utf-8")
            match = re.search(r"`(SYNTHETIC_[A-Z0-9_]+)`", local_text)
            marker = match.group(1) if match else None
            chain.append("local_rules")

        module_paths, role_paths, routed_paths = self._resolve_routes(manifest, triggers)
        read_paths.extend(routed_paths)
        chain.append("modules")

        decision = None
        provider_reached = False
        continued = False
        audit_written = False
        if action_envelope is not None:
            if "external_effect" not in triggers:
                raise NeutralHarnessError("Action Envelope ohne external_effect-Trigger")
            decision, provider_reached = self._evaluate(action_envelope)
            continued = decision == "allow"
            try:
                self._append_audit(action_envelope, decision, provider_reached)
                audit_written = True
            except (OSError, TypeError, ValueError):
                decision = "error"
                continued = False
                audit_written = False

        used_legacy = any(
            part in {"core", "adapters", "profile"}
            for path in read_paths
            for part in path.parts
        )
        return SessionResult(
            chain=tuple(chain),
            governance_loaded=True,
            manifest_loaded=True,
            local_rules_loaded=local_rules_loaded,
            synthetic_rule_effect=marker is not None,
            marker=marker,
            used_legacy_source=used_legacy,
            module_paths=module_paths,
            role_paths=role_paths,
            read_paths=tuple(read_paths),
            decision=decision,
            provider_reached=provider_reached,
            continued=continued,
            audit_written=audit_written,
        )

    def _local_rules_path(self, manifest: Mapping[str, object]) -> Path:
        value = manifest.get("local_rules")
        if not isinstance(value, str) or not value or Path(value).is_absolute():
            raise NeutralHarnessError("local_rules ist kein relativer Manifestpfad")
        candidate = Path(os.path.normpath(self.manifest_dir / value))
        try:
            candidate.relative_to(self.manifest_dir)
        except ValueError as error:
            raise NeutralHarnessError("local_rules verlässt das Manifestverzeichnis") from error
        self._reject_existing_symlink_chain(candidate)
        return candidate

    def _resolve_routes(
        self, manifest: Mapping[str, object], triggers: Sequence[str]
    ) -> tuple[tuple[str, ...], tuple[str, ...], list[Path]]:
        routing = manifest.get("routing")
        modules = manifest.get("modules")
        roles = manifest.get("roles")
        if not isinstance(routing, dict) or not isinstance(modules, dict) or not isinstance(roles, dict):
            raise NeutralHarnessError("Manifestindex ist unvollständig")
        known = routing.get("known_triggers")
        if not isinstance(known, list) or any(trigger not in known for trigger in triggers):
            raise NeutralHarnessError("Unbekannter oder mehrdeutiger Trigger")

        selected: set[str] = set()
        selected_roles: list[str] = []
        for name, data in modules.items():
            if not isinstance(data, dict):
                raise NeutralHarnessError("Modulindex ist ungültig")
            module_triggers = data.get("triggers")
            if isinstance(module_triggers, list) and any(trigger in module_triggers for trigger in triggers):
                selected.add(name)
        for name, data in roles.items():
            if not isinstance(data, dict):
                raise NeutralHarnessError("Rollenindex ist ungültig")
            role_triggers = data.get("triggers")
            if isinstance(role_triggers, list) and any(trigger in role_triggers for trigger in triggers):
                selected_roles.append(name)
                role_modules = data.get("modules")
                if not isinstance(role_modules, list):
                    raise NeutralHarnessError("Rollenmodule sind ungültig")
                selected.update(role_modules)

        ordered: list[str] = []
        visiting: set[str] = set()

        def visit(name: str) -> None:
            if name in ordered:
                return
            if name in visiting or name not in modules:
                raise NeutralHarnessError("Modulabhängigkeiten sind zyklisch oder unbekannt")
            visiting.add(name)
            dependencies = modules[name].get("dependencies")
            if not isinstance(dependencies, list):
                raise NeutralHarnessError("Modulabhängigkeiten sind ungültig")
            for dependency in dependencies:
                if not isinstance(dependency, str):
                    raise NeutralHarnessError("Modulabhängigkeit ist ungültig")
                visit(dependency)
            visiting.remove(name)
            ordered.append(name)

        for name in sorted(selected):
            visit(name)

        module_paths: list[str] = []
        role_paths: list[str] = []
        read_paths: list[Path] = []
        for name in ordered:
            relative = self._relative_index_path(modules[name].get("path"), "Modul")
            path = self._absolute_file(self.manifest_dir / relative, "Governance-Modul")
            module_paths.append(relative.as_posix())
            read_paths.append(path)
        for name in sorted(selected_roles):
            relative = self._relative_index_path(roles[name].get("path"), "Rolle")
            path = self._absolute_file(self.manifest_dir / relative, "Governance-Rolle")
            role_paths.append(relative.as_posix())
            read_paths.append(path)
        return tuple(module_paths), tuple(role_paths), read_paths

    def _evaluate(self, envelope: Mapping[str, object]) -> tuple[str, bool]:
        if not isinstance(envelope, Mapping) or set(envelope) != self._REQUIRED_ENVELOPE:
            return "error", False
        semantic = envelope.get("semantic_authorization")
        if semantic == "deny":
            return "deny", False
        if semantic != "allow":
            return "error", False
        approval_context = envelope.get("approval_context")
        risk_context = envelope.get("risk_context")
        if (
            not isinstance(risk_context, Mapping)
            or set(risk_context) != {"requires_approval"}
            or not isinstance(risk_context.get("requires_approval"), bool)
        ):
            return "error", False
        if not isinstance(approval_context, Mapping):
            return "error", False
        approval_valid = approval_context.get("valid")
        if approval_valid is False:
            if set(approval_context) != {"valid"}:
                return "error", False
        elif approval_valid is True:
            approval_id = approval_context.get("approval_id")
            if (
                set(approval_context) != {"valid", "approval_id"}
                or not isinstance(approval_id, str)
                or not 1 <= len(approval_id) <= 256
            ):
                return "error", False
        else:
            return "error", False
        process_environment = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "LANG": "C.UTF-8",
            **self.provider_environment,
        }
        try:
            process = subprocess.run(
                [str(self.enforcement_command)],
                input=json.dumps(dict(envelope)),
                text=True,
                capture_output=True,
                cwd=self.enforcement_command.parent,
                env=process_environment,
                timeout=10,
                check=False,
            )
            if process.returncode != 0:
                return "error", True
            output = json.loads(process.stdout)
            decision = output.get("decision") if isinstance(output, dict) else None
            return (decision if decision in self._DECISIONS else "unknown"), True
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, TypeError, ValueError):
            return "error", True

    def _append_audit(
        self, envelope: Mapping[str, object], decision: str, provider_reached: bool
    ) -> None:
        action_id = envelope.get("action_id")
        evidence_id = envelope.get("evidence_id")
        if not isinstance(action_id, str) or not isinstance(evidence_id, str):
            raise ValueError("Audit-IDs fehlen")
        record = {
            "action_id": action_id,
            "decision": decision,
            "evidence_id": evidence_id,
            "provider_reached": provider_reached,
        }
        flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(self.evidence, flags, 0o600)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "a", encoding="utf-8", closefd=False) as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            os.close(descriptor)

    @staticmethod
    def _relative_index_path(value: object, kind: str) -> Path:
        if not isinstance(value, str) or not value or Path(value).is_absolute():
            raise NeutralHarnessError(f"{kind}pfad ist ungültig")
        relative = Path(os.path.normpath(value))
        if relative.parts and relative.parts[0] == "..":
            raise NeutralHarnessError(f"{kind}pfad verlässt das Manifestverzeichnis")
        return relative

    @staticmethod
    def _absolute_file(path: Path, kind: str) -> Path:
        if not path.is_absolute() or path.is_symlink() or not path.is_file():
            raise NeutralHarnessError(f"{kind} muss eine absolute reguläre Datei sein")
        NeutralHarness._reject_existing_symlink_chain(path)
        return path

    @staticmethod
    def _absolute_directory_value(value: object, kind: str) -> Path:
        if not isinstance(value, str):
            raise NeutralHarnessError(f"{kind} fehlt")
        path = Path(value)
        if not path.is_absolute() or path.is_symlink() or not path.is_dir():
            raise NeutralHarnessError(f"{kind} muss ein absolutes Verzeichnis sein")
        NeutralHarness._reject_existing_symlink_chain(path)
        return path

    @staticmethod
    def _absolute_output_value(value: object, kind: str) -> Path:
        if not isinstance(value, str):
            raise NeutralHarnessError(f"{kind} fehlt")
        path = Path(value)
        if not path.is_absolute() or path.is_symlink():
            raise NeutralHarnessError(f"{kind} muss ein absoluter linkfreier Pfad sein")
        if not path.parent.is_dir() or path.parent.is_symlink():
            raise NeutralHarnessError(f"{kind}-Parent ist ungültig")
        NeutralHarness._reject_existing_symlink_chain(path.parent)
        if path.exists() and not stat.S_ISREG(path.stat().st_mode):
            raise NeutralHarnessError(f"{kind} ist keine reguläre Datei")
        return path

    @staticmethod
    def _reject_existing_symlink_chain(path: Path) -> None:
        current = path
        while True:
            if current.is_symlink():
                raise NeutralHarnessError("Symlink in explizitem Harnesspfad")
            if current.parent == current:
                return
            current = current.parent
