# PR #156 Runtime-Sicherheit und Veröffentlichung — Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Issue #154 einschließlich seiner autorisierten Security-Erweiterung consumerwirksam in Version 1.9.0 ausliefern.

**Architecture:** Ein deterministisch aus dem veröffentlichten, integritätsgeprüften `@agntn/harnesses@0.3.0`-Archiv generierter Datensatz ersetzt den Runtime-Import. Der bestehende `HarnessDiscoveryPort` prüft unverändert passiv die Upstream-Binärnamen; Support und Bindings bleiben in der bestehenden Governance-SSOT. Dependency-PRs und Consumer-Audit sichern künftige Updates ab.

**Tech Stack:** Node >=24, TypeScript 5.9.2 AST, npm, Python-Archivleser, GitHub Actions und Dependabot.

**Spec:** [Issue #154](https://github.com/tomtastisch/agent-governance/issues/154), [Scope-Erweiterung](https://github.com/tomtastisch/agent-governance/issues/154#issuecomment-6056149303).

## Global Constraints

- `smol-toml >= 1.9.0`; keine betroffene SDK-Version im Runtime-Tree.
- Production-Abhängigkeiten exakt gepinnt; keine Overrides, Git-Pins oder Downgrades.
- Keine Harness-CLI-Ausführung und keine neue Support-/Binding-Authority.
- Alle 13 bisherigen Discovery-Einträge einschließlich Reihenfolge und Alternativbinärnamen erhalten.
- Kein Ausführen von Upstream-Code bei der Projektion und kein Download während Installation/Discovery.
- Commit, Push, QA/SEC, CI, Merge und Veröffentlichung bleiben getrennte Evidenzgrenzen.

## Review Focus

- Manipuliertes Archiv oder veraltete Projektion: Integritäts-/Driftprüfung muss abbrechen.
- Dynamische Upstream-Felder, geänderte Basismethode oder Registry: Generator muss abbrechen.
- Fehlende oder alternative Binärdateien: bisherige passive Installed-Semantik erhalten.
- Consumer ohne Root-Lockfile: derselbe sichere Runtime-Tree ist erforderlich.
- Neue verwundbare Updates: automatischer Vorschlag darf Review und Audit nicht umgehen.

### Task 1: Passive Discovery-Projektion

**Files:** `integrations/agntn-harnesses/`, `tools/project-harness-discovery.ts`, `src/init/harness-discovery.generated.ts`, `src/init/harnesses.ts`, `tests/installer/harness-projection.test.ts`, `tests/installer/init-harnesses.test.ts`, `THIRD_PARTY_NOTICES.md`.

**Interfaces:** `extractHarnessDescriptors(source)` liefert `{id, displayName, binaries}[]`; der bestehende `createAgntnHarnessesAdapter(): HarnessDiscoveryPort` bleibt erhalten.

- [x] Negative Generatorfälle als Tests schreiben; gezielt ausführen und RED belegen.
- [x] Verifiziertes Archiv und Lock übernehmen; literale AST-Projektion mit geprüfter Basismethoden-/Registry-Semantik implementieren.
- [x] Adapter auf generierte Daten umstellen; ausschließlich `which`/`where` verwenden.
- [x] Projektions-, Alternativbinärnamen- und Nichtausführungsregressionen GREEN prüfen.

### Task 2: Runtime-Tree und Updatevorsorge

**Files:** `package.json`, `package-lock.json`, `tools/verify-licenses.mjs`, `tests/test_installer_distribution.py`, `tests/e2e/run_package_consumers.sh`, `.github/dependabot.yml`, bestehende CI-/Publish-Workflows, `docs/dependency-evidence.md`, `CHANGELOG.md`.

**Interfaces:** Task 1 erzeugt den in `dist` kompilierten Datensatz; `harnesses:check` verifiziert Quelle, Lizenz und Projektion offline.

- [ ] Harnesses aus Runtime entfernen; erwartete Pins, Paketanzahl und Lizenznachweis aktualisieren.
- [ ] Dependabot täglich PRs für npm-Updates vorschlagen lassen; kein automatischer Merge/Publish.
- [ ] Fresh-Consumer-`npm ls` und Production-Audit ab Moderate in bestehende Paketgates aufnehmen; CI/Publish prüfen zusätzlich Projektion und Production-Audit.
- [ ] Entscheidungsbaum, sicheren Updateweg und Releasehinweise dokumentieren; alle lokalen Gates ausführen.

### Task 3: Finale Delivery

**Files:** Release-Metadaten, PR-Beschreibung und überprüfbare Gate-Evidenz.

**Interfaces:** Lokaler geprüfter Tree wird signiert committed; jede Review-Evidenz gilt nur für den finalen Head.

- [ ] Finalen Commit signieren und normalen Push nach erneuter Remote-Prüfung ausführen.
- [ ] Copilot-QA und unabhängigen SEC-Review auf finalem Head; Findings beheben und betroffene Gates erneuern.
- [ ] CI, Threads, Metadaten und Mergefähigkeit frisch verifizieren; autorisiert mergen und regulären Trusted-Publish durchführen.
- [ ] npm-Version, Integrität/Provenienz, Consumer-Tree, Audit und dynamischen README-Badge nach Veröffentlichung prüfen.
