#!/usr/bin/env python3
"""Konsistenz- und Drift-Tests für das Agent-Governance-Regelwerk (Kern §9, §11, §13).

Diese Suite greift real: sie liest die Regelwerksdateien und schlägt fehl, sobald eine Quelle
gegen eine andere driftet (z. B. eine Regel nennt einen Port, den kein Adapter definiert; ein
Werkzeug im Brewfile fehlt im Katalog `tools/tools.md`; ein §-Verweis zeigt ins Leere). Ziel:
die SSOT-Zusagen des Kerns ohne menschliche Pflege überprüfbar halten.

Ausführung ohne Fremdabhängigkeiten:
    python3 -m unittest discover -s tests

Die `core/branch-tags.toml`-Validierung nutzt das stdlib-Modul `tomllib` (Python 3.11+); auf
älteren Interpretern überspringt sich nur dieser Prüfblock sauber, die übrigen Checks laufen
weiter. CI pinnt 3.11 und erzwingt daher die volle Prüfung.
"""
import os
import re
import unittest

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11: nur die TOML-Prüfung entfällt, Rest läuft weiter.
    tomllib = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def exists(rel):
    return os.path.exists(os.path.join(ROOT, rel))


def load_toml(rel):
    with open(os.path.join(ROOT, rel), "rb") as fh:
        return tomllib.load(fh)


def tracked_markdown(exclude=()):
    """Alle .md-Dateien des Repos, ohne .git/tests/.github und ohne explizite Ausnahmen."""
    out = []
    skip_dirs = {".git", "tests", ".github"}
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for name in files:
            if not name.endswith(".md"):
                continue
            rel = os.path.relpath(os.path.join(base, name), ROOT)
            if rel not in exclude:
                out.append(rel)
    return out


def first_column_keys(text):
    """Backtick-Schlüssel der ersten Tabellenspalte: `| \\`key\\` | ... |`."""
    return set(re.findall(r"(?m)^\|\s*`([^`]+)`\s*\|", text))


def get_section(text, heading):
    """Text zwischen einer `## Überschrift` und der nächsten `## `-Überschrift."""
    m = re.search(r"(?m)^" + re.escape(heading) + r"\s*$", text)
    if not m:
        return ""
    start = m.end()
    nxt = re.search(r"(?m)^##\s", text[start:])
    return text[start:start + nxt.start()] if nxt else text[start:]


CORE = read("core/core.md")
CLAUDE = read("adapters/claude.md")
CODEX = read("adapters/codex.md")
README = read("README.md")
PROFILE_EX = read("profile/profile.example.md")
TOOLS = read("tools/tools.md")
BREW = read("tools/Brewfile")
BREW_OPT = read("tools/Brewfile.optional")
TPL_CLAUDE = read("templates/CLAUDE.md")
TPL_CODEX = read("templates/AGENTS.md")
TPL_README = read("templates/README.md")
QA_ROLE = read("core/roles/qa.md")
SEC_ROLE = read("core/roles/sec.md")
TPL_QA = read("templates/claude-agents/qa-agent.md")
TPL_SEC = read("templates/claude-agents/sec-agent.md")

ROLES = ("ak", "st", "qa", "sec")


class PortContract(unittest.TestCase):
    """Kern ↔ Adapter ↔ README-Port-Vertrag: jede referenzierte Bindung ist definiert."""

    def setUp(self):
        self.readme_ports = first_column_keys(get_section(README, "## Port-Vertrag"))
        self.claude_keys = first_column_keys(get_section(CLAUDE, "## Bindings"))
        self.codex_keys = first_column_keys(get_section(CODEX, "## Bindings"))
        # `key` ist im Intro nur ein Format-Beispiel (`[BINDING:key]`), kein echter Schlüssel.
        self.used = set(re.findall(r"\[BINDING:([a-z0-9_.]+)\]", CORE)) - {"key"}

    def test_readme_declares_ports(self):
        self.assertTrue(self.readme_ports, "Port-Vertrag-Tabelle in README nicht gefunden")

    def test_used_bindings_are_declared(self):
        missing = self.used - self.readme_ports
        self.assertFalse(missing, f"Im Kern genutzte, aber im Port-Vertrag fehlende Bindungen: {missing}")

    def test_each_adapter_realizes_every_declared_port(self):
        for name, txt in (("claude", CLAUDE), ("codex", CODEX)):
            for key in self.readme_ports:
                self.assertIn(f"`{key}`", txt, f"Adapter {name} realisiert Port '{key}' nicht")

    def test_adapters_define_no_undeclared_binding(self):
        for name, keys in (("claude", self.claude_keys), ("codex", self.codex_keys)):
            extra = keys - self.readme_ports
            self.assertFalse(extra, f"Adapter {name} definiert nicht deklarierte Bindung(en): {extra}")


class ProfileContract(unittest.TestCase):
    def setUp(self):
        self.profile_keys = first_column_keys(PROFILE_EX)
        self.used = set(re.findall(r"\[PROFILE:([a-z0-9_.]+)\]", CORE)) - {"key"}

    def test_used_profile_keys_defined(self):
        missing = self.used - self.profile_keys
        self.assertFalse(missing, f"Im Kern genutzte, aber im Profil fehlende Schlüssel: {missing}")

    def test_readme_mentions_every_profile_key(self):
        for key in self.profile_keys:
            self.assertIn(f"`{key}`", README, f"README nennt Profilschlüssel '{key}' nicht")


class SectionReferences(unittest.TestCase):
    def setUp(self):
        self.nums = [int(n) for n in re.findall(r"(?m)^## (\d+)\.", CORE)]

    def test_sections_contiguous(self):
        self.assertEqual(self.nums, list(range(1, len(self.nums) + 1)),
                         "Kern-Abschnitte sind nicht lückenlos von 1 an nummeriert")

    def test_no_dangling_section_reference(self):
        valid = set(self.nums)
        for rel in ["core/core.md", "core/roles/qa.md", "core/roles/ak.md",
                    "core/roles/st.md", "core/roles/sec.md", "tools/tools.md"]:
            for ref in re.findall(r"§(\d+)", read(rel)):
                self.assertIn(int(ref), valid, f"{rel}: Verweis §{ref} zeigt auf keinen Abschnitt")


class Roles(unittest.TestCase):
    def test_role_extension_files_exist(self):
        for r in ROLES:
            self.assertTrue(exists(f"core/roles/{r}.md"), f"Rollenerweiterung core/roles/{r}.md fehlt")

    def test_subagent_wrappers_exist(self):
        for r in ROLES:
            self.assertTrue(exists(f"templates/claude-agents/{r}-agent.md"),
                            f"Subagent-Wrapper {r}-agent.md fehlt")

    def test_core_routing_table_lists_roles(self):
        routing = get_section(CORE, "## 6. Rollen & Routing")
        for r in ROLES:
            self.assertRegex(routing, rf"\b{r.upper()}\b", f"§6 nennt Rolle {r.upper()} nicht")


class PathFreeCore(unittest.TestCase):
    """Der Kern bleibt pfadfrei; nur Adapter/Templates kennen den Root-Pfad (templates/README)."""

    def test_core_has_no_root_path(self):
        core_dir = os.path.join(ROOT, "core")
        for base, _dirs, files in os.walk(core_dir):
            for name in files:
                if name.endswith(".md"):
                    txt = read(os.path.relpath(os.path.join(base, name), ROOT))
                    self.assertNotIn("~/agent-governance", txt,
                                     f"core/{name} enthält einen Root-Pfad — Kern muss pfadfrei sein")


class ToolsCatalog(unittest.TestCase):
    def test_no_leftover_toml_manifest(self):
        self.assertFalse(exists("tools/tools.toml"), "tools/tools.toml sollte konsolidiert (entfernt) sein")

    def test_no_file_references_toml(self):
        # tools.md darf die Ablösung historisch erwähnen; sonst kein Verweis auf das alte Manifest.
        for rel in tracked_markdown(exclude=("tools/tools.md",)):
            self.assertNotIn("tools.toml", read(rel), f"{rel} verweist noch auf das entfernte tools.toml")

    def test_brewfiles_documented_and_correctly_classified(self):
        # Der Standard-Pfad (Brewfile) darf keine freigabepflichtigen (optionalen) Werkzeuge
        # mitziehen: Pflichtpakete stehen als erforderlich, optionale als optional in tools.md.
        cli = get_section(TOOLS, "## CLI-Grundwerkzeuge")
        self.assertTrue(cli, "Abschnitt '## CLI-Grundwerkzeuge' in tools/tools.md fehlt")
        req_line = next((ln for ln in cli.splitlines() if "erforderlich" in ln), "")
        opt_line = next((ln for ln in cli.splitlines() if "Optional empfohlen" in ln), "")
        req_doc = set(re.findall(r"`([^`]+)`", req_line))
        opt_doc = set(re.findall(r"`([^`]+)`", opt_line))
        req_pkgs = set(re.findall(r'brew\s+"([^"]+)"', BREW))
        opt_pkgs = set(re.findall(r'brew\s+"([^"]+)"', BREW_OPT))
        self.assertTrue(req_pkgs, "Erforderliches Brewfile enthält keine Pakete")
        both = req_pkgs & opt_pkgs
        self.assertFalse(both, f"Paket in erforderlichem UND optionalem Brewfile: {both}")
        for pkg in req_pkgs:
            self.assertIn(pkg, req_doc,
                          f"Pflichtpaket '{pkg}' ist in tools/tools.md nicht als erforderlich dokumentiert")
        for pkg in opt_pkgs:
            self.assertIn(pkg, opt_doc,
                          f"Optionales Paket '{pkg}' ist in tools/tools.md nicht als optional dokumentiert")

    def test_every_tool_entry_is_complete(self):
        # Jeder ###-Eintrag braucht eine Freigabe-Kennzeichnung und einen Installationsblock.
        blocks = re.split(r"(?m)^### ", TOOLS)[1:]
        self.assertTrue(blocks, "tools/tools.md enthält keine Werkzeug-Einträge (###)")
        for block in blocks:
            title = block.splitlines()[0].strip()
            self.assertRegex(block, r"(Standard-Setup|Optional empfohlen)",
                             f"Werkzeug '{title}' ohne Freigabe-Kennzeichnung")
            self.assertIn("```", block, f"Werkzeug '{title}' ohne Installationsblock")

    def test_links_are_well_formed(self):
        for url in re.findall(r"https?://\S+", TOOLS):
            url = url.rstrip(">).,")
            self.assertRegex(url, r"^https?://[^\s]+\.[^\s]+$", f"Ungültige URL-Form: {url}")


class Templates(unittest.TestCase):
    def test_claude_imports_resolve(self):
        for imp in re.findall(r"@~/agent-governance/(\S+)", TPL_CLAUDE):
            if imp == "profile/profile.md":
                # profile.md ist nutzerlokal (.gitignore) — im Repo liegt nur das Beispiel.
                self.assertTrue(exists("profile/profile.example.md"),
                                "profile/profile.example.md fehlt")
            else:
                self.assertTrue(exists(imp), f"Import {imp} in templates/CLAUDE.md zeigt ins Leere")


class InteractionPolicyWiring(unittest.TestCase):
    """Ausgabepolicy: eine TOML-SSOT, ehrliche Harness-Grenzen und geschlossene Doku."""

    POLICY = "core/interaction.toml"
    ENTRY_ARTIFACTS = {
        "adapters/claude.md": CLAUDE,
        "adapters/codex.md": CODEX,
        "templates/CLAUDE.md": TPL_CLAUDE,
        "templates/AGENTS.md": TPL_CODEX,
    }

    def test_entry_wiring_loads_the_single_policy_before_voluntary_status(self):
        self.assertIn("@~/agent-governance/core/interaction.toml", TPL_CLAUDE)
        self.assertIn("~/agent-governance/core/interaction.toml", TPL_CODEX)
        self.assertIn(self.POLICY, TPL_README)
        self.assertIn("intermediate_status", CORE)
        self.assertTrue(exists(self.POLICY), "Die zentrale Ausgabepolicy fehlt")

    def test_checked_in_policy_has_the_fail_closed_default(self):
        if tomllib is None:
            self.skipTest("tomllib ist erst ab Python 3.11 verfügbar")
        policy = load_toml(self.POLICY)
        self.assertIs(policy["output"]["intermediate_status"], False)

    def test_adapters_and_templates_do_not_assign_a_second_default(self):
        assignment = re.compile(
            r"(?im)^\\s*intermediate_status\\s*=\\s*(?:true|false)\\s*$"
        )
        for rel, text in self.ENTRY_ARTIFACTS.items():
            self.assertNotRegex(text, assignment, f"{rel} dupliziert den TOML-Default")

    def test_capability_table_keeps_prompt_based_harnesses_best_effort(self):
        for harness in ("Claude Code", "Codex", "MCP-Orchestrator", "anderer Harness"):
            self.assertIn(f"| {harness} |", README, f"Fähigkeitstabelle fehlt für {harness}")
        self.assertEqual(
            README.count("promptbasiert/best-effort"),
            2,
            "Nur Claude Code und Codex dürfen vor externen Abnahmefällen best-effort heißen",
        )
        self.assertIn("abhängig vom Zielharness", README)
        self.assertIn("zunächst unbekannt", README)
        self.assertIn("externen Akzeptanzfällen", README)

    def test_true_keeps_normal_harness_status_without_overriding_mandatory_output(self):
        for rel, document in (("core/core.md", CORE), ("README.md", README)):
            self.assertIn("intermediate_status = true", document, f"{rel} fehlt die true-Semantik")
            self.assertIn(
                "normale Harness-Zwischenstatusverhalten unverändert",
                document,
                f"{rel} beschreibt die true-Semantik nicht geschlossen",
            )
            self.assertRegex(
                document,
                r"[Hh]öher priorisierte System- oder Harnesspflichten.*(?:gehen|haben).*vor",
                f"{rel} lässt die nicht übersteuerbare Ausgabepflicht offen",
            )

    def test_readme_and_install_document_the_read_only_cli_contract(self):
        for rel, document in (("README.md", README), ("INSTALL.md", read("INSTALL.md"))):
            self.assertIn(
                "python3 -m review_routing output-policy --json",
                document,
                f"{rel} dokumentiert den vierten read-only Befehl nicht",
            )
            self.assertIn(self.POLICY, document, f"{rel} referenziert die Default-SSOT nicht")
            self.assertIn("schema_version", document, f"{rel} nennt das Erfolgsschema nicht")
            self.assertIn("intermediate_status", document, f"{rel} nennt das Erfolgsschema nicht")
            self.assertIn("Exit 31", document, f"{rel} dokumentiert den Fehler-Exit nicht")
            self.assertIn("sanitisiert", document, f"{rel} dokumentiert den sanitisierten Fehlervertrag nicht")


class ReviewRoutingDocumentation(unittest.TestCase):
    """Routingprosa referenziert die SSOT, statt deren Matrix zu duplizieren."""

    POLICY = "core/review-routing.toml"
    ADR = "docs/decisions/0003-review-routing.md"
    ARTIFACTS = {
        "core/core.md": CORE,
        "core/roles/qa.md": QA_ROLE,
        "core/roles/sec.md": SEC_ROLE,
        "adapters/claude.md": CLAUDE,
        "adapters/codex.md": CODEX,
        "templates/claude-agents/qa-agent.md": TPL_QA,
        "templates/claude-agents/sec-agent.md": TPL_SEC,
        "README.md": README,
        "INSTALL.md": read("INSTALL.md"),
        "tools/tools.md": TOOLS,
    }

    def test_every_routing_artifact_references_the_policy_ssot(self):
        for rel, text in self.ARTIFACTS.items():
            self.assertIn(self.POLICY, text, f"{rel} verweist nicht auf die Routing-SSOT")

    def test_governance_prose_does_not_duplicate_route_cells(self):
        forbidden_route_literals = ("`copilot_qa`", "`copilot_qa_sec`", "`qa_sec`")
        matrix_row = re.compile(
            r"(?m)^\|\s*`?(?:low|medium|high|critical)`?\s*\|.*"
            r"(?:local_checks|copilot_qa|copilot_qa_sec|qa_sec)"
        )
        for rel, text in self.ARTIFACTS.items():
            for literal in forbidden_route_literals:
                self.assertNotIn(literal, text, f"{rel} dupliziert die maschinelle Routingmatrix")
            self.assertNotRegex(text, matrix_row, f"{rel} enthält eine zweite Routingtabelle")

    def test_core_has_one_policy_invariant_and_no_unconditional_cluster_qa(self):
        checkpoint = get_section(CORE, "## 5. Arbeitsweise (iterativ)")
        gate = get_section(CORE, "## 16. Review- & Merge-Gate (fail-closed)")
        for token in (
            "copilot_usable = false",
            "QA",
            "`high`",
            "critical",
            "security_relevant",
            "SEC",
            "Korrekturrunde",
            "neuen Head",
            "explizite Einzelfreigabe",
        ):
            self.assertIn(token, gate, f"Kern §16 fehlt Routing-Invariante '{token}'")
        self.assertIn(self.POLICY, checkpoint)
        self.assertIn(self.POLICY, gate)
        stale = (
            "nach dessen Grün den gelieferten Exact Head durch einen unabhängigen QA-Agenten",
            "laufende Cluster-QA",
            "laufenden Cluster-QA",
            "laufend je fertiggestelltem Cluster-Push",
            "Ausgelöst laufend je Cluster-Push",
            "QA-Alternativpfad und die laufende Cluster-QA",
        )
        for phrase in stale:
            for rel, text in self.ARTIFACTS.items():
                self.assertNotIn(phrase, text, f"{rel} verlangt noch pauschale Cluster-QA")

    def test_cli_documentation_matches_the_closed_interface(self):
        installation = self.ARTIFACTS["INSTALL.md"]
        for document_name, document in (
            ("README.md", README),
            ("INSTALL.md", installation),
            ("tools/tools.md", TOOLS),
        ):
            for command in (
                "python3 -m review_routing probe",
                "python3 -m review_routing route",
                "python3 -m review_routing validate",
            ):
                self.assertIn(command, document, f"{document_name} fehlt '{command}'")
            for option in (
                "--repo",
                "--pull-request",
                "--review-mode",
                "--requester",
                "--purpose",
                "--repo-path",
                "--route-file",
                "--evidence-file",
                "--json",
            ):
                self.assertIn(option, document, f"{document_name} fehlt CLI-Option '{option}'")
            self.assertIn("manual", document)
            self.assertIn("automatic", document)
            self.assertNotRegex(
                document,
                r"--(?:billing|budget|trust|runtime-digest|expected-digest)\b",
                f"{document_name} dokumentiert ein nicht existentes Trust-/Billing-Flag",
            )

        for document_name, document in (("README.md", README), ("INSTALL.md", installation)):
            self.assertIn(
                "python3 -m review_routing output-policy --json",
                document,
                f"{document_name} fehlt der vierte geschlossene CLI-Befehl",
            )

    def test_operational_boundaries_are_explicit(self):
        for token in (
            "Plan: read",
            "trusted_base_policy_missing",
            "Task 5",
            "Task 6",
            "preliminary",
            "Issue #3",
            "explizite Einzelfreigabe",
            "GitHub-Copilot",
            "Live-Positivtest",
            self.ADR,
        ):
            self.assertIn(token, README, f"README fehlt Betriebsgrenze '{token}'")
        for adapter_name, adapter in (("Claude", CLAUDE), ("Codex", CODEX)):
            for command in ("python3 -m review_routing route", "python3 -m review_routing validate"):
                self.assertIn(command, adapter, f"{adapter_name}-Adapter fehlt '{command}'")
            self.assertIn("explizite Einzelfreigabe", adapter)


class TaskSixDesignContract(unittest.TestCase):
    """Task 6 bleibt formal auf frische Evidenz statt auf den Task-5-Vorplan verdrahtet."""

    def setUp(self):
        self.spec = read(
            "docs/superpowers/specs/2026-07-26-review-routing-and-output-policy-design.md"
        )
        plan = read("docs/superpowers/plans/2026-07-26-review-routing.md")
        self.task_two = plan.split("### Task 2:", 1)[1].split("### Task 3:", 1)[0]
        self.task_six = plan.split("### Task 6:", 1)[1].split("### Task 7:", 1)[0]
        self.adr = read("docs/decisions/0003-review-routing.md")

    def test_gate_evaluation_context_is_complete_and_non_authoritative(self):
        required = (
            "PreliminaryRoutePlan",
            "GateEvaluationContext",
            "preliminary_plan",
            "current_pr_state",
            "probe_request",
            "fresh_probe",
            "reviewer_availability",
            "evaluated_at",
            "valid_until",
            "coverage_complete",
            "copilot_review_mode",
            "coverage_source",
            "review_mode_source",
            "untrusted preliminary",
        )
        for token in required:
            self.assertIn(token, self.spec, f"Design-Spec fehlt Task-6-Vertrag '{token}'")
            self.assertIn(token, self.task_six, f"Task-6-Plan fehlt Vertrag '{token}'")
        self.assertNotIn(
            "decision: RouteDecision",
            self.task_six,
            "Task 6 darf die vorläufige RouteDecision nicht als Validierungsautorität übernehmen",
        )
        for document in (self.spec, self.task_six, self.adr):
            self.assertIn(
                "probe_request_digest",
                document,
                "Digest muss ausdrücklich als nicht rekonstruierbare Nicht-Autorität dokumentiert sein",
            )

    def test_validate_cli_requires_the_fresh_probe_context(self):
        for token in (
            "--review-mode",
            "--requester",
            "--organization",
            "--enterprise",
            "--cost-center",
            "--capability-reference",
        ):
            self.assertIn(token, self.task_six, f"Task-6-CLI fehlt '{token}'")
        for token in (
            "ProbePort",
            "ReviewerAvailabilityPort",
            "PullRequestStatePort",
            "ClockPort",
        ):
            self.assertIn(token, self.task_six, f"Task-6-CliDependencies fehlt '{token}'")

    def test_correction_latest_event_and_result_digest_contract_cannot_drift(self):
        required = (
            "PriorGateEvidence",
            "PriorGateEvidencePort",
            "load_immediate",
            "correction_prior_gate_unavailable",
            "gate_result_digest",
            "event_id",
            "DISMISSED",
            "event_at <= source.observed_at",
            "evaluated_at < snapshot.valid_until",
            "Issue #3",
            "Findings-Correction",
            "adjusted_prior_floor UNION current_final_exact_head_matrix_floor",
        )
        for document_name, document in (
            ("Design-Spec", self.spec),
            ("Task-6-Plan", self.task_six),
            ("ADR 0003", self.adr),
        ):
            for token in required:
                self.assertIn(
                    token,
                    document,
                    f"{document_name} fehlt korrigierten Task-6-Vertrag '{token}'",
                )

    def test_task_two_correction_contract_is_explicitly_superseded_by_task_six(self):
        self.assertIn(
            "adjusted_prior_floor UNION current_final_exact_head_matrix_floor",
            self.task_two,
            "Task 2 darf nicht mehr nur die historische Reviewer-Menge als Correction-Vertrag nennen",
        )
        self.assertIn(
            "Task 6",
            self.task_two,
            "Der frühe Zwischenstand muss seine verbindliche Ablösung ausdrücklich benennen",
        )


class BranchTags(unittest.TestCase):
    """`core/branch-tags.toml` ist wohlgeformt, git-ref-sicher und driftfrei mit dem Kern (§15)."""

    TAG_RE = re.compile(r"^[a-z][a-z0-9-]*$")
    TOML_REL = "core/branch-tags.toml"

    def setUp(self):
        if tomllib is None:
            self.skipTest("tomllib erfordert Python 3.11+; TOML-Validierung nur dort")
        self.assertTrue(exists(self.TOML_REL), f"{self.TOML_REL} fehlt")
        self.data = load_toml(self.TOML_REL)
        self.entries = self.data.get("tags", [])

    def test_has_entries(self):
        self.assertTrue(self.entries, "core/branch-tags.toml enthält keine [[tags]]-Einträge")

    def test_entries_complete(self):
        for i, e in enumerate(self.entries):
            for field in ("tag", "name", "description"):
                val = e.get(field)
                self.assertTrue(isinstance(val, str) and val.strip(),
                                f"[[tags]]-Eintrag #{i} ohne nicht-leeres Feld '{field}'")

    def test_tags_ref_safe(self):
        for e in self.entries:
            tag = e.get("tag", "")
            self.assertRegex(tag, self.TAG_RE,
                             f"Tag '{tag}' ist nicht git-ref-sicher (Kleinbuchstaben/Ziffern/'-', "
                             f"Beginn mit Buchstabe)")

    def test_tags_unique(self):
        tags = [e.get("tag") for e in self.entries]
        dupes = {t for t in tags if tags.count(t) > 1}
        self.assertFalse(dupes, f"Doppelte Tags in core/branch-tags.toml: {dupes}")

    def test_default_refers_to_existing_tag(self):
        default = self.data.get("default")
        self.assertTrue(default, "core/branch-tags.toml deklariert keinen 'default'-Tag")
        self.assertIn(default, {e.get("tag") for e in self.entries},
                      f"'default = \"{default}\"' zeigt auf keinen definierten Tag")

    def test_core_references_tag_file(self):
        self.assertIn(self.TOML_REL, CORE,
                      "Kern §15 verweist nicht auf core/branch-tags.toml (Drift)")

    def test_retired_binding_absent(self):
        # Der abgelöste Agenten-Präfix-Port darf nirgends mehr referenziert werden.
        for rel in ("core/core.md", "README.md", "adapters/claude.md", "adapters/codex.md"):
            self.assertNotIn("vcs.branch_prefix", read(rel),
                             f"{rel} verweist noch auf den abgelösten Port vcs.branch_prefix")


if __name__ == "__main__":
    unittest.main()
