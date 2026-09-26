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

### Paket-API: Forward-only Replacement

Der additive Export `@tomtastisch/agent-governance/replacement` stellt
`replaceInstallation(request)` bereit (SemVer minor, kein zusätzlicher CLI-Command).
Er ersetzt ausschließlich den ausdrücklich gewählten Einstieg durch eine frische
Installation. Historische Receipts, Bindings und Releases werden weder gelesen noch
repariert; andere Bindings und der alte Installationsroot bleiben bestehen.

```js
import { replaceInstallation } from "@tomtastisch/agent-governance/replacement";

const request = {
  sourceInstallationRoot: "/absolute/old-installation",
  installationRoot: "/absolute/new-installation", // muss fehlen
  releaseRoot: "/absolute/verified-package",
  targetRoot: "/absolute/harness-config",
  entryFile: "AGENTS.md",
  // localRules: "/absolute/explicit-private-rules.md", // optional
};
const plan = await replaceInstallation({ ...request, dryRun: true });
// Nach Prüfung des Plans im autorisierten Ziel:
const result = await replaceInstallation(request);
```

Alle Roots müssen kanonisch und absolut sein; die Installationsroots sind disjunkt.
Target und Entry liegen außerhalb beider Roots, der Release-Root außerhalb der
Installationsroots. Der neue Root benötigt einen bereits vorhandenen sicheren Parent.
Entry-Parent und Entry müssen existieren; Symlinks, Hardlinks, nicht reguläre Dateien,
ungültiges UTF-8 sowie fehlende, doppelte, fremde oder unvollständige Marker werden
abgelehnt. Genau eine aktuelle Markerhülle ist erforderlich; ihr Inneres bleibt opak.
Jedes Byte außerhalb der Hülle bleibt erhalten, einschließlich BOM, Zeilenenden und
Abständen. Historische Angaben wie `Boundary prefix added` erlauben keine Entfernung
zusätzlicher Bytes.

Auch mehrere führende U+FEFF-Codepoints bleiben bytegenau erhalten. Der ursprüngliche
Entry-Snapshot wird bis zum nativen Schreibaufruf gebunden; gleiche Bytes eines später
ersetzten Inodes begründen kein Schreibrecht.

Lokale Regeln werden ausschließlich über `localRules` ausdrücklich übernommen und
mit dem aktuellen Local-Rules-Vertrag validiert. Der validierte Snapshot wird privat
isoliert und anschließend durch den normalen Installer übernommen. Ein Release mit
bereits enthaltenen privaten lokalen Regeln wird abgelehnt; es muss ein sauberes
Releasepaket sein. Ohne Opt-in werden keine alten Regeln übernommen.
Die installierte Regeldatei wird an der Aktivierungsgrenze, nach der Verifikation und
nach der abschließenden Verzeichnissynchronisierung auf erwartete Abwesenheit oder
die explizit freigegebenen Bytes geprüft; fremde Regeldateien bleiben bei Abbruch erhalten.

`PLANNED` ist ein schreibfreier Plan ohne `CURRENT`-Aussage und ohne schreibenden
Native-Probe. Erst der mutierende Aufruf prüft die reale native Capability. Er reserviert
den neuen Root exklusiv und legt neben dem Entry ein privates Verzeichnis
`.agent-governance-quarantine-<id>` an. `entry.bin` enthält den vollständigen ursprünglichen
Entry, `resources.json` ausschließlich Ressourcenreferenzen, `detached.bin` den abgetrennten
Entry und gegebenenfalls `local-rules.md` den expliziten Regel-Snapshot. Datei- und
Verzeichnis-Synchronisierung sichern die ursprünglichen Bytes vor dem Abtrennen.
Die Identitäten von neuem Root und Quarantäne stammen aus dem nativen mkdir-Aufruf;
JavaScript übernimmt keine danach erneut aufgelöste Ersatzidentität. Vor privaten
Schreibzugriffen werden außerdem Modus `0700` und aktueller Eigentümer geprüft.

`SUCCESS` mit `state: "CURRENT"` setzt frische `verify`- und `status`-Prüfungen voraus.
`quarantine.directory` und `quarantine.entryPath` referenzieren die beibehaltene Isolation.
Quarantäne und neuer Root werden auch bei Fehlern niemals automatisch gelöscht.
`FAILURE` liefert nur `REPLACEMENT_FAILED`, eine feste Phase, Ressourcenreferenzen
soweit bekannt und `recovery`: `NOT_REQUIRED`, `RESTORED` oder `RETAINED`.
Ein Ressourcenpfad ist keine Besitz- oder Existenzgarantie: bei einem Fehler kann
bereits eine Reservierung versucht worden sein oder ein Parent inzwischen ersetzt sein.
Ausnahmen, private Inhalte und deren Fingerprints werden nicht zurückgegeben.

Die ursprünglichen Bytes werden bei Fehlern nur zurückgeschrieben, wenn Identität und
Snapshot des eigenen Live-Entry weiterhin nachweisbar sind oder sein Name fehlt;
die Neuanlage ist immer no-clobber. Kann Besitz nicht bewiesen werden, bleibt die
Isolation zur manuellen, erneut autorisierten Wiederherstellung bestehen. Insbesondere
kann ein interner Installer-Rollback einen neuen Inode erzeugen: dann ist `RETAINED`
absichtlich konservativ. Vor Wiederherstellung müssen Parent, Live-Entry und
Quarantäne frisch geprüft werden; niemals einen konkurrierenden Writer überschreiben.
Der normale Installer-Rollback im neuen Root ist kein Rückweg in den alten Root.
Für einen erneuten Replacement-Versuch ist wiederum ein neuer, fehlender Root nötig.

SIGKILL oder Stromausfall werden nicht als atomar zurückgerollt beschrieben. Die
dauerhaft gesicherte Isolation ist die Wiederherstellungsgrundlage. Die dokumentierten
Same-UID-Finalkomponenten-Racegrenzen der nativen Primitiven gelten weiterhin;
beobachtbare Parent-, Identitäts- und Snapshotwechsel brechen fail-closed ab. Erfolgreiche
lokale Tests ersetzen keine unabhängige QA/SEC und keine plattformübergreifende CI.

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

## Advanced: Automation und CI

Der normale Einstieg steht im [README](../README.md). Für nicht-interaktive Automation, CI oder
Troubleshooting verwenden die folgenden Low-Level-Commands exakt dieselben expliziten Pfade:

```sh
agent-governance plan --scope global --installation-root "$HOME/.agent-governance" --target-root "/absoluter/zielroot" --entry-file "EINSTIEG.md" --non-interactive --json
agent-governance install --scope global --installation-root "$HOME/.agent-governance" --target-root "/absoluter/zielroot" --entry-file "EINSTIEG.md" --non-interactive --json
agent-governance verify --scope global --installation-root "$HOME/.agent-governance" --target-root "/absoluter/zielroot" --entry-file "EINSTIEG.md" --non-interactive --json
agent-governance status --scope global --installation-root "$HOME/.agent-governance" --target-root "/absoluter/zielroot" --entry-file "EINSTIEG.md" --non-interactive --json
```

Harness-spezifische, extern dokumentierte Rezepte stehen in den
[Harness-Rezepten](https://github.com/tomtastisch/agent-governance/blob/main/docs/harness-recipes.md).

## Häufige Fehler

- `--installation-root` und `--target-root` werden verwechselt.
- Für `--entry-file` wird ein absoluter statt eines relativen Markdownpfads angegeben.
- `--target-root` wird relativ angegeben oder auf einen nicht aktiven Workspace gesetzt.
- Ein implizites Produkt- oder Defaultziel wird erwartet, obwohl jedes Ziel explizit sein muss.
- `update` wird auf `FRESH` oder `ABSENT` wie eine Erstinstallation verwendet.
- Persönliche lokale Regeln werden mit dem normativen Governancebundle verwechselt.

## Weiterführende Referenzen

- [README](../README.md) – Schnellstart und Orientierung
- [Harness-Rezepte](https://github.com/tomtastisch/agent-governance/blob/main/docs/harness-recipes.md) – geprüfte globale Zielpfade
- [Installerarchitektur](https://github.com/tomtastisch/agent-governance/blob/main/docs/installer-architecture.md)
- [Installer-Threat-Model](https://github.com/tomtastisch/agent-governance/blob/main/docs/installer-threat-model.md)
- [Installer-JSON-Schemas](https://github.com/tomtastisch/agent-governance/blob/main/docs/installer-json-schemas.md)
