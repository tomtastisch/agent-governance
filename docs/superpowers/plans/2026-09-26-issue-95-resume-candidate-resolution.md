# Plan: Deterministische Resume-Candidate-Resolution (#95)

> Historische Evidenz - nicht normativ.

## Kontext

Issue #95 verlangt eine rein read-/resolve-seitige Capability, die persistierte
Resume-Zustände aus einem begrenzten autorisierten Candidate-Scope liest, über die
bestehende `ResumeCheckpointStore`-API validiert und deterministisch dem aktuellen
Arbeitskontext zuordnet. Ergebnis: `RESUME | NO_MATCH | AMBIGUOUS | INVALID`.

Implementierungszeitpunkt: `main` = `19bc4241d719d66d6646b1a642260a40c1cec743`,
veröffentlicht `1.7.0`. Keine Candidate-Resolution vorhanden („Resolver fehlt“).

## Lieferpfad

1. Isolierter Worktree `.worktrees/issue-95` auf Branch
   `feat/issue-95/resume-candidate-resolution` von `origin/main`. ✅
2. Baseline: Node 400 / Python 547 grün. ✅
3. Resolver testgetrieben in `src/resume-resolve.ts` umsetzen.
4. Repository-Gates auf dem finalen Exact Head.
5. Unabhängige SEC + QA auf demselben Head; SemVer-Auswirkung bestimmen.

## Designentscheidungen

Siehe `2026-09-26-issue-95-resume-candidate-resolution-design.md`:
D1 internes Modul (kein öffentlicher Export), D2 explizite Candidate-Scope,
D3 exakter Identitätsvergleich ohne Heuristik, D4 Vorrang INVALID > AMBIGUOUS > RESUME
> NO_MATCH, D5 Referenz statt zweitem Zustand, D6 keine External-Effect-Ausführung,
D7 kein GitHub im Kern.

## Mindesttests (TDD)

RESUME (genau ein Match), NO_MATCH (leer/fremdes Repo/Scope), AMBIGUOUS (mehrere
ununterscheidbare Stores), INVALID (beschädigte Generation, Generation Gap, unsicherer
Symlink-Pfad, manipulierte Rechte), Dedup zweier Locator-Einträge, mehrere Generationen =
ein Candidate, gleicher Task + neuer HEAD → RESUME, gleicher HEAD + abweichender Dirty
State (keine SHA-only-Gleichsetzung), abgeschlossener Task → kein RESUME, Fresh Chat ohne
taskId → RESUME, PREPARED/UNKNOWN ohne Effektausführung, keine Netzwerk-/GitHub-Abhängigkeit.

## Gates

`npm test`, `npm run typecheck`, `npm run lint`, `npm run build`, `npm run pack:check`,
`npm run license:check`, Python `pytest tests/`, plus ggf. weitere vom Repository
definierte Checks, jeweils auf demselben finalen Exact Head.
