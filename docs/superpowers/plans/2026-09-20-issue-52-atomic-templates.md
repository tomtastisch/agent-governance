# Issue #52 — Atomare Governance-Templates mit einer kanonischen Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (empfohlen) oder superpowers:executing-plans.

**Goal:** Die wiederverwendbaren generischen Form- und Interaktionsverträge aus dem Sammelmodul
`bundle/agent-governance/modules/templates.md` atomisieren, über genau eine kanonische
Template-Registry auffindbar machen und die zwei realen generischen Template-Lücken
(Release-Checkpoint, External-Effect-Approval-Checkpoint) schließen.

**Architecture:** Das Root-Manifest (schema_version 4) referenziert zusätzlich zum SSOT-Index
eine kanonische Template-Registry (`templates = "templates/manifest.toml"`). Die Registry ist ein
geschlossener Index stabiler Template-IDs auf atomare Markdown-Dateien unter `templates/`. Ein
Template-Resolver (TS `src/templates-catalog.ts`, Python `tests/support/catalog_validator.py`)
validiert Registry und Dateien fail-closed. Das Modul `modules/templates.md` wird zur rein
erklärenden Übersicht reduziert; die domain-spezifische Resume-Checkpoint-Form verbleibt beim
Resume-Owner (`modules/resume.md`).

**Spec:** GitHub Issue #52 (tomtastisch/agent-governance#52).

## Ausgangsinventur (realer Zustand, Exact Head 8da3e47)

1. Default Branch `main`, Exact Head `8da3e47` (VERSION `1.2.1`).
2. Sammel-SSOT für Formverträge: `bundle/agent-governance/modules/templates.md` (Regel `TPL-001`
   plus 7 strikte Vorlagen inkl. `Resume-Checkpoint` und 3 strukturierte Verträge).
3. Konsumenten: `modules/context.md` (Link `templates.md#kontextübergabe`),
   `modules/resume.md` (Link `templates.md#resume-checkpoint`), Rollen
   `quality-assurance.md`/`security-review.md` (laden Modul `templates`).
4. Registrarmechanismus vorhanden: `ssot/manifest.toml` (TOML-Katalog-Domains, erlaubt nur
   `.toml`-Pfade — für Markdown-Templates ungeeignet) → deshalb eigene Registry.
5. GitHub-native Templates: keine (keine `.github/ISSUE_TEMPLATE`/`PULL_REQUEST_TEMPLATE`).
6. Tests mit Templateinhalten: `tests/test_bundle.py::TemplateContract`,
   `tests/test_resume.py::ResumeTemplateContract`, `tests/test_bundle.py::test_template_markers_*`.
7. Registry-/Manifestmechanismen: `src/ssot-manifest.ts`, `src/governance-contract.ts`,
   `tests/support/catalog_validator.py`, `tests/support/neutral_harness.py`.
8. Reale generische Lücken ohne kanonischen Vertrag: **Release-Checkpoint** und
   **External-Effect-Approval-Checkpoint** (beide in #52 ausdrücklich als zu prüfende Lücken
   benannt; beide Vorgänge treten real wiederkehrend auf und verlieren bei freier Form
   Identity/Evidence/Autorisierung).

## Zielstruktur

```text
bundle/agent-governance/
├── manifest.toml                 # schema_version=4; ssot + templates
├── ssot/…                        # unverändert (routing/commands/discovery)
├── templates/
│   ├── manifest.toml             # geschlossene Registry (schema_version=1)
│   ├── git/{commit,branch}.md
│   ├── delivery/{push-pr-checkpoint,pull-request,release-checkpoint}.md
│   ├── review/finding.md
│   ├── context/handoff.md
│   ├── communication/{status,tool-error-blocker,completion}.md
│   └── external-effects/approval-checkpoint.md
├── modules/
│   ├── templates.md              # Übersicht/Index (kein Sammelvertrag mehr)
│   └── resume.md                 # übernimmt domain-spezifische Resume-Checkpoint-Form
└── roles/…
```

## Entscheidungen

- **Stable IDs** folgen der vorhandenen Repository-Konvention `[a-z][a-z0-9_]*` (Module-, Trigger-
  und Tool-IDs), also `git_commit`, `delivery_push_pr_checkpoint` usw. — keine Punkt-IDs
  (im geschlossenen TOML-Parser nicht zulässig) und keine parallelen Alias-IDs.
- **Resume-Entscheidung:** kein generisches `context/resume.md`. Die Resume-Checkpoint-Form ist
  domain-spezifisch (Owner: Resume-Capability, `RES-005`), unterscheidet sich von `context/handoff`
  durch bindungsbasierte Pflichtfelder (Task-/Scope-Identität, Dirty-State,
  Evidence-Bindungsmatrix REUSE/RERUN/INVALIDATE/INCOMPLETE, TOON-Projektion). Eine Erweiterung
  von `handoff` würde dessen generische Semantik verschlechtern. Die Form wandert in
  `modules/resume.md` und wird **nicht** in die generische Registry aufgenommen.
- **Release-Checkpoint** und **External-Effect-Approval-Checkpoint** werden als echte generische
  Lücken ergänzt (siehe Gap-Analyse).
- Keine Template-DSL, keine Vererbung, keine leeren Zukunftsdomains (YAGNI).

## Global Constraints

- `one semantic authority → one canonical template → one registry entry`; keine Dual Authority.
- Registry-/Pfadwerte sind untrusted: fail-closed bei unbekanntem Feld, doppelter ID, doppeltem
  Pfad, fehlender Datei, absolutem Pfad, Traversal, Symlink-Escape, Verzeichnis statt Datei,
  Template ohne Owner, zwei kanonischen Templates derselben Semantik.
- Governanceinhalte semantisch unverändert migrieren; bestehende relevante Tests nicht abschwächen.
- Kein Push/PR/Merge/Release/npm-publish ohne ausdrückliche Freigabe.

---

### Task 1: Atomare Templates + Registry (Bundle)

- [ ] `templates/manifest.toml` mit 11 geschlossenen Einträgen anlegen.
- [ ] 11 atomare Template-Dateien unter `templates/{git,delivery,review,context,communication,external-effects}/`.
- [ ] `modules/templates.md` auf Übersicht/Index reduzieren (Regel `TPL-001` bleibt).
- [ ] `modules/resume.md` um `## Resume-Checkpoint`-Form erweitern; `RES-005`-Link anpassen.
- [ ] `modules/context.md`-Link auf `../templates/context/handoff.md` umstellen.
- [ ] `manifest.toml`: `schema_version = 4`, `templates = "templates/manifest.toml"`.

### Task 2: TS-Resolver + Contract

- [ ] `src/templates-catalog.ts`: `parseTemplatesManifestText`, `loadTemplateIndex`,
      `resolveTemplate(id)` — geschlossen, pfad-/symlinksicher.
- [ ] `src/catalog-paths.ts`: Template-Pfadauflösung ergänzen.
- [ ] `src/governance-contract.ts`: schema 4 + Templates-Registry-Validierung + `referencedPaths`.

### Task 3: Python-Validator + Runtime

- [ ] `tests/support/catalog_validator.py`: `MANIFEST_FIELDS` + schema 4 + Templates-Validierung
      (Registry, Pfade, Dateien, Owner, Duplikate) + `contract.template_paths`.
- [ ] `tests/support/neutral_harness.py`: Template-Pfade in `read_paths` aufnehmen.

### Task 4: Tests

- [ ] Neu: `tests/test_templates.py` (Registry-Completeness, Duplicate/Unknown/Missing/Root-Escape/
      Symlink-Escape, Stable IDs, Required-Fields, Non-Responsibilities, No-Duplicate-Semantic,
      Gap-Analysis, Release-Checkpoint, External-Effect-Approval, Resume-Entscheidung,
      Fresh-Consumer).
- [ ] Neu: `tests/installer/templates-catalog.test.ts` (TS-Resolver positiv/negativ).
- [ ] Migrieren: `test_bundle.py`, `test_catalogs.py`, `test_resume.py`,
      `tests/installer/release.test.ts`, `tests/installer/pack-verifier.test.ts`.

### Task 5: Docs, Packaging, Gates

- [ ] `docs/decisions/0004-atomic-template-registry.md` (ADR, Ownershipregeln, Gap-Analyse).
- [ ] `CHANGELOG.md` `[Unreleased]` (Added/Changed; `**Breaking changes:** none`).
- [ ] `tools/verify-pack.mjs` requiredPaths um `templates/manifest.toml` ergänzen.
- [ ] `python3 tools/release_manifest.py generate`.
- [ ] Gates: `npm run typecheck`, `npm test`, `npm run build`, `npm run lint`,
      `python3 -m unittest discover -s tests -v`, `python3 tools/release_check.py tree`,
      `npm run pack:check`, `npm run test:package`.
- [ ] Unabhängige QA + SEC auf exaktem final Head.

## Gap-Analyse (reproduzierbar, in ADR-0004 belegt)

| Interaktion | Generisch? | Lücke? | Entscheidung |
|---|---|---|---|
| Release-Checkpoint | ja (mehrere Domains) | ja | `delivery/release-checkpoint.md` ergänzt |
| External-Effect-Approval | ja | ja | `external-effects/approval-checkpoint.md` ergänzt |
| Resume-Checkpoint | nein (Resume-Domain) | nein (bereits domain-ownend) | in `modules/resume.md`, kein generisches `resume.md` |
