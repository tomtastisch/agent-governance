# Agent-Governance

> **Version:** [`0.1.0`](VERSION) &mdash; [Changelog](CHANGELOG.md)

Harness-agnostisches Regelwerk für LLM-Entwicklungsagenten (Claude Code, Codex, weitere),
geschnitten nach hexagonalem Prinzip: ein Kern, definierte Ports, austauschbare Adapter,
genau eine Verdrahtungsstelle je Harness. SSOT: jede Regel steht genau einmal.

## Struktur

```
agent-governance/
├── core/
│   ├── core.md          # Kernregelwerk — harness-agnostisch, keine Pfade, keine Personendaten
│   ├── branch-tags.toml # Branch-/PR-Tags (SSOT): tag/name/description je Änderungstyp
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
├── docs/decisions/      # Entscheidungssätze (ADR): Begründung struktureller Änderungen
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
| `effort.mapping` | Stufen der Arbeitsintensität und ihre Zuordnung |
| `net.policy` | Egress-Regeln inkl. freigegebener CI-Abfragen |
| `machine.notes` | Maschinen-/Harness-Besonderheiten (z. B. Commit-Signierung) |
| `tools.install` | Installationsweg für den Werkzeug-Katalog `tools/tools.md` |
| `native.enforced` | Kernregeln, die der Harness bereits nativ erzwingt |

Das Profil liefert `user`, `stack`, `language`, optional `palette`, `prefs`.

## Versionierung & Releases

Die [autoritative SemVer-Version](VERSION) steht in der Datei `VERSION` — genau eine Quelle
(SSOT, Kern §9). Ein [CHANGELOG](CHANGELOG.md) führt jeden freigegebenen Stand mit
`Added`/`Changed`/`Fixed`/`Removed` und kennzeichnet Breaking Changes ausdrücklich.

- **Stabiler Release:** ein signierter Git-Tag `v<MAJOR>.<MINOR>.<PATCH>` auf demselben Commit
  wie `VERSION`, verknüpft mit einem [GitHub-Release](https://github.com/tomtastisch/agent-governance/releases).
  Nur dieser Stand ist ein geprüfter, reproduzierbarer Lieferstand.
- **`main`-Branch:** beweglicher Entwicklungsstand. Darf nicht mit einem veröffentlichten Release
  gleichgesetzt werden. Zwischen Releases können auf `main` unveröffentlichte Änderungen liegen.
- **Installation eines bestimmten Releases:** `git clone --branch v0.1.0 https://github.com/tomtastisch/agent-governance`
  oder nach dem Klonen: `git checkout v0.1.0`.

Tag-Push und GitHub-Release sind externe Aktionen, die erst nach Prüfung aller CI- und
Review-Gates ausgeführt werden (Kern §17). Ein nur lokal existierender Tag ist kein
veröffentlichter Release.

## Übernahme (für Dritte)

Schnellster Weg: den Install-Prompt aus [INSTALL.md](INSTALL.md) unverändert an den Agenten des
Ziel-Harness geben — ein Prompt für alle Harnesse; er erkennt den Harness, legt die Dateien laut
[templates/README.md](templates/README.md) ab, substituiert abweichende Root-Pfade und
verifiziert fail-closed. Manuell:

1. Repository klonen — **empfohlen: einen stabilen Release-Tag** (s. o.) statt des beweglichen
   `main`-Branch verwenden. Der Prompt in [INSTALL.md](INSTALL.md) klont standardmäßig den
   aktuellen `main`-Stand; für Produktivumgebungen den gewünschten Tag angeben.
   Zielverzeichnis: `~/agent-governance` (abweichendes Root: Pfad-Liste in `templates/README.md`,
   Abschnitt „Root-Pfad" beachten).
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
  entfernte alte Manifest bleibt zurück;
- `core/branch-tags.toml` ist wohlgeformt und git-ref-sicher: Tags eindeutig, Zeichensatz
  ref-tauglich, `tag`/`name`/`description` je Eintrag gesetzt, `default` verweist auf einen
  existierenden Tag, der Kern verweist auf die Datei, und der abgelöste Agenten-Präfix-Port taucht
  in Kern, Port-Vertrag und Adaptern nicht mehr auf (nutzt stdlib-`tomllib`, Python 3.11+; auf
  älteren Interpretern überspringt sich nur dieser Block, CI pinnt 3.11 und erzwingt ihn).

`tests/check_links.py` prüft zusätzlich die Erreichbarkeit der Katalog-Links — netzabhängig und
daher advisory (§13). Die Pipeline (`.github/workflows/ci.yml`) trennt beides klar: blockierende
Konsistenz-Tests, advisory Link-Check. Lokal: `python3 -m unittest discover -s tests`.

## Prinzipien der Struktur selbst

- Drift-frei: Kern existiert genau einmal; Harnesse referenzieren, statt zu kopieren.
- Tokensparend: Rollenerweiterungen werden nur im jeweiligen Rollenagenten geladen;
  Abschluss-/Protokollformate sind auf substanzielle Aufgaben begrenzt (Kern §8).
- Nativ erzwungene Harness-Regeln stehen trotzdem im Kern (§17), damit jeder Harness identisch
  arbeitet; Adapter kennzeichnen nur, was bereits nativ gilt.
