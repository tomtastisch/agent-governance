# Typed Governance Catalogs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Historische Evidenz - nicht normativ.** Dieser Plan dokumentiert die Umsetzung der vom
> Nutzer bereits genehmigten Katalogarchitektur. Normative Governance liegt ausschließlich unter
> `bundle/`; die Katalogvokabulare selbst liegen ausschließlich in den vier TOML-Dateien unter
> `bundle/agent-governance/catalogs/`.

**Goal:** Agent Governance 0.4.0 mit einem Manifest-Schema 2 und je genau einer geschlossenen,
maschinenvalidierbaren TOML-SSOT für Trigger, Policy-Tags, Scopes und Tools liefern sowie zwei
nicht normative README-Grafiken integrieren.

**Architecture:** `manifest.toml` bleibt der Root-Index und referenziert vier relativ zum
Manifestverzeichnis aufgelöste Kataloge. Ein gemeinsamer Python-3.11-Validator prüft geschlossene
Schemen, sichere Pfade und sämtliche Referenzen; der neutrale Harness verwendet denselben
Validator, bevor er Module oder Rollen routet. `modules/tool-routing.md` enthält danach nur noch
allgemeine Routing- und Autorisierungssemantik, während `catalogs/tools.toml` sämtliche
Toolprofile besitzt.

**Tech Stack:** TOML mit Python 3.11 `tomllib`, Python-`unittest`, Markdown/HTML-`details`, PNG,
Git/GitHub Actions und die bestehenden repositoryeigenen Release- und Runtimechecks.

---

## Dateiverantwortung

- `bundle/agent-governance/manifest.toml`: Root-Index, Katalogpfade, Modul- und Rollenindex.
- `bundle/agent-governance/catalogs/triggers.toml`: einziges geschlossenes Trigger-Vokabular.
- `bundle/agent-governance/catalogs/policy-tags.toml`: einziges geschlossenes Wirkungsarten-Vokabular.
- `bundle/agent-governance/catalogs/scopes.toml`: einziges geschlossenes Ressourcenklassen-Vokabular.
- `bundle/agent-governance/catalogs/tools.toml`: einziges maschinenlesbares Toolprofil- und Routing-Vokabular.
- `bundle/agent-governance/modules/tool-routing.md`: allgemeine normative Routingsemantik ohne Toolprofile.
- `tests/support/catalog_validator.py`: gemeinsamer mechanischer Schema-, Pfad- und Referenzvalidator.
- `tests/support/neutral_harness.py`: Runtimeconsumer des Manifest- und Katalogvertrags.
- `tests/test_catalogs.py`: positive und negative Katalogverträge.
- `tests/test_bundle.py`: bestehende Manifest-, Modul-, Rollen- und SSOT-Verträge.
- `tests/test_documentation.py`: README-Bilder, Alt-Texte, Pfade und Nichtnormativität.
- `bundle/GOVERNANCE.md`: Bootstrap-Routing auf Manifest plus Triggerkatalog.
- `Installation.bootstrap.prompt.md`: Distributionsprüfung umfasst die vier manifestreferenzierten Kataloge.
- `README.md`: gezielte Architektur-, Routing-, Erweiterungs- und Verifikationsdokumentation.
- `docs/images/*.png`: byte-identische, nicht normative Erklärungsgrafiken.
- `VERSION` und `CHANGELOG.md`: Produktversionskandidat 0.4.0 und Breaking-Migrationshinweis.

## A/B-Entscheidung für den bisherigen Markdown-Toolkatalog

Jedes bisherige Profil wird als konkrete Toolklasse nach **A** migriert. Seine Felder werden
verlustfrei abgebildet: `Name -> name`, `Zweck -> purpose`, Trigger/Erforderlich/Nützlich ->
`required_on`/`useful_on`, `Evidenzgewinn -> evidence`, `Fallback -> fallback` und
Read-/Write-Grenze plus Keine-Folgerung -> `policy_tags`/`scopes`/`constraints`.

| Bisheriger Eintrag | Entscheidung | Ziel-ID |
|---|---|---|
| Lokale Git-CLI | A | `local_git_cli` |
| Repositoryeigene Prüfungen | A | `repository_checks` |
| GitHub CLI | A | `github_cli` |
| GitHub-Connector | A | `github_connector` |
| Autoritative Dokumentationsrecherche | A | `authoritative_documentation` |
| Strukturierter Engineering-Workflow | A; konkretisiert als Superpowers | `superpowers` |
| Unabhängiger Reviewprovider | A | `independent_review_provider` |
| Security-Diff-Prüfung | A | `security_diff_scan` |
| Microsoft APM | A | `microsoft_apm` |

Nach **B** verbleiben ausschließlich die profilübergreifenden Regeln: fachlicher Trigger statt
Zeremonie, nur tatsächliche Aufrufe erzeugen Evidenz, ein fehlgeschlagener Pflichtpfad blockiert
nur das abhängige Gate, Read before Write, Tool und Provider erzeugen keine Autorisierung,
Policy-Tags und Scopes erzeugen keine konkrete Freigabe, Referenzen sind geschlossen und unbekannte
IDs scheitern fail-closed. Die Einleitung des bisherigen `TOL-002` wird auf diese
Katalogautorität reduziert; kein Toolprofil bleibt parallel in Markdown stehen.

## Geschlossene Vokabulare

Der Triggerkatalog übernimmt alle 24 bestehenden IDs unverändert und ergänzt nur direkt von den
Toolprofilen benötigte IDs: `git_repository`, `repository_verification`, `github_remote`,
`authoritative_documentation`, `issue_tracking`, `project_tracking`, `initiative_tracking`,
`work_status_tracking`, `acceptance_criteria`, `postgresql`, `database_schema`,
`database_migration`, `row_level_security`, `backend_authentication`, `object_storage`,
`realtime_backend`, `edge_functions`, `backend_diagnostics`, `marketing_data`, `ads_data`,
`commerce_metrics`, `cross_channel_marketing_analysis`, `structured_data`, `tabular_data`,
`metric_analysis`, `aggregation`, `calculation`, `statistical_analysis`, `data_visualization`,
`canonical_memory_verification`, `agent_package_provenance` und `dependency_drift`.

Der Policy-Tag-Katalog enthält ausschließlich `read` und `write`. Der Scope-Katalog enthält nur
die von den 15 Toolprofilen verwendeten Ressourcenklassen: `repository`, `github`,
`documentation`, `work_tracking`, `database`, `authentication`, `storage`, `realtime`,
`edge_functions`, `marketing_data`, `structured_data`, `analytics_artifacts`,
`canonical_memory` und `agent_packages`.

Der Toolkatalog enthält genau die migrierten Profile plus die ausdrücklich verlangten Ergänzungen:
`local_git_cli`, `repository_checks`, `github`, `github_cli`, `github_connector`,
`authoritative_documentation`, `superpowers`, `independent_review_provider`,
`security_diff_scan`, `microsoft_apm`, `linear`, `supabase`, `supermetrics`, `data_analytics` und
`canonical_memory_verifier`. Er enthält keine Host-, Installations-, Verfügbarkeits-, Login- oder
Accountzustände.

### Task 1: Rote Manifest-, Katalog- und Referenzverträge

**Files:**
- Create: `tests/test_catalogs.py`
- Modify: `tests/test_bundle.py`
- Modify: `tests/test_documentation.py`

- [ ] **Step 1: Schreibe den positiven Zielvertrag für Manifest und Katalogschemen**

```python
class ManifestCatalogContract(unittest.TestCase):
    def test_manifest_schema_two_references_exact_catalogs(self):
        data = load_manifest()
        self.assertEqual(data["schema_version"], 2)
        self.assertEqual(data["catalogs"], {
            "triggers": "catalogs/triggers.toml",
            "policy_tags": "catalogs/policy-tags.toml",
            "scopes": "catalogs/scopes.toml",
            "tools": "catalogs/tools.toml",
        })
        self.assertEqual(set(data["routing"]), {"unknown", "ambiguous"})
        self.assertNotIn("known_triggers", data["routing"])
```

- [ ] **Step 2: Schreibe geschlossene Schema- und Referenztests**

```python
def test_every_reference_resolves_to_its_catalog(self):
    contract = load_catalog_contract(GOVERNANCE_ROOT)
    manifest = contract.manifest
    for group in (manifest["modules"], manifest["roles"]):
        for entry in group.values():
            self.assertLessEqual(set(entry["triggers"]), contract.triggers)
    for tool in contract.tools.values():
        self.assertLessEqual(set(tool["required_on"]), contract.triggers)
        self.assertLessEqual(set(tool["useful_on"]), contract.triggers)
        self.assertLessEqual(set(tool["policy_tags"]), contract.policy_tags)
        self.assertLessEqual(set(tool["scopes"]), contract.scopes)
```

- [ ] **Step 3: Schreibe für jeden Fail-closed-Fall eine reale temporäre Bundlemutation**

```python
def test_unknown_required_on_fails(self):
    self.replace("catalogs/tools.toml", 'required_on = ["git_repository"]',
                 'required_on = ["unknown_trigger"]')
    with self.assertRaisesRegex(CatalogValidationError, "unbekannten Trigger"):
        self.load()

def test_catalog_traversal_fails(self):
    self.replace("manifest.toml", 'tools = "catalogs/tools.toml"',
                 'tools = "../tools.toml"')
    with self.assertRaisesRegex(CatalogValidationError, "Katalogpfad"):
        self.load()
```

Die Testklasse deckt zusätzlich unbekannten Modultrigger, unbekannten Rollentrigger, unbekanntes
`useful_on`, unbekannten Policy-Tag, unbekannten Scope, unbekanntes Toolfeld, fehlendes Pflichtfeld,
falschen Typ, ungültige ID, fehlenden Katalog, absoluten Pfad, Root-Escape und unerwarteten
Katalog-Symlink ab.

- [ ] **Step 4: Schreibe README-Bildverträge**

```python
def test_governance_diagrams_are_local_non_normative_explanations(self):
    for name in ("Governance-ujjm885-44_44.png", "Governance-dsfs652-20_44.png"):
        self.assertTrue((ROOT / "docs" / "images" / name).is_file())
        self.assertIn(f"docs/images/{name}", README)
    self.assertIn("nicht normative", README)
    self.assertIn("<details>", README)
```

- [ ] **Step 5: Führe nur die neuen Zielverträge aus und bestätige erwartetes Rot**

Run: `python3 -m unittest tests.test_catalogs tests.test_documentation -v`

Expected: `FAIL` wegen fehlender Kataloge, Manifest-Schema 1 und fehlender README-Bilder; keine
Syntax- oder Importfehler.

- [ ] **Step 6: Committe ausschließlich den roten Zielvertrag und diesen Plan**

```bash
git add docs/superpowers/plans/2026-08-17-typed-routing-catalogs.md tests/test_catalogs.py tests/test_bundle.py tests/test_documentation.py
git commit -S -m "test(governance): define typed catalog contracts"
```

### Task 2: Gemeinsamer Katalogvalidator und sichere Pfadauflösung

**Files:**
- Create: `tests/support/catalog_validator.py`
- Modify: `tests/support/neutral_harness.py`
- Modify: `tests/test_local_rules_runtime.py`
- Test: `tests/test_catalogs.py`
- Test: `tests/test_neutral_harness.py`

- [ ] **Step 1: Implementiere exakt die geschlossenen Feldmengen**

```python
ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
VOCABULARY_FIELDS = frozenset({"label", "description"})
TOOL_FIELDS = frozenset({
    "name", "purpose", "required_on", "useful_on", "policy_tags", "scopes",
    "evidence", "fallback", "constraints",
})
CATALOG_PATHS = frozenset({"triggers", "policy_tags", "scopes", "tools"})
```

`load_catalog_contract(manifest_dir, manifest=None)` prüft Manifest-Schema 2, exakte
Top-Level-Felder, `routing = {unknown, ambiguous}`, vier Katalogpfade, Katalog-Schema 1,
ID-Format, Feldmengen, Datentypen, nichtleere Texte, listenförmige Stringreferenzen und alle
Modul-, Rollen- und Toolreferenzen.

- [ ] **Step 2: Binde Katalogpfade ausschließlich an das absolute Manifestverzeichnis**

```python
def _catalog_file(manifest_dir: Path, raw: object) -> Path:
    if not isinstance(raw, str) or not raw or Path(raw).is_absolute():
        raise CatalogValidationError("Katalogpfad ist ungültig")
    pure = PurePosixPath(raw)
    if ".." in pure.parts or "~" in pure.parts:
        raise CatalogValidationError("Katalogpfad enthält Traversal")
    candidate = manifest_dir.joinpath(*pure.parts)
    _reject_symlink_chain(candidate, stop=manifest_dir)
    if candidate.is_symlink() or not candidate.is_file():
        raise CatalogValidationError("Katalog muss eine reguläre Nicht-Symlink-Datei sein")
    candidate.resolve(strict=True).relative_to(manifest_dir.resolve(strict=True))
    return candidate
```

- [ ] **Step 3: Verwende den Validator in jeder neutralen Runtime-Session**

```python
contract = load_catalog_contract(self.manifest_dir, manifest=manifest)
read_paths.extend(contract.catalog_paths)
chain.append("catalogs")
module_paths, role_paths, routed_paths = self._resolve_routes(
    contract.manifest, contract.triggers, triggers
)
```

- [ ] **Step 4: Führe die Negativmatrix fokussiert aus**

Run: `python3 -m unittest tests.test_catalogs -v`

Expected: Die Validator-Unit-Tests erreichen den neuen Code; positive Tests bleiben bis zur
Katalogmaterialisierung rot, die negativen Fixtures scheitern mit `CatalogValidationError`.

### Task 3: Vier TOML-SSOTs und Manifest-Schema 2 materialisieren

**Files:**
- Create: `bundle/agent-governance/catalogs/triggers.toml`
- Create: `bundle/agent-governance/catalogs/policy-tags.toml`
- Create: `bundle/agent-governance/catalogs/scopes.toml`
- Create: `bundle/agent-governance/catalogs/tools.toml`
- Modify: `bundle/agent-governance/manifest.toml`
- Modify: `bundle/GOVERNANCE.md`
- Modify: `Installation.bootstrap.prompt.md`

- [ ] **Step 1: Erzeuge die drei geschlossenen Vokabularkataloge**

Jede Datei erhält ausschließlich `schema_version = 1` und ihre eine Tabelle. Jede ID aus dem
Abschnitt „Geschlossene Vokabulare“ erhält exakt `label` und eine nichtleere `description`; es
werden keine Alias-, Default-, Availability- oder Installationsfelder eingeführt.

- [ ] **Step 2: Erzeuge die 15 Toolprofile mit exakt neun Feldern**

```toml
[tools.linear]
name = "Linear"
purpose = """
Projekt-, Issue-, Initiative- und Arbeitsstatusverwaltung einschließlich Akzeptanzkriterien.
"""
required_on = ["issue_tracking", "project_tracking", "initiative_tracking", "work_status_tracking"]
useful_on = ["acceptance_criteria"]
policy_tags = ["read", "write"]
scopes = ["work_tracking"]
evidence = """
Objektkennungen, Status, Beziehungen, Akzeptanzkriterien und nachvollziehbare Änderungsstände.
"""
fallback = """
Ohne den Pflichtpfad bleibt nur das davon abhängige Work-Tracking-Gate offen oder blockiert.
"""
constraints = """
Toolzugriff erzeugt keine Autorisierung; Schreibwirkungen bleiben am konkreten Auftrag gebunden.
"""
```

Die übrigen Profile verwenden ausschließlich IDs aus den drei Vokabularkatalogen. Microsoft APM
nennt `github.com/microsoft/apm`, `apm.yml`, `apm.lock.yaml` und read-only Audit-Evidenz, aber keine
Installation oder Aktualisierung. Canonical Memory Verifier bleibt auf ein ausdrücklich gewähltes
kanonisches Bundle begrenzt und führt keine allgemeine Memory-Suche ein.

- [ ] **Step 3: Migriere den Root-Index ohne parallele Triggerliste**

```toml
schema_version = 2
local_rules = "local/user-rules.md"

[catalogs]
triggers = "catalogs/triggers.toml"
policy_tags = "catalogs/policy-tags.toml"
scopes = "catalogs/scopes.toml"
tools = "catalogs/tools.toml"

[routing]
unknown = "block"
ambiguous = "block"
```

- [ ] **Step 4: Aktualisiere Bootstrap und Installationsvertrag auf dieselbe Pfadkette**

`bundle/GOVERNANCE.md` lädt nach dem Manifest die manifestreferenzierten Kataloge, klassifiziert
gegen `triggers.toml` und löst Katalog-, Modul-, Rollen- und lokale Pfade nur relativ zum
beibehaltenen absoluten Manifestverzeichnis auf. `Installation.bootstrap.prompt.md` prüft und
materialisiert die vier Kataloge als Teil der Distribution, ohne eine zweite Rootauflösung.

- [ ] **Step 5: Führe die Katalog- und Runtimeverträge grün**

Run: `python3 -m unittest tests.test_catalogs tests.test_bundle tests.test_local_rules_runtime tests.test_neutral_harness tests.test_offline_runtime -v`

Expected: `PASS` einschließlich aller Negativfälle und der Runtimekette
`bootstrap -> manifest -> catalogs -> local_rules? -> modules`.

- [ ] **Step 6: Committe Schema, Validator und Kataloge atomar**

```bash
git add bundle/GOVERNANCE.md bundle/agent-governance/manifest.toml bundle/agent-governance/catalogs Installation.bootstrap.prompt.md tests/support/catalog_validator.py tests/support/neutral_harness.py tests/test_local_rules_runtime.py
git commit -S -m "feat(governance): add typed governance catalogs"
```

### Task 4: Tool-Routing auf die TOML-SSOT reduzieren

**Files:**
- Modify: `bundle/agent-governance/modules/tool-routing.md`
- Modify: `tests/test_bundle.py`
- Test: `tests/test_catalogs.py`

- [ ] **Step 1: Ersetze die Markdownprofile durch allgemeine Regeln**

```markdown
### TOL-002 — Katalogautorität und geschlossene Referenzen

Der manifestreferenzierte `../catalogs/tools.toml` ist die einzige maschinenlesbare SSOT für
Toolprofile. Trigger, Policy-Tags und Scopes verweisen ausschließlich auf ihre Katalog-IDs;
unbekannte Referenzen blockieren fail-closed.

### TOL-003 — Wirkung, Scope und Autorisierung

Policy-Tags beschreiben mögliche Wirkungsarten und Scopes betroffene Ressourcenklassen. Weder
beides noch ein Toolzugriff erzeugt konkrete Autorisierung; vor einer Schreibwirkung wird der
aktuelle Zustand gelesen und die bestehende Auftragsautorisierung geprüft.
```

- [ ] **Step 2: Ersetze profilparsendende Tests durch SSOT- und Verlustfreiheitsprüfungen**

Die Tests verlangen 15 exakte Tool-IDs, die acht Mindesttools, alle neun migrierten Profile,
geschlossene Referenzen, Read/Write- und Scope-Trennung, keine Installation/Availability/Login-
Felder und keine `####`-Toolprofile mehr in `tool-routing.md`.

- [ ] **Step 3: Führe Tool-Routing und Source-Consolidation grün**

Run: `python3 -m unittest tests.test_catalogs tests.test_bundle tests.test_governance tests.test_source_consolidation -v`

Expected: `PASS`; keine zweite maschinenlesbare oder profilweise Markdown-SSOT.

- [ ] **Step 4: Committe die Routingmigration**

```bash
git add bundle/agent-governance/modules/tool-routing.md tests/test_bundle.py tests/test_catalogs.py
git commit -S -m "refactor(governance): route tools through catalog ssot"
```

### Task 5: README-Erklärung und byte-identische Bilder

**Files:**
- Create: `docs/images/Governance-ujjm885-44_44.png`
- Create: `docs/images/Governance-dsfs652-20_44.png`
- Modify: `README.md`
- Modify: `tests/test_documentation.py`

- [ ] **Step 1: Kopiere beide eindeutig aufgelösten Quellen byte-identisch**

```bash
cp /Users/tomwerner/Downloads/Governance-ujjm885-44_44.png docs/images/Governance-ujjm885-44_44.png
cp /Users/tomwerner/Downloads/Governance-dsfs652-20_44.png docs/images/Governance-dsfs652-20_44.png
cmp -s /Users/tomwerner/Downloads/Governance-ujjm885-44_44.png docs/images/Governance-ujjm885-44_44.png
cmp -s /Users/tomwerner/Downloads/Governance-dsfs652-20_44.png docs/images/Governance-dsfs652-20_44.png
```

- [ ] **Step 2: Integriere die Wirkungsgrafik zuerst**

Unter „Welches Problem löst es?“ folgt „Was die Governance bewirkt“ mit sinngemäßem Alt-Text und
relativem Pfad. Der Begleittext bezeichnet README und Bilder ausdrücklich als nicht normative
Erklärung und verweist auf `bundle/` als technische SSOT.

- [ ] **Step 3: Integriere die Binding-Grafik nur als schematische Detailansicht**

```html
<details>
<summary>Technischen Governance-Ablauf als Grafik anzeigen</summary>

![Schematische Übersicht darüber, wie Governance-Bindings, Manifest, Kataloge, Module und Rollen ineinandergreifen.](docs/images/Governance-dsfs652-20_44.png)

</details>
```

Direkt davor stehen die aktuellen normativen Pfade `catalogs/triggers.toml`,
`catalogs/policy-tags.toml`, `catalogs/scopes.toml` und `catalogs/tools.toml`; der Text erklärt,
dass vereinfachte oder ältere Bildbezeichnungen keine Dateikarte und keine SSOT sind.

- [ ] **Step 4: Aktualisiere gezielt Architektur, Routing, Erweiterung und Tests**

README beschreibt Manifest als Root-Index, die vier Katalogverantwortungen und
`modules/tool-routing.md` als allgemeine Semantik, ohne Kataloginhalte zu duplizieren.

- [ ] **Step 5: Prüfe Bild- und Dokumentationsverträge**

Run: `python3 -m unittest tests.test_documentation tests.test_source_consolidation.HistoricalEvidenceContract -v`

Expected: `PASS`; lokale Links, Alt-Texte, Detailansicht und Nichtnormativität sind belegt.

- [ ] **Step 6: Committe Dokumentation und Bilder**

```bash
git add README.md docs/images tests/test_documentation.py
git commit -S -m "docs(governance): add catalog docs and governance diagrams"
```

### Task 6: Produktversion 0.4.0 und Migrationshinweis

**Files:**
- Modify: `VERSION`
- Modify: `CHANGELOG.md`
- Modify: `tests/test_documentation.py`
- Modify: `tests/test_source_consolidation.py`

- [ ] **Step 1: Setze die unabhängige Produktversion auf 0.4.0**

Run: `printf '0.4.0\n' > VERSION` ist nicht zulässig; ändere `VERSION` mit `apply_patch` auf
exakt eine Zeile `0.4.0` plus finales Newline.

- [ ] **Step 2: Fülle ausschließlich den Unreleased-Abschnitt**

`Added` nennt die vier Kataloge und den erweiterten Toolbestand. `Changed` nennt Manifest-Schema
2, Tool-Routing-SSOT und README-Grafiken. `Fixed` und `Removed` bleiben explizit gepflegt.
`**Breaking changes:** present` wird durch einen `**BREAKING:**`-Eintrag begründet: Consumer von
`routing.known_triggers` müssen den manifestreferenzierten Triggerkatalog lesen. Es wird kein
veröffentlichter `0.4.0`-Releaseabschnitt erfunden.

- [ ] **Step 3: Aktualisiere nur versionsgebundene Tests**

Die Tests erwarten `VERSION == 0.4.0`, den README-Link auf 0.4.0 und den beschriebenen
Unreleased-Breaking-Vertrag; historische 0.3.2-Releaseevidenz bleibt unverändert im Changelog.

- [ ] **Step 4: Prüfe Release-Tree und Versionskonsistenz**

Run: `python3 -m unittest tests.test_documentation tests.test_source_consolidation tests.test_release_check -v && python3 tools/release_check.py tree`

Expected: `PASS` und `OK: all release consistency checks passed`.

- [ ] **Step 5: Committe den Versionskandidaten**

```bash
git add VERSION CHANGELOG.md tests/test_documentation.py tests/test_source_consolidation.py
git commit -S -m "chore(release): prepare governance 0.4.0"
```

### Task 7: Vollständige Regression und lokale Exact-Head-Gates

**Files:**
- Verify only; keine geplante Produktänderung.

- [ ] **Step 1: Führe fokussierte Syntax- und Diffprüfungen aus**

Run: `python3 -m py_compile tests/support/catalog_validator.py tests/support/neutral_harness.py && git diff --check`

Expected: beide Befehle ohne Ausgabe und Exit 0.

- [ ] **Step 2: Führe die vollständige Repositorysuite sequenziell aus**

Run: `python3 -m unittest discover -s tests -v`

Expected: alle Tests PASS, keine Fehler oder Warnings.

- [ ] **Step 3: Führe die aktuellen zusätzlichen Repositorychecks aus**

Run: `python3 tools/release_check.py tree && tests/e2e/run_neutral_harness.sh && git diff --check`

Expected: alle Checks PASS. Kein echter Clean-Linux-Codex-E2E wird ohne einen aktuellen
Repositoryvertrag, der ihn für diesen PR-Stand lokal verlangt, zusätzlich kostenpflichtig
wiederholt; GitHub-CI bleibt das Remote-Gate.

- [ ] **Step 4: Prüfe Historie, Signaturen und Arbeitsbaum**

Run: `git log --show-signature --format=fuller origin/main..HEAD && git status --short && git diff --stat origin/main...HEAD`

Expected: fünf fachlich kohärente signierte Commits, sauberer Arbeitsbaum und nur autorisierter
Scope.

### Task 8: Unabhängige QA und separate Security-Prüfung

**Files:**
- Review only; Reviewer arbeiten read-only auf demselben Exact Head.

- [ ] **Step 1: Lade die Reviewskills vor der Prüfung**

Verwende `superpowers:requesting-code-review` für QA und `codex-security:security-diff-scan` für
SEC. Falls der Security-Provider nicht geeignet nutzbar ist, verwende einen frischen separaten
read-only SEC-Agenten.

- [ ] **Step 2: Binde beide Rollen an denselben Head**

Run: `git rev-parse HEAD`

Expected: eine 40-stellige SHA, die in beiden Reviewaufträgen als Base/Head-Grenze genannt wird.

- [ ] **Step 3: QA prüft den vollständigen Akzeptanzumfang**

QA prüft SSOT-Eindeutigkeit, Schemen, Referenzen, A/B-Verlustfreiheit, Toolbestand,
Installationsgrenze, Read/Write- und Scope-Semantik, README/Bilder, Version und 0.3.x-Regressionen.

- [ ] **Step 4: SEC prüft die sicherheitsrelevanten Flächen**

SEC prüft Manifest-/Katalogpfade, Traversal, Symlinks, Unknown-ID-Fail-closed,
Policy-/Scope-/Tool-Autorisierungsverwechslung, Schema-Bypass, Parsergrenzen und bestehende
Enforcementverträge.

- [ ] **Step 5: Behandle Findings nach dem Finding-Lifecycle**

Vor jeder Umsetzung externer Findings wird `superpowers:receiving-code-review` geladen. Jedes
Finding wird `blocking-valid`, `nonblocking-valid`, `invalid` oder `not-applicable`; nach jeder
Korrektur werden Tests, Commit und beide betroffenen Rollen auf dem neuen Head wiederholt.

Expected: QA PASS, SEC PASS und `blocking-valid = 0` auf derselben SHA.

### Task 9: Push, genau ein PR und SHA-gebundene CI

**Files:**
- External Git/GitHub state only; kein Merge, Tag oder Release.

- [ ] **Step 1: Lade `verification-before-completion` und wiederhole lokale Pflichtgates**

Run: `git status --short && git rev-parse HEAD && python3 -m unittest discover -s tests -v && python3 tools/release_check.py tree && tests/e2e/run_neutral_harness.sh && git diff --check`

Expected: sauberer Worktree, ein Exact Head und ausschließlich PASS.

- [ ] **Step 2: Verifiziere Remote-main und offene PRs unmittelbar vor Push**

Run: `git fetch --prune origin && gh pr list -R tomtastisch/agent-governance --state open --json number,title,headRefName,headRefOid,baseRefName`

Expected: `origin/main` bleibt die geprüfte Base oder ist konfliktfrei erklärbar; kein
konkurrierender PR implementiert denselben Scope.

- [ ] **Step 3: Pushe ohne Force und erstelle genau einen PR**

```bash
git push -u origin feat/governance/typed-routing-catalogs
gh pr create --repo tomtastisch/agent-governance --base main --head feat/governance/typed-routing-catalogs --title "feat(governance): add typed routing catalogs" --body "$(printf '%s\n' 'Ausgangsversion: 0.3.2' 'Manifest-Schemaänderung: 1 -> 2' 'Trigger-Katalog: neue geschlossene TOML-SSOT' 'Policy-Tag-Katalog: read/write als geschlossene Wirkungsklassen' 'Scope-Katalog: geschlossene Ressourcenklassen' 'Tool-Katalog: einzige maschinenlesbare Tool-Routing-SSOT' 'Tool-Routing-Migration: neun bestehende Profile verlustfrei nach TOML migriert' 'README-Visualisierungen: zwei lokale PNGs, ausdrücklich nicht normativ' 'Tests: vollständige Repositorysuite und Negativmatrix' 'QA: Exact-Head-Evidenz wird vor PR-Aktualisierung eingesetzt' 'SEC: separater Security-Diff-Review auf demselben Head' 'CI: wird auf dem PR-Head abgewartet' 'Versionierungsentscheidung: 0.4.0 als MINOR-Kandidat, Manifest-Schema 2 separat' 'Known Limitations: Binding-Grafik ist schematisch und enthält vereinfachte ältere Bezeichnungen' 'Nicht autorisiert: Merge, Tag oder GitHub Release')"
```

Die Beschreibung enthält Ausgangsversion, Manifest-Schemaänderung, vier Kataloge,
Tool-Routing-Migration, README-Grafiken, Tests, QA, SEC, CI-Status, Versionierungsentscheidung,
Known Limitations und die Nichtautorisierung von Merge/Tag/Release.

- [ ] **Step 4: Fordere den bevorzugten realen QA-Provider an, falls verfügbar**

Fordere GitHub Copilot Review genau einmal an. Ein bestätigter Providerstatus `no` oder `unknown`
verwendet die bereits ausgeführte unabhängige read-only QA als Fallback; kein Retry-Spam.

- [ ] **Step 5: Verifiziere Local/Remote/PR-Head-Gleichheit und warte auf CI**

Run: `git rev-parse HEAD`, `git ls-remote origin refs/heads/feat/governance/typed-routing-catalogs`
und `gh pr view --json headRefOid,statusCheckRollup,reviews,reviewDecision,url`.

Expected: Local Head = Remote Branch Head = PR Head = QA Head = SEC Head. Beide blockierenden
GitHub-Actions-Checks PASS auf genau dieser SHA; offene Reviewthreads und Findings sind null oder
vollständig klassifiziert.

### Task 10: Finale frische Verifikation und Abschluss

**Files:**
- Verify only.

- [ ] **Step 1: Wiederhole die vorgeschriebenen lokalen Abschlussbefehle frisch**

Run: `git status --short`, `git rev-parse HEAD`, `python3 -m unittest discover -s tests -v`,
`python3 tools/release_check.py tree`, `tests/e2e/run_neutral_harness.sh`, `git diff --check`.

Expected: sauberer Worktree und alle Checks PASS.

- [ ] **Step 2: Lies Remote-, PR-, Review-, CI-, Version- und Schemaidentität frisch**

Expected: Local = Remote Branch = PR = QA = SEC = CI; `VERSION = 0.4.0`, Manifest
`schema_version = 2`, `blocking-valid = 0`.

- [ ] **Step 3: Berichte ausschließlich den nachgewiesenen Lieferstand**

Die Abschlussantwort nennt Base, finalen SHA, Branch, PR, Version, Schema, vier Kataloge,
README-Bilder, Tests, QA, SEC, CI und verbleibende Risiken. Sie behauptet keinen Merge, Tag,
GitHub Release oder produktive Hoständerung.
