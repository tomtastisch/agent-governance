# Design: Deterministische Resume-Candidate-Resolution (#95)

> Historische Evidenz - nicht normativ. Der maßgebliche Vertrag ist Issue #95 und die
> Implementierung samt Tests.

## Ziel

Eine rein read-/resolve-seitige Capability, die aus einer begrenzten, vom Aufrufer
bereitgestellten Candidate-Scope deterministisch entscheidet, ob genau ein sicher
fortsetzbarer Resume-Kandidat dem aktuellen Arbeitskontext zugeordnet werden kann.

Kein neuer öffentlicher Package-/CLI-Vertrag. Keine zweite Resume-, Checkpoint-,
Evidence-, Workflow-, Task- oder Work-Item-Authority.

## Current-State (Implementierungszeitpunkt)

- `main`-Head: `19bc4241d719d66d6646b1a642260a40c1cec743` (Release 1.7.0).
- Veröffentlicht: `1.7.0` (`latest`), SLSA-Provenance + npm-Signaturen.
- `ResumeCheckpointStore` (`@tomtastisch/agent-governance/resume-checkpoint`) ist
  integriert und die alleinige Checkpoint-Authority (Generation, Fingerprint, Kette,
  Atomicity, Crash/Stale/Concurrent-Writer, External-Effect-Write-ahead).
- Es existiert **keine** Candidate-Resolution und **keine** globale Candidate-Registry.
  Die Orchestrierung kennt keinen autoritativen Candidate-Scope.
- `identities.repository|scope|worktree|branch|dirty` und `projection.taskId`,
  `state.workItem`, `state.taskStatus`, `state.externalEffects` sind vorhandene Bindungen.

## Entscheidungen

### D1 — Internal Module, kein öffentlicher Export

Der Resolver wird als internes Modul `src/resume-resolve.ts` umgesetzt und **nicht** in
`package.json` `exports` aufgenommen. Damit bleibt der öffentliche Package-Vertrag
unverändert (SemVer-patch-kompatibel). Ein Harness/Client kann den Resolver später
aufrufen; die öffentliche Freigabe ist eine separate, dann als `minor` zu bewertende
Entscheidung.

### D2 — Candidate-Scope ist explizite Eingabe, keine Suche

`resolveResumeCandidates(candidates, context)` erhält die Candidate-Scope als
`readonly string[]` kanonischer Store-Verzeichnispfade. Es findet **keine** Dateisystem-
oder `$HOME`-/`~/.config`-Suche statt. Die begrenzte, kontrollierte Referenzmenge wird
vom Aufrufer bereitgestellt.

### D3 — Matching ist exakter Identitätsvergleich, keine Heuristik

Ein Candidate `cp` matcht den `context` genau dann, wenn **alle** im `context`
bereitgestellten Bindungen exakt übereinstimmen:

| `context`-Feld | Checkpoint-Bindung |
|---|---|
| `repository` (Pflicht) | `identities.repository` |
| `scope` | `identities.scope` |
| `taskId` | `projection.taskId` |
| `workItem` | `state.workItem` (nur wenn beide nicht leer) |
| `worktree` | `identities.worktree` |
| `branch` | `identities.branch` |
| `dirty` | `identities.dirty` |

Nicht als Identität verwendet: `exactHead`, `dependencies`, `configuration`,
`governance`, `environment`. Diese bleiben Evidence-Bindungen.

`exactHead`/`HEAD` ist **nie** Matching-Schlüssel: gleicher HEAD ist kein Gleichheits-
nachweis, und ein neuer HEAD erzeugt keine neue Task-Identität. Der Aufrufer entscheidet
über die reale Policy, welche Bindungen er als strikte Identität übergibt; der Resolver
ist ein reiner deterministischer Vergleicher.

### D4 — Ergebnis-Vorrang: INVALID > AMBIGUOUS > RESUME > NO_MATCH

Pro Candidate (in Eingabereihenfolge):

1. `ResumeCheckpointStore.open()` oder `captureIdentity()` scheitert
   (nicht-kanonisch, Symlink, falsche Rechte, Path-Identity-Konflikt, fehlt)
   → **INVALID** `"unsafe-or-invalid candidate directory"`.
2. `store.read()` scheitert (Generationslücke, beschädigter Fingerprint, Schemafehler,
   unbekannte Datei) → **INVALID** `"corrupted checkpoint history"`.
3. `read()` liefert `null` (leerer Store, keine publizierten Generationen) → überspringen.
4. `taskStatus === "COMPLETED"` → überspringen (kein automatischer aktiver Resume).
5. Identitätsvergleich scheitert → überspringen.
6. sonst → match.

Mehrere Locator-Einträge auf denselben kanonischen Store werden über die sichere
Path-Identity (`device:inode` aus `captureIdentity`) dedupliziert und ergeben maximal
einen Candidate.

Danach: `INVALID` dominiert (ein beschädigter relevanter Kandidat wird nicht still
verworfen). Sonst `0` Matches → `NO_MATCH`, `1` → `RESUME`, `>1` → `AMBIGUOUS`.

### D5 — RESUME liefert Referenz und Identität, keinen zweiten Zustand

`RESUME` liefert Store-Pfad, `generation`, `fingerprint`, `taskId`, `objective`, `scope`,
`exactHead`, `taskStatus`, `nextAtomicAction`, `workItem` und `externalEffects`.
Der Zustand wird nicht persistiert; TOON wird vom Aufrufer ausschließlich über
`ResumeCheckpointStore.open(store).toToon({ generation, fingerprint })` erneut validiert
abgeleitet.

### D6 — External Effects werden nie ausgeführt

Der Resolver ist rein lesend. Er ruft weder `executeEffect` noch `recoverEffect` auf.
`PREPARED`/`UNKNOWN` bleiben unverändert und werden im `RESUME`-Ergebnis nur referenziert;
der bestehende External-Effect-/Readback-Vertrag bleibt zuständig.

### D7 — GitHub ist kein Bestandteil des Kerns

Kein Netzwerkzugriff, kein PR-Readback im Resolver. Lokaler Resume benötigt keinen PR.
PR-Head/-Base sind Evidence-Bindungen und gehören dem Resume-/Evidence-Vertrag, nicht dem
Resolver.

## Nicht-Ziele

Keine Materialisierungs-, Schema-, Chain-, Effect- oder Evidence-Logik duplizieren.
Keine Locator-State-Authority. Keine globale Registry. Keine neue Dependency.
