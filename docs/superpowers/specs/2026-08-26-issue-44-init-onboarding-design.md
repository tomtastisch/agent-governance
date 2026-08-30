# Issue 44 Init-Onboarding Design

> Kompakte Repository-Projektion der vom Nutzer bestätigten Architektur aus GitHub Issue #44 und dem Auftragsvertrag vom 26.08.2026. Bei Abweichungen gilt der aktuelle Nutzerauftrag vor dieser Projektion.

## Ziel und Abgrenzung

Die einzige normale öffentliche Installations- und Erstkonfigurationswahrheit ist exakt `npm i @tomtastisch/agent-governance` gefolgt von `npx agent-governance init`. README und jede nutzerorientierte GitHub-Installationsanleitung vermitteln eindeutig nur diesen Zwei-Command-Weg. Explizite Low-Level-Aufrufe mit `install --scope`, `--target-root`, `--entry-file` oder `--installation-root` bleiben rückwärtskompatibel, dürfen aber ausschließlich in klar bezeichneten Advanced-/Automation-/CI-/Low-level-CLI-/Troubleshooting-Referenzen erscheinen und nie als zweiter normaler Installationsweg. `init` ist eine interaktive Orchestrierung über der vorhandenen `InstallerTransaction`; die einzige mutierende Engine bleibt `plan -> install -> verify`. Management-Namespaces aus #42 und die Startup-/Readiness-Zustandsmaschine aus #37 bleiben außerhalb des Scopes.

## Öffentlicher Command-Vertrag

`bundle/agent-governance/catalogs/commands.toml` ist die einzige Command-Level-SSOT für `inspect`, `plan`, `install`, `verify`, `status`, `update`, `uninstall`, `rollback` und `init`; das Manifest registriert sie. Jeder Eintrag enthält stabile ID, namespacefähigen Pfad, kanonische Kurzbeschreibung, Capability, Wirkungsklasse und Orchestrierungs-/Interaktivitätsmetadaten. Ein strikt validierender Loader auf Basis von `smol-toml` lehnt unbekannte Felder, Typen, doppelte Pfade und semantisch ungültige Kataloge fail-closed ab. Help liest diese Beschreibungen; jeder SSOT-Command besitzt genau einen Handler. `InstallerCommand` bleibt auf Transaktionscommands begrenzt, `init` wird als Orchestrierungscommand modelliert. Globales und command-spezifisches `--help`/`-h` sind ohne Pflichtargumente, Discovery, Prompt oder Mutation read-only mit Exit 0.

## Passive Discovery

`bundle/agent-governance/catalogs/discovery-signals.toml` ist die deklarative SSOT für generische Evidence-Familien, Metadatensignale, Confidence-Grenzen, Discovery-Klassen und Ressourcenlimits. TypeScript übernimmt bounded Traversal, Parser, Root-Boundary-Refinement und Duplicate-Auflösung. Die Discovery untersucht ausschließlich begrenzte standardisierte HOME-/XDG-/macOS-Zonen, folgt keinen Symlinks, startet keine Kandidaten, verwendet kein Netzwerk und nutzt keine Produktnamen, Produktpfade oder Binary-Namen zur Klassifikation.

Strukturierte Dateien werden größen-, tiefen-, datei-, entry-, SQLite- und budgetbegrenzt analysiert; Ausgabe und Persistenz enthalten nur notwendige Strukturmetadaten. SQLite wird über `node:sqlite` mit `DatabaseSync(path, { readOnly: true })` geöffnet, ausschließlich über `sqlite_schema`/Schema-Pragmas ausgewertet und garantiert geschlossen. Package-Metadaten sind lokal und allein höchstens `UNCERTAIN`. `HIGH_CONFIDENCE` erfordert mehrere unabhängige Quellen, starke Runtime-Evidence und korroborierende Familien; Plugin-/Skill-/MCP-Overlays und ein einzelnes breites Dokument reichen nie.

Breite Container werden auf kleinste kohärente Child-Roots verfeinert oder verworfen. Nahezu identische Roots werden anhand normalisierter Evidence-Struktur, kleiner Evidence-Digests, Dichte/Kohärenz und passiver Aktivität generisch aufgelöst; bei nicht belastbarer Unterscheidung werden beide auf `UNCERTAIN` zurückgestuft. Post-Classification-Identität ist ausschließlich Anzeige-/Deduplizierungslogik. App-Bundles sind eine eigene Candidate-Klasse und bei schwacher Evidence `UNCERTAIN`.

## Drei-Schritt-Wizard

1. **Umgebung prüfen:** Standardroot `~/.agent-governance`, Voraussetzungen, bounded Discovery, Boundary-, Duplicate- und Confidence-Aufbereitung; Spinner statt Fake-Prozent.
2. **AI-/LLM-Ziele auswählen:** Tastatur-Multiselect mit Pfeilen, Space, Enter und Ctrl+C; High Confidence darf vorselektiert sein, Uncertain nicht. Confidence, Fokus und Auswahl besitzen kombinierbare Textmarker und Grün/Gelb/Cyan; Footer-Legende und `AI/LLM nicht dabei?` bleiben sichtbar. `NO_COLOR`, monochrome und reduzierte ANSI-Terminals bleiben semantisch eindeutig. Der manuelle Fallback erfasst innerhalb dieses Schritts nur Root und relative Markdown-Entry-Datei.
3. **Prüfen und einrichten:** Für jedes deterministisch sortierte Ziel erzeugt die vorhandene Engine einen Plan; erst nach einer expliziten Gesamtfreigabe erfolgen `install` und verpflichtendes `verify`. Kein Teil- oder Gesamterfolg wird vor Verify ausgegeben; Fehler bleiben Fehler und erzeugen keinen falschen Gesamterfolg.

Ohne interaktives TTY bricht `init` deterministisch ab und verweist auf den expliziten nicht-interaktiven Installerweg. Wiederholtes Init respektiert `CURRENT` und bleibt zustandsbewusst. Terminaltexte aus lokalen Metadaten werden von Steuerzeichen bereinigt.

## Terminalidentität und Dependencies

`@clack/prompts@1.7.0` ist der einzige Prompt-Stack; `smol-toml@1.8.0` ist der TOML-Parser. Beide werden nur bei direktem Runtime-Import als Production-Dependencies aufgenommen. Das kanonische Icon wird als kleines deterministisch abgeleitetes Runtime-Asset paketiert; Rendering ist dekorativ und fällt auf eine kompakte ANSI-/Textmarke zurück. `terminal-image@5.0.1` wird nur aufgenommen, wenn direkte/transitive Abhängigkeiten, Größe, Lizenzen, Audit, Maintenance und Tarballwirkung verhältnismäßig sind; andernfalls bleibt es bewusst ausgeschlossen.

`package.json.dependencies` und das zugehörige Lockfile sind die einzige Runtime-Dependency-SSOT. Ein normales `npm i @tomtastisch/agent-governance` muss alle direkt benötigten Runtime-Pakete installieren; der anschließende `npx agent-governance init`-Pfad konsumiert ausschließlich diese bereits vorhandenen Pakete. `init` startet weder npm, pnpm, yarn noch bun, bootstrapt keinen Package Manager und besitzt keine Self-Install-, Repair- oder bedingte Nachladefunktion. Eine fehlende deklarierte Runtime-Dependency ist ein fehlerhaftes Package und wird fail-closed gemeldet, niemals automatisch installiert. `chalk`, `boxen` und `log-update` werden ohne direkten fachlich notwendigen Import nicht deklariert.

## Tests, Packaging und Release

Synthetische HOME-/XDG-/Application-Support-Fixtures decken positive, uncertain, negative, Boundary-, Duplicate-, SQLite- und Ressourcenlimitfälle ab; reale Nutzerzustände sind verboten. CLI-/Help-, Wizard-, Cancel-, non-TTY-, NO_COLOR-, Idempotenz-, Multi-Target- und Verify-Failure-Tests werden per Red-Green-Refactor ergänzt. Ein repositoryweiter automatisierter Dokumentationsvertrag verhindert konkurrierende normale Installations-Quickstarts und erzwingt auch für `docs/harness-recipes.md` die Trennung zwischen kanonischem Zwei-Command-Weg und klar markierter Advanced-/Manual-/Diagnostic-Referenz. Der echte npm-Tarball enthält beide Kataloge, Runtime-Branding, alle Runtime-Dateien und sämtliche direkt verwendeten Production-Dependencies; er wird in einem frischen Consumer sowie per `npx` getestet. Ein Regressionstest instrumentiert Child-Process-Starts und beweist, dass `init` keinen Package Manager zur Dependency-Installation startet. Eine reale PTY-QA prüft 60/80/120 Spalten, Farbe, `NO_COLOR`, Cancel/Error und Fallback.

Wenn Registry, Release und `VERSION` vor der Versionsänderung weiter `1.0.1` sind, ist die kohärente Minor-Version `1.1.0`. VERSION, package projections, Changelog, Inventar und Release-Metadaten werden nach Repositoryvertrag aktualisiert. Vor Integration sind vollständige lokale Gates, unabhängige QA und unabhängige SEC auf exakt demselben Head erforderlich; Merge, signierter Tag, GitHub Release und Trusted Publishing erfolgen nur bei erfüllten Schutzregeln und realem Readback.
