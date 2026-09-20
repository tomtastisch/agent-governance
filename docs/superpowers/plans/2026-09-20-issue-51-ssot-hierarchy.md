# Issue #51 — SSOT-Hierarchie für deklarative Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (empfohlen) oder superpowers:executing-plans.
> Steps use checkbox (`- [ ]`) syntax.

**Goal:** Alle real vorhandenen deklarativen Governance-SSOTs unter einen gemeinsamen, manifestierten und fail-closed validierten SSOT-Root (`bundle/agent-governance/ssot/`) mit genau einem geschlossenen Index ordnen.

**Architecture:** Root-Manifest (`bundle/agent-governance/manifest.toml`, schema_version 3) referenziert den SSOT-Index (`ssot/manifest.toml`). Der SSOT-Index registriert drei reale Domains — `routing`, `commands`, `discovery` — und ordnet jeder Semantik genau einen kanonischen Dateipfad zu. Root-Resolver kennt Domains, nicht deren Fachsemantik; Domain-Loader (routing/commands/discovery) lesen und validieren ausschließlich ihre Domain.

**Tech Stack:** TypeScript 5.9 (Node 24, ESM, smol-toml), Python 3.11 (tomllib) Testreferenz, npm-Package mit native prebuilds.

**Spec:** GitHub Issue #51 (tomtastisch/agent-governance#51); Design-Evidenz `docs/decisions/0003-canonical-governance-bundle.md`, `docs/superpowers/plans/2026-08-17-typed-routing-catalogs.md`.

## Ausgangsinventur (realer Zustand, Exact Head 096473b3cbb7f9e9359a388fda1e36791843f317)

Deklarative Governance-SSOTs (6 Kataloge unter `bundle/agent-governance/catalogs/`):
1. `triggers.toml` — Trigger-Vokabular (Semantik: routing/Trigger)
2. `policy-tags.toml` — Policy-Tag-Vokabular (routing/Wirkungsart)
3. `scopes.toml` — Scope-Vokabular (routing/Ressourcenklasse)
4. `tools.toml` — Toolkatalog (referenziert triggers/policy_tags/scopes)
5. `commands.toml` — Command-Katalog (öffentliche CLI-Commands)
6. `discovery-signals.toml` — Discovery-Signalkatalog (generische Discovery)

Root-Manifest `bundle/agent-governance/manifest.toml` (schema_version 2) indiziert diese über `[catalogs]`.

Consumer:
- TS: `src/governance-contract.ts` (God-Validator), `src/command-catalog.ts`, `src/discovery/catalog.ts`, `src/catalog-paths.ts`, `src/release.ts`, `src/cli.ts`/`src/public-commands.ts` (via loadCommandCatalog).
- Python-Testreferenz: `tests/support/catalog_validator.py` (paralleler Validator).
- Normative Markdown: `bundle/GOVERNANCE.md` (Referenz `catalogs/triggers.toml`), `bundle/agent-governance/modules/tool-routing.md` (Links `../catalogs/*.toml`).
- Packaging: `tools/verify-pack.mjs`, `release.files.sha256`, `tools/release_manifest.py`.
- Tests (TS + Python) mit fest codierten `catalogs/*`-Pfaden.

## Zielstruktur

```text
bundle/agent-governance/
├── manifest.toml            # schema_version=3; ssot = "ssot/manifest.toml"
├── ssot/
│   ├── manifest.toml        # schema_version=1; geschlossener Domain-Index
│   ├── routing/
│   │   ├── triggers.toml
│   │   ├── policy-tags.toml
│   │   ├── scopes.toml
│   │   └── tools.toml
│   ├── commands/
│   │   └── commands.toml
│   └── discovery/
│       └── discovery-signals.toml
├── modules/
├── roles/
└── local/
```

SSOT-Manifest (Pfade relativ zum SSOT-Verzeichnis `ssot/`):
```toml
schema_version = 1

[domains.routing]
triggers = "routing/triggers.toml"
policy_tags = "routing/policy-tags.toml"
scopes = "routing/scopes.toml"
tools = "routing/tools.toml"

[domains.commands]
commands = "commands/commands.toml"

[domains.discovery]
discovery_signals = "discovery/discovery-signals.toml"
```

## Global Constraints

- Nur real vorhandene Domains registrieren; keine leeren Zukunftsordner (YAGNI).
- `one semantic authority → one canonical location → one manifest path`; keine Dual Authority.
- Manifest-/Pfadwerte sind untrusted declarative input: fail-closed bei unbekannter Domain, unbekanntem Feld, fehlender Datei, doppelter Domain-ID, doppelter Authority, absoluten Pfaden, `..`-Traversal, Symlink-Escape, falschem Dateityp, Root-Escape, unbekannter Referenz, Selbstreferenz, Zyklus.
- Manifestwerte dürfen keine Codeausführung/Imports/Shellcommands/URLs autorisieren.
- Governanceinhalte semantisch unverändert migrieren (byte-identischer Kataloginhalt).
- Bestehende relevante Tests nicht abschwächen.
- Kein Push/PR/Merge/Release/npm-publish ohne ausdrückliche Freigabe.

---

### Task 1: SSOT-Verzeichnis, Index und Dateimigration (Bundle)

**Files:**
- Create: `bundle/agent-governance/ssot/manifest.toml`
- Create: `bundle/agent-governance/ssot/routing/triggers.toml` (byte-identisch von `catalogs/triggers.toml`)
- Create: `bundle/agent-governance/ssot/routing/policy-tags.toml`
- Create: `bundle/agent-governance/ssot/routing/scopes.toml`
- Create: `bundle/agent-governance/ssot/routing/tools.toml`
- Create: `bundle/agent-governance/ssot/commands/commands.toml`
- Create: `bundle/agent-governance/ssot/discovery/discovery-signals.toml`
- Delete: `bundle/agent-governance/catalogs/` (alle 6 Dateien)
- Modify: `bundle/agent-governance/manifest.toml` (schema_version 3, `ssot = "ssot/manifest.toml"` statt `[catalogs]`)
- Modify: `bundle/GOVERNANCE.md` (Katalogpfad-Referenz anpassen)
- Modify: `bundle/agent-governance/modules/tool-routing.md` (Markdown-Links `../catalogs/*` → `../ssot/routing/*`)

- [ ] Kataloge `git mv` in `ssot/{routing,commands,discovery}/`.
- [ ] `ssot/manifest.toml` mit obigem Inhalt anlegen.
- [ ] Root-Manifest `[catalogs]` → `ssot`, schema_version 3.
- [ ] `GOVERNANCE.md` Referenz `catalogs/triggers.toml` → `ssot/routing/triggers.toml` (und ggf. Satz „vier Kataloge" präzisieren).
- [ ] `tool-routing.md` Links anpassen.
- [ ] `python3 tools/release_manifest.py generate` ausführen (regeneriert `release.files.sha256`).

---

### Task 2: TypeScript SSOT-Resolver + Domain-Module

**Files:**
- Create: `src/ssot-manifest.ts` (SSOT-Index-Parser + Resolver, fail-closed)
- Create: `src/routing-catalog.ts` (routing Domain-Loader + Validator: vocabularies + tools)
- Modify: `src/catalog-paths.ts` (SSOT-Manifest-Pfadauflösung)
- Modify: `src/governance-contract.ts` (Root-Resolver; orchestriert Domain-Loader; schema 3)
- Modify: `src/command-catalog.ts` (Pfad via SSOT-Index)
- Modify: `src/discovery/catalog.ts` (Pfad via SSOT-Index)
- Modify: `src/release.ts` (SSOT-Dateien als Referenzen/Inventory)

- [ ] `src/ssot-manifest.ts`: `parseSsotManifestText`, `loadSsotIndex` (Domain-IDs `routing|commands|discovery`, Pfadsicherheit, Duplikat-/Unbekannt-/Missing-Fail-closed).
- [ ] `src/routing-catalog.ts`: übernimmt `parseClosedToml` + Vokabular-/Tool-Validierung aus `governance-contract.ts`.
- [ ] `governance-contract.ts` auf Root-Resolver reduzieren, Domain-Loader aufrufen, schema_version 3 + `ssot`.
- [ ] `command-catalog.ts`/`discovery/catalog.ts` lesen Pfade über SSOT-Index.
- [ ] `release.ts`: `referencedPaths` um SSOT-Dateien erweitern, `REQUIRED` + Inventory-Abgleich.

---

### Task 3: Python-Testreferenz + Tests

**Files:**
- Modify: `tests/support/catalog_validator.py` (SSOT-Index lesen, schema 3, Domain-Validierung)
- Modify: `tests/test_bundle.py`, `tests/test_catalogs.py`, `tests/test_governance.py`, `tests/test_local_rules_runtime.py`, `tests/test_neutral_harness.py`, `tests/test_resume.py`, `tests/test_copilot_qa_binding.py`, `tests/test_documentation.py`, `tests/test_e2e_contract.py`, `tests/test_source_consolidation.py`, `tests/test_bootstrap_contract.py`, `tests/support/neutral_harness.py`
- Modify: TS-Tests `tests/installer/{release,command-catalog,discovery-catalog,pack-verifier,discovery-regression,init-branding,discovery-boundary}.test.ts`

- [ ] `catalog_validator.py` auf SSOT-Index + schema 3 umstellen.
- [ ] Alle Python-Tests auf neue Pfade/Assertions umstellen.
- [ ] Alle TS-Tests auf neue Pfade umstellen.

---

### Task 4: Packaging, Tools, Docs, Gates

**Files:**
- Modify: `tools/verify-pack.mjs` (Pfade `catalogs/*` → `ssot/*`)
- Modify: `CHANGELOG.md` (`[Unreleased]` um Added/Changed-Eintrag ergänzen)
- Modify: `README.md` (falls Pfadreferenzen vorhanden)
- Modify: `docs/decisions/0003-canonical-governance-bundle.md` (Strukturdiagramm, historisch/nicht-normativ)

- [ ] `verify-pack.mjs` requiredPaths auf `ssot/...` umstellen.
- [ ] CHANGELOG `[Unreleased]` ergänzen (Added/Changed; Breaking changes: none oder present je nach SemVer-Klassifikation).
- [ ] Docs abgleichen.

---

### Task 5: Verifikation

- [ ] `npm run typecheck`, `npm test`, `npm run build`, `npm run lint`
- [ ] `python3 -m unittest discover -s tests -v`
- [ ] `python3 tools/release_manifest.py check`, `python3 tools/release_check.py tree`
- [ ] `npm run pack:check`, `npm run test:package`
- [ ] Fresh-Tarball-Consumer (alle Domains auflösbar)
- [ ] `git diff --check`
- [ ] Unabhängige QA + SEC auf exaktem final Head.
