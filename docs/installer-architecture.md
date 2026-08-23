# Installerarchitektur 0.6.0

> Historische Evidenz - nicht normativ. Der normative Installationsvertrag bleibt
> [`Installation.bootstrap.prompt.md`](../Installation.bootstrap.prompt.md).

## Verantwortungsgrenzen

Der Installer ist ein Distributionsconsumer außerhalb des normativen Bundles. Er validiert den
veröffentlichten Payload, inventarisiert ausschließlich explizite Ziele unter einer absoluten
erlaubten Wurzel und erzeugt vor der ersten Mutation einen maschinenlesbaren Plan. Nur Codex ist in
0.6.0 produktiv unterstützt. OpenCode, Claude Code und andere Harnesses enden vor jeder Mutation mit
`UNSUPPORTED_HARNESS`.

## Transaktion

Der Ablauf ist `inspect → classify → plan → backup → stage → activate → verify`; jeder Fehler nach
einem verifizierten Backup wechselt in `rollback`. Backups unterscheiden vorhandene Objekte und
explizite Abwesenheit. Staging liegt unter derselben erlaubten Dateisystemgrenze. Unmittelbar vor
der Aktivierung werden Elternidentitäten erneut geprüft. Jede Aktivierung verwendet einen Rename
innerhalb eines Dateisystems; Erfolg wird erst nach Readback und Payload-Verifikation gemeldet.

`SIGTERM` und `SIGINT` können nur best-effort behandelt werden. `SIGKILL`, Stromausfall und
Dateisystemdefekte sind nicht synchron abfangbar. Deshalb bleibt ein privates Recovery-Receipt mit
dem verifizierten Backup erhalten. Wiederholtes Rollback ist idempotent.

## Codex-Adapter

Der Adapter verwendet den expliziten Codex-Home-Pfad, globale `AGENTS.md`-Instruktionen und
`hooks.json`. `AGENTS.override.md`, parallele Inline-Hooks, doppelte Governance-Hooks,
unbekannte Legacyimporte oder beschädigte Konfigurationen werden nicht geraten, sondern als
`UNKNOWN` abgelehnt. Die globale Instruktion ist byte-identisch mit `bundle/GOVERNANCE.md`.

Der Adapter bindet nur `agent_governance__execute` an `PreToolUse`. Er ändert `config.toml` und MCP
nicht, erweitert keine Toolfreigabe und behauptet keine universelle Interception. Andere
Toolwirkungen außerhalb des expliziten Hooks bleiben außerhalb der synchron garantierten Wirkung.

## CLI

Das Paket stellt `agent-governance inspect|plan|install|verify|rollback|status` bereit. Alle
produktiven Pfade verlangen `--harness`, `--home`, `--allowed-root`, `--release-root` und
`--install-root`. `--dry-run` erzeugt keine produktiven Nebenwirkungen; `--json` liefert den
strukturierten Vertrag. Tests verwenden ausschließlich temporäre Homes.
