#!/usr/bin/env python3
"""Mitarbeiterfluss, Boundary-Dokument und aktuelle Releasemetadaten."""

from __future__ import annotations

from pathlib import Path
import json
import re
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
CLI_REFERENCE_PATH = ROOT / "docs" / "installer-cli-reference.md"
HARNESS_RECIPES_PATH = ROOT / "docs" / "harness-recipes.md"
PACKAGE = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
PACKAGE_LOCK = json.loads((ROOT / "package-lock.json").read_text(encoding="utf-8"))

# These are deliberately explicit: historical records may retain old examples, but a newly
# added Markdown document must enter the current-document scan instead of being silently ignored.
HISTORICAL_INSTALLATION_DOCUMENTS = frozenset({
    "CHANGELOG.md",
    "docs/adapter-audit.md",
    "docs/dependency-evidence.md",
    "docs/audits/2026-07-30-source-migration.md",
    "docs/decisions/0001-branch-tags-statt-agenten-praefix.md",
    "docs/decisions/0002-vorgang-sub-pr-in-haupt-pr-branch.md",
    "docs/decisions/0003-canonical-governance-bundle.md",
    "docs/superpowers/plans/2026-08-12-generic-bootstrap-enforcement.md",
    "docs/superpowers/plans/2026-08-17-typed-routing-catalogs.md",
    "docs/superpowers/plans/2026-08-19-copilot-qa-binding.md",
    "docs/superpowers/plans/2026-08-24-global-explicit-path-installer.md",
    "docs/superpowers/plans/2026-08-24-installer-security-contract-boundary.md",
    "docs/superpowers/plans/2026-08-25-issue-39-documentation-architecture.md",
    "docs/superpowers/plans/2026-08-26-issue-44-init-onboarding.md",
    "docs/superpowers/specs/2026-08-12-generic-bootstrap-enforcement-design.md",
    "docs/superpowers/specs/2026-08-19-copilot-qa-binding-design.md",
    "docs/superpowers/specs/2026-08-24-global-explicit-path-installer-design.md",
    "docs/superpowers/specs/2026-08-25-issue-39-documentation-architecture-design.md",
    "docs/superpowers/specs/2026-08-26-issue-44-init-onboarding-design.md",
})
NON_CONSUMER_MARKDOWN_ROOTS = frozenset({".git", ".superpowers", "bundle", "integrations", "node_modules", "tests"})
NORMAL_INSTALLATION_COMMANDS = (
    "npm i @tomtastisch/agent-governance",
    "npx agent-governance init",
)
NORMAL_INSTALLATION_SECTION = ("agent governance", "schnellstart")
ALLOWED_NORMAL_REFERENCE_SECTIONS = frozenset({
    ("docs/harness-recipes.md", ("harness-rezepte",)),
    ("docs/installer-architecture.md", ("installerarchitektur 1.0", "init-onboarding und dependency-grenze")),
})
LOW_LEVEL_INVOCATION_RE = (
    r"(?:agent-governance|npx\s+agent-governance|"
    r"(?:\.\.?/)*node_modules/\.bin/agent-governance|"
    r"/(?:[^\s/]+/)*node_modules/\.bin/agent-governance)"
)
LOW_LEVEL_COMMAND_RE = re.compile(
    rf"(?:^|\s){LOW_LEVEL_INVOCATION_RE}\s+"
    r"(?:inspect|plan|install|verify|status|update|uninstall|rollback|init)(?:\s|$)"
)
ADVANCED_HEADING_RE = re.compile(r"\b(?:advanced|automation|ci|low-level|troubleshooting)\b", re.IGNORECASE)


def _current_consumer_documents(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.md")
        if path.is_file()
        and path.relative_to(root).as_posix() not in HISTORICAL_INSTALLATION_DOCUMENTS
        and not NON_CONSUMER_MARKDOWN_ROOTS.intersection(path.relative_to(root).parts)
    )


def _copy_current_consumer_documents(destination: Path) -> None:
    for source in _current_consumer_documents(ROOT):
        target = destination / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _normalize_shell_commands(lines: list[str]) -> list[str]:
    commands: list[str] = []
    pending = ""
    for line in lines:
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        if value.endswith("\\"):
            pending += f"{value[:-1].rstrip()} "
            continue
        commands.append(f"{pending}{value}".strip())
        pending = ""
    if pending:
        commands.append(pending.strip())
    return commands


def _current_installation_violations(root: Path) -> list[str]:
    violations: list[str] = []
    normal_sequences: list[tuple[str, tuple[str, ...]]] = []
    for path in _current_consumer_documents(root):
        relative = path.relative_to(root).as_posix()
        headings: list[str] = []
        section_commands: dict[tuple[str, ...], list[str]] = {}
        fence: tuple[str, int, list[str], tuple[str, ...]] | None = None
        lines = path.read_text(encoding="utf-8").splitlines()
        for number, line in enumerate(lines, start=1):
            if fence is not None:
                marker, minimum_length, fence_lines, fence_headings = fence
                if _is_fence_close(line, marker, minimum_length):
                    _record_commands(
                        _normalize_shell_commands(fence_lines), relative, number, fence_headings,
                        section_commands, violations,
                    )
                    fence = None
                    continue
                fence_lines.append(line)
                continue

            heading = re.match(r"^ {0,3}(#{1,6})\s+(.+?)\s*$", line)
            if heading:
                level = len(heading.group(1))
                headings = headings[: level - 1]
                headings.append(heading.group(2).lower())
                continue

            opener = _fence_open(line)
            if opener is not None:
                fence = (*opener, [], tuple(headings))
                continue

            for inline in re.findall(r"`([^`\n]+)`", line):
                _record_commands(
                    [inline], relative, number, tuple(headings), section_commands, violations,
                )

        if fence is not None:
            _, _, fence_lines, fence_headings = fence
            _record_commands(
                _normalize_shell_commands(fence_lines), relative, len(lines),
                fence_headings, section_commands, violations,
            )

        for section, commands in section_commands.items():
            section_sequences = 0
            for first, second in zip(commands, commands[1:]):
                if not (_is_npm_install_command(first) and _is_npx_init_command(second)):
                    continue
                pair = (" ".join(first.split()), " ".join(second.split()))
                if pair == NORMAL_INSTALLATION_COMMANDS:
                    section_sequences += 1
                    if (relative, section) not in ALLOWED_NORMAL_REFERENCE_SECTIONS or section_sequences > 1:
                        normal_sequences.append((relative, section))
    if normal_sequences != [("README.md", NORMAL_INSTALLATION_SECTION)]:
        violations.append(f"normal installation sequences must be exactly README.md once; found {normal_sequences}")
    if len(normal_sequences) > 1:
        violations.append("second normal installation sequence")
    return violations


def _fence_open(line: str) -> tuple[str, int] | None:
    match = re.match(r"^ {0,3}(?P<marker>`{3,}|~{3,})(?P<info>[^\n]*)$", line)
    if match is None:
        return None
    marker = match.group("marker")
    if marker[0] == "`" and "`" in match.group("info"):
        return None
    return marker[0], len(marker)


def _is_fence_close(line: str, marker: str, minimum_length: int) -> bool:
    return bool(re.match(rf"^ {{0,3}}{re.escape(marker)}{{{minimum_length},}}\s*$", line))


def _record_commands(
    commands: list[str],
    path: str,
    number: int,
    headings: tuple[str, ...],
    sections: dict[tuple[str, ...], list[str]],
    violations: list[str],
) -> None:
    normalized = [" ".join(command.split()) for command in commands]
    if any(_is_installation_command(command) for command in normalized):
        sections.setdefault(headings, []).extend(normalized)
    for command in normalized:
        _check_installation_command(command, path, number, list(headings), violations)


def _is_npm_install_command(command: str) -> bool:
    return bool(re.match(r"^npm\s+(?:i|install)\b", command))


def _is_npx_init_command(command: str) -> bool:
    return bool(re.match(r"^npx\s+agent-governance\s+init\b", command))


def _check_installation_command(command: str, path: str, number: int, headings: list[str], violations: list[str]) -> None:
    normalized = " ".join(command.split())
    normal_prefix = _is_installation_command(normalized)
    if normal_prefix and normalized not in NORMAL_INSTALLATION_COMMANDS:
        violations.append(f"{path}:{number}: normal command must exactly match the installation path")
        return
    if LOW_LEVEL_COMMAND_RE.search(normalized) and normalized not in NORMAL_INSTALLATION_COMMANDS:
        heading_path = " > ".join(headings)
        if not ADVANCED_HEADING_RE.search(heading_path):
            violations.append(f"{path}:{number}: low-level command outside Advanced/Automation/CI/Low-level/Troubleshooting section")


def _is_installation_command(command: str) -> bool:
    normalized = " ".join(command.split())
    return bool(re.match(r"^(?:npm\s+(?:i|install)\b|npx\s+agent-governance\s+init\b)", normalized))


class ReadmeEntryContract(unittest.TestCase):
    """Catches a return from the concise entry layer to duplicated reference content."""

    REPOSITORY = "tomtastisch/agent-governance"
    RAW_MAIN = "https://raw.githubusercontent.com/tomtastisch/agent-governance/main"
    BLOB_MAIN = "https://github.com/tomtastisch/agent-governance/blob/main"

    def test_hero_orders_icon_title_pitch_and_exact_badge_classes(self):
        """Catches a missing pitch or badges taking the pitch position in the entry hero."""
        hero = README.split("\n## ", 1)[0]
        blocks = hero.strip().split("\n\n")
        self.assertEqual(len(blocks), 4)
        icon, title, pitch, badges = blocks
        self.assertIn("assets/branding/agent-governance-icon.png", icon)
        self.assertEqual(title, "# Agent Governance")
        self.assertRegex(pitch, r"^[A-ZÄÖÜ][^\n]{20,159}\.$")
        self.assertEqual(len(re.findall(r"[.!?](?:\s|$)", pitch)), 1)
        self.assertFalse(pitch.startswith("[!"))
        self.assertEqual(badges.count("[!["), 3)
        for badge_class in ("![npm]", "![CI]", "![License: Apache-2.0]"):
            self.assertEqual(badges.count(badge_class), 1)

    def test_readme_has_exactly_the_six_entry_sections(self):
        """Catches README growing into a second CLI, architecture, or security reference."""
        self.assertEqual(
            re.findall(r"(?m)^## .+$", README),
            [
                "## Was ist Agent Governance?",
                "## Warum Agent Governance?",
                "## Schnellstart",
                "## Wie funktioniert es?",
                "## Dokumentation",
                "## Support und Lizenz",
            ],
        )

    def test_badges_follow_package_and_ci_metadata(self):
        """Catches stale badges that no longer identify the published package, CI, or license."""
        ci_workflow = ROOT / ".github" / "workflows" / "ci.yml"
        self.assertTrue(ci_workflow.is_file())
        package_name = PACKAGE["name"]
        license_name = PACKAGE["license"]
        expected_badges = (
            f"https://img.shields.io/npm/v/{package_name}?style=flat-square",
            f"https://github.com/{self.REPOSITORY}/actions/workflows/{ci_workflow.name}/badge.svg?branch=main",
            f"License-{license_name.replace('-', '--')}",
        )
        for badge in expected_badges:
            with self.subTest(badge=badge):
                self.assertIn(badge, README)

    def test_quickstart_has_the_only_normal_two_command_installation_path(self):
        """Catches a return to a second normal explicit-path quickstart."""
        section = README.split("## Schnellstart", 1)[1].split("\n## ", 1)[0]
        self.assertIn("npm i @tomtastisch/agent-governance", section)
        self.assertIn("npx agent-governance init", section)
        self.assertNotIn("agent-governance install", section)
        self.assertNotIn("--installation-root", section)
        self.assertNotIn("@latest", section)
        self.assertNotIn("@next", section)
        self.assertNotIn("--harness", section)

    def test_quickstart_links_wizard_and_advanced_references_after_commands(self):
        """Catches a quickstart that leaves parameter or target-path questions unnavigable."""
        section = README.split("## Schnellstart", 1)[1].split("\n## ", 1)[0]
        after_commands = section.split("```", 2)[2].strip()
        cli_url = f"{self.BLOB_MAIN}/docs/installer-cli-reference.md"
        harness_url = f"{self.BLOB_MAIN}/docs/harness-recipes.md"
        self.assertIn(f"]({cli_url})", after_commands)
        self.assertIn(f"]({harness_url})", after_commands)
        self.assertIn("Advanced", after_commands)
        self.assertIn("Harness", after_commands)
        self.assertNotIn("](docs/", after_commands)
        self.assertEqual(len(re.findall(r"[.!?](?:\s|$)", after_commands)), 2)

    def test_readme_navigates_to_current_reference_owners_on_main(self):
        """Catches relative or historical links instead of durable current-reference navigation."""
        paths = (
            "docs/installer-cli-reference.md",
            "docs/harness-recipes.md",
            "docs/installer-architecture.md",
            "docs/installer-threat-model.md",
            "docs/installer-json-schemas.md",
            "CHANGELOG.md",
            "bundle/GOVERNANCE.md",
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).is_file())
                self.assertIn(f"{self.BLOB_MAIN}/{path}", README)

    def test_assets_have_semantic_paths_and_a_single_readme_overview(self):
        """Catches duplicate, stale, or wrongly assigned visual documentation assets."""
        icon = "assets/branding/agent-governance-icon.png"
        overview = "assets/diagrams/governance-overview.png"
        architecture = "assets/diagrams/governance-architecture.png"
        for path in (icon, overview, architecture):
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).is_file())
        self.assertFalse((ROOT / "docs" / "images").exists())
        self.assertIn(f"{self.RAW_MAIN}/{icon}", README)
        self.assertEqual(README.count(f"{self.RAW_MAIN}/{overview}"), 1)
        architecture_doc = (ROOT / "docs" / "installer-architecture.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(f"../{architecture}", architecture_doc)
        for stale in (
            "docs/images/",
            "Governance-ujjm885-44_44.png",
            "Governance-dsfs652-20_44.png",
            "82b014a1-7278-4be4-a665-37dae365c850.png",
        ):
            self.assertNotIn(stale, "\n".join((README, architecture_doc)))

    def test_overview_graphic_belongs_to_how_it_works(self):
        """Catches the sole overview drifting into the problem or benefit narrative."""
        overview = f"{self.RAW_MAIN}/assets/diagrams/governance-overview.png"
        how = README.split("## Wie funktioniert es?", 1)[1].split("\n## ", 1)[0]
        self.assertEqual(how.count(overview), 1)

    def test_why_section_has_three_to_five_compact_benefits(self):
        """Catches a prose-only why section that does not expose the approved benefits."""
        why = README.split("## Warum Agent Governance?", 1)[1].split("\n## ", 1)[0]
        benefits = re.findall(r"(?m)^- \S.+$", why)
        self.assertGreaterEqual(len(benefits), 3)
        self.assertLessEqual(len(benefits), 5)

    def test_readme_drops_retired_entry_points_and_keeps_support(self):
        """Catches retired RC guidance or the accidental loss of the intended support destination."""
        for stale in ("@next", "Release Candidate", "RC", "INSTALL.md"):
            self.assertNotIn(stale, README)
        self.assertIn("https://buymeacoffee.com/tomtastisch", README)
        self.assertIn(PACKAGE["license"], README)

    def test_support_uses_the_canonical_buy_me_a_coffee_button(self):
        """Catches replacement of the functional support button with a plain text link."""
        support = README.split("## Support und Lizenz", 1)[1]
        image_url = (
            "https://img.buymeacoffee.com/button-api/"
            "?text=Buy%20me%20a%20coffee&emoji=&slug=tomtastisch"
            "&button_colour=FFDD00&font_colour=000000&font_family=Cookie"
            "&outline_colour=000000&coffee_colour=ffffff"
        )
        expected = (
            f"[![Buy Me a Coffee]({image_url})]"
            "(https://buymeacoffee.com/tomtastisch)"
        )
        self.assertIn(expected, support)
        self.assertNotRegex(support, r"(?m)^\[Buy Me a Coffee\]\(")


class InstallationDocumentationContract(unittest.TestCase):
    def test_current_consumer_documents_have_one_exact_normal_installation_sequence(self):
        self.assertEqual(_current_installation_violations(ROOT), [])

    def test_scanner_rejects_lookalike_package_and_init_repair(self):
        with tempfile.TemporaryDirectory(prefix="agent-governance-docs-lookalike-") as directory:
            fixture_root = Path(directory)
            _copy_current_consumer_documents(fixture_root)
            readme = fixture_root / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "npm i @tomtastisch/agent-governance\nnpx agent-governance init",
                    "npm i @tomtastisch/agent-governance-lookalike\nnpx agent-governance init --repair",
                ),
                encoding="utf-8",
            )
            violations = _current_installation_violations(fixture_root)
        self.assertTrue(any("normal command must exactly match" in violation for violation in violations), violations)

    def test_scanner_rejects_a_second_normal_quickstart(self):
        with tempfile.TemporaryDirectory(prefix="agent-governance-docs-second-quickstart-") as directory:
            fixture_root = Path(directory)
            _copy_current_consumer_documents(fixture_root)
            (fixture_root / "GETTING_STARTED.md").write_text(
                "# Getting started\n\n```sh\nnpm i @tomtastisch/agent-governance\nnpx agent-governance init\n```\n",
                encoding="utf-8",
            )
            violations = _current_installation_violations(fixture_root)
        self.assertTrue(any("second normal installation sequence" in violation for violation in violations), violations)

    def test_scanner_rejects_unmarked_low_level_quickstart(self):
        with tempfile.TemporaryDirectory(prefix="agent-governance-docs-low-level-") as directory:
            fixture_root = Path(directory)
            _copy_current_consumer_documents(fixture_root)
            (fixture_root / "GETTING_STARTED.md").write_text(
                "# Getting started\n\n```sh\nagent-governance plan --scope global\nagent-governance install --scope global\nagent-governance verify --scope global\n```\n",
                encoding="utf-8",
            )
            violations = _current_installation_violations(fixture_root)
        self.assertTrue(any("low-level command outside" in violation for violation in violations), violations)

    def test_scanner_rejects_a_nested_current_consumer_quickstart(self):
        with tempfile.TemporaryDirectory(prefix="agent-governance-docs-nested-quickstart-") as directory:
            fixture_root = Path(directory)
            _copy_current_consumer_documents(fixture_root)
            nested = fixture_root / "docs" / "getting-started" / "README.md"
            nested.parent.mkdir(parents=True)
            nested.write_text(
                "# Getting started\n\n```sh\nnpm i @tomtastisch/agent-governance\nnpx agent-governance init\n```\n",
                encoding="utf-8",
            )
            violations = _current_installation_violations(fixture_root)
        self.assertTrue(any("second normal installation sequence" in violation for violation in violations), violations)

    def test_scanner_rejects_a_nested_inline_normal_quickstart(self):
        with tempfile.TemporaryDirectory(prefix="agent-governance-docs-nested-inline-quickstart-") as directory:
            fixture_root = Path(directory)
            _copy_current_consumer_documents(fixture_root)
            nested = fixture_root / "docs" / "getting-started" / "README.md"
            nested.parent.mkdir(parents=True)
            nested.write_text(
                "# Getting started\n\nInstall with `npm i @tomtastisch/agent-governance` and then run `npx agent-governance init`.\n",
                encoding="utf-8",
            )
            violations = _current_installation_violations(fixture_root)
        self.assertTrue(any("second normal installation sequence" in violation for violation in violations), violations)

    def test_scanner_rejects_low_level_commands_in_console_fences(self):
        with tempfile.TemporaryDirectory(prefix="agent-governance-docs-console-fence-") as directory:
            fixture_root = Path(directory)
            _copy_current_consumer_documents(fixture_root)
            (fixture_root / "docs" / "getting-started.md").write_text(
                "# Getting started\n\n```console\nagent-governance install --scope global\n```\n",
                encoding="utf-8",
            )
            violations = _current_installation_violations(fixture_root)
        self.assertTrue(any("low-level command outside" in violation for violation in violations), violations)

    def test_scanner_rejects_indented_console_fences(self):
        with tempfile.TemporaryDirectory(prefix="agent-governance-docs-indented-console-fence-") as directory:
            fixture_root = Path(directory)
            _copy_current_consumer_documents(fixture_root)
            (fixture_root / "docs" / "getting-started.md").write_text(
                "# Getting started\n\n   ```console\n   agent-governance install --scope global\n   ```\n",
                encoding="utf-8",
            )
            violations = _current_installation_violations(fixture_root)
        self.assertTrue(any("low-level command outside" in violation for violation in violations), violations)

    def test_scanner_rejects_variable_backtick_and_tilde_fences(self):
        for opener, closer in (("````console", "````"), ("~~~console", "~~~~")):
            with self.subTest(fence=opener), tempfile.TemporaryDirectory(prefix="agent-governance-docs-variable-fence-") as directory:
                fixture_root = Path(directory)
                _copy_current_consumer_documents(fixture_root)
                (fixture_root / "docs" / "getting-started.md").write_text(
                    f"# Getting started\n\n{opener}\nagent-governance install --scope global\n{closer}\n",
                    encoding="utf-8",
                )
                violations = _current_installation_violations(fixture_root)
            self.assertTrue(any("low-level command outside" in violation for violation in violations), violations)

    def test_scanner_rejects_low_level_command_in_tilde_fence_with_backtick_info(self):
        with tempfile.TemporaryDirectory(prefix="agent-governance-docs-tilde-backtick-info-") as directory:
            fixture_root = Path(directory)
            _copy_current_consumer_documents(fixture_root)
            (fixture_root / "docs" / "tilde-info.md").write_text(
                "~~~console title=`manual`\nagent-governance install --scope global\n~~~\n",
                encoding="utf-8",
            )
            violations = _current_installation_violations(fixture_root)
        self.assertTrue(any("low-level command outside" in violation for violation in violations), violations)

    def test_scanner_rejects_direct_binary_path_in_console_fence(self):
        with tempfile.TemporaryDirectory(prefix="agent-governance-docs-direct-binary-") as directory:
            fixture_root = Path(directory)
            _copy_current_consumer_documents(fixture_root)
            (fixture_root / "docs" / "direct-binary.md").write_text(
                "```console\n./node_modules/.bin/agent-governance install --scope global\n```\n",
                encoding="utf-8",
            )
            violations = _current_installation_violations(fixture_root)
        self.assertTrue(any("low-level command outside" in violation for violation in violations), violations)


class CurrentDocumentationBoundaryContract(unittest.TestCase):
    def test_harness_recipes_are_source_linked_and_runtime_neutral(self):
        recipes = HARNESS_RECIPES_PATH.read_text(encoding="utf-8")
        for term in (
            "$HOME/.codex", "$HOME/.claude", "$HOME/.config/opencode",
            "$HOME/.openclaw/workspace", "AGENTS.md", "CLAUDE.md",
            "developers.openai.com/codex/guides/agents-md",
            "code.claude.com/docs/en/memory",
            "opencode.ai/v2/docs/instructions",
            "docs.openclaw.ai/agent-workspace",
        ):
            self.assertIn(term, recipes)
        self.assertIn(
            "https://github.com/tomtastisch/agent-governance/blob/main/docs/harness-recipes.md",
            README,
        )

    def test_threat_model_schema_and_adapter_decision_are_durable(self):
        threat = (ROOT / "docs" / "installer-threat-model.md").read_text(encoding="utf-8")
        schemas = (ROOT / "docs" / "installer-json-schemas.md").read_text(encoding="utf-8")
        audit = (ROOT / "docs" / "adapter-audit.md").read_text(encoding="utf-8")
        for term in ("Trust Boundaries", "Symlink", "TOCTOU", "Receipt", "Residual"):
            self.assertIn(term, threat)
        for term in ("schemaVersion", "OUTDATED", "DOWNGRADE_BLOCKED", "Feldsemantik"):
            self.assertIn(term, schemas)
        for term in ("NO_GO", "rulesync", "uri-templates", "keine Runtime-Abhängigkeit"):
            self.assertIn(term, audit)

    def test_installer_security_contract_has_one_narrow_atomicity_boundary(self):
        threat = (ROOT / "docs" / "installer-threat-model.md").read_text(encoding="utf-8")
        architecture = (ROOT / "docs" / "installer-architecture.md").read_text(encoding="utf-8")
        for term in (
            "## In Scope",
            "## Out of Atomic Guarantee",
            "Same-UID-Final-Component-Co-Writer",
            "kein atomarer Inode-CAS-Vertrag",
            "kein privilegierter Broker",
            "RENAME_NOREPLACE",
            "RENAME_EXCL",
        ):
            self.assertIn(term, threat)
        self.assertIn(
            "https://github.com/tomtastisch/agent-governance/blob/main/docs/installer-threat-model.md",
            README,
        )
        self.assertIn("reale Capability-Probe", threat)
        self.assertIn("verifizierter unveränderlicher Recoveryzustand erhalten", threat)
        for absolute_claim in ("race-free", "TOCTOU-proof", "tamper-proof", "atomic against all concurrent writers"):
            self.assertNotIn(absolute_claim, "\n".join((README, threat, architecture)).lower())

    def test_catchable_and_uncatchable_interruption_boundaries_are_explicit(self):
        architecture = (ROOT / "docs" / "installer-architecture.md").read_text(encoding="utf-8")
        for term in (
            "SIGINT",
            "SIGTERM",
            "PREPARED",
            "SIGKILL",
            "Stromausfall",
        ):
            self.assertIn(term, architecture)
        self.assertNotIn("registriert keine Signalhandler", architecture)
        cli_reference = CLI_REFERENCE_PATH.read_text(encoding="utf-8")
        for code in ("`130`", "`143`"):
            self.assertIn(code, cli_reference)


class InstallerCliReferenceContract(unittest.TestCase):
    def test_reference_is_linked_complete_and_non_normative(self):
        self.assertTrue(CLI_REFERENCE_PATH.is_file())
        reference = CLI_REFERENCE_PATH.read_text(encoding="utf-8")
        self.assertIn("docs/installer-cli-reference.md", README)
        self.assertRegex(reference, r"(?i)nicht normative.+CLI-Bedienreferenz")
        for command in (
            "inspect", "plan", "install", "verify",
            "status", "update", "uninstall", "rollback",
        ):
            self.assertRegex(reference, rf"(?m)^### `?{command}`?$")
        for option in (
            "--scope global", "--installation-root", "--target-root",
            "--entry-file", "--local-rules", "--dry-run", "--json",
            "--non-interactive",
        ):
            self.assertIn(f"`{option}`", reference)
        self.assertNotIn("--harness", reference)
        self.assertRegex(reference, r"(?i)kein cwd-Fallback")
        self.assertRegex(reference, r"(?i)kein implizites (?:Default-)?Ziel")

    def test_reference_is_the_only_packaged_docs_file(self):
        self.assertIn("docs/installer-cli-reference.md", PACKAGE["files"])
        packaged_docs = [entry for entry in PACKAGE["files"] if entry.startswith("docs/")]
        self.assertEqual(packaged_docs, ["docs/installer-cli-reference.md"])

    def test_packaged_reference_uses_absolute_links_for_nonpackaged_current_docs(self):
        reference = CLI_REFERENCE_PATH.read_text(encoding="utf-8")
        expected_counts = {
            "docs/harness-recipes.md": 2,
            "docs/installer-architecture.md": 1,
            "docs/installer-threat-model.md": 1,
            "docs/installer-json-schemas.md": 1,
        }
        for path, count in expected_counts.items():
            absolute = f"https://github.com/tomtastisch/agent-governance/blob/main/{path}"
            with self.subTest(path=path):
                self.assertEqual(reference.count(f"]({absolute})"), count)
                self.assertNotIn(f"]({Path(path).name})", reference)

    def test_current_cli_examples_do_not_retain_the_next_channel(self):
        """Catches a prerelease or current-version literal in the durable CLI contract."""
        reference = CLI_REFERENCE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("@next", reference)
        self.assertNotIn("@tomtastisch/agent-governance@latest", reference)
        self.assertIn("## Advanced: Automation und CI", reference)

    def test_cli_reference_owns_exit_behavior(self):
        """Catches exit behavior being split across lifecycle or schema references."""
        reference = CLI_REFERENCE_PATH.read_text(encoding="utf-8")
        self.assertIn("## Exitverhalten", reference)
        for code in ("`0`", "`2`", "`4`", "`5`", "`6`", "`130`", "`143`"):
            self.assertIn(code, reference)


class HarnessRecipeReferenceContract(unittest.TestCase):
    def test_harness_recipes_keep_each_verified_harness_contract_source_backed(self):
        """Catches a return to undocumented README-owned harness paths."""
        self.assertTrue(HARNESS_RECIPES_PATH.is_file())
        recipes = HARNESS_RECIPES_PATH.read_text(encoding="utf-8")
        contracts = {
            "Advanced: Codex": (
                "${CODEX_HOME:-$HOME/.codex}/AGENTS.md",
                "https://developers.openai.com/codex/guides/agents-md",
            ),
            "Advanced: Claude Code": (
                "$HOME/.claude/CLAUDE.md",
                "https://code.claude.com/docs/en/memory",
            ),
            "Advanced: OpenCode V2": (
                "$XDG_CONFIG_HOME/opencode/AGENTS.md",
                "https://opencode.ai/v2/docs/instructions",
            ),
            "Advanced: OpenClaw": (
                "AGENTS.md",
                "https://docs.openclaw.ai/agent-workspace",
            ),
        }
        for heading, (target, source_url) in contracts.items():
            with self.subTest(heading=heading):
                section = re.search(
                    rf"(?ms)^## {re.escape(heading)}$\n(.*?)(?=^## |\Z)", recipes
                )
                self.assertIsNotNone(section)
                self.assertIn(target, section.group(0))
                self.assertIn(source_url, section.group(0))

    def test_harness_recipes_mark_low_level_examples_as_advanced(self):
        """Catches low-level install commands presented as a normal installation route."""
        recipes = HARNESS_RECIPES_PATH.read_text(encoding="utf-8")
        self.assertIn("npm i @tomtastisch/agent-governance", recipes)
        self.assertIn("npx agent-governance init", recipes)
        self.assertIn("## Advanced: Codex", recipes)
        self.assertIn("## Advanced: Claude Code", recipes)
        self.assertNotIn("@tomtastisch/agent-governance@latest", recipes)


class InstallerArchitectureReferenceContract(unittest.TestCase):
    def test_architecture_uses_the_exact_normal_two_command_entry(self):
        architecture = (ROOT / "docs" / "installer-architecture.md").read_text(encoding="utf-8")
        self.assertIn(
            "`npm i @tomtastisch/agent-governance` gefolgt von\n`npx agent-governance init`",
            architecture,
        )

    def test_architecture_retains_the_managed_block_recovery_contract(self):
        """Catches loss of durable managed-block and retained-recovery semantics after migration."""
        architecture = (ROOT / "docs" / "installer-architecture.md").read_text(encoding="utf-8")
        for term in (
            "<!-- BEGIN AGENT_GOVERNANCE_MANAGED_V1 -->",
            "<!-- END AGENT_GOVERNANCE_MANAGED_V1 -->",
            "Außenbytes",
            "LF-/CRLF-Zeilenenden",
            "doppelte, unvollständige, fremde oder manipulierte Marker scheitern fail-closed",
            "entry.bin",
        ):
            self.assertIn(term, architecture)
        self.assertRegex(
            architecture,
            r"weder von Uninstall noch durch spätere Transaktionen implizit\s+gelöscht",
        )

    def test_architecture_links_to_schema_owner_instead_of_enumerating_json_or_exits(self):
        """Catches a second JSON or exit-code contract in the lifecycle reference."""
        architecture = (ROOT / "docs" / "installer-architecture.md").read_text(encoding="utf-8")
        self.assertIn("[JSON-Schemas](installer-json-schemas.md)", architecture)
        self.assertNotIn("JSON-Schema 1 nennt", architecture)
        self.assertNotIn("Exitcodes sind", architecture)


class ReleaseMetadataContract(unittest.TestCase):
    def test_documentation_release_metadata_is_version_derived(self):
        self.assertEqual(PACKAGE["version"], VERSION)
        self.assertEqual(PACKAGE_LOCK["version"], VERSION)
        self.assertEqual(PACKAGE_LOCK["packages"][""]["version"], VERSION)
        self.assertIn("## Support und Lizenz", README)
        self.assertIn("https://buymeacoffee.com/tomtastisch", README)
        self.assertIn(PACKAGE["license"], README)
        current = CHANGELOG.split(f"## [{VERSION}]", 1)[1].split("\n## [", 1)[0]
        for term in (
            "init",
            "npm i @tomtastisch/agent-governance",
            "@clack/prompts",
            "smol-toml",
            "Package Manager",
            "Drei-Command-Quickstart",
        ):
            self.assertIn(term, current)
        self.assertIn("**Breaking changes:** none", current)
        recovery_patch = CHANGELOG.split("## [0.4.1]", 1)[1].split("\n## [", 1)[0]
        self.assertIn("**Breaking changes:** none", recovery_patch)
        historical = CHANGELOG.split("## [0.4.0]", 1)[1].split("\n## [", 1)[0]
        for term in (
            "Manifest-Schema 2",
            "catalogs/triggers.toml",
            "catalogs/policy-tags.toml",
            "catalogs/scopes.toml",
            "catalogs/tools.toml",
            "**BREAKING:**",
        ):
            self.assertIn(term, historical)
        self.assertIn("**Breaking changes:** present", historical)

    def test_published_032_recovery_metadata_remains_historical(self):
        self.assertIn("## [0.3.2] — 2026-08-15", CHANGELOG)
        section = CHANGELOG.split("## [0.3.2]", 1)[1].split("\n## [", 1)[0]
        for term in (
            "Allowed-Signers",
            "fingerprint",
            "Release-Verifikation",
            "v0.3.1",
            "ohne GitHub Release",
        ):
            self.assertIn(term, section)
        self.assertIn("**Breaking changes:** none", section)


if __name__ == "__main__":
    unittest.main()
