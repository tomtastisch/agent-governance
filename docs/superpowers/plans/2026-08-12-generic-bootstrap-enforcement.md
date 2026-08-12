# Generic Bootstrap and Enforcement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Historische Evidenz - nicht normativ.** Dieser Plan dokumentiert die Umsetzung der genehmigten
> Spezifikation. Normative Governance liegt ausschließlich unter `bundle/`.

**Goal:** Agent Governance 0.3.0 mit generischem Bootstrapvertrag, providerneutralem Enforcement,
exakt gepinntem Microsoft AGT, reproduzierbaren Migrationspfaden und vollständigen Releasegates
veröffentlichen.

**Architecture:** Das Bundle behält seine einzige normative Einstiegskette und erhält genau ein
triggerbares Enforcement-Modul. Außerhalb des Bundles materialisiert eine kleine JSON-Bridge den
Microsoft-Provider; ein einmaliger Bootstrapvertrag erkennt Harness und Installationszustand,
führt eine sichere Transaktion aus und bindet nur belegte Pre-Effect-Flächen.

**Tech Stack:** Markdown/TOML, Python 3.11 Standardbibliothek, Node.js 18+, Microsoft AGT
TypeScript PolicyEngine aus dem vendorten Release, Git/GitHub Actions, Docker/Colima, Codex CLI
0.147.0.

---

### Task 0: Genehmigtes Design und ausführbaren Plan festhalten

**Files:**
- Create: `docs/superpowers/specs/2026-08-12-generic-bootstrap-enforcement-design.md`
- Create: `docs/superpowers/plans/2026-08-12-generic-bootstrap-enforcement.md`

- [ ] **Step 1: Prüfe beide Dokumente auf nichtnormative Einordnung und ausführbare Schritte**

Run: `python3 -m unittest tests.test_source_consolidation.HistoricalEvidenceContract -v`

Expected: `PASS`; beide Dokumente sind ausdrücklich nichtnormative historische Evidenz.

- [ ] **Step 2: Prüfe, dass kein Pfad unter `bundle/` eine zweite Design-SSOT erhält**

Run: `git status --short`

Expected: ausschließlich die beiden neuen Dateien unter `docs/superpowers/`.

- [ ] **Step 3: Committe die freigegebene Spezifikation und den Plan**

```bash
git add docs/superpowers
git commit -m "docs(governance): record approved 0.3.0 design"
```

### Task 1: Rote Verträge für Enforcement und Providergrenze

**Files:**
- Create: `tests/test_enforcement_contract.py`
- Modify: `tests/test_bundle.py`
- Test: `tests/test_enforcement_contract.py`

- [ ] **Step 1: Schreibe Tests für die einzige Enforcement-SSOT**

```python
def test_manifest_routes_single_enforcement_module(self):
    data = load_manifest()
    self.assertEqual(data["modules"]["enforcement"]["path"], "modules/enforcement.md")
    self.assertEqual(data["modules"]["enforcement"]["triggers"], ["external_effect"])

def test_provider_can_only_restrict_governance(self):
    text = ENFORCEMENT.read_text(encoding="utf-8")
    for decision in ("allow", "deny", "require_approval", "error", "unknown"):
        self.assertIn(f"`{decision}`", text)
    self.assertRegex(text, r"(?is)Governance.+deny.+Provider.+allow.+niemals")
```

- [ ] **Step 2: Verifiziere den roten Test**

Run: `python3 -m unittest tests.test_enforcement_contract -v`

Expected: `FAIL` wegen fehlendem `modules/enforcement.md` und Manifesteintrag.

- [ ] **Step 3: Ergänze Negative Tests für Microsoft-Semantik im generischen Vertrag**

```python
def test_generic_contract_has_no_microsoft_semantics(self):
    text = ENFORCEMENT.read_text(encoding="utf-8")
    self.assertNotRegex(text, r"(?i)Microsoft|AGT|Cedar|MCP Gateway")
```

- [ ] **Step 4: Committe nur die roten Vertragsprüfungen**

```bash
git add tests/test_enforcement_contract.py tests/test_bundle.py
git commit -m "test(governance): define bootstrap and enforcement contracts"
```

### Task 2: Generischer normativer Enforcement-Vertrag

**Files:**
- Create: `bundle/agent-governance/modules/enforcement.md`
- Modify: `bundle/agent-governance/manifest.toml`
- Modify: `bundle/agent-governance/modules/invariants.md`
- Test: `tests/test_enforcement_contract.py`

- [ ] **Step 1: Definiere die Action Envelope und Entscheidungsregeln**

```markdown
### ENF-001 — Providerneutrale Action Envelope

Die Envelope enthält ausschließlich Action-ID, Aktion, Ressource, Effekt, bereits bestehende
semantische Governance-Autorisierung, Approval-/Risikokontext und Evidence-ID.

### ENF-002 — Geschlossene Entscheidung

Ein Provider liefert genau `allow`, `deny`, `require_approval`, `error` oder `unknown`.
```

- [ ] **Step 2: Route ausschließlich `external_effect` auf das neue Modul**

```toml
[modules.enforcement]
path = "modules/enforcement.md"
triggers = ["external_effect"]
dependencies = ["invariants"]
```

- [ ] **Step 3: Führe fokussierte und vollständige Tests aus**

Run: `python3 -m unittest tests.test_enforcement_contract tests.test_bundle -v`

Expected: `PASS`.

Run: `python3 -m unittest discover -s tests -v`

Expected: `PASS`.

- [ ] **Step 4: Committe den normativen Vertrag**

```bash
git add bundle/agent-governance tests/test_enforcement_contract.py
git commit -m "feat(governance): add generic enforcement contract"
```

### Task 3: Microsoft-Upstream reproduzierbar materialisieren

**Files:**
- Create: `integrations/microsoft-agent-governance-toolkit/README.md`
- Create: `integrations/microsoft-agent-governance-toolkit/upstream.lock.toml`
- Create: `integrations/microsoft-agent-governance-toolkit/LICENSE.upstream`
- Create: `integrations/microsoft-agent-governance-toolkit/NOTICE.upstream`
- Create: `integrations/microsoft-agent-governance-toolkit/TRADEMARKS.upstream.md`
- Create: `integrations/microsoft-agent-governance-toolkit/upstream/**`
- Create: `tests/test_microsoft_upstream.py`

- [ ] **Step 1: Schreibe Pin-, Lizenz- und Instruction-Boundary-Tests**

```python
def test_lock_pins_official_release(self):
    self.assertEqual(lock["resolved_tag"], "v4.1.0")
    self.assertEqual(lock["resolved_commit"], "0de71ca6c95cf8b9b975ac96f48eaa7826bbe258")
    self.assertEqual(lock["archive_sha256"], "f087836d4e6cbad246c728c76454dd573a701f35d7560cbf869c250b3862d473")

def test_manifest_never_traverses_upstream(self):
    manifest_text = MANIFEST.read_text(encoding="utf-8")
    self.assertNotIn("integrations/", manifest_text)
```

- [ ] **Step 2: Verifiziere den roten Test**

Run: `python3 -m unittest tests.test_microsoft_upstream -v`

Expected: `FAIL` wegen fehlender Integration.

- [ ] **Step 3: Materialisiere das validierte vollständige Releasearchiv mechanisch**

Run: `cp /private/tmp/agent-governance-msagt.xTIWAO/upstream-1.tar.gz integrations/microsoft-agent-governance-toolkit/upstream/agent-governance-toolkit-v4.1.0.tar.gz`

Expected: ein byte-identisches offizielles Archiv mit 4.633 regulären Snapshotdateien, keine
`.git`-Metadaten und keine Archiveinträge mit absoluten Pfaden, `..`, Devices oder Links. Direkte
Extraktion im Repository wird vermieden, weil die Upstream-`.gitattributes` offizielle CRLF-Blobs
beim Git-Staging normalisieren würde.

- [ ] **Step 4: Erfasse den Materialisierungszeitpunkt und schreibe den unveränderlichen Lock**

Run unmittelbar vor der Extraktion: `date -u '+%Y-%m-%dT%H:%M:%SZ'`

Den exakt ausgegebenen Wert mit `apply_patch` als `resolved_at` eintragen; keine gerundete oder
nachträglich erfundene Uhrzeit verwenden.

```toml
repository = "https://github.com/microsoft/agent-governance-toolkit"
resolved_version = "4.1.0"
resolved_tag = "v4.1.0"
resolved_commit = "0de71ca6c95cf8b9b975ac96f48eaa7826bbe258"
archive_source = "https://codeload.github.com/microsoft/agent-governance-toolkit/tar.gz/refs/tags/v4.1.0"
archive_sha256 = "f087836d4e6cbad246c728c76454dd573a701f35d7560cbf869c250b3862d473"
license = "MIT"
upstream_status = "Public Preview"
tag_signature_status = "lightweight-tag"
commit_signature_status = "verified"
materialization_strategy = "complete-official-release-archive"
```

- [ ] **Step 5: Prüfe Snapshot und Repositorylimits**

Run: `python3 -m unittest tests.test_microsoft_upstream -v`

Expected: `PASS`, einschließlich maximaler Einzeldatei unter 100 MB.

- [ ] **Step 6: Committe den Pin**

```bash
git add integrations/microsoft-agent-governance-toolkit tests/test_microsoft_upstream.py
git commit -m "feat(integration): pin Microsoft AGT release"
```

### Task 4: Echte Microsoft-Providerbridge mit TDD

**Files:**
- Create: `integrations/microsoft-agent-governance-toolkit/bridge/provider.mjs`
- Create: `integrations/microsoft-agent-governance-toolkit/bridge/codex-hook.mjs`
- Create: `integrations/microsoft-agent-governance-toolkit/bridge/policy.json`
- Create: `integrations/microsoft-agent-governance-toolkit/bridge/build-provider.sh`
- Create: `tests/node/provider_bridge.test.mjs`
- Create: `tests/test_provider_bridge.py`

- [ ] **Step 1: Schreibe rote allow/deny/approval/error-Tests**

```javascript
assert.equal((await evaluate(envelope({effect: "read", semantic_authorization: "allow"}))).decision, "allow");
assert.equal((await evaluate(envelope({semantic_authorization: "deny"}))).decision, "deny");
assert.equal((await evaluate(envelope({risk_context: {requires_approval: true}}))).decision, "require_approval");
assert.equal((await evaluate(envelope({provider_failure_probe: true}))).decision, "error");
```

- [ ] **Step 2: Verifiziere den roten Test**

Run: `node --test tests/node/provider_bridge.test.mjs`

Expected: `FAIL` wegen fehlender Bridge.

- [ ] **Step 3: Implementiere strikte Envelope-Validierung und Microsoft-Aufruf**

```javascript
const engine = new PolicyEngine();
engine.loadJson(await readFile(policyPath, "utf8"));
const result = engine.evaluatePolicy("agent-governance", envelope);
return normalize(result.action);
```

Nur `allow` ergibt einen Fortsetzungsausgang. `deny`, ungelöstes `require_approval`, Exceptions und
unbekannte Werte erzeugen eine Codex-`permissionDecision: "deny"`-Antwort.

- [ ] **Step 4: Baue den vendorten Provider aus Lockzustand**

Run: `integrations/microsoft-agent-governance-toolkit/bridge/build-provider.sh`

Expected: Das verifizierte Archiv wird in eine temporäre Stagingwurzel extrahiert, dort sind
`npm ci` und `npm run build` erfolgreich; danach funktioniert `provider.mjs` ohne
Netzwerkzugriff.

- [ ] **Step 5: Beweise reale Effektreihenfolge**

Run: `python3 -m unittest tests.test_provider_bridge -v`

Expected: allow erzeugt die synthetische Zieldatei, deny/Approval/error erzeugen sie nicht und
Audit-Evidence zeigt die Providerentscheidung vor dem fehlenden Effekt.

- [ ] **Step 6: Committe die Bridge**

```bash
git add integrations/microsoft-agent-governance-toolkit/bridge tests/node tests/test_provider_bridge.py
git commit -m "feat(integration): bridge normalized actions to Microsoft AGT"
```

### Task 5: Generischer Bootstrapvertrag und Referenztransaktion

**Files:**
- Create: `Installation.bootstrap.prompt.md`
- Create: `tests/support/bootstrap_reference.py`
- Create: `tests/test_bootstrap_contract.py`
- Create: `tests/fixtures/bootstrap/{fresh,current,legacy}/**`

- [ ] **Step 1: Schreibe rote Vertrags- und Zustandsmatrixtests**

```python
for state in ("FRESH", "CURRENT", "LEGACY"):
    self.assertIn(f"### {state}", BOOTSTRAP_TEXT)

def test_legacy_preserves_synthetic_private_rules(self):
    before = fixture.private_rules.read_bytes()
    result = run_bootstrap(fixture)
    self.assertTrue(result.ok)
    self.assertEqual(result.private_rules.read_bytes(), before)
```

- [ ] **Step 2: Verifiziere den roten Test**

Run: `python3 -m unittest tests.test_bootstrap_contract -v`

Expected: `FAIL` wegen fehlendem Prompt und Referenztransaktion.

- [ ] **Step 3: Schreibe den Bootstrap als ausführbaren Entscheidungsvertrag**

Der Prompt muss Preflight, Harnesserkennung, absolute Rootvalidierung, Release-Pin, FRESH/CURRENT/
LEGACY, Backup, private Regeln, Providerbuild, Hookbindung, Verifikation, Rollback, sichere Evidenz
und Abbruchsemantik vollständig vorgeben. Er darf weder `CODEX_HOME`, einen Homepfad noch einen
Produktnamen als generische Voraussetzung verwenden.

- [ ] **Step 4: Implementiere die synthetische Referenztransaktion**

`BootstrapTransaction.run()` ruft genau `inspect -> backup -> stage -> activate -> verify` auf und
liefert nur nach erfolgreichem `verify` ein Commit-Receipt. Jede Exception ab `backup` ruft
`rollback` auf und prüft anschließend den wiederhergestellten Zustand. `inspect` klassifiziert
FRESH/CURRENT/LEGACY und verwirft unbekannte Mischzustände. `backup` erfasst nur die konkret
betroffenen Pfade außerhalb aktiver Instruktionsnamen. `stage` kopiert Bundle und Integration aus
dem geprüften Releasebaum in ein neues Verzeichnis derselben Installationswurzel. `activate`
verwendet atomare `os.replace`-Operationen; `verify` startet eine neue synthetische Session und
prüft Root, Manifest, private Regeln und Provider. Jeder Pfad verwendet `lstat`, dirfd-gebundene
Elternprüfungen und Boolean-Gleichheit für private Regeln; Reports enthalten keine privaten
Metadaten.

- [ ] **Step 5: Prüfe FRESH und CURRENT**

Run: `python3 -m unittest tests.test_bootstrap_contract.FreshInstall tests.test_bootstrap_contract.CurrentInstall -v`

Expected: FRESH `PASS`; CURRENT beim zweiten Lauf ohne Mutation `PASS`.

- [ ] **Step 6: Prüfe LEGACY und Rollback**

Run: `python3 -m unittest tests.test_bootstrap_contract.LegacyInstall tests.test_bootstrap_contract.Rollback -v`

Expected: Legacy-`core/adapters/profile`-Imports entfernt, synthetische Regeln erhalten, Backup
verifiziert; injizierter Verifikationsfehler stellt den Ausgang byte-identisch wieder her.

- [ ] **Step 7: Prüfe die Hostile- und Portabilitätsmatrix**

Run: `LC_ALL=C TZ=UTC python3 -m unittest tests.test_bootstrap_contract.PathSafety tests.test_bootstrap_contract.Portability -v`

Expected: HOME mit Leerzeichen, fremdes CWD, ungesetzte optionale Harnessvariable und
`init.defaultBranch=master` funktionieren; leerer, relativer oder `.`-Root, Rootkonflikte,
Traversal, unerwartete Symlinks, außerhalb liegende Ziele und eine zwischen Inspect/Aktivierung
veränderte Elternidentität werden fail-closed blockiert.

- [ ] **Step 8: Committe den Bootstrap**

```bash
git add Installation.bootstrap.prompt.md tests/support tests/fixtures tests/test_bootstrap_contract.py
git commit -m "feat(governance): add generic installation bootstrap"
```

### Task 6: local_rules-Runtime, neutraler Harness und Offlinebetrieb

**Files:**
- Create: `tests/support/neutral_harness.py`
- Create: `tests/test_neutral_harness.py`
- Create: `tests/test_local_rules_runtime.py`
- Create: `tests/test_offline_runtime.py`
- Create: `tests/fixtures/runtime/synthetic-local-rules.md`

- [ ] **Step 1: Schreibe rote Runtime-Tests mit synthetischen Regeln**

```python
def test_runtime_loads_local_rules_after_manifest(self):
    result = harness.new_session(task="return synthetic marker")
    self.assertEqual(result.chain, ["bootstrap", "manifest", "local_rules", "modules"])
    self.assertTrue(result.synthetic_rule_effect)
    self.assertFalse(result.used_legacy_source)
```

- [ ] **Step 2: Verifiziere den roten Test**

Run: `python3 -m unittest tests.test_local_rules_runtime tests.test_neutral_harness -v`

Expected: `FAIL` wegen fehlendem neutralen Harness.

- [ ] **Step 3: Implementiere den produktneutralen Testharness**

Der Harness akzeptiert ausschließlich absolute Pfade für globale Instruktion, Konfiguration und
Enforcementcommand. Er setzt weder `CODEX_HOME` noch produktbezogene Defaults.

- [ ] **Step 4: Prüfe Offlinebetrieb**

Run: `python3 -m unittest tests.test_offline_runtime -v`

Expected: Nach Materialisierung blockiert ein Netzwerk-Guard jeden Socketzugriff; Discovery,
Manifest, lokale Regeln, Routing, Providerinitialisierung, allow/deny und Audit bleiben `PASS`.

- [ ] **Step 5: Belege explizit die Grenze des deterministischen Unit-Harness**

`tests/test_local_rules_runtime.py` prüft die Governance-Ladereihenfolge, ersetzt aber nicht den
verpflichtenden echten `codex exec`-Lauf. Die echte Runtimeprobe wird in Task 8 aus identischer
Clean-Linux-Basis mit ausschließlich synthetischen Regeln ausgeführt; `codex debug prompt-input`
ist nur Diagnostik und kein local_rules-Nachweis.

- [ ] **Step 6: Committe Runtime- und Neutral-Harness-Tests**

```bash
git add tests/support/neutral_harness.py tests/test_neutral_harness.py tests/test_local_rules_runtime.py tests/test_offline_runtime.py
git commit -m "test(governance): cover neutral and offline runtime paths"
```

### Task 7: Mitarbeiterdokumentation und Releasemetadaten

**Files:**
- Modify: `README.md`
- Modify: `INSTALL.md`
- Modify: `CHANGELOG.md`
- Modify: `VERSION`
- Modify: `.gitignore`
- Test: `tests/test_documentation.py`

- [ ] **Step 1: Schreibe Dokumentationsverträge**

```python
for heading in REQUIRED_README_HEADINGS:
    self.assertIn(heading, README)
self.assertLessEqual(README.count("```mermaid"), 3)
self.assertIn("Public Preview", README)
self.assertIn("Installation.bootstrap.prompt.md", README)
```

- [ ] **Step 2: Verifiziere den roten Test**

Run: `python3 -m unittest tests.test_documentation -v`

Expected: `FAIL` wegen fehlender Schnellstart-, Migrations-, Enforcement- und Limitationsabschnitte.

- [ ] **Step 3: Überarbeite README und Boundary-Dokument**

README erklärt Mitarbeiterfluss, Architektur, Governance/Enforcement, drei Installationszustände,
private Regeln, Routing/Rollen, Microsoft-Pin, Tests, Securitygrenzen und Known Limitations mit
höchstens drei Mermaid-Diagrammen. `INSTALL.md` bleibt Boundary-Dokument und verweist auf den
ausführbaren Prompt.

- [ ] **Step 4: Klassifiziere SemVer als MINOR und setze 0.3.0**

Run: `printf '0.3.0\n'` darf nicht als Shell-Schreibtrick verwendet werden; ändere `VERSION`,
README und CHANGELOG mit `apply_patch` und halte `VERSION` als einzige Versions-SSOT.

- [ ] **Step 5: Prüfe Dokumentation und Releasebaum**

Run: `python3 -m unittest tests.test_documentation -v && python3 tools/release_check.py tree`

Expected: `PASS`.

- [ ] **Step 6: Committe Dokumentation und Version**

```bash
git add README.md INSTALL.md CHANGELOG.md VERSION .gitignore tests/test_documentation.py
git commit -m "chore(release): prepare governance version 0.3.0"
```

### Task 8: Clean-Linux-Codex-E2E und CI

**Files:**
- Create: `tests/e2e/Dockerfile`
- Create: `tests/e2e/run_clean_linux.sh`
- Create: `tests/e2e/run_codex_local_rules.sh`
- Create: `tests/e2e/run_neutral_harness.sh`
- Create: `tests/e2e/codex_probes.md`
- Create: `tests/test_e2e_contract.py`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Schreibe rote Container-/Secret-Isolationsverträge**

```python
self.assertNotIn("COPY auth.json", DOCKERFILE)
self.assertIn("codex-cli@0.147.0", DOCKERFILE)
self.assertIn("--network none", RUNNER)
self.assertIn("LEGACY", RUNNER)
```

- [ ] **Step 2: Verifiziere den roten Test**

Run: `python3 -m unittest tests.test_e2e_contract -v`

Expected: `FAIL` wegen fehlender Containerartefakte.

- [ ] **Step 3: Baue identische baseline/governed-Basis**

Run: `docker build -t agent-governance-e2e-base:0.3.0 tests/e2e`

Expected: Linux, CA-Zertifikate, git, Python, Node/npm und Codex 0.147.0; kein Governancebundle,
kein Microsoftsnapshot und keine Credentials im Image.

- [ ] **Step 4: Führe echte Codex-Probes aus**

Run: `tests/e2e/run_clean_linux.sh --source HEAD`

Expected: Governance/Manifest/local_rules, Routing, read-only, Workspacewrite, unauthorized effect,
Priorität, Provider-before-effect, deny, Approval, Providerfehler und Instruction Boundary `PASS`.

`run_codex_local_rules.sh` startet dazu einen neuen `codex exec`-Prozess in einem unabhängigen
Git-Workspace. Der Child-Agent liest Bootstrap, absoluten Root, Manifest und synthetische
`local_rules` read-only, zeigt ausschließlich Boolean-PASS-Felder und beweist Regelwirkung sowie
die Nichtverwendung von Legacy- und Hostquellen.

- [ ] **Step 5: Führe den neutralen Harness aus**

Run: `tests/e2e/run_neutral_harness.sh --source HEAD`

Expected: kein `CODEX_HOME`, kein Produktdefault und kein bekannter Harnessname im Input;
Bootstrap bestimmt absolute Governance-, Instruktions-, Konfigurations- und Enforcementpfade und
Fresh/Current/Legacy bestehen.

- [ ] **Step 6: Führe Offline- und Secret-Isolation aus**

Run: `tests/e2e/run_clean_linux.sh --source HEAD --offline --verify-secrets`

Expected: `PASS`; kein Auth in Image, History, Export oder Report; ephemere Authkopie Modus 0600
unter Verzeichnis 0700 und nach dem Lauf entfernt.

- [ ] **Step 7: Prüfe die vollständige Portabilitätsmatrix im Container**

Run: `LC_ALL=C TZ=UTC tests/e2e/run_clean_linux.sh --source HEAD --hostile-matrix`

Expected: fremdes CWD, Git-Defaultbranch `master`, HOME mit Leerzeichen, absolute Pfade,
ungesetzte optionale Harnessvariablen, Rootkonflikte, relative Roots, Symlinks sowie vorhandene
und fehlende lokale Regeln entsprechen dem Vertrag.

- [ ] **Step 8: Binde relevante Linuxchecks blockierend in CI ein**

CI führt Unit-/Releasechecks, neutralen Harness, Providerbridge und containergeeignete Tests aus.
Echte Codex-Auth-E2E bleibt ein getrennt belegtes Gate, falls GitHub Actions keine sichere
Authentisierung besitzt.

- [ ] **Step 9: Committe E2E und CI**

```bash
git add tests/e2e tests/test_e2e_contract.py .github/workflows/ci.yml
git commit -m "test(governance): add clean-room integration coverage"
```

### Task 9: Exact-Head-Gates, PR, Merge und Release

**Files:**
- Modify: keine Produktdateien ohne neues Finding
- Create: temporäre sichere Evidenz außerhalb des Repositorys

- [ ] **Step 1: Lade `requesting-code-review` und `verification-before-completion`**

Exact Head, Risikoklasse und Rollen werden vor den Prüfungen fixiert.

- [ ] **Step 2: Führe vollständige lokale Verifikation aus**

Run: `LC_ALL=C TZ=UTC python3 -m unittest discover -s tests -v`

Run: `python3 tools/release_check.py tree`

Run: `git diff --check && git status --short && git rev-parse HEAD`

Expected: alle `PASS`, Arbeitsbaum sauber.

- [ ] **Step 3: Pushe und erstelle genau einen Draft-PR**

```bash
git push -u origin feat/governance/generic-bootstrap-enforcement
gh pr create --draft --base main --head feat/governance/generic-bootstrap-enforcement \
  --title "feat(governance): add generic bootstrap and enforcement layer" \
  --body-file /private/tmp/agent-governance-pr-body.md
```

- [ ] **Step 4: Belege SHA-Gleichheit und unabhängige Rollen**

Local Head, Remote Branch Head und PR Head müssen identisch sein. GitHub Copilot Review wird genau
einmal versucht; bei `no` oder `unknown` prüft ein frischer read-only QA-Agent. Ein anderer
frischer read-only SEC-Kontext beziehungsweise Codex Security prüft denselben Head. QA prüft
SSOT, Scope, Neutralität, FRESH/CURRENT/LEGACY, local_rules, Reihenfolge, Microsoft-Abgrenzung,
Pin/Lizenz/Instruction Boundary, Rollback, Dokumentation, Container und Releasefähigkeit. SEC
prüft Dateisystem/Archive/Supply Chain/Dependencies, Enforcement- und Approval-Bypass,
Prompt-/Instruction-/Authority-Confusion, Traversal/Symlink/TOCTOU, Credential- und
Private-Rule-Leaks einschließlich Fingerprints, Fail-open, Rollbackverlust, Hostüberschreibung und
unsichere Releaseartefakte. Beide liefern `blocking-valid = 0`.

- [ ] **Step 5: Warte alle blockierenden GitHub-Actions ab**

Run: `pr_number="$(gh pr view --json number --jq .number)" && gh pr checks "$pr_number" --watch`

Expected: jeder tatsächlich blockierende Job `success` und `headSha` gleich Exact Head.

- [ ] **Step 6: Klassifiziere Reviewthreads und erneuere Gates nach jedem Fix**

Jeder Thread erhält `valid-blocking`, `valid-nonblocking`, `invalid`, `duplicate` oder
`stale-after-change`. Jede inhaltliche Änderung erzwingt neue QA-, SEC-, CI- und betroffene
E2E-Evidenz.

- [ ] **Step 7: Merge ohne Bypass**

Run: `pr_number="$(gh pr view --json number --jq .number)" && exact_head="$(git rev-parse HEAD)" && gh pr merge "$pr_number" --merge --match-head-commit "$exact_head"`

Expected: PR gemerged, kein Force-/Ruleset-Bypass, frisches `main` auf dem Releasecommit.

- [ ] **Step 8: Erzeuge und verifiziere signierten Tag**

```bash
release_sha="$(git rev-parse origin/main)"
git tag -s v0.3.0 "$release_sha" -m "Agent Governance 0.3.0"
git tag -v v0.3.0
git push origin v0.3.0
python3 tools/release_check.py tag v0.3.0
```

Expected: Signatur `PASS`, Tag zeigt exakt auf Release-SHA.

- [ ] **Step 9: Veröffentliche GitHub Release**

```bash
gh release create v0.3.0 --verify-tag --title "Agent Governance 0.3.0" \
  --notes-file /private/tmp/agent-governance-release-notes.md
```

Release Notes nennen Microsoft `v4.1.0`, Commit, Public Preview, verifizierte Harnesses, E2E und
Known Limitations ohne Microsoft-Zertifizierungsbehauptung.

- [ ] **Step 10: Führe Post-Release-Checkout und Cleanup aus**

Frisch geklonter Tag durchläuft Volltests, Releasecheck, FRESH, LEGACY, local_rules, Codex-E2E,
Provider allow/deny/Approval/error und Secret-Isolation. Danach werden ausschließlich erzeugte
Container, Volumes, Networks, Tempdateien, Authkopien und Worktree bereinigt. Erst bei vollständiger
SHA-Gleichheit darf `PRODUCTION_READY = PASS` gemeldet werden.
