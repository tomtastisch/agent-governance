#!/usr/bin/env python3
"""Integrationstests für die read-only lokale Git-Policy- und Diffquelle."""
from __future__ import annotations

from pathlib import Path, PurePosixPath
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from review_routing.adapters.git_cli import LocalGit
from review_routing.contracts import (
    DetectionMode,
    DiffMode,
    DiffSourcePort,
    DocumentTrust,
    FileStatus,
    GitSourceError,
    PolicySourcePort,
)
from review_routing.registry import RuntimeRegistry


REPOSITORY = "owner/repository"


def run_git(repo: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        timeout=10,
    )
    return completed.stdout


class RepositoryFixture:
    def __init__(self, root: Path):
        self.root = root
        run_git(root, "init", "-b", "main")
        run_git(root, "config", "user.name", "Synthetic Test")
        run_git(root, "config", "user.email", "synthetic@example.invalid")
        run_git(root, "remote", "add", "origin", "git@github.com:owner/repository.git")

    def write(self, relative_path: str, content: str | bytes) -> None:
        target = self.root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8")

    def commit(self, message: str) -> str:
        run_git(self.root, "add", "-A")
        run_git(self.root, "commit", "-m", message)
        return run_git(self.root, "rev-parse", "HEAD").decode("ascii").strip()


class LocalGitIntegrationTest(unittest.TestCase):
    """Der Adapter bindet vollständige Commitobjekte an Repo, Merge-Base und NUL-Diff."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="review-routing-git-")
        self.repo = Path(self.temporary.name)
        self.fixture = RepositoryFixture(self.repo)
        self.fixture.write("core/review-routing.toml", "schema_version = 1\nvalue = \"base\"\n")
        self.fixture.write("kept.txt", "before\n")
        self.fixture.write("deleted.txt", "delete me\n")
        self.base_sha = self.fixture.commit("base")

    def tearDown(self):
        self.temporary.cleanup()

    def commit_changed_head(self) -> str:
        self.fixture.write("core/review-routing.toml", "schema_version = 1\nvalue = \"head\"\n")
        self.fixture.write("kept.txt", "before\nafter\n")
        (self.repo / "deleted.txt").unlink()
        self.fixture.write("added.txt", "new\n")
        self.fixture.write("binary.dat", b"\x00\x01\x02")
        return self.fixture.commit("head")

    def test_complete_diff_enumerates_add_modify_delete_and_binary(self):
        head_sha = self.commit_changed_head()

        result = LocalGit().load(self.repo, REPOSITORY, self.base_sha, head_sha)
        by_path = {file.path: file for file in result.files}

        self.assertEqual(result.api_base_sha, self.base_sha)
        self.assertEqual(result.merge_base_sha, self.base_sha)
        self.assertEqual(result.head_sha, head_sha)
        self.assertIs(result.diff_mode, DiffMode.MERGE_BASE_TO_HEAD)
        self.assertIs(result.rename_detection, DetectionMode.DISABLED)
        self.assertIs(result.copy_detection, DetectionMode.DISABLED)
        self.assertEqual(
            {path: file.status for path, file in by_path.items()},
            {
                "added.txt": FileStatus.ADDED,
                "binary.dat": FileStatus.ADDED,
                "core/review-routing.toml": FileStatus.MODIFIED,
                "deleted.txt": FileStatus.DELETED,
                "kept.txt": FileStatus.MODIFIED,
            },
        )
        self.assertEqual((by_path["binary.dat"].additions, by_path["binary.dat"].deletions), (0, 0))
        self.assertTrue(by_path["binary.dat"].binary)
        self.assertFalse(by_path["kept.txt"].binary)
        self.assertRegex(result.diff_digest, r"\Asha256:[0-9a-f]{64}\Z")

    def test_policy_is_read_from_the_requested_base_commit_not_the_worktree_or_head(self):
        head_sha = self.commit_changed_head()

        document = LocalGit().read_at_commit(
            self.repo,
            REPOSITORY,
            self.base_sha,
            PurePosixPath("core/review-routing.toml"),
        )
        head_document = LocalGit().read_at_commit(
            self.repo,
            REPOSITORY,
            head_sha,
            PurePosixPath("core/review-routing.toml"),
        )

        self.assertEqual(document.trust, DocumentTrust.COMMIT_OBJECT)
        self.assertIn('value = "base"', document.content)
        self.assertNotIn('value = "head"', document.content)
        self.assertIn('value = "head"', head_document.content)
        self.assertEqual(
            document.source,
            f"{self.base_sha}:core/review-routing.toml",
        )

    def test_only_full_lowercase_commit_ids_are_accepted_and_objects_must_be_commits(self):
        head_sha = self.commit_changed_head()
        tree_sha = run_git(self.repo, "rev-parse", f"{head_sha}^{{tree}}").decode("ascii").strip()
        invalid_ids = ("HEAD", "a" * 39, "A" * 40, "f" * 40, tree_sha)

        for invalid in invalid_ids:
            with self.subTest(invalid=invalid):
                with self.assertRaises(GitSourceError):
                    LocalGit().load(self.repo, REPOSITORY, invalid, head_sha)
                with self.assertRaises(GitSourceError):
                    LocalGit().read_at_commit(
                        self.repo,
                        REPOSITORY,
                        invalid,
                        PurePosixPath("core/review-routing.toml"),
                    )

    def test_annotated_tag_object_sha_is_rejected_without_implicit_peeling(self):
        head_sha = self.commit_changed_head()
        run_git(self.repo, "tag", "-a", "annotated", "-m", "synthetic annotated tag", head_sha)
        tag_object_sha = run_git(self.repo, "rev-parse", "refs/tags/annotated").decode("ascii").strip()
        self.assertEqual(
            run_git(self.repo, "cat-file", "-t", tag_object_sha).decode("ascii").strip(),
            "tag",
        )

        with self.assertRaises(GitSourceError):
            LocalGit().load(self.repo, REPOSITORY, tag_object_sha, head_sha)
        with self.assertRaises(GitSourceError):
            LocalGit().read_at_commit(
                self.repo,
                REPOSITORY,
                tag_object_sha,
                PurePosixPath("core/review-routing.toml"),
            )

    def test_lightweight_tag_resolves_to_the_commit_object_sha_and_remains_valid(self):
        head_sha = self.commit_changed_head()
        run_git(self.repo, "tag", "--no-sign", "lightweight", head_sha)
        lightweight_sha = run_git(
            self.repo,
            "rev-parse",
            "refs/tags/lightweight",
        ).decode("ascii").strip()
        self.assertEqual(lightweight_sha, head_sha)
        self.assertEqual(
            run_git(self.repo, "cat-file", "-t", lightweight_sha).decode("ascii").strip(),
            "commit",
        )

        result = LocalGit().load(self.repo, REPOSITORY, self.base_sha, lightweight_sha)
        document = LocalGit().read_at_commit(
            self.repo,
            REPOSITORY,
            lightweight_sha,
            PurePosixPath("core/review-routing.toml"),
        )

        self.assertEqual(result.head_sha, head_sha)
        self.assertIn('value = "head"', document.content)

    def test_canonical_toplevel_and_origin_are_bound_to_repository_identity(self):
        head_sha = self.commit_changed_head()
        nested = self.repo / "nested"
        nested.mkdir()

        with self.assertRaises(GitSourceError):
            LocalGit().load(nested, REPOSITORY, self.base_sha, head_sha)
        with self.assertRaises(GitSourceError):
            LocalGit().load(self.repo, "owner/other", self.base_sha, head_sha)

        run_git(self.repo, "remote", "set-url", "origin", "https://example.invalid/owner/repository.git")
        with self.assertRaises(GitSourceError):
            LocalGit().load(self.repo, REPOSITORY, self.base_sha, head_sha)

        run_git(self.repo, "remote", "remove", "origin")
        with self.assertRaises(GitSourceError):
            LocalGit().load(self.repo, REPOSITORY, self.base_sha, head_sha)

    def test_https_and_ssh_github_origins_normalize_to_the_same_repository(self):
        head_sha = self.commit_changed_head()
        origins = (
            "https://github.com/OWNER/Repository.git",
            "ssh://git@github.com/owner/repository.git",
            "git@github.com:owner/repository.git",
        )

        for origin in origins:
            with self.subTest(origin=origin):
                run_git(self.repo, "remote", "set-url", "origin", origin)
                result = LocalGit().load(self.repo, REPOSITORY, self.base_sha, head_sha)
                self.assertEqual(result.repository, REPOSITORY)

    def test_diverged_and_advanced_api_base_diff_from_merge_base_to_head(self):
        run_git(self.repo, "switch", "-c", "feature")
        self.fixture.write("feature.txt", "feature\n")
        head_sha = self.fixture.commit("feature")
        run_git(self.repo, "switch", "main")
        self.fixture.write("advanced-base.txt", "base advanced\n")
        advanced_base_sha = self.fixture.commit("advance base")

        result = LocalGit().load(self.repo, REPOSITORY, advanced_base_sha, head_sha)

        self.assertEqual(result.api_base_sha, advanced_base_sha)
        self.assertEqual(result.merge_base_sha, self.base_sha)
        self.assertEqual(result.head_sha, head_sha)
        self.assertEqual(tuple(file.path for file in result.files), ("feature.txt",))

    def test_replace_refs_cannot_substitute_diff_or_policy_objects(self):
        self.fixture.write("core/review-routing.toml", "schema_version = 1\nvalue = \"original\"\n")
        self.fixture.write("auth/login.py", "".join(f"line {index}\n" for index in range(1000)))
        original_head_sha = self.fixture.commit("original head")

        run_git(self.repo, "switch", "-c", "replacement", self.base_sha)
        self.fixture.write("core/review-routing.toml", "schema_version = 1\nvalue = \"replacement\"\n")
        self.fixture.write("note.txt", "replacement\n")
        replacement_sha = self.fixture.commit("replacement head")
        run_git(self.repo, "switch", "main")
        run_git(self.repo, "replace", original_head_sha, replacement_sha)

        result = LocalGit().load(self.repo, REPOSITORY, self.base_sha, original_head_sha)
        document = LocalGit().read_at_commit(
            self.repo,
            REPOSITORY,
            original_head_sha,
            PurePosixPath("core/review-routing.toml"),
        )

        self.assertIn("auth/login.py", {file.path for file in result.files})
        self.assertNotIn("note.txt", {file.path for file in result.files})
        self.assertIn('value = "original"', document.content)
        self.assertNotIn('value = "replacement"', document.content)

    def test_local_grafts_fail_closed_before_commit_graph_evidence_is_used(self):
        head_sha = self.commit_changed_head()
        grafts_path = self.repo / ".git/info/grafts"
        grafts_path.write_text(f"{head_sha} {self.base_sha}\n", encoding="ascii")

        with self.assertRaises(GitSourceError):
            LocalGit().load(self.repo, REPOSITORY, self.base_sha, head_sha)
        with self.assertRaises(GitSourceError):
            LocalGit().read_at_commit(
                self.repo,
                REPOSITORY,
                head_sha,
                PurePosixPath("core/review-routing.toml"),
            )

    def test_rename_and_ambiguous_copy_candidates_are_delete_and_add(self):
        self.fixture.write("old.txt", "same\n")
        self.fixture.write("copy-source.txt", "copy\n")
        base_sha = self.fixture.commit("rename base")
        os.rename(self.repo / "old.txt", self.repo / "new.txt")
        self.fixture.write("copy-a.txt", "copy\n")
        self.fixture.write("copy-b.txt", "copy\n")
        head_sha = self.fixture.commit("rename and copies")

        result = LocalGit().load(self.repo, REPOSITORY, base_sha, head_sha)
        statuses = {(file.path, file.status) for file in result.files}

        self.assertIn(("old.txt", FileStatus.DELETED), statuses)
        self.assertIn(("new.txt", FileStatus.ADDED), statuses)
        self.assertIn(("copy-a.txt", FileStatus.ADDED), statuses)
        self.assertIn(("copy-b.txt", FileStatus.ADDED), statuses)
        self.assertFalse(any(file.status in {FileStatus.RENAMED, FileStatus.COPIED} for file in result.files))

    def test_nul_delimited_diff_preserves_tabs_newlines_and_unicode_paths(self):
        unusual_paths = (
            "tab\tname.txt",
            "line\nname.txt",
            "unicode/Café.txt",
        )
        for path in unusual_paths:
            self.fixture.write(path, "synthetic\n")
        head_sha = self.fixture.commit("unusual paths")

        result = LocalGit().load(self.repo, REPOSITORY, self.base_sha, head_sha)

        self.assertEqual(tuple(file.path for file in result.files), tuple(sorted(unusual_paths)))
        self.assertTrue(all(file.status is FileStatus.ADDED for file in result.files))

    def test_committed_binary_attribute_cannot_hide_a_thousand_text_lines(self):
        self.fixture.write("payload.txt", "before\n")
        base_sha = self.fixture.commit("payload base")
        self.fixture.write(".gitattributes", "payload.txt binary\n")
        self.fixture.write("payload.txt", "".join(f"line {index}\n" for index in range(1000)))
        head_sha = self.fixture.commit("candidate attributes")

        with self.assertRaises(GitSourceError):
            LocalGit().load(self.repo, REPOSITORY, base_sha, head_sha)

    def test_uncommitted_binary_attribute_cannot_change_commit_to_commit_diffstat(self):
        self.fixture.write("payload.txt", "before\n")
        base_sha = self.fixture.commit("payload base")
        self.fixture.write("payload.txt", "".join(f"line {index}\n" for index in range(1000)))
        head_sha = self.fixture.commit("payload head")
        self.fixture.write(".gitattributes", "payload.txt binary\n")

        with self.assertRaises(GitSourceError):
            LocalGit().load(self.repo, REPOSITORY, base_sha, head_sha)

    def test_foreign_git_attr_source_cannot_hide_a_thousand_text_lines(self):
        self.fixture.write("payload.txt", "before\n")
        base_sha = self.fixture.commit("payload base")
        self.fixture.write("payload.txt", "".join(f"line {index}\n" for index in range(1000)))
        head_sha = self.fixture.commit("payload head")

        run_git(self.repo, "switch", "-c", "attribute-source", base_sha)
        self.fixture.write(".gitattributes", "payload.txt binary\n")
        attribute_source_sha = self.fixture.commit("foreign attribute source")
        run_git(self.repo, "switch", "main")

        with patch.dict(
            os.environ,
            {"GIT_ATTR_SOURCE": attribute_source_sha},
            clear=False,
        ):
            result = LocalGit().load(self.repo, REPOSITORY, base_sha, head_sha)

        payload = next(file for file in result.files if file.path == "payload.txt")
        self.assertFalse(payload.binary)
        self.assertEqual((payload.additions, payload.deletions), (1000, 1))

    def test_local_big_file_threshold_cannot_hide_a_thousand_text_lines(self):
        self.fixture.write("payload.txt", "before\n")
        base_sha = self.fixture.commit("payload base")
        self.fixture.write("payload.txt", "".join(f"line {index}\n" for index in range(1000)))
        head_sha = self.fixture.commit("payload head")
        run_git(self.repo, "config", "core.bigFileThreshold", "1")

        result = LocalGit().load(self.repo, REPOSITORY, base_sha, head_sha)

        payload = next(file for file in result.files if file.path == "payload.txt")
        self.assertFalse(payload.binary)
        self.assertEqual((payload.additions, payload.deletions), (1000, 1))

    def test_local_ignore_submodules_cannot_hide_a_changed_gitlink(self):
        run_git(
            self.repo,
            "update-index",
            "--add",
            "--cacheinfo",
            f"160000,{self.base_sha},auth/component",
        )
        run_git(self.repo, "commit", "-m", "gitlink base")
        gitlink_base_sha = run_git(self.repo, "rev-parse", "HEAD").decode("ascii").strip()

        run_git(
            self.repo,
            "update-index",
            "--cacheinfo",
            f"160000,{gitlink_base_sha},auth/component",
        )
        self.fixture.write("note.txt", "harmless\n")
        run_git(self.repo, "add", "note.txt")
        run_git(self.repo, "commit", "-m", "changed gitlink")
        head_sha = run_git(self.repo, "rev-parse", "HEAD").decode("ascii").strip()
        run_git(self.repo, "config", "diff.ignoreSubmodules", "all")

        result = LocalGit().load(self.repo, REPOSITORY, gitlink_base_sha, head_sha)

        self.assertEqual(
            {file.path: file.status for file in result.files},
            {
                "auth/component": FileStatus.MODIFIED,
                "note.txt": FileStatus.ADDED,
            },
        )

    def test_diff_and_policy_reads_do_not_change_the_worktree_or_index(self):
        self.fixture.write("untracked.txt", "keep untracked\n")
        before = run_git(self.repo, "status", "--porcelain=v1", "-z")

        LocalGit().load(self.repo, REPOSITORY, self.base_sha, self.base_sha)
        LocalGit().read_at_commit(
            self.repo,
            REPOSITORY,
            self.base_sha,
            PurePosixPath("core/review-routing.toml"),
        )
        after = run_git(self.repo, "status", "--porcelain=v1", "-z")

        self.assertEqual(after, before)

    def test_conflicting_raw_and_numstat_metadata_fails_closed(self):
        head_sha = self.commit_changed_head()
        real_run = subprocess.run

        def corrupt_numstat(args, **kwargs):
            completed = real_run(args, **kwargs)
            if "--numstat" in args and completed.returncode == 0:
                return subprocess.CompletedProcess(
                    args=args,
                    returncode=0,
                    stdout=b"1\t0\tconflicting.txt\x00",
                    stderr=b"",
                )
            return completed

        with patch("review_routing.adapters.git_cli.subprocess.run", side_effect=corrupt_numstat):
            with self.assertRaises(GitSourceError):
                LocalGit().load(self.repo, REPOSITORY, self.base_sha, head_sha)

    def test_git_failures_are_sanitized_and_commands_use_argv_timeout_and_no_diff_helpers(self):
        head_sha = self.commit_changed_head()
        sentinel = self.repo / "must-not-exist"
        malicious_repository = f"owner/repository;touch {sentinel}"

        with self.assertRaises(GitSourceError):
            LocalGit().load(self.repo, malicious_repository, self.base_sha, head_sha)
        self.assertFalse(sentinel.exists())

        calls = []
        real_run = subprocess.run

        def observe(args, **kwargs):
            calls.append((args, kwargs))
            return real_run(args, **kwargs)

        with patch.dict(
            os.environ,
            {"GIT_UNTRUSTED_SENTINEL": "must-not-propagate"},
            clear=False,
        ):
            with patch("review_routing.adapters.git_cli.subprocess.run", side_effect=observe):
                LocalGit().load(self.repo, REPOSITORY, self.base_sha, head_sha)

        self.assertTrue(all(isinstance(args, list) for args, _ in calls))
        self.assertTrue(all(kwargs["timeout"] == 10 for _, kwargs in calls))
        self.assertTrue(all(kwargs.get("shell", False) is False for _, kwargs in calls))
        self.assertTrue(all("--no-replace-objects" in args for args, _ in calls))
        self.assertTrue(
            all("core.attributesFile=/dev/null" in args for args, _ in calls)
        )
        self.assertTrue(
            all("core.bigFileThreshold=512m" in args for args, _ in calls)
        )
        self.assertTrue(
            all(kwargs["env"]["GIT_NO_REPLACE_OBJECTS"] == "1" for _, kwargs in calls)
        )
        self.assertTrue(
            all(kwargs["env"]["GIT_ATTR_NOSYSTEM"] == "1" for _, kwargs in calls)
        )
        expected_environment_keys = {
            "GIT_ATTR_NOSYSTEM",
            "GIT_CONFIG_GLOBAL",
            "GIT_CONFIG_NOSYSTEM",
            "GIT_CONFIG_SYSTEM",
            "GIT_NO_LAZY_FETCH",
            "GIT_NO_REPLACE_OBJECTS",
            "GIT_OPTIONAL_LOCKS",
            "GIT_TERMINAL_PROMPT",
            "LC_ALL",
            "PATH",
        }
        self.assertTrue(
            all(set(kwargs["env"]) == expected_environment_keys for _, kwargs in calls)
        )
        diff_calls = [args for args, _ in calls if "diff" in args]
        self.assertTrue(diff_calls)
        for args in diff_calls:
            self.assertIn("--no-ext-diff", args)
            self.assertIn("--no-textconv", args)
            self.assertIn("--no-renames", args)
            self.assertIn("--ignore-submodules=none", args)
            self.assertIn("--diff-algorithm=myers", args)
            self.assertIn("--no-indent-heuristic", args)
            self.assertIn("--no-relative", args)
            self.assertIn("-z", args)

        failure = subprocess.CompletedProcess(
            args=["git"],
            returncode=128,
            stdout=b"",
            stderr=b"secret-token /private/sensitive/repository",
        )
        with patch("review_routing.adapters.git_cli.subprocess.run", return_value=failure):
            with self.assertRaises(GitSourceError) as raised:
                LocalGit().load(self.repo, REPOSITORY, self.base_sha, head_sha)
        self.assertNotIn("secret-token", str(raised.exception))
        self.assertNotIn("/private/", str(raised.exception))

    def test_policy_paths_are_closed_relative_nfc_posix_paths(self):
        for invalid in (
            PurePosixPath("/core/review-routing.toml"),
            PurePosixPath("../review-routing.toml"),
            PurePosixPath("core/../review-routing.toml"),
            PurePosixPath("."),
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(GitSourceError):
                    LocalGit().read_at_commit(self.repo, REPOSITORY, self.base_sha, invalid)

    def test_registry_resolves_both_local_git_ports_to_one_adapter(self):
        registry = RuntimeRegistry.bootstrap(None)

        self.assertIsInstance(registry.resolve(PolicySourcePort), LocalGit)
        self.assertIsInstance(registry.resolve(DiffSourcePort), LocalGit)


if __name__ == "__main__":
    unittest.main()
