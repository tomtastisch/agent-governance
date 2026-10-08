# Abhängigkeits- und Provenienzevidenz

> Historische Evidenz - nicht normativ. Maßgeblich sind Lockfiles, Paketartefakte und der geprüfte
> Exact Head des Pull Requests.

## Runtime-Dependency-Projektion des Releasekandidaten 1.9.2

`package.json.dependencies` und `package-lock.json` sind die einzige Runtime-Dependency-SSOT.
Die drei direkten, exakt gepinnten Runtime-Pakete sind `@clack/prompts` `1.8.1` (MIT)
für den interaktiven Prompt-Stack, `@toon-format/toon` `4.1.1` (MIT) für die deterministische
Resume-TOON-Projektion und `smol-toml` `1.9.0` (BSD-3-Clause) für die direkt importierten
Command- und Discovery-Kataloge. Der Lock löst exakt
`12 = 1 Root + 8 Production ohne Root + 3 Development` Paketdatensätze auf.
Integritäten und Registry-URLs stehen im Lockfile. Production-Audit ab Moderate,
License-Allowlist, Projektionsprüfung und echter Tarball-Consumer sind Releasegates.

Die Registry-Integritäten der direkten Pins sind für `@clack/prompts` exakt
`sha512-dlT1m5e/0yUL0kRNcQn7yGLVThkgbB0Ga/1AmfDDC/8ik6AIiSf2QLQO2zPYvefsHP0aFgxO93cVLCCfDp7kzQ==`,
für `@toon-format/toon` exakt
`sha512-SGCkS7IjVpwRmGPgnY8ENKpAf0EdAnZDOQkvFW0d2cgOpdn9FEFl7sTgryESyypXrWr0YajHGpwsAUX4zw9ZvA==`
und für `smol-toml` exakt
`sha512-hpd+HLON7HdZXqYchMM/+LaTTbdK0AU3NngIJ4KVyWbY9bfQqdL9cD+4yf6dUoU2Ap4VsU0JkQi6FxAI1B2mXQ==`.
Die Projekte sind jeweils über ihre veröffentlichten Repository-URLs nachverfolgbar; Maintenance,
Lizenz- und Auditstatus bleiben vor jedem Dependency-Update neu zu prüfen.

Der lokale Pack-Check für 1.1.0 ergab 131 Dateien, 137.388 Bytes komprimiert und 611.802 Bytes
entpackt. Ein frischer Consumer mit ausschließlich dem Tarball installierte acht Paketverzeichnisse
in 1.368 KiB `node_modules`; der Audit auf High-Severity meldete null Vulnerabilities.

`terminal-image@5.0.1` bleibt ausgeschlossen: Das kleine paketierte Terminal-Branding benötigt
keinen Bildrenderer, und dessen zusätzliche transitive Größe, Lizenz-, Audit- und Maintenance-Fläche
ist für dekoratives Rendering nicht verhältnismäßig. `chalk`, `boxen` und `log-update` sind ebenfalls
nicht deklariert, weil kein direkter Runtime-Import besteht. Der Init-Pfad installiert, repariert
oder lädt keine Pakete nach und startet weder npm, pnpm, yarn noch bun.

## Eigene Paketabhängigkeiten

Der Installer besitzt genau drei direkte Third-Party-Runtime-Abhängigkeiten:
`@clack/prompts` `1.8.1`, `@toon-format/toon` `4.1.1` und
`smol-toml` `1.9.0`. Die schmale
repository-eigene Node-API-C-Komponente nutzt ausschließlich OS- und stabile Node-API-Symbole;
sie wird für Darwin/Linux auf arm64/x64 im Releaseworkflow gebaut und als vier Prebuilds im
gleichen provenance-gebundenen npm-Tarball ausgeliefert. Exakt gelockte Entwicklungsabhängigkeiten
sind TypeScript `5.9.2` und `@types/node` `24.19.1`; die Lockfile-Projektion umfasst wie oben
beschrieben 12 Datensätze. Der lokale `npm audit --audit-level=high` meldete bei der Einführung null bekannte
Schwachstellen. Die direkten und Entwicklungsabhängigkeiten stammen aus der npm-Registry, ihre
Integritätswerte stehen in `package-lock.json`; Entwicklungsabhängigkeiten werden nicht in das
Laufzeitpaket gebündelt. Repository und Paket verwenden Apache-2.0.

## `neon-solutions/add-mcp`

Geprüft wurden das öffentliche Repository `neon-solutions/add-mcp`, der konkret relevante
Codex-/TOML-Upsertpfad und die npm-Metadaten von `add-mcp` 2.2.0. Die Registry nennt Apache-2.0,
Git-Head `a31f796e85f9dd1b5dcb4af1f8fdfd87abcdfe21`, Integrität
`sha512-5oPJRJHJqSiMZDQIT7svGa2SJVAZ4vP19XekxG80eUCIFJaGUG11qjLSXmErMIvJ7vgJ4gLSSnlSI7jk8x1LVA==`
und die Laufzeitabhängigkeiten `chalk`,
`js-yaml`, `commander`, `@iarna/toml`, `jsonc-parser` und `@clack/prompts`. Das Werkzeug schreibt
direkt in Konfigurationen vieler Harnesses, unterstützt interaktive Mehrfachauswahl und stellt
keine transaktionsweite Backup-, Readback- oder Rollbackgarantie bereit.

Da 0.6.0 keinen MCP-Eintrag benötigt und Fremdschreibvorgänge nicht an der kontrollierten
Aktivierungsgrenze vorbeiführen darf, wird `add-mcp` nicht übernommen. Seine API würde keine
wesentliche eigene Logik vermeiden, aber Supply-Chain- und Stabilitätsfläche vergrößern.

## `vercel-labs/skills`

Geprüft wurden das öffentliche Repository `vercel-labs/skills` und die npm-Metadaten des Pakets
`skills` 1.5.23. Die Registry nennt MIT, Git-Head
`435076e78988e1e6ec40d00b0b1d76bdbbc5419a`, Integrität
`sha512-+hMNBSi35yfX0sKD+ZcRm9y5or7u313OdkcvrRvJAsAzGCaA8wRTu2OmVdN0KRbk9ybqKby5dijkn6OVvNTUmw==`
und die Laufzeitabhängigkeiten `tar` und `yaml`. Der Funktionsumfang installiert bedarfsabhängige Agent-Skills;
er besitzt keine transaktionale Codex-Home-, Instruktions-, Hook- oder Rollback-Schnittstelle.

Governance muss vor Klassifikation und Wirkung immer aktiv sein und darf nicht als optionaler Skill
modelliert werden. Das Paket wird deshalb unabhängig von seiner Lizenzkompatibilität nicht
übernommen.

## `@agntn/harnesses`: passive Discovery-Projektion

Der unveränderte veröffentlichte Tarball `@agntn/harnesses@0.3.0` bleibt die Quelle für
Discovery-Metadaten, ist aber keine Runtime-Abhängigkeit mehr. Das Archiv und sein
[Herkunfts-Lock](../integrations/agntn-harnesses/upstream.lock.json) liegen außerhalb des
npm-Paketinventars. Der Generator liest das kompilierte Upstream-JavaScript ausschließlich
als Daten über die bereits vorhandene TypeScript-AST-API. Er führt weder Upstream-Code aus
noch lädt er zur Laufzeit Pakete nach.

Alle 13 Registry-Einträge werden in Originalreihenfolge mit `id`, `name` und `binaries`
übernommen. Nichtliterale Felder, Konstruktoren, Discovery-Overrides, statische Blöcke, doppelte IDs und
unbekannte Registry-/Metadatenstrukturen blockieren die Projektion. Der zusätzliche Digest der
vollständigen Basis- und registrierten Klassen sowie der Registry-Funktionen erzwingt eine
erneute Semantikprüfung bei Änderungen, auch an sonstigen Feldinitialisierungen.
`npm run harnesses:check` prüft Archiv-SRI/SHA-256 und vergleicht die vollständige generierte
Datei und MIT-Notice bytegenau. Der Check ist Teil von Build, CI und dem aktuellen Trusted-Publishpfad.
Die Datei darf daher keine manuell gepflegte zweite Harnessliste werden.

`HarnessDiscoveryPort` und `createAgntnHarnessesAdapter()` bleiben erhalten. Der Adapter
prüft wie zuvor mit `which` beziehungsweise `where`, ob mindestens ein Upstream-Binärname
auf dem PATH auflösbar ist. Keine Harness-CLI und keine Versionsprobe werden gestartet.
Support, Bindings, Zielpfade und Integrität bleiben allein bei der bestehenden
Agent-Governance-SSOT. Im npm-Paket liegen nur der kompilierte Datenauszug und die
[MIT-Notice](../THIRD_PARTY_NOTICES.md), kein Upstream-Archiv, MCP SDK oder Harness-Runtimecode.

Die Herkunft wurde am 2026-10-08 vor Entfernung der Runtime-Abhängigkeit mittels
`npm audit signatures --json --include-attestations` verifiziert. Die harnesses-Attestation
bindet den Tarball an Commit `c4a7cb28488cf9bf13a482cd730e83fa9796bdd2`, Tag `v0.3.0` und den
[Upstream-Publish-Lauf](https://github.com/agntn/harnesses/actions/runs/35917252710/attempts/1).
SRI und SHA-256 stehen im Herkunfts-Lock. Dieser historische Nachweis ersetzt nicht die
Integritätsprüfung bei jedem Build oder eine frische Provenienzprüfung bei einem Pinwechsel.

## Security- und Upstream-Entscheidung vom 2026-10-08

Der direkte Parser ist exakt auf `smol-toml@1.9.0` aktualisiert und behebt damit
[GHSA-r4xh-jqrq-34v2](https://github.com/advisories/GHSA-r4xh-jqrq-34v2).
Die separate verwundbare TOML-Kopie und das von
[GHSA-6qxp-vccf-f47h](https://github.com/advisories/GHSA-6qxp-vccf-f47h) betroffene SDK
entfallen vollständig aus dem Runtime-Tree.

Der vorgeschriebene Entscheidungsbaum wurde in dieser Reihenfolge angewendet:

1. Der neueste veröffentlichte Stable-Release von harnesses ist `0.4.2`; er pinnt weiterhin
   SDK `1.30.1` und TOML `1.8.0` und verlangt zusätzlich Node `>=26`. Damit ist er für den
   sicheren Node-`>=24`-Produktvertrag ungeeignet.
2. [Upstream-PR agntn/harnesses#97](https://github.com/agntn/harnesses/pull/97) enthält
   SDK `1.32.0` und TOML `1.9.0`, ist aber am Prüftag noch nicht veröffentlicht.
   Dies bleibt die dokumentierte Upstream-Abhängigkeit.
3. Das Warten blockierte die autorisierte Veröffentlichung. Die
   [Scope-Erweiterung von Issue #154](https://github.com/tomtastisch/agent-governance/issues/154#issuecomment-6056149303)
   erlaubt deshalb einen consumerwirksamen eigenen Korrekturpfad. Der unabhängige
   Architekturvergleich wählte die schmale Datenprojektion hinter dem bestehenden Port:
   Sie bewahrt die gesamte bisherige Installed-Erkennung und entfernt ungenutzte Runtime-Fläche.
4. Root-Overrides allein wären beim Downstream nicht wirksam. Override-Bundling ist ebenfalls
   verworfen: npm 12 verweigert es mit `EBUNDLEOVERRIDE`; ein npm-11-Tarball behält ungültige
   Dependency-Edges gegen Upstream-Exaktpins. Es gibt keine Overrides, Git-Pins, Downgrades,
   CLI-Ausführung oder stille Entfernung der Discovery.

## Künftige Updates und Installationen

Dependabot prüft die npm-Abhängigkeiten täglich und schlägt Versionsanhebungen als PR vor.
`@types/node` bleibt auf der unterstützten Node-24-Basis; Major-Updates dieser
Entwicklungsabhängigkeit sind ausgeschlossen, bis die minimale Laufzeit bewusst angehoben wird.
Direkte Production-Pins bleiben exakt; Versionsvertrag, Evidenz und Review müssen gemeinsam
aktualisiert werden. Es gibt keinen automatischen Merge oder Publish. Der separate
Discovery-Quellpin wird bewusst aktualisiert: sicheren Stable-Release und Node-Vertrag prüfen,
Archiv und Provenienz verifizieren, Semantik reviewen, Lock ändern, `npm run harnesses:generate`
ausführen und anschließend sämtliche Gates prüfen. Eine künftige Rückkehr zur Library ist
nur nach erneutem Vertrags- und Supply-Chain-Nachweis zulässig.

CI und Publish prüfen den Production-Tree ab Moderate. `npm run test:package` installiert
zusätzlich den realen Tarball in einem frischen Consumer ohne Root-Lockfile oder Overrides,
prüft `npm ls --all`, den Production-Audit und den Ausschluss von Harness-Runtime und SDK.
So darf ein lokaler Scheinfix keine Veröffentlichung passieren.

Installation und `init` verändern keine Paketpins und führen keinen Dependency-Reparaturprozess
aus. Für eine neu veröffentlichte geprüfte Gesamtversion kann der Nutzer beispielsweise
`npx --yes @tomtastisch/agent-governance@latest init` verwenden; bestehende Bindings folgen dem
regulären geprüften Update-/Replacement-Vertrag. Automatisches Erhöhen einzelner Abhängigkeiten
während einer Installation würde Reproduzierbarkeit und geprüften Releaseumfang aufheben.
Eine sichere Korrektur wird deshalb vor der Installation als neue Gesamtversion veröffentlicht.

## Bekannte Grenzen der Evidenz

Registry- und GitHub-Metadaten belegen Herkunft und veröffentlichten Stand, nicht zukünftige
Maintainer- oder API-Stabilität. Da beide Kandidaten abgelehnt wurden, entsteht aus ihnen keine
transitive Produktabhängigkeit. Der vendorte Microsoft-Snapshot behält seinen separaten bestehenden
Pin-, Lizenz-, Dateimanifest- und Advisory-Vertrag.
