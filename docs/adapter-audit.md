# Architekturentscheidung: keine Harnessadapter

> Historische Evidenz - nicht normativ. Diese Datei dokumentiert die verworfene Alternative.

## Entscheidung

Der Fremdadapteraudit endete mit `NO_GO`. Der Installer verwendet keine eigene Harnessmatrix und
keine Runtime-Abhängigkeit zu einem Fremdadapter. Zielroot und Markdown-Entry bleiben vollständig
explizit; dokumentierte Harnessrezepte werden nicht in Runtime-Presets übersetzt.

## Bewertete Pakete

- `skills@1.5.23` verteilt Skills, erzeugt aber keine globale persistente Instruktionsbindung; die
  geprüfte Provenance verwies zudem auf einen Elterncommit mit vorheriger Versionsnummer.
- `add-mcp@2.2.0` konfiguriert MCP und löst den Governance-Bindingvertrag nicht.
- `@intellectronica/ruler@0.3.44` unterstützt Projektinstruktionen, aber keine echte globale
  Zielbindung.
- `rulesync@16.15.0` wurde wegen großer Runtimefläche und nicht geschlossener Herkunfts- und
  Lizenzkette über `uri-templates@0.2.0` endgültig ausgeschlossen.
- Ebenfalls ohne geeigneten Vertrag blieben `@dallay/agentsync`, `aitoolsync`, `glooit`,
  `sync-agents-settings`, `@panishandsome/agentsync`, `ai-rules-sync`, `sync-ai-context`,
  `agent-rules` und `@fialhosoft/agentlink`.

## Konsequenzen

Die Runtime kennt weder Codex, Claude Code, OpenCode, OpenClaw noch andere Produktnamen. Sie
verarbeitet nur generische Dateien, Releaseinventar, Managed Block, Backup und Receipt. Neue
Harnesses benötigen ausschließlich ein extern verifiziertes Befehlsrezept und eine reale Fresh
Session; sie rechtfertigen keine Adapterdependency.
