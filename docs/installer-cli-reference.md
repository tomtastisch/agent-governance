# Installer-CLI-Referenz

> Nicht normative CLI-Bedienreferenz. Maßgeblich bleiben die CLI-Implementierung und ihre Tests.

Diese nicht normative CLI-Bedienreferenz erklärt die öffentliche Oberfläche des Installers. Die
CLI-Implementierung und ihre Tests bleiben Source of Truth; Architektur-, Schema- und
Sicherheitsverträge werden hier nicht neu definiert.

## Mentales Modell

`--installation-root` bezeichnet den absoluten Ort, an dem Agent Governance seine verwalteten
Releases, Bindings, Receipts und Backups hält. Der typische Wert ist
`$HOME/.agent-governance`.

`--target-root` bezeichnet den bewusst gewählten absoluten globalen Instruktionsroot des
Ziel-Harnesses, beispielsweise `$HOME/.codex`, `$HOME/.claude`,
`$HOME/.config/opencode` oder ein tatsächlich verifizierter aktiver OpenClaw-Workspace. Der
Installer erkennt keinen Harness und leitet daraus kein Ziel ab.

`--entry-file` bezeichnet den relativen Markdownpfad innerhalb des Target-Roots, etwa
`AGENTS.md` oder `CLAUDE.md`. Target-Root und Entry-Datei bestimmen gemeinsam die tatsächliche
globale Einstiegsdatei; die Implementierung validiert und bindet beide Pfadbestandteile sicher,
statt sie als ungeprüfte Zeichenketten zusammenzufügen.

Es gibt kein implizites Ziel, kein cwd-Fallback, keine Projektinstallation und keine
Harnesserkennung.

## Command-Referenz

Alle Commands verlangen denselben expliziten Pfadvertrag.

### `inspect`

- **Art:** read-only.
- **Zweck:** Ermittelt den Zustand der angegebenen Bindung und des mitgelieferten Releases.
- **Ausgangszustand:** Jeder sicher lesbare Zustand, einschließlich einer noch nicht installierten
  Bindung.
- **Prüft:** Target, Releaseinventar, Managed Block, Current-Metadaten und installierte
  Releasebindung.
- **Verändert:** Nichts.
- **Typisch:** Vor `plan`, bei Diagnose oder zur Zustandsklassifikation.
- **Fail-closed:** Unsichere Pfade, Symlinks, ungültige Releases und nicht sicher klassifizierbare
  Persistenz führen nicht zu einer Mutation.

### `plan`

- **Art:** read-only; verhält sich stets wie ein Dry Run.
- **Zweck:** Erzeugt den deterministischen Installationsplan für die explizite Bindung.
- **Ausgangszustand:** `FRESH`, `ABSENT`, `CURRENT` oder `OUTDATED`; unsichere Zustände werden
  abgelehnt.
- **Prüft:** Dieselben Pfad-, Release- und Zustandsgrenzen wie die spätere Operation.
- **Verändert:** Nichts.
- **Typisch:** Vor der ersten Installation zur Prüfung von Release, Binding, Entry, Backup und
  Receipt.
- **Fail-closed:** `TAMPERED`, `RECOVERY_REQUIRED` und `DOWNGRADE_BLOCKED` sind nicht planbar.

### `install`

- **Art:** mutierend, außer mit `--dry-run`.
- **Zweck:** Installiert das geprüfte Release und materialisiert den Managed Block sowie die
  Binding-Metadaten.
- **Ausgangszustand:** `FRESH`, `ABSENT` oder idempotent `CURRENT`.
- **Prüft:** Releaseinventar und Digests, explizite Pfade, Native-Capability, Backups,
  Zwischenstände und abschließendes Postimage.
- **Verändert:** Verwaltetes Release, Binding, Receipt/Backup und ausschließlich den eigenen
  Managed Block in der Entry-Datei; optional die expliziten lokalen Regeln.
- **Typisch:** Nach einem geprüften `plan` für eine neue Bindung.
- **Fail-closed:** Bei `OUTDATED` ist `update` erforderlich; manipulierte, recoverypflichtige oder
  Downgrade-Zustände werden nicht installiert.

### `verify`

- **Art:** read-only.
- **Zweck:** Bestätigt, dass die explizite Bindung exakt dem mitgelieferten Release entspricht.
- **Ausgangszustand:** `CURRENT`.
- **Prüft:** Release, Current-Metadaten, Managed Block, Digests und Bindungszustand.
- **Verändert:** Nichts.
- **Typisch:** Direkt nach `install` oder `update` und vor weiterer Nutzung.
- **Fail-closed:** Jeder Zustand außer `CURRENT` schlägt fehl.

### `status`

- **Art:** read-only.
- **Zweck:** Liefert die Zustands- und Capabilitysicht der expliziten Bindung.
- **Ausgangszustand:** Jeder sicher lesbare Zustand.
- **Prüft:** Dieselbe Zustandsbasis wie `inspect`.
- **Verändert:** Nichts.
- **Typisch:** Für Betriebsabfragen und Automation, besonders zusammen mit `--json`.
- **Fail-closed:** Unsichere oder nicht kanonische Pfade werden nicht still als gesunder Zustand
  behandelt.

### `update`

- **Art:** mutierend, außer mit `--dry-run`.
- **Zweck:** Aktualisiert eine bestehende Bindung auf das mitgelieferte neuere Release und kann
  explizit neue lokale Regeln übernehmen.
- **Ausgangszustand:** `OUTDATED`; `CURRENT` ist nur idempotent beziehungsweise für einen
  expliziten Local-Rules-Austausch zulässig.
- **Prüft:** Bestehendes und neues Release, Binding, lokale Regeln, Backup/Receipt und sämtliche
  Postimages.
- **Verändert:** Verwaltetes Release, Current-Metadaten, Receipt/Backup, Managed Block und nur bei
  entsprechendem Vertrag lokale Regeln.
- **Typisch:** Nach `inspect` oder `status`, wenn `OUTDATED` gemeldet wird.
- **Fail-closed:** Auf `FRESH` oder `ABSENT` installiert `update` nicht; Downgrades und manipulierte
  Zustände bleiben blockiert.

### `uninstall`

- **Art:** mutierend, außer mit `--dry-run`.
- **Zweck:** Entfernt die aktive Bindung, ohne fremde Entry-Bytes zu verändern.
- **Ausgangszustand:** Eine sicher klassifizierte Bindung; `FRESH` und `ABSENT` sind idempotent.
- **Prüft:** Managed Block, Current-Metadaten, Releasezustand, Backup und Receipt.
- **Verändert:** Entfernt ausschließlich den verwalteten Block und die aktive Current-Metadatei;
  Releases und Recovery-Evidenz bleiben erhalten.
- **Typisch:** Zum kontrollierten Lösen einer globalen Bindung.
- **Fail-closed:** Manipulierte oder recoverypflichtige Zustände sowie konkurrierend geänderte
  Bytes werden nicht überschrieben.

### `rollback`

- **Art:** mutierend, außer mit `--dry-run`.
- **Zweck:** Stellt aus dem letzten gebundenen Receipt und dessen verifiziertem Backup den vorherigen
  Zustand wieder her.
- **Ausgangszustand:** Ein gültiges, zur expliziten Bindung gehörendes Rollback-Receipt.
- **Prüft:** Beide Receiptkopien, persistierte Identitäten, Backupdigests, aktuelle Postimages und
  Native-Capability.
- **Verändert:** Stellt ausschließlich die receiptgebundenen Entry-, Current- und gegebenenfalls
  Local-Rules-Zustände wieder her; fremde oder neuere Bytes bleiben unangetastet.
- **Typisch:** Nach einer fehlgeschlagenen Änderung oder für die bewusste Rückkehr zum gesicherten
  Vorzustand.
- **Fail-closed:** Fehlende, stale, manipulierte oder nicht übereinstimmende Recovery-Evidenz wird
  nicht verwendet.

## Options- und Keyword-Referenz

### `--scope global`

- **Pflicht:** Ja.
- **Typ/Wert:** Keyword; ausschließlich `global`.
- **Zweck:** Begrenzt die öffentliche CLI auf globale Bindungen.
- **Sicherheit:** Andere Scopes und Projektinstallationen werden abgelehnt.
- **Beispiel:** `--scope global`.
- **Fehlanwendung:** `project` oder ein ausgelassener Scope.

### `--installation-root`

- **Pflicht:** Ja.
- **Typ:** Absoluter kanonischer Verzeichnispfad.
- **Zweck:** Hält Releases, Bindings, Receipts und Backups von Agent Governance.
- **Sicherheit:** Kein relativer Pfad, kein Symlink und keine implizite Basis.
- **Beispiel:** `--installation-root "$HOME/.agent-governance"`.
- **Fehlanwendung:** Mit dem Instruktionsroot des Harnesses verwechseln.

### `--target-root`

- **Pflicht:** Ja.
- **Typ:** Absoluter kanonischer Verzeichnispfad.
- **Zweck:** Wählt den bereits bekannten globalen Instruktionsroot explizit aus.
- **Sicherheit:** Kein relatives Ziel, keine automatische Produkterkennung und kein Defaultziel.
- **Beispiel:** `--target-root "$HOME/.codex"`.
- **Fehlanwendung:** Einen falschen oder nicht aktiven Harness-Workspace angeben.

### `--entry-file`

- **Pflicht:** Ja.
- **Typ:** Relativer Markdownpfad innerhalb des Target-Roots.
- **Zweck:** Bestimmt die globale Einstiegsdatei der Bindung.
- **Sicherheit:** Absolute Pfade, Traversal und Nicht-Markdown-Dateien werden abgelehnt.
- **Beispiel:** `--entry-file AGENTS.md`.
- **Fehlanwendung:** `/absolute/AGENTS.md` angeben.

### `--local-rules`

- **Pflicht:** Nein.
- **Typ:** Absoluter kanonischer Pfad zu einer regulären Markdown-Datei.
- **Zweck:** Übernimmt persönliche lokale Regeln an den vom Manifest festgelegten Ort.
- **Sicherheit:** Die Quelle muss gültiger kontrollzeichenbegrenzter UTF-8-Text sein; Inhalte werden
  nicht in CLI-Ausgaben oder Evidenzfingerprints aufgenommen.
- **Beispiel:** `--local-rules "$HOME/private/agent-rules.md"`.
- **Fehlanwendung:** Das Governancebundle selbst statt persönlicher Regeln übergeben.

### `--dry-run`

- **Pflicht:** Nein.
- **Typ:** Boolescher Schalter ohne Wert.
- **Zweck:** Liefert für mutierende Commands den Plan, ohne produktiv zu mutieren.
- **Sicherheit:** Ermöglicht die Prüfung derselben expliziten Ressourcen vor der Änderung.
- **Beispiel:** `install ... --dry-run`.
- **Fehlanwendung:** Einen Wert wie `true` anhängen oder einen Dry Run als ausgeführte Installation
  behandeln.

### `--json`

- **Pflicht:** Nein.
- **Typ:** Boolescher Schalter ohne Wert.
- **Zweck:** Gibt das geschlossene JSON-Schema 1 statt der kompakten Textausgabe aus.
- **Sicherheit:** Strukturierte Fehler enthalten keine Local-Rules-Inhalte oder Secrets.
- **Beispiel:** `status ... --json`.
- **Fehlanwendung:** Freitextannahmen auf die JSON-Ausgabe anwenden.

### `--non-interactive`

- **Pflicht:** Nein.
- **Typ:** Boolescher Schalter ohne Wert.
- **Zweck:** Kennzeichnet vollständig automatisierte Aufrufe.
- **Sicherheit:** Erzeugt keine automatische Zustimmung, Zielerkennung oder Approval-Erweiterung.
- **Beispiel:** `--non-interactive`.
- **Fehlanwendung:** Den Schalter als Erlaubnis für implizite Pfade verstehen.

## Exitverhalten

- `0`: Erfolg.
- `2`: `INVALID_INVOCATION` für einen ungültigen Aufruf.
- `4`: `UNSAFE_STATE` für einen nicht sicher klassifizierbaren Zustand.
- `5`: `VERIFICATION_ROLLED_BACK` für einen Fehler mit erfolgreichem Rollback.
- `6`: `ROLLBACK_FAILED` für einen fehlgeschlagenen Rollback.
- `130`: serialisierte Unterbrechung durch `SIGINT`.
- `143`: serialisierte Unterbrechung durch `SIGTERM`.

## Generischer Ablauf

Alle Schritte verwenden exakt dieselben expliziten Pfade:

```sh
npx @tomtastisch/agent-governance@1.0.1 plan --scope global --installation-root "$HOME/.agent-governance" --target-root "/absoluter/zielroot" --entry-file "EINSTIEG.md" --non-interactive --json
npx @tomtastisch/agent-governance@1.0.1 install --scope global --installation-root "$HOME/.agent-governance" --target-root "/absoluter/zielroot" --entry-file "EINSTIEG.md" --non-interactive --json
npx @tomtastisch/agent-governance@1.0.1 verify --scope global --installation-root "$HOME/.agent-governance" --target-root "/absoluter/zielroot" --entry-file "EINSTIEG.md" --non-interactive --json
npx @tomtastisch/agent-governance@1.0.1 status --scope global --installation-root "$HOME/.agent-governance" --target-root "/absoluter/zielroot" --entry-file "EINSTIEG.md" --non-interactive --json
```

Harness-spezifische, extern dokumentierte Rezepte stehen in den
[Harness-Rezepten](harness-recipes.md).

## Häufige Fehler

- `--installation-root` und `--target-root` werden verwechselt.
- Für `--entry-file` wird ein absoluter statt eines relativen Markdownpfads angegeben.
- `--target-root` wird relativ angegeben oder auf einen nicht aktiven Workspace gesetzt.
- Ein implizites Produkt- oder Defaultziel wird erwartet, obwohl jedes Ziel explizit sein muss.
- `update` wird auf `FRESH` oder `ABSENT` wie eine Erstinstallation verwendet.
- Persönliche lokale Regeln werden mit dem normativen Governancebundle verwechselt.

## Weiterführende Referenzen

- [README](../README.md) – Schnellstart und Orientierung
- [Harness-Rezepte](harness-recipes.md) – geprüfte globale Zielpfade
- [Installerarchitektur](installer-architecture.md)
- [Installer-Threat-Model](installer-threat-model.md)
- [Installer-JSON-Schemas](installer-json-schemas.md)
