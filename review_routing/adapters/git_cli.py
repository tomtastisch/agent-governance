"""Read-only lokaler Git-Adapter für Commit-Policy und vollständige Diff-Evidenz."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
from typing import Mapping
from urllib.parse import urlsplit

from review_routing.contracts import (
    AdapterFactory,
    DetectionMode,
    DiffFile,
    DiffMode,
    DiffSnapshot,
    DiffSourcePort,
    DocumentTrust,
    FileStatus,
    GitSourceError,
    normalize_repo_path,
    PolicyDocument,
    PolicySourcePort,
    require_full_sha,
    require_repository,
)


_GIT_TIMEOUT_SECONDS = 10
# Gits Standard schützt vor unbeschränkter Diff-Speicherlast; größere Blobs bleiben binär.
_GIT_BIG_FILE_THRESHOLD = "512m"
_RAW_MODE_RE = re.compile(rb"[0-7]{6}")
_RAW_SHA_RE = re.compile(rb"[0-9a-f]{40}")
_ORIGIN_SCP_RE = re.compile(
    r"(?:git@)?github\.com:([^/]+)/([^/]+?)(?:\.git)?/?",
    re.IGNORECASE,
)


def _decode_utf8(value: bytes, operation: str) -> str:
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError as error:
        raise GitSourceError(f"Git lieferte für {operation} kein gültiges UTF-8") from error


def _normalized_origin(origin: str) -> str:
    candidate = origin.strip()
    scp_match = _ORIGIN_SCP_RE.fullmatch(candidate)
    if scp_match:
        return f"{scp_match.group(1)}/{scp_match.group(2)}".removesuffix(".git").casefold()

    parsed = urlsplit(candidate)
    if (
        parsed.scheme not in {"https", "ssh", "git"}
        or parsed.hostname is None
        or parsed.hostname.casefold() != "github.com"
        or parsed.query
        or parsed.fragment
        or parsed.password is not None
        or (parsed.scheme == "https" and parsed.username is not None)
        or (parsed.scheme in {"ssh", "git"} and parsed.username not in {None, "git"})
    ):
        raise GitSourceError("Der Origin ist keine unterstützte GitHub-Repository-URL")
    path = parsed.path.removeprefix("/").removesuffix(".git").removesuffix("/")
    try:
        require_repository(path)
    except ValueError as error:
        raise GitSourceError("Der Origin enthält keine eindeutige Repository-Identität") from error
    return path.casefold()


@dataclass(frozen=True)
class _RawFile:
    path: str
    status: FileStatus


class LocalGit(PolicySourcePort, DiffSourcePort):
    """Erhebt nur lokale, SHA-gebundene Git-Objekte ohne Hooks oder Netzwerk."""

    def _run_git(self, repo_path: Path, operation: str, *arguments: str) -> bytes:
        argv = [
            "git",
            "--no-replace-objects",
            "-c",
            "core.attributesFile=/dev/null",
            "-c",
            f"core.bigFileThreshold={_GIT_BIG_FILE_THRESHOLD}",
            "-C",
            str(repo_path),
            *arguments,
        ]
        environment = {
            "PATH": os.environ.get("PATH", os.defpath),
            "LC_ALL": "C",
            "GIT_ATTR_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
        }
        try:
            result = subprocess.run(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=_GIT_TIMEOUT_SECONDS,
                env=environment,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise GitSourceError(f"Lokale Git-Operation fehlgeschlagen: {operation}") from error
        if result.returncode != 0:
            raise GitSourceError(f"Lokale Git-Operation fehlgeschlagen: {operation}")
        return result.stdout

    def _bind_repository(self, repo_path: Path, repository: str) -> Path:
        try:
            require_repository(repository)
            canonical = repo_path.resolve(strict=True)
        except (OSError, ValueError) as error:
            raise GitSourceError("Repository-Pfad oder -Identität ist ungültig") from error
        top_level_raw = self._run_git(canonical, "Repository-Toplevel", "rev-parse", "--show-toplevel")
        top_level_text = _decode_utf8(top_level_raw, "Repository-Toplevel").strip()
        try:
            top_level = Path(top_level_text).resolve(strict=True)
        except OSError as error:
            raise GitSourceError("Das kanonische Repository-Toplevel ist nicht verfügbar") from error
        if top_level != canonical:
            raise GitSourceError("Der Repository-Pfad ist nicht das kanonische Toplevel")
        origin_raw = self._run_git(canonical, "Origin-Bindung", "remote", "get-url", "origin")
        origin = _normalized_origin(_decode_utf8(origin_raw, "Origin-Bindung"))
        if origin != repository.casefold():
            raise GitSourceError("Der Origin stimmt nicht mit der Repository-Identität überein")
        return canonical

    def _reject_local_grafts(self, repo_path: Path) -> None:
        grafts_raw = self._run_git(
            repo_path,
            "Graft-Metadaten lokalisieren",
            "rev-parse",
            "--git-path",
            "info/grafts",
        )
        grafts_text = _decode_utf8(grafts_raw, "Graft-Metadaten").strip()
        if not grafts_text:
            raise GitSourceError("Git lieferte keinen eindeutigen Graft-Metadatenpfad")
        grafts_path = Path(grafts_text)
        if not grafts_path.is_absolute():
            grafts_path = repo_path / grafts_path
        try:
            if grafts_path.exists() and grafts_path.stat().st_size > 0:
                raise GitSourceError("Lokale Graft-Metadaten sind für SHA-gebundene Evidenz unzulässig")
        except OSError as error:
            raise GitSourceError("Lokale Graft-Metadaten können nicht sicher geprüft werden") from error

    def _reject_attribute_sources(
        self,
        repo_path: Path,
        commit_shas: tuple[str, ...],
    ) -> None:
        info_attributes_raw = self._run_git(
            repo_path,
            "Lokale Attribute lokalisieren",
            "rev-parse",
            "--git-path",
            "info/attributes",
        )
        info_attributes_text = _decode_utf8(
            info_attributes_raw,
            "Lokale Attribute",
        ).strip()
        if not info_attributes_text:
            raise GitSourceError("Git lieferte keinen eindeutigen lokalen Attributpfad")
        info_attributes_path = Path(info_attributes_text)
        if not info_attributes_path.is_absolute():
            info_attributes_path = repo_path / info_attributes_path
        try:
            if info_attributes_path.exists() and info_attributes_path.stat().st_size > 0:
                raise GitSourceError("Lokale Git-Attribute sind für Diff-Evidenz unzulässig")
        except OSError as error:
            raise GitSourceError("Lokale Git-Attribute können nicht sicher geprüft werden") from error

        index_paths = self._run_git(
            repo_path,
            "Index-Attribute prüfen",
            "ls-files",
            "-z",
            "--cached",
        )
        self._reject_attribute_records(index_paths, "Index")
        for commit_sha in commit_shas:
            tree_paths = self._run_git(
                repo_path,
                "Commit-Attribute prüfen",
                "ls-tree",
                "-r",
                "-z",
                "--name-only",
                commit_sha,
            )
            self._reject_attribute_records(tree_paths, "Commit")

        def fail_on_walk_error(error: OSError) -> None:
            raise GitSourceError("Der Worktree kann nicht vollständig auf Attribute geprüft werden") from error

        for _, directory_names, file_names in os.walk(
            repo_path,
            topdown=True,
            onerror=fail_on_walk_error,
            followlinks=False,
        ):
            directory_names[:] = [name for name in directory_names if name != ".git"]
            if ".gitattributes" in file_names:
                raise GitSourceError("Worktree-Attribute sind für Diff-Evidenz unzulässig")

    @classmethod
    def _reject_attribute_records(cls, output: bytes, source: str) -> None:
        for raw_path in cls._nul_records(output, f"{source}-Attributpfade"):
            try:
                path = normalize_repo_path(_decode_utf8(raw_path, f"{source}-Attributpfad"))
            except ValueError as error:
                raise GitSourceError(f"{source}-Attributpfade sind nicht normalisiert") from error
            if path == ".gitattributes" or path.endswith("/.gitattributes"):
                raise GitSourceError(f"{source}-Attribute sind für Diff-Evidenz unzulässig")

    def _require_commit(self, repo_path: Path, commit_sha: str, field_name: str) -> None:
        try:
            require_full_sha(commit_sha, field_name)
        except ValueError as error:
            raise GitSourceError("Git-Referenzen müssen vollständige Commit-SHAs sein") from error
        object_type = self._run_git(
            repo_path,
            "Ungepeelten Objekttyp prüfen",
            "cat-file",
            "-t",
            commit_sha,
        )
        if object_type != b"commit\n":
            raise GitSourceError("Die angegebene Objekt-SHA bezeichnet kein Commitobjekt")

    def read_at_commit(
        self,
        repo_path: Path,
        repository: str,
        commit_sha: str,
        policy_path: PurePosixPath,
    ) -> PolicyDocument:
        canonical = self._bind_repository(repo_path, repository)
        self._reject_local_grafts(canonical)
        self._require_commit(canonical, commit_sha, "commit_sha")
        try:
            normalized_path = normalize_repo_path(policy_path, "policy_path")
        except ValueError as error:
            raise GitSourceError("Der Policy-Pfad ist kein normalisierter relativer POSIX-Pfad") from error

        tree_output = self._run_git(
            canonical,
            "Policy-Objektauflösung",
            "ls-tree",
            "--full-tree",
            "-z",
            commit_sha,
            "--",
            f":(literal){normalized_path}",
        )
        if not tree_output.endswith(b"\x00"):
            raise GitSourceError("Die Policy-Objektauflösung ist unvollständig")
        records = tree_output[:-1].split(b"\x00") if tree_output else []
        if len(records) != 1:
            raise GitSourceError("Der Commit enthält nicht genau ein Policy-Blob")
        try:
            metadata, raw_path = records[0].split(b"\t", 1)
            mode, object_type, object_sha = metadata.split(b" ")
        except ValueError as error:
            raise GitSourceError("Die Policy-Objektmetadaten sind widersprüchlich") from error
        if (
            object_type != b"blob"
            or not _RAW_MODE_RE.fullmatch(mode)
            or not _RAW_SHA_RE.fullmatch(object_sha)
            or _decode_utf8(raw_path, "Policy-Pfad") != normalized_path
        ):
            raise GitSourceError("Die Policy-Objektmetadaten sind widersprüchlich")
        content_bytes = self._run_git(
            canonical,
            "Policy-Blob lesen",
            "cat-file",
            "blob",
            object_sha.decode("ascii"),
        )
        return PolicyDocument(
            content=_decode_utf8(content_bytes, "Policy-Inhalt"),
            trust=DocumentTrust.COMMIT_OBJECT,
            source=f"{commit_sha}:{normalized_path}",
        )

    def load(
        self,
        repo_path: Path,
        repository: str,
        api_base_sha: str,
        head_sha: str,
    ) -> DiffSnapshot:
        canonical = self._bind_repository(repo_path, repository)
        self._reject_local_grafts(canonical)
        self._require_commit(canonical, api_base_sha, "api_base_sha")
        self._require_commit(canonical, head_sha, "head_sha")
        merge_base_raw = self._run_git(
            canonical,
            "Merge-Base bestimmen",
            "merge-base",
            api_base_sha,
            head_sha,
        )
        merge_base_sha = _decode_utf8(merge_base_raw, "Merge-Base").strip()
        try:
            require_full_sha(merge_base_sha, "merge_base_sha")
        except ValueError as error:
            raise GitSourceError("Git lieferte keine vollständige Merge-Base-SHA") from error
        self._require_commit(canonical, merge_base_sha, "merge_base_sha")
        self._reject_attribute_sources(
            canonical,
            (api_base_sha, merge_base_sha, head_sha),
        )

        common_arguments = (
            "--no-ext-diff",
            "--no-textconv",
            "--no-renames",
            "--ignore-submodules=none",
            "--diff-algorithm=myers",
            "--no-indent-heuristic",
            "--no-relative",
            "-z",
            merge_base_sha,
            head_sha,
            "--",
        )
        raw = self._run_git(
            canonical,
            "Raw-Diff lesen",
            "diff",
            "--raw",
            "--abbrev=40",
            *common_arguments,
        )
        numstat = self._run_git(
            canonical,
            "Numstat-Diff lesen",
            "diff",
            "--numstat",
            *common_arguments,
        )
        files = self._reconcile_diff(raw, numstat)
        return DiffSnapshot(
            schema_version=1,
            repository=repository,
            api_base_sha=api_base_sha,
            merge_base_sha=merge_base_sha,
            head_sha=head_sha,
            diff_mode=DiffMode.MERGE_BASE_TO_HEAD,
            rename_detection=DetectionMode.DISABLED,
            copy_detection=DetectionMode.DISABLED,
            files=files,
        )

    @staticmethod
    def _nul_records(output: bytes, operation: str) -> list[bytes]:
        if not output:
            return []
        if not output.endswith(b"\x00"):
            raise GitSourceError(f"Git lieferte unvollständige {operation}")
        return output[:-1].split(b"\x00")

    @classmethod
    def _parse_raw(cls, output: bytes) -> dict[str, _RawFile]:
        records = cls._nul_records(output, "Raw-Diffdaten")
        if len(records) % 2:
            raise GitSourceError("Die Raw-Diffdaten enthalten keine vollständigen Dateipaare")
        parsed: dict[str, _RawFile] = {}
        status_map = {
            b"A": FileStatus.ADDED,
            b"M": FileStatus.MODIFIED,
            b"D": FileStatus.DELETED,
            b"T": FileStatus.MODIFIED,
        }
        zero_sha = b"0" * 40
        for index in range(0, len(records), 2):
            metadata = records[index]
            raw_path = records[index + 1]
            fields = metadata.split(b" ")
            if len(fields) != 5 or not fields[0].startswith(b":"):
                raise GitSourceError("Die Raw-Diffmetadaten sind widersprüchlich")
            old_mode = fields[0][1:]
            new_mode, old_sha, new_sha, raw_status = fields[1:]
            if (
                not _RAW_MODE_RE.fullmatch(old_mode)
                or not _RAW_MODE_RE.fullmatch(new_mode)
                or not _RAW_SHA_RE.fullmatch(old_sha)
                or not _RAW_SHA_RE.fullmatch(new_sha)
                or raw_status not in status_map
            ):
                raise GitSourceError("Die Raw-Diffmetadaten sind widersprüchlich")
            status = status_map[raw_status]
            identities_valid = (
                status is FileStatus.ADDED
                and old_mode == b"000000"
                and old_sha == zero_sha
                and new_mode != b"000000"
                and new_sha != zero_sha
            ) or (
                status is FileStatus.DELETED
                and new_mode == b"000000"
                and new_sha == zero_sha
                and old_mode != b"000000"
                and old_sha != zero_sha
            ) or (
                status is FileStatus.MODIFIED
                and old_mode != b"000000"
                and new_mode != b"000000"
                and old_sha != zero_sha
                and new_sha != zero_sha
            )
            if not identities_valid:
                raise GitSourceError("Die Raw-Diffobjekte widersprechen dem Dateistatus")
            try:
                path = normalize_repo_path(_decode_utf8(raw_path, "Diff-Pfad"))
            except ValueError as error:
                raise GitSourceError("Der Raw-Diff enthält einen ungültigen Pfad") from error
            if path in parsed:
                raise GitSourceError("Der Raw-Diff enthält einen Pfad mehrfach")
            parsed[path] = _RawFile(path=path, status=status)
        return parsed

    @classmethod
    def _parse_numstat(cls, output: bytes) -> dict[str, tuple[int, int, bool]]:
        parsed: dict[str, tuple[int, int, bool]] = {}
        for record in cls._nul_records(output, "Numstat-Diffdaten"):
            try:
                additions_raw, deletions_raw, raw_path = record.split(b"\t", 2)
            except ValueError as error:
                raise GitSourceError("Die Numstat-Diffmetadaten sind widersprüchlich") from error
            binary = additions_raw == b"-" and deletions_raw == b"-"
            if binary:
                additions = deletions = 0
            else:
                if not additions_raw.isdigit() or not deletions_raw.isdigit():
                    raise GitSourceError("Die Numstat-Zählwerte sind ungültig")
                additions = int(additions_raw)
                deletions = int(deletions_raw)
            try:
                path = normalize_repo_path(_decode_utf8(raw_path, "Diff-Pfad"))
            except ValueError as error:
                raise GitSourceError("Der Numstat-Diff enthält einen ungültigen Pfad") from error
            if path in parsed:
                raise GitSourceError("Der Numstat-Diff enthält einen Pfad mehrfach")
            parsed[path] = (additions, deletions, binary)
        return parsed

    @classmethod
    def _reconcile_diff(cls, raw_output: bytes, numstat_output: bytes) -> tuple[DiffFile, ...]:
        raw = cls._parse_raw(raw_output)
        numstat = cls._parse_numstat(numstat_output)
        if set(raw) != set(numstat):
            raise GitSourceError("Raw- und Numstat-Diff beschreiben unterschiedliche Dateien")
        return tuple(
            DiffFile(
                path=path,
                status=raw[path].status,
                additions=numstat[path][0],
                deletions=numstat[path][1],
                binary=numstat[path][2],
            )
            for path in sorted(raw)
        )


@dataclass(frozen=True)
class LocalGitFactory:
    provided_ports = (PolicySourcePort, DiffSourcePort)
    required_ports: tuple[type[object], ...] = ()

    def build(self, dependencies: Mapping[type[object], object]) -> Mapping[type[object], object]:
        if dependencies:
            raise GitSourceError("Der lokale Git-Adapter erwartet keine Abhängigkeiten")
        adapter = LocalGit()
        return {
            PolicySourcePort: adapter,
            DiffSourcePort: adapter,
        }


def factory() -> AdapterFactory:
    """Meldet beide read-only Git-Ports gemeinsam an der Runtime-Registry an."""
    return LocalGitFactory()
