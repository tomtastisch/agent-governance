# Abhängigkeits- und Provenienzevidenz 0.6.0

> Historische Evidenz - nicht normativ. Maßgeblich sind Lockfiles, Paketartefakte und der geprüfte
> Exact Head des Pull Requests.

## Eigene Paketabhängigkeiten

Der Installer besitzt keine Runtime-Abhängigkeiten. Exakt gelockte Entwicklungsabhängigkeiten sind
TypeScript `5.9.2` und `@types/node` `24.3.0`; npm löst insgesamt vier Pakete auf. Der lokale
`npm audit --audit-level=high` meldete bei der Einführung null bekannte Schwachstellen. Beide
Pakete stammen aus der npm-Registry, ihre Integritätswerte stehen in `package-lock.json`; sie werden
nicht in das Laufzeitpaket gebündelt. Repository und Paket verwenden Apache-2.0.

## `neon-solutions/add-mcp`

Geprüft wurden das öffentliche Repository `neon-solutions/add-mcp`, der konkret relevante
Codex-/TOML-Upsertpfad und die npm-Metadaten von `add-mcp` 2.2.0. Die Registry nennt Apache-2.0,
Git-Head `a31f796e85f9dd1b5dcb4af1f8fdfd87abcdfe21`, Integrität
`sha512-5oPJRJHJqSiMZDQIT7svGa2SJVAZ4vP19XekxG80eUCIFJaGUG11qjLSXmErMIvJ7vgJ4gLSSnlSI7jk8x1LVA==`
und die Laufzeitabhängigkeiten `chalk`,
`js-yaml`, `commander`, `@iarna/toml`, `jsonc-parser` und `@clack/prompts`. Das Werkzeug schreibt
direkt in Konfigurationen vieler Harnesses, unterstützt interaktive Mehrfachauswahl und stellt
keine transaktionsweite Backup-, Readback- oder Rollbackgarantie bereit.

Da 0.6.0 keinen MCP-Eintrag benötigt und Fremdschreibvorgänge nicht an der kontrollierten
Aktivierungsgrenze vorbeiführen darf, wird `add-mcp` nicht übernommen. Seine API würde keine
wesentliche eigene Logik vermeiden, aber Supply-Chain- und Stabilitätsfläche vergrößern.

## `vercel-labs/skills`

Geprüft wurden das öffentliche Repository `vercel-labs/skills` und die npm-Metadaten des Pakets
`skills` 1.5.23. Die Registry nennt MIT, Git-Head
`435076e78988e1e6ec40d00b0b1d76bdbbc5419a`, Integrität
`sha512-+hMNBSi35yfX0sKD+ZcRm9y5or7u313OdkcvrRvJAsAzGCaA8wRTu2OmVdN0KRbk9ybqKby5dijkn6OVvNTUmw==`
und die Laufzeitabhängigkeiten `tar` und `yaml`. Der Funktionsumfang installiert bedarfsabhängige Agent-Skills;
er besitzt keine transaktionale Codex-Home-, Instruktions-, Hook- oder Rollback-Schnittstelle.

Governance muss vor Klassifikation und Wirkung immer aktiv sein und darf nicht als optionaler Skill
modelliert werden. Das Paket wird deshalb unabhängig von seiner Lizenzkompatibilität nicht
übernommen.

## Bekannte Grenzen der Evidenz

Registry- und GitHub-Metadaten belegen Herkunft und veröffentlichten Stand, nicht zukünftige
Maintainer- oder API-Stabilität. Da beide Kandidaten abgelehnt wurden, entsteht aus ihnen keine
transitive Produktabhängigkeit. Der vendorte Microsoft-Snapshot behält seinen separaten bestehenden
Pin-, Lizenz-, Dateimanifest- und Advisory-Vertrag.
