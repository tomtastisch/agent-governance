# Cross-Language-Conformance Implementation Plan (#90)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Couple the TS governance validators and the Python reference validator through a shared contract fixture and a cross-language conformance gate.

**Architecture:** One neutral `contracts/governance-contract.json` becomes the single source of structural definitions; both languages load it and keep independent validation logic; `tests/test_conformance.py` runs both against shared fixtures and asserts identical verdicts.

**Tech Stack:** TypeScript (NodeNext ESM, `node --experimental-strip-types`), Python 3.11+ (`unittest`, `tomllib`), JSON fixture.

**Spec:** `docs/superpowers/specs/2026-09-26-issue-90-cross-language-conformance-design.md`

## Global Constraints

- Governance-Bundle und Kataloge bleiben unverändert (keine SSOT-Änderung).
- Öffentlicher Package-/CLI-Vertrag unverändert; SemVer patch.
- Fixture ist reine Deklaration, keine Validierungslogik.
- Fixture liegt außerhalb `bundle/` und beeinflusst `release.files.sha256` nicht.
- `npm run build` muss `contracts/governance-contract.json` in das Paket übernehmen
  (`package.json` `files`).

---

### Task 1: Contract-Fixture anlegen

**Files:**
- Create: `contracts/governance-contract.json`

**Interfaces:**
- Produces: JSON mit `schema_version`, `fields`, `domains`, `vocabularies` (exakt wie im Spec).

- [ ] **Step 1: Fixture schreiben**

Inhalt gemäß Spec `## Fixture-Struktur`, mit den exakten Feld-/Vokabularlisten der aktuellen
Implementierung (siehe `catalog_validator.py` und die TS-Module). Keine Logik, nur Daten.

- [ ] **Step 2: JSON syntaktisch validieren**

Run: `python3 -m json.tool contracts/governance-contract.json >/dev/null && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add contracts/governance-contract.json
git commit -m "feat(conformance): add shared governance contract fixture (#90)"
```

---

### Task 2: TS-Loader für die Fixture

**Files:**
- Create: `src/contract-fixture.ts`

**Interfaces:**
- Produces: `export interface GovernanceContractFixture { ... }` (typisiert) und
  `export const governanceContract: Readonly<GovernanceContractFixture>` (gefroren).

- [ ] **Step 1: Fail-closed-Loader schreiben**

Liest `join(PACKAGE_RELEASE_ROOT, "contracts", "governance-contract.json")`, validiert ein
geschlossenes Schema (unbekannte Schlüssel → Fehler) und friert das Ergebnis ein.

- [ ] **Step 2: Typecheck**

Run: `npm run typecheck`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/contract-fixture.ts
git commit -m "feat(conformance): add typed contract-fixture loader (#90)"
```

---

### Task 3: TS-Validatoren auf die Fixture umstellen

**Files:**
- Modify: `src/governance-contract.ts`, `src/ssot-manifest.ts`, `src/routing-catalog.ts`,
  `src/discovery-catalog.ts`, `src/command-catalog.ts`, `src/templates-catalog.ts`, `src/work-items.ts`

**Interfaces:**
- Consumes: `governanceContract` aus `src/contract-fixture.ts`.
- Produces: unveränderte öffentliche Funktionen (`validateGovernanceContract`,
  `parseRoutingCatalogs`, `parseDiscoveryCatalogText`, `parseCommandCatalogText`,
  `parseTemplatesManifestText`, `parseClassificationsText`, `parseProjectionsText`,
  `loadSsotIndex`), nur die Feld-/Vokabularwerte stammen aus der Fixture.

- [ ] **Step 1: Konstanten je Modul durch Fixture-Werte ersetzen**

`MODULE_FIELDS`, `ROLE_FIELDS`, `TOOL_FIELDS`, `SSOT_DOMAIN_IDS`, `TEMPLATE_FIELDS`,
`TEMPLATE_CATEGORIES`, `COMMAND_FIELDS`/`CAPABILITIES`/`EFFECTS`, Discovery- und
Work-Item-Feldmengen/Vokabulare aus der Fixture beziehen.

- [ ] **Step 2: Tests grün halten**

Run: `npm test`
Expected: PASS (alle bestehenden TS-Tests unverändert grün)

- [ ] **Step 3: Typecheck + Lint**

Run: `npm run typecheck && npm run lint`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/
git commit -m "refactor(conformance): derive validator field sets from contract fixture (#90)"
```

---

### Task 4: Python-Referenz auf die Fixture umstellen

**Files:**
- Modify: `tests/support/catalog_validator.py`

**Interfaces:**
- Consumes: `contracts/governance-contract.json` via `json.load`.
- Produces: `load_contract_fixture()`, bestehende Konstanten werden daraus abgeleitet.

- [ ] **Step 1: `load_contract_fixture()` und Konstanten ableiten**

Alle `frozenset(...)`-Konstanten (`MANIFEST_FIELDS`, `SSOT_DOMAINS`, `SSOT_DOMAIN_CATALOGS`,
`VOCABULARY_FIELDS`, `MODULE_FIELDS`, `ROLE_FIELDS`, `TOOL_FIELDS`, `COMMAND_FIELDS`,
`COMMAND_CAPABILITIES`, `COMMAND_EFFECTS`, `DISCOVERY_*`, `TEMPLATE_*`, `WORK_ITEM_*`) aus der
Fixture laden.

- [ ] **Step 2: Bestehende Python-Tests grün halten**

Run: `python3 -m unittest tests.test_catalogs -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/support/catalog_validator.py
git commit -m "refactor(conformance): derive python reference field sets from contract fixture (#90)"
```

---

### Task 5: Cross-Language-Conformance-Gate

**Files:**
- Create: `tests/installer/conformance.test.ts`
- Create: `tests/test_conformance.py`
- Create: `tests/contracts/conformance-mutations.json`

**Interfaces:**
- Consumes: `validateGovernanceContract` (TS) in `npm test`; `catalog_validator.load_catalog_contract`
  (Python).
- Produces: geteilte Mutation-Batterie; je Sprache ein Test mit identischen Accept/Reject-Verdicts.

- [ ] **Step 1: TS-Test schreiben**

`tests/installer/conformance.test.ts`: validiert das reale Bundle mit `validateGovernanceContract`
und weist jede Mutation der geteilten Batterie zurück (frische Bundle-Kopie pro Mutation).

- [ ] **Step 2: Python-Test schreiben**

`tests/test_conformance.py`: Fixture-Selbstkonsistenz, Python-Referenz akzeptiert das reale Bundle,
lehnt jede Mutation ab und leitet ihre Konstanten aus der Fixture ab. Kein Node-Aufruf.

- [ ] **Step 3: Mutation-Batterie-Fixture schreiben**

`tests/contracts/conformance-mutations.json`: Liste von `{ "file", "find", "replace" }`
(relative Pfade unter `bundle/agent-governance/`).

- [ ] **Step 4: Tests ausführen**

Run: `npm test` und `python3 -m unittest tests.test_conformance -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/
git commit -m "test(conformance): add cross-language conformance gate (#90)"
```

---

### Task 6: Paketauslieferung und Dokumentation

**Files:**
- Modify: `package.json` (`files` um `contracts` ergänzen), `CHANGELOG.md`
- Modify: `docs/decisions/0007-cross-language-conformance.md` (neu, kurz)

- [ ] **Step 1: `package.json` `files` ergänzen**

`contracts` in das `files`-Array aufnehmen, damit `npm pack` die Fixture ausliefert.

- [ ] **Step 2: `pack:check` verifizieren**

Run: `npm run pack:check`
Expected: PASS, Fixture im Pack enthalten

- [ ] **Step 3: CHANGELOG + Entscheidungsrecord**

`CHANGELOG.md` unter `[Unreleased]` → `### Added`; kurzer Entscheidungsrecord anlegen.

- [ ] **Step 4: Commit**

```bash
git add package.json CHANGELOG.md docs/decisions/
git commit -m "docs(conformance): ship contract fixture and record decision (#90)"
```

---

### Task 7: Vollständige Verifikation und Issue-Abgleich

- [ ] **Step 1: Gesamte Test-Suite**

Run: `npm test && npm run typecheck && npm run lint && npm run build && npm run pack:check`
und `python3 -m unittest discover -s tests -p 'test_*.py' -v`
Expected: PASS

- [ ] **Step 2: Issue #90 aktualisieren**

Issue-Körper auf den realen Ist-Stand bringen (Pfade, bereits erfolgte Konsolidierung,
verbleibender Scope) und den umgesetzten Scope dokumentieren.

- [ ] **Step 3: PR erstellen**

```bash
git push -u origin feat/issue-90/cross-language-conformance
gh pr create --title "..." --body "Closes #90 ..."
```
