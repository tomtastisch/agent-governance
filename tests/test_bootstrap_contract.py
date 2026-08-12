#!/usr/bin/env python3
"""Generischer Bootstrapvertrag mit FRESH-/CURRENT-/LEGACY-Referenztransaktion."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "Installation.bootstrap.prompt.md"
REFERENCE = ROOT / "tests" / "support" / "bootstrap_reference.py"
FIXTURES = ROOT / "tests" / "fixtures" / "bootstrap"


def load_reference():
    if not REFERENCE.is_file():
        raise AssertionError("synthetische Bootstrap-Referenz fehlt")
    spec = importlib.util.spec_from_file_location("bootstrap_reference", REFERENCE)
    if spec is None or spec.loader is None:
        raise AssertionError("Bootstrap-Referenz ist nicht ladbar")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def synthetic_provider_builder(_integration: Path, output: Path) -> Path:
    module = output / "microsoft-sdk" / "dist" / "policy.js"
    module.parent.mkdir(parents=True)
    module.write_text("// synthetic provider fixture\n", encoding="utf-8")
    (output / "build.receipt").write_text("synthetic_provider=PASS\n", encoding="utf-8")
    return module


def tree_bytes(root: Path) -> dict[str, bytes]:
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }


@contextmanager
def foreign_cwd():
    previous = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="foreign-cwd-") as directory:
        os.chdir(directory)
        try:
            yield
        finally:
            os.chdir(previous)


class BootstrapPromptContract(unittest.TestCase):
    def read_prompt(self) -> str:
        if not BOOTSTRAP.is_file():
            raise AssertionError("Installation.bootstrap.prompt.md fehlt")
        return BOOTSTRAP.read_text(encoding="utf-8")

    def test_prompt_is_one_time_harness_neutral_contract(self):
        text = self.read_prompt()
        for term in (
            "einmaliger Installations-, Integrations- und Migrationsvertrag",
            "Harness-Erkennung",
            "AGENT_GOVERNANCE_ROOT",
            "absolut",
            "FRESH",
            "CURRENT",
            "LEGACY",
            "Rollback",
            "frische Session",
        ):
            self.assertIn(term, text)
        self.assertNotIn("~/.codex", text)
        self.assertNotRegex(text, r"(?m)/(?:Users|home)/")
        self.assertRegex(text, r"(?is)CODEX_HOME.+nur.+Codex.+Kandidat")
        self.assertRegex(text, r"(?is)kein.+Updater.+kein.+Daemon.+keine.+Control Plane")

    def test_prompt_reads_local_rules_path_from_manifest_and_protects_privacy(self):
        text = self.read_prompt()
        self.assertRegex(text, r"(?is)local_rules.+manifest\.toml.+nicht.+hardcod")
        for forbidden in (
            "private Regelhashes",
            "private Regelgrößen",
            "private Regelzeilenzahlen",
        ):
            self.assertIn(forbidden, text)
        self.assertRegex(text, r"(?is)Boolean.+cmp.+keine.+Fingerprint")
        self.assertRegex(text, r"(?is)codex debug prompt-input.+nicht ausreichend")
        self.assertIn("codex exec", text)

    def test_prompt_requires_transactional_pre_effect_enforcement(self):
        text = self.read_prompt()
        for decision in ("allow", "deny", "require_approval", "error", "unknown"):
            self.assertIn(f"`{decision}`", text)
        self.assertRegex(text, r"(?is)Provider.+vor.+Effekt")
        self.assertRegex(text, r"(?is)ausschließlich.+`allow`.+fort")
        self.assertRegex(text, r"(?is)Providerfehler.+fail-closed")
        self.assertIn("upstream.lock.toml", text)
        self.assertIn("snapshot.files.sha256", text)

    def test_prompt_emits_only_safe_evidence(self):
        text = self.read_prompt()
        for field in (
            "Version",
            "Release-/Commitkennung",
            "Governance-Root",
            "Harness-Typ",
            "Enforcement-Provider",
            "PASS/FAIL",
        ):
            self.assertIn(field, text)
        self.assertRegex(text, r"(?is)keine.+Secrets.+Tokens.+private Regeltexte")


class BootstrapFixtureContract(unittest.TestCase):
    def test_synthetic_reference_transaction_exists(self):
        self.assertTrue(REFERENCE.is_file())

    def test_fresh_current_and_legacy_fixtures_exist(self):
        for state in ("fresh", "current", "legacy"):
            self.assertTrue((FIXTURES / state / "README.md").is_file(), state)

    def test_legacy_fixture_covers_removed_wiring_and_private_rules(self):
        legacy = FIXTURES / "legacy"
        for relative in (
            "install/core/core.md",
            "install/adapters/codex.md",
            "install/profile/personal-rules.md",
            "global-instructions.md",
            "harness-config.json",
        ):
            self.assertTrue((legacy / relative).is_file(), relative)
        global_text = (legacy / "global-instructions.md").read_text(encoding="utf-8")
        for legacy_path in ("core/", "adapters/", "profile/"):
            self.assertIn(legacy_path, global_text)
        self.assertIn("missing-legacy-target.md", global_text)


class BootstrapTestCase(unittest.TestCase):
    def setUp(self):
        self.reference = load_reference()
        self.temporary = tempfile.TemporaryDirectory(prefix="agent governance bootstrap ")
        self.base = Path(self.temporary.name).resolve(strict=True)
        self.allowed = self.base / "Allowed Root With Spaces"
        self.allowed.mkdir()
        self.harness = self.allowed / "neutral-harness"
        self.harness.mkdir()
        self.install = self.allowed / "agent-governance"
        self.global_instruction = self.harness / "global-instructions.md"
        self.config = self.harness / "config.json"
        self.evidence = self.harness / "evidence.jsonl"
        self.config.write_text('{"preserve": "yes"}\n', encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def request(self, **overrides):
        values = {
            "release_root": ROOT,
            "allowed_root": self.allowed,
            "install_dir": self.install,
            "global_instruction_path": self.global_instruction,
            "config_path": self.config,
            "evidence_log_path": self.evidence,
            "harness_type": "synthetic-neutral",
            "root_candidates": {},
            "provider_builder": synthetic_provider_builder,
        }
        values.update(overrides)
        return self.reference.BootstrapRequest(**values)

    def run_transaction(self, **overrides):
        return self.reference.BootstrapTransaction(self.request(**overrides)).run()


class FreshInstall(BootstrapTestCase):
    def test_fresh_installs_bundle_binding_provider_and_safe_receipt(self):
        with foreign_cwd():
            result = self.run_transaction()

        self.assertEqual(result.state, "FRESH")
        self.assertTrue(all(result.checks.values()))
        self.assertGreater(result.mutation_count, 0)
        self.assertEqual(
            self.global_instruction.read_bytes(),
            (ROOT / "bundle" / "GOVERNANCE.md").read_bytes(),
        )
        manifest = self.install / "bundle" / "agent-governance" / "manifest.toml"
        self.assertTrue(manifest.is_file())
        config = json.loads(self.config.read_text(encoding="utf-8"))
        self.assertEqual(config["preserve"], "yes")
        self.assertEqual(config["agent_governance"]["root"], str(self.install / "bundle"))
        self.assertEqual(result.harness_type, "synthetic-neutral")
        safe_result = json.dumps(asdict(result), sort_keys=True).lower()
        for forbidden in ("personal-rules", "rule_hash", "rule_size", "synthetic_rule_active"):
            self.assertNotIn(forbidden, safe_result)


class CurrentInstall(BootstrapTestCase):
    def test_second_run_is_byte_and_metadata_idempotent(self):
        first = self.run_transaction()
        before_bytes = tree_bytes(self.allowed)
        before_mtimes = {
            path.relative_to(self.allowed).as_posix(): path.stat().st_mtime_ns
            for path in self.allowed.rglob("*")
            if path.is_file()
        }

        second = self.run_transaction()

        self.assertEqual(first.state, "FRESH")
        self.assertEqual(second.state, "CURRENT")
        self.assertEqual(second.mutation_count, 0)
        self.assertEqual(tree_bytes(self.allowed), before_bytes)
        self.assertEqual(
            {
                path.relative_to(self.allowed).as_posix(): path.stat().st_mtime_ns
                for path in self.allowed.rglob("*")
                if path.is_file()
            },
            before_mtimes,
        )

    def test_missing_binding_is_repaired_without_rewriting_install_or_local_rules(self):
        self.run_transaction()
        local_rules = self.install / "bundle" / "agent-governance" / "local" / "user-rules.md"
        local_rules.write_bytes(b"SYNTHETIC CURRENT RULE\n")
        install_before = tree_bytes(self.install)
        install_mtimes = {
            path.relative_to(self.install).as_posix(): path.stat().st_mtime_ns
            for path in self.install.rglob("*")
            if path.is_file()
        }
        self.global_instruction.unlink()
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config.pop("agent_governance")
        self.config.write_text(json.dumps(config) + "\n", encoding="utf-8")

        result = self.run_transaction()

        self.assertEqual(result.state, "CURRENT")
        self.assertGreater(result.mutation_count, 0)
        self.assertEqual(tree_bytes(self.install), install_before)
        self.assertEqual(
            {
                path.relative_to(self.install).as_posix(): path.stat().st_mtime_ns
                for path in self.install.rglob("*")
                if path.is_file()
            },
            install_mtimes,
        )
        self.assertEqual(local_rules.read_bytes(), b"SYNTHETIC CURRENT RULE\n")
        self.assertEqual(
            self.global_instruction.read_bytes(),
            (self.install / "bundle" / "GOVERNANCE.md").read_bytes(),
        )
        repaired_config = json.loads(self.config.read_text(encoding="utf-8"))
        self.assertEqual(repaired_config["preserve"], "yes")
        self.assertEqual(
            repaired_config["agent_governance"]["root"], str(self.install / "bundle")
        )


class LegacyInstall(BootstrapTestCase):
    def prepare_legacy(self):
        fixture = FIXTURES / "legacy"
        shutil.copytree(fixture / "install", self.install)
        shutil.copy2(fixture / "global-instructions.md", self.global_instruction)
        shutil.copy2(fixture / "harness-config.json", self.config)

    def test_legacy_migrates_active_wiring_and_preserves_rules(self):
        self.prepare_legacy()
        private_source = self.install / "profile" / "personal-rules.md"
        private_before = private_source.read_bytes()

        result = self.run_transaction(legacy_private_rules_path=private_source)

        self.assertEqual(result.state, "LEGACY")
        self.assertTrue(result.local_rules_preserved)
        self.assertFalse((self.install / "core").exists())
        self.assertFalse((self.install / "adapters").exists())
        self.assertFalse((self.install / "profile").exists())
        local_rules = self.install / "bundle" / "agent-governance" / "local" / "user-rules.md"
        self.assertEqual(local_rules.read_bytes(), private_before)
        self.assertNotIn("core/", self.global_instruction.read_text(encoding="utf-8"))
        self.assertNotIn("adapters/", self.global_instruction.read_text(encoding="utf-8"))
        self.assertNotIn("profile/", self.global_instruction.read_text(encoding="utf-8"))
        config = json.loads(self.config.read_text(encoding="utf-8"))
        self.assertEqual(config["preserve"], "legacy-value")
        self.assertNotIn("legacy_import", config)
        self.assertTrue(result.backup_verified)


class Rollback(LegacyInstall):
    def test_failed_verification_restores_complete_legacy_state(self):
        self.prepare_legacy()
        before = tree_bytes(self.allowed)
        private_source = self.install / "profile" / "personal-rules.md"

        with self.assertRaises(self.reference.BootstrapError):
            self.run_transaction(
                legacy_private_rules_path=private_source,
                verification_hook=lambda _request: False,
            )

        self.assertEqual(tree_bytes(self.allowed), before)

    def test_provider_build_failure_restores_fresh_state(self):
        before = tree_bytes(self.allowed)

        def fail_provider(_integration: Path, _output: Path) -> Path:
            raise RuntimeError("synthetic provider failure")

        with self.assertRaises(self.reference.BootstrapError):
            self.run_transaction(provider_builder=fail_provider)

        self.assertEqual(tree_bytes(self.allowed), before)

    def test_restore_failure_preserves_verified_backup_and_recoverable_prior_install(self):
        self.prepare_legacy()
        private_source = self.install / "profile" / "personal-rules.md"
        transaction = self.reference.BootstrapTransaction(
            self.request(
                legacy_private_rules_path=private_source,
                verification_hook=lambda _request: False,
            )
        )
        original_copy = transaction._copy_item

        def fail_one_restore(source: Path, target: Path) -> None:
            if transaction._backup is not None and source.parent == transaction._backup \
                    and target == self.global_instruction:
                raise OSError("synthetic restore failure")
            original_copy(source, target)

        with mock.patch.object(transaction, "_copy_item", side_effect=fail_one_restore):
            with self.assertRaises(self.reference.BootstrapError):
                transaction.run()

        self.assertIsNotNone(transaction._backup)
        self.assertTrue(transaction._backup.is_dir())
        self.assertTrue(
            self.install.is_dir() or (transaction._backup / "0").is_dir(),
            "prior installation must remain recoverable",
        )


class PathSafety(BootstrapTestCase):
    def test_relative_and_dot_roots_fail_closed(self):
        for value in ("", ".", "relative/root"):
            with self.subTest(value=value):
                request = self.request(root_candidates={"candidate": value})
                with self.assertRaises(self.reference.BootstrapError):
                    self.reference.BootstrapTransaction(request).run()

    def test_conflicting_valid_root_candidates_fail_closed(self):
        second = self.allowed / "second-root"
        shutil.copytree(ROOT / "bundle", second)
        request = self.request(
            root_candidates={
                "first": str(ROOT / "bundle"),
                "second": str(second),
            }
        )
        with self.assertRaises(self.reference.BootstrapError):
            self.reference.BootstrapTransaction(request).run()

    def test_symlinked_target_parent_and_outside_target_fail_closed(self):
        outside = self.base / "outside"
        outside.mkdir()
        link = self.allowed / "linked-parent"
        link.symlink_to(outside, target_is_directory=True)
        for config_path in (link / "config.json", outside / "config.json"):
            with self.subTest(config_path=config_path):
                request = self.request(config_path=config_path)
                with self.assertRaises(self.reference.BootstrapError):
                    self.reference.BootstrapTransaction(request).run()

    def test_symlinked_internal_backup_root_fails_without_copying_outside(self):
        outside = self.base / "outside-backups"
        outside.mkdir()
        (self.allowed / ".agent-governance-backups").symlink_to(
            outside, target_is_directory=True
        )

        with self.assertRaises(self.reference.BootstrapError):
            self.run_transaction()

        self.assertEqual(list(outside.iterdir()), [])


class Portability(BootstrapTestCase):
    def test_foreign_cwd_home_with_spaces_and_unset_optional_variables(self):
        environment = os.environ.copy()
        environment.pop("CODEX_HOME", None)
        environment.pop("AGENT_GOVERNANCE_ROOT", None)
        with mock.patch.dict(os.environ, environment, clear=True), foreign_cwd():
            result = self.run_transaction()
        self.assertEqual(result.state, "FRESH")
        self.assertTrue(all(result.checks.values()))


if __name__ == "__main__":
    unittest.main()
