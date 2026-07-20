# Templates — Ablageorte der Verdrahtungsdateien

Diese Vorlagen werden in das Home des jeweiligen Harness kopiert; nur dort werden sie
automatisch geladen. Empfohlener Weg: den Install-Prompt aus `../INSTALL.md` verwenden —
er kopiert, substituiert Pfade und verifiziert vollständig.

## Zuordnung

| Vorlage | Zielort | Harness | Zweck |
|---|---|---|---|
| `CLAUDE.md` | `~/.claude/CLAUDE.md` | Claude Code | Einstiegsdatei: importiert Kern, Adapter, Profil |
| `claude-agents/ak-agent.md` | `~/.claude/agents/ak-agent.md` | Claude Code | Subagent-Wrapper AK (Architektur/Kontext) |
| `claude-agents/st-agent.md` | `~/.claude/agents/st-agent.md` | Claude Code | Subagent-Wrapper ST (Scope-Triage) |
| `claude-agents/qa-agent.md` | `~/.claude/agents/qa-agent.md` | Claude Code | Subagent-Wrapper QA (Diff-Review) |
| `claude-agents/sec-agent.md` | `~/.claude/agents/sec-agent.md` | Claude Code | Subagent-Wrapper SEC (Sicherheits-Audit) |
| `AGENTS.md` | `~/.codex/AGENTS.md` | Codex | Einstiegsdatei: weist Lesen von Kern, Adapter, Profil an |

Existiert am Zielort bereits eine Datei, vor dem Überschreiben ein zeitgestempeltes Backup
anlegen (`<datei>.bak-YYYYMMDD-HHMMSS`).

## Root-Pfad (`GOVERNANCE_ROOT`)

Alle Vorlagen referenzieren das Default-Root `~/agent-governance`. Liegt das Repo woanders,
muss der Pfad beim Kopieren in genau diesen Dateien ersetzt werden (vollständige Liste; Kern
und Rollen sind bewusst pfadfrei):

- `templates/CLAUDE.md` (Zielkopie `~/.claude/CLAUDE.md`)
- `templates/claude-agents/*.md` (Zielkopien unter `~/.claude/agents/`)
- `templates/AGENTS.md` (Zielkopie `~/.codex/AGENTS.md`)
- `adapters/claude.md` und `adapters/codex.md` (Schlüssel `governance.root`, `tools.install`)

Hintergrund: Claude-`@`-Imports erlauben keine Variablen — der Root-Pfad muss literal in den
Einstiegsdateien stehen. Deshalb gilt die Konvention: Der Root-Pfad steht ausschließlich in den
oben gelisteten Verdrahtungs-/Adapter-Dateien; `core/` bleibt pfadfrei. Der Install-Prompt
(`../INSTALL.md`) übernimmt die Substitution automatisch.
