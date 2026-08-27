# Task-5-Ergänzungsreport — universelle Discovery und fokussierter Pfad

## Scope und Ausgangsstand

- Worktree: `/Users/tomwerner/agent-governance/.worktrees/issue-44-init-onboarding`
- Branch: `feat/issue-44/init-onboarding`
- Start-HEAD: `a61a67750a004a60d57c6758f5fee03f73751e91`
- Die vorbestehenden Änderungen an Issue-44-Plan und -Spec wurden nicht verändert und bleiben vom Commit ausgeschlossen.
- `tests/installer/init-dependency-boundary.test.ts` blieb vollständig ungelesen, unverändert und vom Commit ausgeschlossen.
- Keine neue Dependency, Produktallowlist, Runtime-/Candidate-Ausführung oder Netzwerkabfrage wurde ergänzt.

## TDD- und Debugging-Evidenz

### Charakterisierung der generischen Discovery

Die neuen Tests modellieren eine vollständig fiktive, dem Produktcode unbekannte Umgebung mit vier unabhängigen lokalen Struktursignalen: Runtime/Transport, persistente Sessions, Capabilities/Tools sowie persistente Instructions/Rules. Der vorhandene generische Discovery-Pfad klassifizierte sie bereits als `HIGH_CONFIDENCE` und bot sie über den realen Schritt-2-Adapter an. Ein separater reiner Model-Cache mit Modellmetadaten und GGUF-Artefakt blieb negativ. Deshalb war keine Discovery-Produktänderung nötig.

```text
node --experimental-strip-types --test tests/installer/discovery-regression.test.ts
5/5 PASS, Exit 0
```

### Erwartetes RED

Hypothese: Der fehlende Exklusivfokus entsteht nicht in der Discovery, sondern weil `renderCandidate()` den Root dauerhaft in jedes Optionslabel schreibt; Clack rendert dagegen `option.hint` nativ nur für `focusedValue`.

```text
node --experimental-strip-types --test --test-name-pattern='candidate roots are sanitized' tests/installer/init-prompt.test.ts
0/1 PASS, Exit 1
```

Der Test scheiterte erwartungsgemäß, weil `/synthetic/AsterveilAI` im statischen Label stand. Das war die früheste belegte Ursache für den alten Root beim Fokuswechsel.

### GREEN

Die minimale Produktänderung entfernt den Root aus dem statischen Label und erzeugt einen fokussierten Clack-Hint aus `candidate.root`. Der Hint hält Fokusmarker, gedimmten Pfad und Confidence/Selection getrennt, sanitisiert Steuerzeichen und teilt das 60-Spalten-Budget zwischen vollständigem, umgebrochenem Label und sicher gekürztem Pfad auf. Die Anzeige liest weder Runtime noch Netzwerk.

```text
node --experimental-strip-types --test --test-name-pattern='candidate roots are sanitized' tests/installer/init-prompt.test.ts
1/1 PASS, Exit 0

node --experimental-strip-types --test --test-name-pattern='focused candidate path follows' tests/installer/init-prompt.test.ts
1/1 PASS, Exit 0
```

Die reale `expect`-PTY-Matrix wechselte den Fokus bei 60, 80 und 120 Spalten jeweils mit Farbe und `NO_COLOR`. Beide fokussierten Pfade wurden nacheinander erkannt, der injizierte Escape-Code blieb unschädlich, jede geprüfte Pfadzeile blieb innerhalb der Terminalbreite und alle sechs Läufe wurden sauber per Ctrl+C beendet.

## Regressionen und statische Gates

- Discovery-Regressionen: `node --experimental-strip-types --test tests/installer/discovery-*.test.ts` — 34/34 PASS, Exit 0.
- Task-5-Suiten: `node --experimental-strip-types --test tests/installer/init-branding.test.ts tests/installer/init-theme.test.ts tests/installer/init-prompt.test.ts` — 21/21 PASS, Exit 0.
- PTY-Matrix: Bestandteil von `init-prompt.test.ts`; 60/80/120 × Farbe/`NO_COLOR` — 6/6 PASS.
- Ein parallel zu Discovery und Typecheck ausgeführter Zwischenlauf meldete 20/21, weil eine an ein noch nicht vollständig konsumiertes CSI-Fragment angrenzende Expect-Markierung ihr erstes Zeichen verlor. Die Produktanzeige und beide Fokuspfade waren im Fehleroutput vorhanden. Der PTY-Treiber erhielt deshalb ein bewusst entbehrliches Präfix vor den Evidenzmarkern; der anschließende serielle Task-5-Gesamtlauf bestand 21/21.
- Typecheck: `./node_modules/.bin/tsc -p tsconfig.task5-temp.json --noEmit` — Exit 0. Die nur für den Lauf erzeugte Konfiguration entsprach `tsconfig.json`, schloss aber die ausdrücklich verbotene Task-6-Datei aus und wurde anschließend entfernt.
- Lint-Vertrag: derselbe TypeScript-Check plus `git diff --check` — beide Exit 0. Die kanonischen npm-Aliase wurden nicht gestartet, weil deren Glob die ausdrücklich ungelesen zu lassende Task-6-Datei einbezogen hätte.
- Dependency-Diff: `package.json` und `package-lock.json` unverändert; bestehende Runtime-Dependencies bleiben `@clack/prompts@1.7.0` und `smol-toml@1.8.0`.
- Produktcode-/Katalogsuche nach dem fiktiven Fixture-Namen: kein Treffer.

## Nachweislabels

```text
UNKNOWN_AI_ENVIRONMENT_DISCOVERY=PASS
FOCUSED_PATH_RENDERING=PASS
NO_PRODUCT_ALLOWLIST=PASS
NO_COLOR_PATH_RENDERING=PASS
NO_NEW_DISCOVERY_RUNTIME_DEPENDENCY=PASS
```

## Verbleibende Gates und Risiken

- Die selbst ausgeführte Diff-/Boundary-Prüfung ersetzt keine unabhängige QA oder SEC. Der Elternworkflow muss beide Rollen auf dem exakten integrierten Head ausführen, bevor Liefer- oder Integrationsreife behauptet wird.
- Der reale PTY-Nachweis verwendet das im aktuellen macOS-Umfeld vorhandene `expect`; andere Plattformen wurden in diesem Task nicht ausgeführt.
- Der kanonische repositoryweite Typecheck-/Lint-Alias bleibt bis zur Freigabe der ausdrücklich ausgeschlossenen Task-6-Datei unausgeführt; die fachlich gleichen Checks waren für den Task-5-Scope grün.
