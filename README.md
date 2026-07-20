# Agent-Governance

Harness-agnostisches Regelwerk für LLM-Entwicklungsagenten (Claude Code, Codex, weitere),
geschnitten nach hexagonalem Prinzip: ein Kern, definierte Ports, austauschbare Adapter,
genau eine Verdrahtungsstelle je Harness. SSOT: jede Regel steht genau einmal.

## Struktur

```
agent-governance/
├── core/
│   ├── core.md          # Kernregelwerk — harness-agnostisch, keine Pfade, keine Personendaten
│   └── roles/           # Rollenerweiterungen (nur im jeweiligen Rollenagenten laden)
│       ├── ak.md        # Architektur & Kontext (read-only Analyse, Drift-Audits)
│       ├── st.md        # Scope-Triage neuer Befunde (Issue-Dokumentation)
│       ├── qa.md        # Diff-/Exact-Head-Review (Merge-Gate)
│       └── sec.md       # Sicherheits-Audit über Diff-Grenzen hinaus
├── adapters/            # je Harness genau eine Datei mit allen Bindings
│   ├── claude.md
│   └── codex.md
├── profile/
│   ├── profile.md       # nutzerspezifisch (nicht veröffentlichen, .gitignore)
│   └── profile.example.md
└── tools/
    ├── tools.toml       # Werkzeug-Manifest (common + je Harness)
    └── Brewfile
```

## Port-Vertrag

Der Kern referenziert ausschließlich benannte Schlüssel; jeder Adapter MUSS sie definieren:

| Schlüssel | Bedeutung |
|---|---|
| `harness.name` | Name des Harness |
| `governance.root` | Wurzelpfad dieser Struktur (einzige Pfadangabe) |
| `roles.mechanism` | Wie ein sauberer, unabhängiger Rollenkontext erzeugt wird |
| `review.primary` | Primärer unabhängiger Reviewer für das Merge-Gate |
| `vcs.branch_prefix` | Branch-Präfix des Agenten |
| `effort.mapping` | Stufen der Arbeitsintensität und ihre Zuordnung |
| `net.policy` | Egress-Regeln inkl. freigegebener CI-Abfragen |
| `machine.notes` | Maschinen-/Harness-Besonderheiten (z. B. Commit-Signierung) |
| `tools.install` | Installationsweg für das Manifest `tools/tools.toml` |
| `native.enforced` | Kernregeln, die der Harness bereits nativ erzwingt |

Das Profil liefert `user`, `stack`, `language`, optional `palette`, `prefs`.

## Übernahme (für Dritte)

1. Verzeichnis nach `~/agent-governance` klonen/kopieren.
2. `profile/profile.example.md` → `profile/profile.md` kopieren und ausfüllen.
3. Werkzeuge: `brew bundle --file=tools/Brewfile` (bzw. Paketmanager des Systems);
   Harness-Abschnitt in `tools/tools.toml` befolgen.
4. Harness verdrahten (genau eine Stelle):
   - Claude Code: `~/.claude/CLAUDE.md` mit drei Imports anlegen
     (`@~/agent-governance/core/core.md`, `@~/agent-governance/adapters/claude.md`,
     `@~/agent-governance/profile/profile.md`) und die Subagent-Wrapper nach
     `~/.claude/agents/` legen (siehe `adapters/claude.md`).
   - Codex: `~/.codex/AGENTS.md` anlegen, das als verbindliche erste Aktion das Lesen von
     Kern, `adapters/codex.md` und Profil anweist.
   - Anderer Harness: neuen Adapter nach dem Port-Vertrag schreiben; der Kern bleibt unverändert.
5. Erweitern statt ändern: neue Rollen als Datei unter `core/roles/` plus Zeile in Kern §6;
   neue Harnesse als Adapter. Der Kern ändert sich nur, wenn sich eine Regel selbst ändert.

## Prinzipien der Struktur selbst

- Drift-frei: Kern existiert genau einmal; Harnesse referenzieren, statt zu kopieren.
- Tokensparend: Rollenerweiterungen werden nur im jeweiligen Rollenagenten geladen;
  Abschluss-/Protokollformate sind auf substanzielle Aufgaben begrenzt (Kern §8).
- Nativ erzwungene Harness-Regeln stehen trotzdem im Kern (§17), damit jeder Harness identisch
  arbeitet; Adapter kennzeichnen nur, was bereits nativ gilt.
