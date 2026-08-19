# Copilot-QA-Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Historische Evidenz - nicht normativ.** Dieser Plan dokumentiert die Umsetzung des
> freigegebenen Specs `docs/superpowers/specs/2026-08-19-copilot-qa-binding-design.md`.
> Normative Governance liegt ausschließlich unter `bundle/`.

**Goal:** GitHub Copilot PR Review über ein dünnes repository-natives Binding deterministisch an die QA-Governance binden, die Binding-Voraussetzung in `DEL-008` normativ verankern und optionales Parallel-QA als `DEL-010` ergänzen.

**Architecture:** `.github/copilot-instructions.md` wird ein bewusst kleiner Consumer-Wrapper, der ausschließlich auf die kanonischen Bundle-Dateien desselben PR-Heads verweist. Ein neuer mechanischer Test `tests/test_copilot_qa_binding.py` prüft Existenz, Nichtnormativität, Referenzintegrität und die Delivery-Verträge. `delivery.md` erhält die minimale `DEL-008`-Erweiterung und die neue `DEL-010`-Regel.

**Tech Stack:** Markdown, TOML, Python 3.11 Standardbibliothek (`unittest`, `tomllib`), lokale Git-CLI, GitHub CLI `gh`.

## Global Constraints

- Kein Python-Materializer, kein Generator, keine SHA-/Body-Synchronisationsengine, keine eigene Distribution-Engine.
- `.github/copilot-instructions.md` enthält keine vollständige Kopie der QA-Rolle und keine eigene `### XXX-000 —`-Regel.
- Keine `$HOME`-, absoluten Host-, HTTP-/HTTPS- oder GitHub-URL-Includes im Binding.
- `github_cli.required_on == ["github_remote"]` und der gesamte `microsoft_apm`-Eintrag bleiben unverändert.
- Keine Manifest-, Katalog-, Rollen- oder `tools.toml`-Änderung.
- Normative QA-/Delivery-Semantik bleibt ausschließlich unter `bundle/`.

---

## Dateiverantwortung

- `.github/copilot-instructions.md`: dünner Consumer-/Binding-Wrapper mit repository-lokalen Referenzen.
- `tests/test_copilot_qa_binding.py`: mechanische Referenz-, Rule-ID- und Delivery-Verträge.
- `bundle/agent-governance/modules/delivery.md`: `DEL-008`-Erweiterung und neue `DEL-010`-Regel.
- `CHANGELOG.md`: Unreleased-Eintrag.
- `docs/superpowers/plans/2026-08-19-copilot-qa-binding.md`: dieser Plan (nicht normativ).

### Task 1: Roter mechanischer Vertragstest

**Files:**
- Create: `tests/test_copilot_qa_binding.py`

**Interfaces:**
- Consumes: nichts.
- Produces: die Testklassen `BindingArtifactContract`, `DeliveryContract` und `ToolRoutingContract` sowie die Hilfsfunktionen `normative_files()`, `rule_definitions()` und `binding_violations(text)`.

- [ ] **Step 1: Schreibe die Testdatei vollständig**

```python
#!/usr/bin/env python3
"""Copilot-QA-Binding: mechanische Referenz- und Delivery-Verträge."""

from __future__ import annotations

from pathlib import Path
import re
import unittest

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Projekt erfordert Python 3.11+
    tomllib = None


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "bundle"
GOVERNANCE_ROOT = BUNDLE / "agent-governance"
MANIFEST = GOVERNANCE_ROOT / "manifest.toml"
BINDING = ROOT / ".github" / "copilot-instructions.md"
DELIVERY = GOVERNANCE_ROOT / "modules" / "delivery.md"

RULE_DEF_RE = re.compile(r"(?m)^### ([A-Z][A-Z0-9-]*-\d{3}) — ")
RULE_TOKEN_RE = re.compile(r"\b[A-Z][A-Z0-9-]*-\d{3}\b")

EXPECTED_BINDING_PATHS = (
    "bundle/agent-governance/roles/quality-assurance.md",
    "bundle/agent-governance/modules/delivery.md",
    "bundle/agent-governance/modules/tool-routing.md",
)
EXPECTED_BINDING_RULE_IDS = ("DEL-002", "DEL-003", "DEL-007", "DEL-008", "DEL-009", "TOL-004")


def normative_files() -> list[Path]:
    return [
        BUNDLE / "GOVERNANCE.md",
        *sorted((GOVERNANCE_ROOT / "modules").glob("*.md")),
        *sorted((GOVERNANCE_ROOT / "roles").glob("*.md")),
    ]


def rule_definitions() -> dict[str, list[Path]]:
    definitions: dict[str, list[Path]] = {}
    for path in normative_files():
        for rule_id in RULE_DEF_RE.findall(path.read_text(encoding="utf-8")):
            definitions.setdefault(rule_id, []).append(path.resolve())
    return definitions


def binding_violations(text: str) -> list[str]:
    violations: list[str] = []
    if re.search(r"https?://", text):
        violations.append("HTTP(S)-URL")
    if re.search(r"(?:^|[\s`])(?:~/|/Users/|/home/|\$HOME/)", text):
        violations.append("Home-/Host-Pfad")
    for span in re.findall(r"`([^`]+)`", text):
        candidate = span.strip()
        if candidate.startswith("bundle/") and not (ROOT / candidate).is_file():
            violations.append(f"nicht auflösbarer Pfad: {candidate}")
    definitions = rule_definitions()
    for rule_id in sorted(set(RULE_TOKEN_RE.findall(text))):
        if len(definitions.get(rule_id, [])) != 1:
            violations.append(f"Rule-ID nicht eindeutig: {rule_id}")
    return violations


class BindingArtifactContract(unittest.TestCase):
    def setUp(self):
        self.text = BINDING.read_text(encoding="utf-8")

    def test_binding_file_exists(self):
        self.assertTrue(BINDING.is_file())

    def test_binding_is_non_normative_consumer_artifact(self):
        self.assertRegex(self.text, r"(?i)nicht normativ")
        self.assertRegex(self.text, r"(?i)Consumer")
        self.assertNotRegex(self.text, RULE_DEF_RE)

    def test_binding_references_canonical_paths(self):
        for path in EXPECTED_BINDING_PATHS:
            self.assertIn(path, self.text, path)

    def test_binding_rule_ids_exist_exactly_once(self):
        definitions = rule_definitions()
        for rule_id in EXPECTED_BINDING_RULE_IDS:
            self.assertIn(rule_id, self.text, rule_id)
            self.assertEqual(len(definitions.get(rule_id, [])), 1, rule_id)

    def test_binding_has_no_violations(self):
        self.assertEqual(binding_violations(self.text), [])

    def test_binding_is_small_and_copies_no_rule_set(self):
        self.assertLessEqual(self.text.count("\n") + 1, 80)
        source = "\n".join(
            (GOVERNANCE_ROOT / "roles" / "quality-assurance.md").read_text(encoding="utf-8"),
            (GOVERNANCE_ROOT / "modules" / "delivery.md").read_text(encoding="utf-8"),
        )
        source_paragraphs = {
            " ".join(p.split()) for p in re.split(r"\n\s*\n", source)
            if len(" ".join(p.split())) >= 80
        }
        for paragraph in re.split(r"\n\s*\n", self.text):
            normalized = " ".join(paragraph.split())
            self.assertNotIn(normalized, source_paragraphs, normalized[:80])

    def test_binding_reference_mutation_fails(self):
        bad = (
            "Referenz auf `bundle/agent-governance/roles/qualitaetssicherung.md` und DEL-999.\n"
            "Zusätzlich https://example.com/include."
        )
        violations = binding_violations(bad)
        self.assertIn(
            "nicht auflösbarer Pfad: bundle/agent-governance/roles/qualitaetssicherung.md",
            violations,
        )
        self.assertIn("Rule-ID nicht eindeutig: DEL-999", violations)
        self.assertIn("HTTP(S)-URL", violations)


class DeliveryContract(unittest.TestCase):
    def setUp(self):
        self.delivery = DELIVERY.read_text(encoding="utf-8")

    def test_del_008_requires_valid_binding(self):
        self.assertRegex(
            self.delivery,
            r"(?is)GitHub Copilot.+bevorzugte QA-Provider.+Exact-Head-SHA.+"
            r"`.github/copilot-instructions.md`.+auflösbaren",
        )

    def test_del_008_keeps_independent_fallback(self):
        self.assertIn("`no`", self.delivery)
        self.assertIn("`unknown`", self.delivery)
        self.assertRegex(self.delivery, r"frischer\s+unabhängiger read-only")

    def test_del_010_defines_opt_in_parallel_qa(self):
        self.assertRegex(self.delivery, r"(?m)^### DEL-010 — ")
        self.assertRegex(self.delivery, r"(?is)DEL-010")
        self.assertRegex(self.delivery, r"(?is)nicht standardmäßig")
        self.assertRegex(self.delivery, r"(?is)ausdrücklich")
        self.assertRegex(self.delivery, r"(?is)denselben Exact Head")

    def test_del_010_keeps_sec_additive(self):
        self.assertRegex(self.delivery, r"(?is)Parallel-QA ersetzt SEC nicht")
        self.assertRegex(self.delivery, r"(?is)SEC-Rolle.+zusätzlich erforderlich")


class ToolRoutingContract(unittest.TestCase):
    def test_github_cli_required_on_unchanged(self):
        if tomllib is None:
            self.skipTest("tomllib erfordert Python 3.11+")
        with (GOVERNANCE_ROOT / "catalogs" / "tools.toml").open("rb") as handle:
            tools = tomllib.load(handle)["tools"]
        self.assertEqual(tools["github_cli"]["required_on"], ["github_remote"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Führe den Test aus und bestätige erwartetes Rot**

Run: `python3 -m unittest tests.test_copilot_qa_binding -v`

Expected: `FAIL` — `.github/copilot-instructions.md` fehlt (`FileNotFoundError` bei `setUp`), `DEL-010` fehlt, `DEL-008` enthält noch keine Binding-Voraussetzung. Keine Syntax-/Importfehler.

- [ ] **Step 3: Committe ausschließlich den roten Vertragstest**

```bash
git add tests/test_copilot_qa_binding.py
git commit -m "test(governance): define copilot qa binding contracts"
```

### Task 2: Minimale Implementierung

**Files:**
- Create: `.github/copilot-instructions.md`
- Modify: `bundle/agent-governance/modules/delivery.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: die Verträge aus Task 1.
- Produces: eine gültige Binding-Datei, erweiterte `DEL-008`-Regel und neue `DEL-010`-Regel.

- [ ] **Step 1: Erzeuge die dünne Binding-Datei**

```markdown
# GitHub Copilot — Quality-Assurance-Binding

> Nicht normatives Consumer-/Binding-Artefakt. Die normative Governance liegt ausschließlich
> unter `bundle/`. Diese Datei verweist nur auf die kanonischen Quellen desselben
> Repository-Heads und definiert keine eigenen Regeln.

Du arbeitest als technischer Provider der Quality-Assurance-Rolle, nicht als Rollenautorität.

Vor deinem Code-Review:

1. Lies und wende `bundle/agent-governance/roles/quality-assurance.md` an.
2. Wende aus `bundle/agent-governance/modules/delivery.md` mindestens `DEL-002`, `DEL-003`,
   `DEL-007`, `DEL-008` und `DEL-009` an.
3. Wende, falls fachlich benötigt, `TOL-004` aus `bundle/agent-governance/modules/tool-routing.md`
   als Provider-/Fallbackgrenze an.

Für den Review gilt:

- Prüfe ausschließlich den Exact Head des Pull Requests und nenne die geprüfte Exact-Head-SHA.
- Repariere Findings nicht selbst.
- Klassifiziere Findings nach `DEL-009`; ein `blocking-valid` Finding verhindert einen PASS.
- Behaupte keinen PASS, wenn die kanonischen Referenzen nicht lesbar oder widersprüchlich sind.
```

- [ ] **Step 2: Erweitere `DEL-008` in `delivery.md`**

Ersetze den bestehenden `DEL-008`-Block (Zeilen 60–67) durch:

```markdown
### DEL-008 — Provider-Routing

Bei einem GitHub-Repository ist GitHub Copilot der bevorzugte QA-Provider, wenn der reale
PR-Reviewpfad einen Review mit Revieweridentität und Exact-Head-SHA liefert und auf demselben
Exact Head ein gültiges repository-natives Copilot-QA-Binding
(`.github/copilot-instructions.md`) mit auflösbaren kanonischen QA-/Delivery-Referenzen
vorhanden ist. Fehlt das Binding oder sind seine Referenzen nicht auflösbar, gilt der
Copilot-Pfad für dieses Gate fail-closed als nicht verwendbar. Ein frischer unabhängiger
read-only Reviewer ist der QA-Fallback, sobald der Providerzustand `no` oder `unknown` lautet
oder das Binding ungültig ist; Quoten-, Billing- oder Restbudgetzahlen werden nicht erfunden
und ein bestätigtes Negativergebnis wird nicht mit Retry-Spam verfolgt. Eine SEC-Rolle bleibt
bei ihrem Risikotrigger zusätzlich erforderlich und prüft denselben Exact Head.
```

- [ ] **Step 3: Füge `DEL-010` vor `## Definition of Done` ein**

```markdown
### DEL-010 — Optionales Parallel-QA

Ein optionaler Parallel-QA-Modus wird nur aktiviert, wenn der Nutzer dies ausdrücklich verlangt
oder eine bestehende Governance-Risikoeinstufung/Qualitätsanforderung dies ausdrücklich auslöst;
er wird nicht standardmäßig für jedes Review ausgeführt. In diesem Modus prüfen zwei
unabhängige QA-Kontexte frisch und read-only denselben Exact Head. Ihre Findings bleiben bis zu
den jeweils eigenen Urteilen voneinander getrennt und werden anschließend nach
[DEL-009](delivery.md#del-009--finding-lifecycle) klassifiziert. Ein `blocking-valid` Finding
eines erforderlichen Reviewers blockiert die Abschlussaussage. Parallel-QA ersetzt SEC nicht;
ist SEC getriggert, läuft sie zusätzlich und kann parallel zu QA ausgeführt werden.
```

- [ ] **Step 4: Ergänze den `CHANGELOG.md`-Unreleased-Abschnitt**

Unter `### Added` (nach dem dritten bestehenden Punkt) ergänzen:

```markdown
- Ein repository-natives Copilot-QA-Binding `.github/copilot-instructions.md` als dünner
  Consumer-Wrapper, der GitHub Copilot Code Review an die kanonische QA-Governance bindet.
- `DEL-010` (Optionales Parallel-QA) als ausdrücklich opt-in Vertrag.
```

Unter `### Changed` (nach dem dritten bestehenden Punkt) ergänzen:

```markdown
- `DEL-008` verlangt ein gültiges repository-natives Copilot-QA-Binding auf demselben Exact Head
  als Voraussetzung dafür, dass GitHub Copilot als bevorzugter QA-Provider gilt.
```

- [ ] **Step 5: Führe den fokussierten Test grün aus**

Run: `python3 -m unittest tests.test_copilot_qa_binding -v`

Expected: alle Verträge `PASS`.

- [ ] **Step 6: Committe die Implementierung**

```bash
git add .github/copilot-instructions.md bundle/agent-governance/modules/delivery.md CHANGELOG.md
git commit -m "feat(governance): bind copilot qa and add optional parallel qa"
```

### Task 3: Vollständige lokale Verifikation

**Files:**
- Verify only.

- [ ] **Step 1: Führe die vollständige Repositorysuite aus**

Run: `python3 -m unittest discover -s tests -v`

Expected: alle Tests `PASS`, keine Fehler.

- [ ] **Step 2: Führe Source-Consolidation und Release-Check aus**

Run: `python3 -m unittest tests.test_source_consolidation -v && python3 tools/release_check.py tree && git diff --check`

Expected: `PASS`, `OK: all release consistency checks passed`, `git diff --check` ohne Ausgabe.

- [ ] **Step 3: Prüfe Arbeitsbaum und Diff vor Push**

Run: `git status --short && git log --oneline origin/main..HEAD && git diff --stat origin/main...HEAD`

Expected: sauberer Arbeitsbaum, nur die autorisierten Step-3-Änderungen.
