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
├── tools/
│   ├── tools.md         # Werkzeug-Katalog (SSOT): Beschreibung, Governance-Nutzen, Install-Weg
│   └── Brewfile         # deterministische CLI-Installation (brew bundle)
├── templates/           # kopierfertige Verdrahtungsdateien für die Harness-Homes
│   ├── README.md        # Zuordnungstabelle Vorlage → Zielort + Root-Pfad-Regeln
│   ├── CLAUDE.md        # → ~/.claude/CLAUDE.md
│   ├── AGENTS.md        # → ~/.codex/AGENTS.md
│   └── claude-agents/   # → ~/.claude/agents/ (Subagent-Wrapper AK/ST/QA/SEC)
├── tests/               # Konsistenz-/Drift-Tests + advisory Link-Check (Kern §9/§11/§13)
├── .github/workflows/   # CI-Pipeline (ci.yml)
└── INSTALL.md           # gehärteter Install-Prompt (ein Prompt für alle Harnesse)
```

Die Verdrahtungsdateien selbst liegen bewusst nicht aktiv im Repo, sondern im jeweiligen
Harness-Home (`~/.claude/`, `~/.codex/`) — nur dort werden sie automatisch geladen; im Repo
wären sie totes Duplikat (Drift-Quelle). `templates/` enthält die kopierfertigen Vorlagen.

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
| `tools.install` | Installationsweg für den Werkzeug-Katalog `tools/tools.md` |
| `native.enforced` | Kernregeln, die der Harness bereits nativ erzwingt |

Das Profil liefert `user`, `stack`, `language`, optional `palette`, `prefs`.

## Übernahme (für Dritte)

Schnellster Weg: den Install-Prompt aus [INSTALL.md](INSTALL.md) unverändert an den Agenten des
Ziel-Harness geben — ein Prompt für alle Harnesse; er erkennt den Harness, legt die Dateien laut
[templates/README.md](templates/README.md) ab, substituiert abweichende Root-Pfade und
verifiziert fail-closed. Manuell:

1. Verzeichnis nach `~/agent-governance` klonen/kopieren (abweichendes Root: Pfad-Liste in
   `templates/README.md`, Abschnitt „Root-Pfad" beachten).
2. `profile/profile.example.md` → `profile/profile.md` kopieren und ausfüllen.
3. Werkzeuge: `brew bundle --file=tools/Brewfile` installiert nur die Pflichtwerkzeuge (bzw.
   Paketmanager des Systems); Katalog `tools/tools.md` durchgehen — optional empfohlene erst nach
   Freigabe (Kern §19), CLI-seitig über `tools/Brewfile.optional`.
4. Harness verdrahten (genau eine Stelle, Vorlagen in `templates/`):
   - Claude Code: `templates/CLAUDE.md` → `~/.claude/CLAUDE.md` kopieren und
     `templates/claude-agents/*` → `~/.claude/agents/` (Subagent-Wrapper AK/ST/QA/SEC).
   - Codex: `templates/AGENTS.md` → `~/.codex/AGENTS.md` kopieren.
   - Anderer Harness: neuen Adapter nach dem Port-Vertrag schreiben und eine analoge
     Einstiegsdatei im Home des Harness anlegen; der Kern bleibt unverändert.
5. Erweitern statt ändern: neue Rollen als Datei unter `core/roles/` plus Zeile in Kern §6;
   neue Harnesse als Adapter. Der Kern ändert sich nur, wenn sich eine Regel selbst ändert.

## Konsistenz-Sicherung (CI)

Die SSOT- und Driftfreiheits-Zusagen (Kern §9) sind mechanisch überprüft, nicht nur Konvention —
Governance-Artefakte müssen real greifen (§9, §11). `tests/test_governance.py` (stdlib-`unittest`,
ohne Fremdabhängigkeiten) fällt aus, sobald eine Quelle gegen eine andere driftet:

- jede im Kern genutzte `[BINDING:*]`/`[PROFILE:*]` ist im Port-Vertrag bzw. Profil deklariert und
  in jedem Adapter realisiert (kein nicht deklarierter oder unrealisierter Port);
- jeder `§`-Verweis in Kern, Rollen und Katalog zeigt auf einen existierenden Abschnitt;
- alle Rollen (AK/ST/QA/SEC) haben Erweiterung und Subagent-Wrapper und stehen in §6;
- der Kern bleibt pfadfrei (Root-Pfad nur in Adaptern/Templates);
- `tools/tools.md` bleibt ohne Handpflege synchron: jedes `Brewfile`-Paket ist dort dokumentiert,
  jeder Werkzeug-Eintrag trägt Freigabe-Kennzeichnung und Installationsblock, kein Verweis auf das
  entfernte alte Manifest bleibt zurück.

`tests/check_links.py` prüft zusätzlich die Erreichbarkeit der Katalog-Links — netzabhängig und
daher advisory (§13). Die Pipeline (`.github/workflows/ci.yml`) trennt beides klar: blockierende
Konsistenz-Tests, advisory Link-Check. Lokal: `python3 -m unittest discover -s tests`.

## Prinzipien der Struktur selbst

- Drift-frei: Kern existiert genau einmal; Harnesse referenzieren, statt zu kopieren.
- Tokensparend: Rollenerweiterungen werden nur im jeweiligen Rollenagenten geladen;
  Abschluss-/Protokollformate sind auf substanzielle Aufgaben begrenzt (Kern §8).
- Nativ erzwungene Harness-Regeln stehen trotzdem im Kern (§17), damit jeder Harness identisch
  arbeitet; Adapter kennzeichnen nur, was bereits nativ gilt.
