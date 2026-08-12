#!/usr/bin/env python3
"""Deterministische Testreferenz für den generischen Bootstrapvertrag.

Dieses Modul ist kein Endnutzerinstaller. Es modelliert die Sicherheits- und
Transaktionsinvarianten des ausführbaren Promptvertrags in synthetischen Testwurzeln.
"""

from __future__ import annotations

from dataclasses import dataclass
import filecmp
import json
import os
from pathlib import Path
import shutil
import tomllib
from typing import Callable, Mapping
import uuid


class BootstrapError(RuntimeError):
    """Fail-closed Bootstrapfehler."""


ProviderBuilder = Callable[[Path, Path], Path]
VerificationHook = Callable[["BootstrapRequest"], bool]


@dataclass(frozen=True)
class BootstrapRequest:
    release_root: Path
    allowed_root: Path
    install_dir: Path
    global_instruction_path: Path
    config_path: Path
    evidence_log_path: Path
    harness_type: str
    root_candidates: Mapping[str, str]
    provider_builder: ProviderBuilder
    legacy_private_rules_path: Path | None = None
    verification_hook: VerificationHook | None = None


@dataclass(frozen=True)
class BootstrapResult:
    version: str
    state: str
    install_root: str
    harness_type: str
    enforcement_provider: str
    checks: Mapping[str, bool]
    mutation_count: int
    local_rules_preserved: bool
    backup_verified: bool


class BootstrapTransaction:
    """Sichere FRESH-/CURRENT-/LEGACY-Referenztransaktion."""

    def __init__(self, request: BootstrapRequest):
        self.request = request
        self.release = Path(request.release_root)
        self.allowed = Path(request.allowed_root)
        self.install = Path(request.install_dir)
        self.global_instruction = Path(request.global_instruction_path)
        self.config = Path(request.config_path)
        self.evidence = Path(request.evidence_log_path)
        self._parent_identity: dict[Path, tuple[int, int]] = {}
        self._backup: Path | None = None
        self._stage: Path | None = None
        self._retired_install: Path | None = None
        self._backup_targets_active: tuple[Path, ...] = ()

    def run(self) -> BootstrapResult:
        self._preflight()
        state = self._classify_state()
        version = self._release_version()
        if state == "CURRENT":
            return self._result(version, state, 0, False, True)
        if state == "CURRENT_REPAIR":
            return self._repair_current(version)

        backup_verified = False
        local_rules_preserved = False
        mutation_count = 0
        try:
            self._backup = self.allowed / ".agent-governance-backups" / uuid.uuid4().hex
            self._stage = self.allowed / (".agent-governance-stage-" + uuid.uuid4().hex)
            self._backup_targets()
            backup_verified = self._verify_backup()
            if not backup_verified:
                raise BootstrapError("Backup konnte nicht byteweise verifiziert werden")

            stage_install, staged_global, staged_config, staged_evidence = self._prepare_stage(
                state, version
            )
            local_rules_preserved = state == "LEGACY"
            self._recheck_parent_identities()
            self._activate(stage_install, staged_global, staged_config, staged_evidence)
            mutation_count = 4
            checks = self._verify_active(version, local_rules_preserved)
            if not all(checks.values()):
                raise BootstrapError("Aktiver Bootstrapzustand ist nicht vollständig verifiziert")
            if self.request.verification_hook is not None:
                if not self.request.verification_hook(self.request):
                    raise BootstrapError("Frische Runtime-Verifikation fehlgeschlagen")
            self._discard_retired()
            self._discard_stage()
            return BootstrapResult(
                version=version,
                state=state,
                install_root=str(self.install / "bundle"),
                harness_type=self.request.harness_type,
                enforcement_provider="microsoft-agent-governance-toolkit",
                checks=checks,
                mutation_count=mutation_count,
                local_rules_preserved=local_rules_preserved,
                backup_verified=backup_verified,
            )
        except BootstrapError:
            self._rollback()
            raise
        except Exception as error:
            self._rollback()
            raise BootstrapError(f"Bootstraptransaktion fehlgeschlagen: {type(error).__name__}") from error

    def _result(
        self,
        version: str,
        state: str,
        mutation_count: int,
        local_rules_preserved: bool,
        backup_verified: bool,
    ) -> BootstrapResult:
        return BootstrapResult(
            version=version,
            state=state,
            install_root=str(self.install / "bundle"),
            harness_type=self.request.harness_type,
            enforcement_provider="microsoft-agent-governance-toolkit",
            checks=self._verify_active(version, local_rules_preserved),
            mutation_count=mutation_count,
            local_rules_preserved=local_rules_preserved,
            backup_verified=backup_verified,
        )

    def _preflight(self) -> None:
        if not self.allowed.is_absolute() or str(self.allowed) in {"", ".", "/"}:
            raise BootstrapError("Erlaubte Installationswurzel muss absolut und begrenzt sein")
        if not self.allowed.is_dir() or self.allowed.is_symlink():
            raise BootstrapError("Erlaubte Installationswurzel ist kein reales Verzeichnis")
        allowed_real = self.allowed.resolve(strict=True)
        if allowed_real != self.allowed:
            raise BootstrapError("Erlaubte Installationswurzel darf keinen Symlink enthalten")

        if not self.release.is_absolute() or not self.release.is_dir():
            raise BootstrapError("Releasewurzel ist ungültig")
        for required in (
            self.release / "VERSION",
            self.release / "bundle" / "GOVERNANCE.md",
            self.release / "bundle" / "agent-governance" / "manifest.toml",
            self.release
            / "integrations"
            / "microsoft-agent-governance-toolkit"
            / "upstream.lock.toml",
        ):
            if not required.is_file() or required.is_symlink():
                raise BootstrapError("Releaseartefakt ist unvollständig")

        for target in (self.install, self.global_instruction, self.config, self.evidence):
            self._validate_target(target, allowed_real)
            parent = target.parent
            if not parent.is_dir() or parent.is_symlink():
                raise BootstrapError("Zielparent ist ungültig")
            stat = parent.stat()
            self._parent_identity[parent] = (stat.st_dev, stat.st_ino)
        self._reject_tree_symlinks(self.install)
        if self.install.exists() and not self.install.is_dir():
            raise BootstrapError("Bestehende Installation ist kein Verzeichnis")
        for target in (self.global_instruction, self.config, self.evidence):
            if target.exists() and not target.is_file():
                raise BootstrapError("Bestehendes Harnessziel ist keine reguläre Datei")
        self._validate_root_candidates()

    def _validate_target(self, target: Path, allowed_real: Path) -> None:
        if not target.is_absolute():
            raise BootstrapError("Bootstrapziel muss absolut sein")
        try:
            if Path(os.path.commonpath((str(allowed_real), str(target)))) != allowed_real:
                raise BootstrapError("Bootstrapziel liegt außerhalb der erlaubten Wurzel")
        except ValueError as error:
            raise BootstrapError("Bootstrapziel liegt auf einer fremden Wurzel") from error

        relative = target.relative_to(self.allowed)
        cursor = self.allowed
        for part in relative.parts:
            cursor = cursor / part
            if cursor.is_symlink():
                raise BootstrapError("Symlink im Bootstrapziel ist unzulässig")
            if not cursor.exists():
                break

    def _reject_tree_symlinks(self, root: Path) -> None:
        if not root.exists():
            return
        for path in root.rglob("*"):
            if path.is_symlink():
                raise BootstrapError("Symlink im bestehenden Installationszustand")

    def _validate_root_candidates(self) -> None:
        resolved: set[Path] = set()
        for value in self.request.root_candidates.values():
            if not value or value == ".":
                raise BootstrapError("Rootkandidat ist leer oder relativ")
            candidate = Path(value)
            if not candidate.is_absolute():
                raise BootstrapError("Rootkandidat muss absolut sein")
            try:
                physical = candidate.resolve(strict=True)
            except OSError as error:
                raise BootstrapError("Rootkandidat ist nicht auflösbar") from error
            manifest = physical / "agent-governance" / "manifest.toml"
            if not manifest.is_file() or manifest.is_symlink():
                raise BootstrapError("Rootkandidat besitzt kein gültiges Manifest")
            resolved.add(physical)
        if len(resolved) > 1:
            raise BootstrapError("Widersprüchliche gültige Rootkandidaten")

    def _classify_state(self) -> str:
        if not self.install.exists():
            return "FRESH"
        manifest = self.install / "bundle" / "agent-governance" / "manifest.toml"
        legacy = any((self.install / name).exists() for name in ("core", "adapters", "profile"))
        if legacy:
            return "LEGACY"
        if manifest.is_file() and self._installation_is_current():
            return "CURRENT" if self._bindings_current() else "CURRENT_REPAIR"
        raise BootstrapError("Installationszustand ist unbekannt oder unvollständig")

    def _installation_is_current(self) -> bool:
        try:
            if (self.install / "VERSION").read_text(encoding="utf-8").strip() != self._release_version():
                return False
            if not self._tree_matches_release(
                self.release / "bundle",
                self.install / "bundle",
                {"agent-governance/local/user-rules.md"},
            ):
                return False
            if not self._tree_matches_release(
                self.release / "integrations",
                self.install / "integrations",
                set(),
            ):
                return False
            return (self.install / "runtime" / "microsoft-provider" / "build.receipt").is_file()
        except OSError:
            return False

    def _bindings_current(self) -> bool:
        try:
            if self.global_instruction.read_bytes() != (
                self.release / "bundle" / "GOVERNANCE.md"
            ).read_bytes():
                return False
            config = json.loads(self.config.read_text(encoding="utf-8"))
            binding = config.get("agent_governance", {})
            return (
                binding.get("root") == str(self.install / "bundle")
                and binding.get("entrypoint") == str(self.install / "bundle" / "GOVERNANCE.md")
                and (self.install / "runtime" / "microsoft-provider" / "build.receipt").is_file()
                and self.evidence.is_file()
            )
        except (OSError, json.JSONDecodeError, TypeError):
            return False

    @staticmethod
    def _tree_matches_release(source: Path, target: Path, allowed_extra: set[str]) -> bool:
        if not target.is_dir() or target.is_symlink():
            return False
        source_files = {
            path.relative_to(source).as_posix(): path
            for path in source.rglob("*")
            if path.is_file() and not path.is_symlink()
        }
        target_files = {
            path.relative_to(target).as_posix(): path
            for path in target.rglob("*")
            if path.is_file() and not path.is_symlink()
        }
        if set(target_files) - set(source_files) != allowed_extra.intersection(target_files):
            return False
        if set(source_files) - set(target_files):
            return False
        return all(
            filecmp.cmp(path, target_files[relative], shallow=False)
            for relative, path in source_files.items()
        )

    def _release_version(self) -> str:
        value = (self.release / "VERSION").read_text(encoding="utf-8").strip()
        if not value:
            raise BootstrapError("Releaseversion fehlt")
        return value

    @property
    def _targets(self) -> tuple[Path, ...]:
        return (self.install, self.global_instruction, self.config, self.evidence)

    def _backup_targets(self, targets: tuple[Path, ...] | None = None) -> None:
        assert self._backup is not None
        self._backup_targets_active = targets if targets is not None else self._targets
        self._backup.mkdir(parents=True, mode=0o700)
        metadata: dict[str, bool] = {}
        for index, target in enumerate(self._backup_targets_active):
            exists = target.exists()
            metadata[str(index)] = exists
            if exists:
                self._copy_item(target, self._backup / str(index))
        (self._backup / "presence.json").write_text(
            json.dumps(metadata, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.chmod(self._backup / "presence.json", 0o600)

    def _verify_backup(self) -> bool:
        assert self._backup is not None
        metadata = json.loads((self._backup / "presence.json").read_text(encoding="utf-8"))
        for index, target in enumerate(self._backup_targets_active):
            expected = bool(metadata[str(index)])
            backup_item = self._backup / str(index)
            if expected != backup_item.exists():
                return False
            if expected and not self._same_item(target, backup_item):
                return False
        return True

    def _repair_current(self, version: str) -> BootstrapResult:
        desired = {
            self.global_instruction: (self.install / "bundle" / "GOVERNANCE.md").read_bytes(),
            self.config: self._desired_config_bytes(),
            self.evidence: self._desired_evidence_bytes(self.install, version),
        }
        affected = tuple(
            target
            for target, content in desired.items()
            if not target.is_file() or target.read_bytes() != content
        )
        if not affected:
            raise BootstrapError("CURRENT-Reparatur wurde ohne Abweichung klassifiziert")

        local_target = self._manifest_local_rules_target(self.install)
        local_rules_preserved = local_target.is_file()
        try:
            self._backup = self.allowed / ".agent-governance-backups" / uuid.uuid4().hex
            self._stage = self.allowed / (".agent-governance-stage-" + uuid.uuid4().hex)
            self._backup_targets(affected)
            backup_verified = self._verify_backup()
            if not backup_verified:
                raise BootstrapError("Backup konnte nicht byteweise verifiziert werden")
            self._stage.mkdir(mode=0o700)
            staged: dict[Path, Path] = {}
            for index, target in enumerate(affected):
                path = self._stage / str(index)
                path.write_bytes(desired[target])
                if target == self.evidence:
                    os.chmod(path, 0o600)
                staged[target] = path
            self._recheck_parent_identities()
            for target, path in staged.items():
                os.replace(path, target)
            checks = self._verify_active(version, local_rules_preserved)
            if not all(checks.values()):
                raise BootstrapError("Reparierter CURRENT-Zustand ist nicht vollständig verifiziert")
            if self.request.verification_hook is not None:
                if not self.request.verification_hook(self.request):
                    raise BootstrapError("Frische Runtime-Verifikation fehlgeschlagen")
            self._discard_stage()
            return BootstrapResult(
                version=version,
                state="CURRENT",
                install_root=str(self.install / "bundle"),
                harness_type=self.request.harness_type,
                enforcement_provider="microsoft-agent-governance-toolkit",
                checks=checks,
                mutation_count=len(affected),
                local_rules_preserved=local_rules_preserved,
                backup_verified=backup_verified,
            )
        except BootstrapError:
            self._rollback()
            raise
        except Exception as error:
            self._rollback()
            raise BootstrapError(f"CURRENT-Reparatur fehlgeschlagen: {type(error).__name__}") from error

    def _prepare_stage(
        self, state: str, version: str
    ) -> tuple[Path, Path, Path, Path]:
        assert self._stage is not None
        self._stage.mkdir(mode=0o700)
        stage_install = self._stage / "install"
        stage_install.mkdir()
        shutil.copy2(self.release / "VERSION", stage_install / "VERSION")
        shutil.copytree(self.release / "bundle", stage_install / "bundle")
        shutil.copytree(self.release / "integrations", stage_install / "integrations")

        local_rules_preserved = False
        if state == "LEGACY":
            source = self.request.legacy_private_rules_path
            if source is None or not Path(source).is_file() or Path(source).is_symlink():
                raise BootstrapError("Legacy-Regelquelle ist nicht eindeutig")
            source = Path(source)
            try:
                source.relative_to(self.install)
            except ValueError as error:
                raise BootstrapError("Legacy-Regelquelle liegt außerhalb der Altinstallation") from error
            local_target = self._manifest_local_rules_target(stage_install)
            local_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, local_target)
            if not filecmp.cmp(source, local_target, shallow=False):
                raise BootstrapError("Lokale Regeln konnten nicht bytegleich erhalten werden")
            local_rules_preserved = True

        provider_output = stage_install / "runtime" / "microsoft-provider"
        provider_output.parent.mkdir()
        provider_entry = self.request.provider_builder(
            stage_install / "integrations" / "microsoft-agent-governance-toolkit",
            provider_output,
        )
        if not Path(provider_entry).is_file() or not (provider_output / "build.receipt").is_file():
            raise BootstrapError("Provider-Materialisierung ist unvollständig")

        staged_global = self._stage / "global-instructions.md"
        shutil.copy2(stage_install / "bundle" / "GOVERNANCE.md", staged_global)

        staged_config = self._stage / "config.json"
        staged_config.write_bytes(self._desired_config_bytes())
        staged_evidence = self._stage / "evidence.jsonl"
        staged_evidence.write_bytes(self._desired_evidence_bytes(stage_install, version))
        os.chmod(staged_evidence, 0o600)
        if state == "LEGACY" and not local_rules_preserved:
            raise BootstrapError("Legacy-Regeln wurden nicht erhalten")
        return stage_install, staged_global, staged_config, staged_evidence

    def _desired_config_bytes(self) -> bytes:
        try:
            config = json.loads(self.config.read_text(encoding="utf-8")) if self.config.exists() else {}
        except json.JSONDecodeError as error:
            raise BootstrapError("Harnesskonfiguration ist kein gültiges JSON") from error
        if not isinstance(config, dict):
            raise BootstrapError("Harnesskonfiguration muss ein Objekt sein")
        config.pop("legacy_import", None)
        config["agent_governance"] = {
            "root": str(self.install / "bundle"),
            "entrypoint": str(self.install / "bundle" / "GOVERNANCE.md"),
            "enforcement_provider": "microsoft-agent-governance-toolkit",
            "provider_entrypoint": str(
                self.install
                / "integrations"
                / "microsoft-agent-governance-toolkit"
                / "bridge"
                / "provider.mjs"
            ),
            "provider_runtime": str(self.install / "runtime" / "microsoft-provider"),
            "evidence_log": str(self.evidence),
        }
        return (json.dumps(config, indent=2, sort_keys=True) + "\n").encode("utf-8")

    def _desired_evidence_bytes(self, install: Path, version: str) -> bytes:
        lock = tomllib.loads(
            (
                install
                / "integrations"
                / "microsoft-agent-governance-toolkit"
                / "upstream.lock.toml"
            ).read_text(encoding="utf-8")
        )
        evidence = {
            "version": version,
            "release_commit": lock["resolved_commit"],
            "governance_root": str(self.install / "bundle"),
            "harness_type": self.request.harness_type,
            "enforcement_provider": "microsoft-agent-governance-toolkit",
            "checks": "PASS",
        }
        return (json.dumps(evidence, sort_keys=True) + "\n").encode("utf-8")

    def _manifest_local_rules_target(self, stage_install: Path) -> Path:
        manifest_dir = stage_install / "bundle" / "agent-governance"
        data = tomllib.loads((manifest_dir / "manifest.toml").read_text(encoding="utf-8"))
        value = data.get("local_rules")
        if not isinstance(value, str) or not value or Path(value).is_absolute():
            raise BootstrapError("Manifest-local_rules ist ungültig")
        target = manifest_dir / value
        normalized = Path(os.path.normpath(target))
        try:
            normalized.relative_to(manifest_dir)
        except ValueError as error:
            raise BootstrapError("Manifest-local_rules verlässt das Manifestverzeichnis") from error
        return normalized

    def _recheck_parent_identities(self) -> None:
        for parent, identity in self._parent_identity.items():
            if parent.is_symlink() or not parent.is_dir():
                raise BootstrapError("Zielparent wurde während der Transaktion ersetzt")
            stat = parent.stat()
            if (stat.st_dev, stat.st_ino) != identity:
                raise BootstrapError("Zielparent wurde während der Transaktion ersetzt")

    def _activate(
        self, stage_install: Path, staged_global: Path, staged_config: Path, staged_evidence: Path
    ) -> None:
        if self.install.exists():
            self._retired_install = self.allowed / (".agent-governance-retired-" + uuid.uuid4().hex)
            os.replace(self.install, self._retired_install)
        os.replace(stage_install, self.install)
        for staged, target in (
            (staged_global, self.global_instruction),
            (staged_config, self.config),
            (staged_evidence, self.evidence),
        ):
            os.replace(staged, target)

    def _verify_active(self, version: str, local_rules_preserved: bool) -> dict[str, bool]:
        checks = {
            "version": (self.install / "VERSION").is_file()
            and (self.install / "VERSION").read_text(encoding="utf-8").strip() == version,
            "governance": self.global_instruction.is_file()
            and self.global_instruction.read_bytes()
            == (self.install / "bundle" / "GOVERNANCE.md").read_bytes(),
            "manifest": (self.install / "bundle" / "agent-governance" / "manifest.toml").is_file(),
            "provider": (self.install / "runtime" / "microsoft-provider" / "build.receipt").is_file(),
            "configuration": False,
            "evidence": self.evidence.is_file(),
        }
        try:
            config = json.loads(self.config.read_text(encoding="utf-8"))
            checks["configuration"] = (
                config["agent_governance"]["root"] == str(self.install / "bundle")
                and "legacy_import" not in config
            )
        except (OSError, KeyError, TypeError, json.JSONDecodeError):
            checks["configuration"] = False
        if local_rules_preserved:
            checks["local_rules"] = self._manifest_local_rules_target(self.install).is_file()
        return checks

    def _rollback(self) -> None:
        if self._backup is None or not self._backup.exists():
            self._discard_stage()
            return
        try:
            metadata = json.loads((self._backup / "presence.json").read_text(encoding="utf-8"))
            for target in self._backup_targets_active:
                self._remove_item(target)
            if self._retired_install is not None and self._retired_install.exists():
                shutil.rmtree(self._retired_install)
            for index, target in enumerate(self._backup_targets_active):
                if metadata[str(index)]:
                    self._copy_item(self._backup / str(index), target)
            for index, target in enumerate(self._backup_targets_active):
                if bool(metadata[str(index)]) != target.exists():
                    raise BootstrapError("Rollback konnte den Ausgangszustand nicht herstellen")
                if metadata[str(index)] and not self._same_item(self._backup / str(index), target):
                    raise BootstrapError("Rollback ist nicht bytegleich")
        finally:
            shutil.rmtree(self._backup, ignore_errors=True)
            parent = self._backup.parent
            try:
                parent.rmdir()
            except OSError:
                pass
            self._discard_stage()

    def _discard_stage(self) -> None:
        if self._stage is not None:
            shutil.rmtree(self._stage, ignore_errors=True)

    def _discard_retired(self) -> None:
        if self._retired_install is not None:
            shutil.rmtree(self._retired_install, ignore_errors=True)

    @staticmethod
    def _remove_item(target: Path) -> None:
        if not target.exists() and not target.is_symlink():
            return
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()

    @staticmethod
    def _copy_item(source: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)

    @staticmethod
    def _same_item(first: Path, second: Path) -> bool:
        if first.is_file() and second.is_file():
            return filecmp.cmp(first, second, shallow=False)
        if first.is_dir() and second.is_dir():
            comparison = filecmp.dircmp(first, second)
            if comparison.left_only or comparison.right_only or comparison.funny_files:
                return False
            if any(not filecmp.cmp(first / name, second / name, shallow=False) for name in comparison.common_files):
                return False
            return all(
                BootstrapTransaction._same_item(first / name, second / name)
                for name in comparison.common_dirs
            )
        return False
