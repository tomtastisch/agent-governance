# Templates und Interaktionsverträge

### TPL-001 — Auswahlprinzip

Eine strikte Vorlage ist nur für wiederkehrende Vorgänge verbindlich, bei denen freie Form
Identität, Evidenz oder Übergabeinformation regelmäßig verliert. Alle anderen Interaktionen
folgen einem strukturierten Mindestvertrag. Semantische Regeln bleiben in ihren Fachmodulen;
diese Datei ist alleinige SSOT für Form und Pflichtfelder.

## Strikte Vorlagen

### Commit

```text
<type>(<scope>): <imperative summary>

<optional body: context, breaking/security impact, non-obvious decision>
```

`type` ist ein fachlicher Änderungstyp wie `feat`, `fix`, `refactor`, `docs`, `test` oder
`chore`; eine Agentenmarke ist kein Typ. Der Body entfällt, wenn der Header die atomare
Änderung nach [DEL-004](delivery.md#del-004--atomare-historie) vollständig erklärt.

### Branch

```text
<type>/<scope>/<short-topic>
```

Alle Segmente sind klein geschrieben, kurz und fachlich. Ein ausdrücklich vorgegebener
Branchname hat Vorrang; ein Agentenname ersetzt weder Typ noch Scope.

### Push-/PR-Checkpoint

```text
Branch: <branch>
Local HEAD: <Exact-Head-SHA>
Remote branch HEAD: <Exact-Head-SHA>
PR: <repository>#<number> -> <base>
PR head: <Exact-Head-SHA>
Checks: <command-or-check-id> = <result>
Review: <provider-or-role>/<reference> = <result>
Open findings: <count and classifications>
```

Die drei SHAs müssen vor einer Exact-Head-Aussage gleich sein. Ergebnisse folgen
[DEL-002](delivery.md#del-002--exakter-stand).

### PR-Beschreibung und Reviewevidenz

```text
Ziel: <bounded outcome>
Scope: <included / excluded>

| Teilaufgabe | Commit-SHA | Tests | Reviewreferenz | Findings | Status |
|---|---|---|---|---|---|
| <task> | <sha> | <checks> | <provider-or-role/id on sha> | <classes> | <state> |

Risiken/Blocker: <none or precise remainder>
Nicht autorisiert: <merge/tag/release or task-specific boundary>
```

Die Tabelle wird fortgeführt, nicht durch Review-Rohtranskripte ersetzt.

### QA-/SEC-Finding

```text
Rolle: <QA|SEC|ARCH>
Provider: <provider>
Exact Head: <Exact-Head-SHA>
Finding: <id> — <blocking-valid|nonblocking-valid|invalid|not-applicable>
Ort: <file/object/rule>
Evidenz: <reproduction or authoritative reference>
Auswirkung: <bounded consequence>
Abhilfe/Begründung: <minimal fix or technical rationale>
Re-Review: <required|not required> — <reference or pending>
```

Klassifikation und Re-Review richten sich nach
[DEL-009](delivery.md#del-009--finding-lifecycle).

### Kontextübergabe

```text
Ziel und Scope: <current bounded objective>
Kanonische SSOT: <paths/objects and precedence>
Exact state: <branch, head, PR or artifact identity>
Entscheidungen: <accepted decisions and superseded decisions>
Evidenz: <checks/reviews with result and identity>
Offene Findings/Blocker: <classified list>
Nächster sicherer Schritt: <one actionable continuation>
Nicht übernehmen: <stale, secret or out-of-scope context>
```

## Strukturierte Verträge

### Antwort und Status

Eine sichtbare Arbeitsantwort nennt zuerst, was umgesetzt oder geprüft wurde, dann aktuellen
Status, Evidenz und verbleibende Risiken. Bei längeren Aufgaben folgt eine kumulative
Fortschrittsliste mit höchstens einem aktiven Schritt. Statuswörter bezeichnen nur den durch
Nachweise gedeckten Scope.

### Toolfehler und Blocker

Die Meldung enthält betroffenen Schritt, tatsächlichen Aufruf oder Prüfpfad, beobachtetes
Ergebnis, fachliche Auswirkung, bereits ausgeschöpfte sichere Alternative und die kleinste
notwendige Entscheidung. Ein Toolfehler blockiert nicht automatisch unabhängige Arbeit und
wird nie als positiver Nachweis umgedeutet.

### Abschlussaussage

Ein Abschluss nennt Gegenstand, Exact Head oder Artefaktidentität, ausgeführte Gates,
Ergebnisse, offene Risiken und autorisierte nächste Entscheidung. Er verwendet „abgeschlossen“
oder gleichwertige Sprache nur, wenn [EVD-004](evidence.md#evd-004--abschlussnachweis) erfüllt
ist; andernfalls endet er mit genau dem verbleibenden Blocker.
