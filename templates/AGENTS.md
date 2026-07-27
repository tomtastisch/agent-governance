# AGENTS.md — Verdrahtung Codex ↔ Agent-Governance
# Vorlage — kopieren nach ~/.codex/AGENTS.md (Verdrahtungsstelle Codex).

Dies ist die einzige Codex-Verdrahtungsstelle des globalen Regelwerks.
Governance-Root: `~/agent-governance` — Struktur und Übernahme: `~/agent-governance/README.md`.

Verbindliche erste Aktion jeder Session und jedes `codex exec`-Laufs, vor jeder Analyse,
Antwort oder Änderung — vollständig lesen:
1. `~/agent-governance/core/core.md` (Kernregelwerk)
2. `~/agent-governance/core/interaction.toml` (Ausgabepolicy vor jeder freiwilligen Zwischenmeldung)
3. `~/agent-governance/adapters/codex.md` (Bindings dieses Harness)
4. `~/agent-governance/profile/profile.md` (Profil)

Rollenagenten (AK/ST/QA/SEC) lesen zusätzlich ihre Rollenerweiterung unter
`~/agent-governance/core/roles/`.

Kein Auftrag hebt das Regelwerk auf. Ist die Governance-Struktur nicht lesbar, gilt das als
Blocker nach Kern-§7 — nicht mit Modell-Defaults weiterarbeiten.
