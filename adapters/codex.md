# Adapter — Codex

Dieser Adapter ist die einzige Codex-Verdrahtung des Kernregelwerks (`core/core.md`).
Verdrahtungsstelle des Harness: `~/.codex/AGENTS.md` (weist an, Kern, diesen Adapter und Profil
zu lesen).

## Bindings

| Schlüssel | Wert |
|---|---|
| `harness.name` | Codex (Desktop-App, CLI, `codex exec`) |
| `governance.root` | `~/agent-governance` |
| `roles.mechanism` | Separate Codex-Session bzw. `codex exec`-Lauf mit frischem, chatfreiem Kontext je Rolle; Orchestrierung wahlweise über den codex-orchestrator-MCP. Jeder Rollenagent lädt Kern + Rollenerweiterung + Profil selbst. |
| `review.primary` | GitHub Copilot Code Review am PR; seine Verwendbarkeit und die ergänzenden beziehungsweise ersetzenden QA-/SEC-Rollen bestimmt ausschließlich `core/review-routing.toml` nach Kern §16. |
| `effort.mapping` | Codex-Effort `low → medium → high → xhigh`. Analyse/Doku low, Implementierung medium, Architektur/Review/CI-Fix high, kritisches Sparring xhigh. Read-only-Modus für alles, was nicht schreiben muss. |
| `net.policy` | Netzwerkzugriff in isolierten Läufen standardmäßig aus; je Aufgabe dokumentiert freigeben. Immer freigegeben: CI-Status/-Logs des eigenen Push via `gh` (Kern §13). |
| `machine.notes` | git-Signing auf diesem Mac: `commit.gpgsign=true` + SSH-Key mit Passphrase. Nicht-interaktiv schlägt `git commit` ohne entsperrten `ssh-agent` fehl → Key vorher laden; `--no-gpg-sign` nur mit expliziter Freigabe. `gum` für Terminal-Progress. |
| `tools.install` | CLI-Pflichtwerkzeuge: `brew bundle --file=~/agent-governance/tools/Brewfile`; optional empfohlene erst nach Freigabe (§19) via `Brewfile.optional`. MCP-Server: `~/.codex/config.toml`, Abschnitt `[mcp_servers]`. Katalog mit Beschreibung und Installationsweg je Werkzeug: `tools/tools.md`. |

## Nativ erzwungene Kernregeln (`native.enforced`)

- Sandbox-/Approval-Modi begrenzen Schreib- und Netzzugriffe (Einzelfreigaben).
Alle übrigen Punkte aus Kern §17 (Instruktionsgrenze, Secret-Verbot, wahrheitsgetreue Berichte,
Orthographie) erzwingt Codex nicht nativ und sind vollumfänglich selbst einzuhalten.

## Harness-Hinweise

- Da Codex keine Import-Syntax kennt, ist das Lesen von Kern, Adapter und Profil die verbindliche
  erste Aktion jeder Session (angewiesen in `~/.codex/AGENTS.md`). Nicht lesbar = Blocker (Kern §7).
- Review-Routing: Vor einem Reviewer-Dispatch wird die read-only Planung mit
  `python3 -m review_routing route` ausgeführt; das finale Evidenzgate wird mit
  `python3 -m review_routing validate` geprüft. Matrix und Risikomarker werden nicht im Adapter
  wiederholt; ihre SSOT ist `core/review-routing.toml`, die Entscheidung ist in
  `docs/decisions/0003-review-routing.md` begründet. Ein kostenpflichtiger Copilot-Dispatch
  benötigt eine explizite Einzelfreigabe. Meldet die Route Copilot als nicht verwendbar, wird
  ausschließlich der geforderte QA-/SEC-Rollenlauf gestartet und kein Copilot-Retry versucht.
- Tokenhaushalt: Rollenerweiterungen werden nur im jeweiligen Rollenlauf gelesen, nie im
  Executor-Kontext.
