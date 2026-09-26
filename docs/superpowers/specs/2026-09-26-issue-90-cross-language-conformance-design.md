# Design: Governance-Validator-Konsolidierung und Cross-Language-Conformance (#90)

> Historische Evidenz - nicht normativ. Der maßgebliche Vertrag ist Issue #90 und die
> Implementierung samt Tests.

## Ziel

Die produktiven TypeScript-Governance-Validatoren (`src/governance-contract.ts`,
`src/ssot-manifest.ts`, `src/routing-catalog.ts`, `src/discovery-catalog.ts`,
`src/command-catalog.ts`, `src/templates-catalog.ts`, `src/work-items.ts`) und die
unabhängige Python-Testreferenz (`tests/support/catalog_validator.py`) werden über einen
expliziten **Cross-Language-Conformance-Vertrag** gekoppelt. Die bislang in beiden Sprachen
parallel manuell gepflegten Schema-, Feld-, Domain- und Vokabular-Definitionen wandern in
eine gemeinsame, sprachneutrale **Contract-Fixture** und werden durch ein
**Cross-Language-Conformance-Gate** gegen Drift abgesichert.

Es entsteht keine zweite produktive Authority, die Python-Testreferenz konsumiert nicht die
TypeScript-Implementierung, und die unabhängige Testwirkung wird nicht durch gemeinsame
Implementierungslogik aufgehoben: geteilt wird ausschließlich die *Deklaration* (Struktur-
Metadaten), nicht die Validierungslogik.

## Nicht-Ziele

- Command-spezifische Redundanz (Issue #88) wird nicht erneut implementiert.
- Keine Änderung am öffentlichen Package-/CLI-Vertrag (SemVer-patch-kompatibel).
- Keine Änderung der produktiven Governance-SSOT (Manifest/Kataloge bleiben unverändert).
- Keine gemeinsame Validierungslogik: TS und Python behalten jeweils ihre eigene Implementierung.

## Current-State (Implementierungszeitpunkt)

- `main`-Head: `78cc6fc483f58ce24ca177ce176268a71c3df10c` (Release 1.7.2).
- Die Governance-Kataloge sind in `bundle/agent-governance/ssot/**` abgelegt und werden
  produktiv von `verifyRelease` (`src/release.ts` → `validateGovernanceContract`) geprüft.
- Die Python-Testreferenz `tests/support/catalog_validator.py` (ca. 920 Zeilen) ist eine
  vollständig unabhängige Re-Implementierung derselben Verträge.
- Bereits vorhandene geteilte Test-Fixtures: `tests/contracts/public-commands.json`
  (Command-Oracle, nur Python-seitig konsumiert).

## Entscheidungen

### D1 — Contract-Fixture ist deklarativer JSON, keine Logik

Die Fixture `contracts/governance-contract.json` ist eine reine, sprachneutrale Deklaration
aller strukturellen Definitionen (Feldmengen, Domain-/Kataloglisten, Vokabulare). Sie enthält
keine Validierungslogik und ist damit keine zweite produktive Authority: die produktive
Authority bleibt die Governance-SSOT; die Fixture dokumentiert und pinnt ausschließlich deren
erwartete *Struktur*.

### D2 — Fixture wird im Paket ausgeliefert und von beiden Sprachen gelesen

Die Fixture liegt unter `contracts/governance-contract.json` im Repository-Root und wird in
`package.json` `files` aufgenommen. Beide Sprachen lesen dieselbe physische Datei:

- **TypeScript** über `readFileSync(join(PACKAGE_RELEASE_ROOT, "contracts", "governance-contract.json"))`.
  `PACKAGE_RELEASE_ROOT` (aus `src/catalog-paths.ts`) zeigt im Repo auf den Repo-Root und im
  installierten Paket auf den Paket-Root; der Pfad ist damit in beiden Kontexten stabil.
- **Python** über `ROOT / "contracts" / "governance-contract.json"`.

### D3 — TS konsumiert die Fixture über einen typisierten Loader

`src/contract-fixture.ts` lädt und validiert die Fixture strikt (geschlossenes Schema,
unbekannte/unvollständige Felder → fail-closed) und exportiert gefrorene typisierte Konstanten.
Die sieben Validator-Module ersetzen ihre hartkodierten Konstanten durch diese Werte. Die
Validierungslogik bleibt pro Modul unverändert; nur die *Werte* kommen aus der Fixture.

### D4 — Python konsumiert dieselbe Fixture

`tests/support/catalog_validator.py` lädt die Fixture (`load_contract_fixture`) und ersetzt
alle hartkodierten `frozenset(...)`-Konstanten durch die Fixture-Werte. Der Loader ist
fail-closed: fehlende oder fehlerhaft typisierte Felder brechen den Import ab.

### D5 — Cross-Language-Conformance-Gate über geteilte Fixtures

Beide Validatoren werden gegen dieselbe Menge an Fixtures geprüft und müssen identische
Accept/Reject-Verdicts liefern:

1. **Valid-Bundle**: Python-Referenz und TS-Validator akzeptieren das reale Bundle.
2. **Mutation-Batterie**: Für jede Mutation (aus der gemeinsamen Fixture
   `tests/contracts/conformance-mutations.json`, beschrieben als `(file, find, replace)`)
   müssen beide Validatoren dasselbe Verdict liefern (Reject auf der verletzten Struktur).

Das Gate ist sprachbezogen aufgeteilt, teilt sich aber ausschließlich die Fixture-Dateien:
die Python-Seite prüft die Referenz in `tests/test_conformance.py`, die TypeScript-Seite den
produktiven Validator in `tests/installer/conformance.test.ts` (läuft über `npm test` mit
installierten Dependencies). Damit hängt der Python-Testpfad nicht von `node`/`node_modules`
ab, und die TypeScript-Validierung läuft in ihrer nativen Umgebung.

## Zielarchitektur

```text
produktive Governance-SSOT
        │
        ├── TypeScript Runtime Validator ──┐
        │                                 │
        └── Python Reference Validator ────┤
                    │                     │
                    ▼                     ▼
        contracts/governance-contract.json (gemeinsame Contract-Fixture)
                    │
                    ▼
        tests/test_conformance.py (Cross-Language-Conformance-Gate)
```

## Fixture-Struktur

```jsonc
{
  "schema_version": 1,
  "fields": {
    "manifest": ["schema_version", "local_rules", "ssot", "templates", "routing", "modules", "roles"],
    "routing": ["unknown", "ambiguous"],
    "ssot_manifest": ["schema_version", "domains"],
    "vocabulary": ["label", "description"],
    "module": ["path", "triggers", "dependencies"],
    "role": ["path", "triggers", "modules"],
    "tool": ["name", "purpose", "required_on", "useful_on", "policy_tags", "scopes", "evidence", "fallback", "constraints"],
    "command": ["id", "path", "description", "capability", "effect", "orchestrates", "interactive"],
    "template": ["path", "category", "format"],
    "discovery_top_level": ["schema_version", "limits", "confidence", "candidate_classes", "evidence_families", "signals"],
    "discovery_limits": ["max_depth", "max_files", "max_entries", "max_file_bytes", "max_sqlite_objects", "max_sqlite_columns", "max_duration_ms", "max_metadata_length"],
    "discovery_confidence": ["high_minimum_score", "high_minimum_families", "high_minimum_independent_sources", "high_requires_runtime", "uncertain_minimum_score"],
    "discovery_candidate": ["class", "label"],
    "discovery_family": ["default_strength", "weight"],
    "discovery_signal": ["id", "family", "source_kinds", "keys", "minimum_matches", "strength"],
    "work_item_classifications_top_level": ["schema_version", "dimensions", "classifications"],
    "work_item_dimension": ["label", "cardinality", "description"],
    "work_item_classification": ["label", "description"],
    "work_item_projections_top_level": ["schema_version", "projections", "title_markers"],
    "work_item_projection": ["classification", "name", "description", "color", "aliases"],
    "work_item_title_marker": ["classification", "marker"]
  },
  "domains": {
    "ssot": ["routing", "commands", "discovery", "work_items"],
    "ssot_catalogs": {
      "routing": ["triggers", "policy_tags", "scopes", "tools"],
      "commands": ["commands"],
      "discovery": ["discovery_signals"],
      "work_items": ["classifications", "github_labels"]
    }
  },
  "vocabularies": {
    "template_categories": ["git", "delivery", "review", "context", "communication", "external_effects"],
    "template_formats": ["markdown"],
    "command_capabilities": ["transaction", "orchestration"],
    "command_effects": ["read", "write"],
    "discovery_evidence_families": ["runtime", "state", "tooling", "ai_metadata", "package_metadata", "document"],
    "discovery_source_kinds": ["json", "toml", "plist", "sqlite_schema", "package_metadata"],
    "discovery_strengths": ["strong", "corroborating", "weak"],
    "discovery_candidate_classes": { "directory": "DIRECTORY", "app_bundle": "APP_BUNDLE" },
    "work_item_cardinalities": ["one", "many", "at_most_one", "zero_or_more"]
  }
}
```

## Fehlerbehandlung

- **Fixture-Load (TS wie Python)**: fehlende Datei, ungültiges JSON, unbekannte/unvollständige
  Schlüssel oder falsche Typen führen zu einem fail-closed Fehler beim Laden (kein stiller
  Fallback auf hartkodierte Werte).
- **Conformance-Probe**: jede Abweichung im Verdict (TS akzeptiert, Python lehnt ab oder
  umgekehrt) lässt das Gate fehlschlagen.
- **Release-Inventar**: die neue Fixture liegt außerhalb von `bundle/` und beeinflusst das
  geschlossene Release-Inventar (`release.files.sha256`) nicht.

## Verifikation

- `tests/test_conformance.py` (neu): Fixture-Selbstkonsistenz + Cross-Language-Verdicts.
- `tests/test_catalogs.py` (bestehend): bleibt grün (Python-Referenz unverändert vertragstreu).
- `tests/installer/**` (bestehend): bleibt grün (TS-Validatoren unverändert vertragstreu).
- `npm run typecheck`, `npm run lint`, `npm test`, `npm run build`, `npm run pack:check`.
