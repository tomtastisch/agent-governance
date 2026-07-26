#!/usr/bin/env python3
"""Verhaltensspezifikation für den deterministischen Diff-Risikoklassifikator."""
from dataclasses import replace
from pathlib import Path
import unittest

from review_routing.adapters.toml_config import TomlConfig
from review_routing.contracts import (
    DetectionMode,
    DiffFile,
    DiffMode,
    DiffSnapshot,
    DocumentTrust,
    FileStatus,
    PolicyDocument,
    RiskClassifierPort,
    RiskLevel,
)
from review_routing.registry import RuntimeRegistry
from review_routing.risk import RiskClassifier, assess_risk


ROOT = Path(__file__).resolve().parents[1]
SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40


def diff_file(
    path: str = "src/application.py",
    *,
    status: FileStatus = FileStatus.MODIFIED,
    previous_path: str | None = None,
    additions: int = 1,
    deletions: int = 0,
    binary: bool = False,
) -> DiffFile:
    return DiffFile(
        path=path,
        status=status,
        previous_path=previous_path,
        additions=additions,
        deletions=deletions,
        binary=binary,
    )


def snapshot(
    *files: DiffFile,
    explicit_risk: RiskLevel | None = None,
    security_relevant: bool | None = None,
    risk_reasons: tuple[str, ...] = (),
) -> DiffSnapshot:
    return DiffSnapshot(
        schema_version=1,
        repository="owner/repository",
        api_base_sha=SHA_A,
        merge_base_sha=SHA_C,
        head_sha=SHA_B,
        diff_mode=DiffMode.MERGE_BASE_TO_HEAD,
        rename_detection=DetectionMode.DISABLED,
        copy_detection=DetectionMode.DISABLED,
        files=files,
        explicit_risk=explicit_risk,
        security_relevant=security_relevant,
        risk_reasons=risk_reasons,
    )


class RiskClassificationTest(unittest.TestCase):
    """Das Maximum aus Größe, Pfadmarkern und explizitem Marker bestimmt das Risiko."""

    @classmethod
    def setUpClass(cls):
        cls.config = TomlConfig().parse_routing(
            PolicyDocument(
                content=(ROOT / "core/review-routing.toml").read_text(encoding="utf-8"),
                trust=DocumentTrust.DEVELOPMENT,
                source="core/review-routing.toml",
            )
        )

    def test_each_size_threshold_is_inclusive_and_has_stable_reason_names(self):
        cases = (
            (99, RiskLevel.LOW, None),
            (100, RiskLevel.MEDIUM, "size_threshold:medium:100"),
            (101, RiskLevel.MEDIUM, "size_threshold:medium:100"),
            (299, RiskLevel.MEDIUM, "size_threshold:medium:100"),
            (300, RiskLevel.HIGH, "size_threshold:high:300"),
            (301, RiskLevel.HIGH, "size_threshold:high:300"),
            (799, RiskLevel.HIGH, "size_threshold:high:300"),
            (800, RiskLevel.CRITICAL, "size_threshold:critical:800"),
            (801, RiskLevel.CRITICAL, "size_threshold:critical:800"),
        )

        for changed_lines, expected_level, expected_reason in cases:
            with self.subTest(changed_lines=changed_lines):
                result = assess_risk(
                    snapshot(diff_file(additions=changed_lines)),
                    self.config,
                )
                self.assertEqual(result.level, expected_level)
                if expected_reason is None:
                    self.assertFalse(any(reason.startswith("size_threshold:") for reason in result.reasons))
                else:
                    self.assertIn(expected_reason, result.reasons)

    def test_maximum_of_size_path_and_explicit_signals_wins(self):
        result = assess_risk(
            snapshot(
                diff_file(path=".github/workflows/check.yml", additions=800),
                explicit_risk=RiskLevel.MEDIUM,
            ),
            self.config,
        )

        self.assertEqual(result.level, RiskLevel.CRITICAL)
        self.assertEqual(
            result.reasons,
            (
                "explicit_risk:medium",
                "high_path:.github/workflows/check.yml",
                "size_threshold:critical:800",
            ),
        )

    def test_critical_and_high_path_markers_come_only_from_the_config(self):
        critical = assess_risk(snapshot(diff_file(path="core/core.md")), self.config)
        high = assess_risk(
            snapshot(diff_file(path=".github/workflows/check.yml")),
            self.config,
        )

        self.assertEqual(critical.level, RiskLevel.CRITICAL)
        self.assertIn("critical_path:core/core.md", critical.reasons)
        self.assertEqual(high.level, RiskLevel.HIGH)
        self.assertIn("high_path:.github/workflows/check.yml", high.reasons)

    def test_explicit_risk_can_raise_but_never_lower_path_risk(self):
        raised = assess_risk(
            snapshot(diff_file(), explicit_risk=RiskLevel.HIGH),
            self.config,
        )
        not_lowered = assess_risk(
            snapshot(diff_file(path="core/core.md"), explicit_risk=RiskLevel.LOW),
            self.config,
        )

        self.assertEqual(raised.level, RiskLevel.HIGH)
        self.assertEqual(not_lowered.level, RiskLevel.CRITICAL)

    def test_security_relevance_is_independent_from_the_numeric_maximum(self):
        explicit = assess_risk(
            snapshot(diff_file(), security_relevant=True),
            self.config,
        )
        configured = assess_risk(
            snapshot(diff_file(path="module/auth/login.py")),
            self.config,
        )
        non_security_critical = assess_risk(
            snapshot(diff_file(path="core/core.md")),
            self.config,
        )

        self.assertEqual(explicit.level, RiskLevel.LOW)
        self.assertTrue(explicit.security_relevant)
        self.assertIn("explicit_security_relevant", explicit.reasons)
        self.assertEqual(configured.level, RiskLevel.CRITICAL)
        self.assertTrue(configured.security_relevant)
        self.assertFalse(non_security_critical.security_relevant)

    def test_empty_diff_is_fail_closed_as_incomplete_metadata(self):
        result = assess_risk(snapshot(), self.config)

        self.assertEqual(result.level, RiskLevel.CRITICAL)
        self.assertEqual(result.reasons, ("incomplete_diff_metadata",))

    def test_evidence_reasons_do_not_raise_the_risk(self):
        result = assess_risk(
            snapshot(diff_file(), risk_reasons=("operator note", "external critical claim")),
            self.config,
        )

        self.assertEqual(result.level, RiskLevel.LOW)
        self.assertEqual(
            result.reasons,
            ("evidence:external critical claim", "evidence:operator note"),
        )

    def test_renamed_and_copied_files_classify_both_old_and_new_paths(self):
        renamed = assess_risk(
            snapshot(
                diff_file(
                    path="docs/core-note.md",
                    previous_path="core/core.md",
                    status=FileStatus.RENAMED,
                )
            ),
            self.config,
        )
        copied = assess_risk(
            snapshot(
                diff_file(
                    path="module/auth/login.py",
                    previous_path="docs/example.py",
                    status=FileStatus.COPIED,
                )
            ),
            self.config,
        )

        self.assertEqual(renamed.level, RiskLevel.CRITICAL)
        self.assertIn("critical_path:core/core.md", renamed.reasons)
        self.assertEqual(copied.level, RiskLevel.CRITICAL)
        self.assertTrue(copied.security_relevant)


class DiffContractTest(unittest.TestCase):
    """Das versionierte Diff-Schema lehnt mehrdeutige oder nicht-kanonische Daten ab."""

    def test_schema_version_and_enum_fields_are_closed(self):
        with self.assertRaises(ValueError):
            replace(snapshot(diff_file()), schema_version=2)
        with self.assertRaises(ValueError):
            replace(snapshot(diff_file()), diff_mode="merge_base_to_head")
        with self.assertRaises(TypeError):
            DiffSnapshot(
                schema_version=1,
                repository="owner/repository",
                api_base_sha=SHA_A,
                merge_base_sha=SHA_C,
                head_sha=SHA_B,
                diff_mode=DiffMode.MERGE_BASE_TO_HEAD,
                rename_detection=DetectionMode.DISABLED,
                copy_detection=DetectionMode.DISABLED,
                files=(diff_file(),),
                unknown_field=True,
            )

    def test_full_lowercase_commit_shas_and_repository_identity_are_required(self):
        for field_name, invalid in (
            ("api_base_sha", "main"),
            ("merge_base_sha", "A" * 40),
            ("head_sha", "a" * 39),
            ("repository", "owner"),
            ("repository", "https://github.com/owner/repository"),
        ):
            with self.subTest(field_name=field_name, invalid=invalid):
                with self.assertRaises(ValueError):
                    replace(snapshot(diff_file()), **{field_name: invalid})

    def test_paths_are_normalized_to_nfc_and_duplicate_forms_are_rejected(self):
        normalized = snapshot(diff_file(path="docs/Cafe\u0301.md"))
        self.assertEqual(normalized.files[0].path, "docs/Café.md")

        invalid_paths = (
            "/absolute.py",
            "../escape.py",
            "docs/../escape.py",
            "docs\\windows.py",
            "docs/\x00hidden.py",
            ".",
            "docs//double.py",
        )
        for invalid in invalid_paths:
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    diff_file(path=invalid)

        with self.assertRaises(ValueError):
            snapshot(
                diff_file(path="docs/Café.md"),
                diff_file(path="docs/Cafe\u0301.md"),
            )

    def test_previous_path_is_required_exactly_for_rename_and_copy(self):
        for status in (FileStatus.RENAMED, FileStatus.COPIED):
            with self.subTest(status=status):
                with self.assertRaises(ValueError):
                    diff_file(status=status)
        for status in (FileStatus.ADDED, FileStatus.MODIFIED, FileStatus.DELETED):
            with self.subTest(status=status):
                with self.assertRaises(ValueError):
                    diff_file(status=status, previous_path="old.py")

    def test_counts_are_non_negative_integers_and_binary_counts_are_zero(self):
        for field_name, invalid in (
            ("additions", -1),
            ("deletions", -1),
            ("additions", True),
            ("deletions", 1.5),
        ):
            with self.subTest(field_name=field_name, invalid=invalid):
                with self.assertRaises(ValueError):
                    diff_file(**{field_name: invalid})
        with self.assertRaises(ValueError):
            diff_file(binary=True, additions=1)
        self.assertEqual(
            diff_file(binary=True, additions=0, deletions=0).binary,
            True,
        )

    def test_snapshot_is_immutable_canonical_and_has_a_stable_digest(self):
        source_files = [
            diff_file(path="z.py"),
            diff_file(path="a.py"),
        ]
        source_reasons = ["z", "a"]
        first = snapshot(*source_files, risk_reasons=source_reasons)
        second = snapshot(*reversed(source_files), risk_reasons=tuple(reversed(source_reasons)))
        source_files.append(diff_file(path="late.py"))
        source_reasons.append("late")

        self.assertEqual(tuple(file.path for file in first.files), ("a.py", "z.py"))
        self.assertEqual(first.risk_reasons, ("a", "z"))
        self.assertEqual(first.diff_digest, second.diff_digest)
        self.assertRegex(first.diff_digest, r"\Asha256:[0-9a-f]{64}\Z")

    def test_bool_and_optional_enum_fields_reject_python_lookalikes(self):
        for invalid in ("true", 0, 1):
            with self.subTest(target="binary", invalid=invalid):
                with self.assertRaises(ValueError):
                    diff_file(binary=invalid)
            with self.subTest(target="security_relevant", invalid=invalid):
                with self.assertRaises(ValueError):
                    snapshot(diff_file(), security_relevant=invalid)
        with self.assertRaises(ValueError):
            snapshot(diff_file(), explicit_risk="high")

    def test_registry_resolves_the_risk_classifier_port(self):
        self.assertIsInstance(
            RuntimeRegistry.bootstrap(None).resolve(RiskClassifierPort),
            RiskClassifier,
        )


if __name__ == "__main__":
    unittest.main()
