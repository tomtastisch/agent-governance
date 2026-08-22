# Microsoft Agent Governance Toolkit Provider

Dieses Verzeichnis materialisiert Microsoft Agent Governance Toolkit ausschließlich als konkret
gepinnte Enforcement-Providerdependency. Es definiert weder die semantische Governance noch
Rollen, Instruktionsautorität, Installation, Updates oder eine Control Plane für
`agent-governance`.

## Aufgelöster Upstream

| Feld | Wert |
|---|---|
| Offizielles Repository | `https://github.com/microsoft/agent-governance-toolkit` |
| Stabiles GitHub Release | `v4.1.0` |
| Tag | `v4.1.0` |
| Commit | `0de71ca6c95cf8b9b975ac96f48eaa7826bbe258` |
| Archiv-SHA-256 | `f087836d4e6cbad246c728c76454dd573a701f35d7560cbf869c250b3862d473` |
| Upstreamstatus | **Public Preview** |
| Lizenz | MIT |

Der Tag ist ein Lightweight-Tag und zeigt direkt auf den genannten Commit. GitHub verifiziert die
Commit-Signatur als gültig; für das offizielle Source-Archiv stellt dieser Release keine separate
Archivsignatur bereit. Zwei unabhängig geladene offizielle codeload-Archive waren byte-identisch
und ergaben den im Lock gespeicherten SHA-256.

Die Datei `VERSION` im Snapshot enthält abweichend `3.7.0`. Für diese Materialisierung sind der
offizielle GitHub Release `v4.1.0`, dessen Tag und dessen exakter Commit maßgeblich; die Abweichung
wird weder verborgen noch als anderer Pin interpretiert.

## Materialisierung und Betrieb

`upstream/agent-governance-toolkit-v4.1.0.tar.gz` ist das vollständige byte-identische offizielle
Releasearchiv ohne Git-Metadaten. Alle Archiveinträge wurden auf absolute Pfade, Traversal, Geräte
und Links geprüft. `snapshot.files.sha256` erfasst alle 4.633 regulären Snapshotdateien
deterministisch; `upstream.lock.toml` ist die unveränderliche Releaseprovenienz.

Das Archiv bleibt im Repository binär, weil die enthaltene Upstream-`.gitattributes` einzelne
offizielle CRLF-Blobs beim direkten Git-Staging zu LF normalisieren würde. Der Bootstrap prüft den
Archivhash und die Eintragssicherheit erneut und extrahiert erst in seine isolierte
Installations-Stagingwurzel. Dadurch bleiben die offiziellen Bytes im Release unverändert und der
Provider kann nach dem einmaligen Bootstrap offline starten.

Normaler Betrieb löst weder `latest` noch einen Releasechannel auf, fragt keine Upstream-API ab
und ersetzt den Snapshot nicht. Ein Upgrade erfolgt ausschließlich in einem späteren, separat
autorisierten `agent-governance`-Release. Die Providerbridge folgt dem offiziellen Framework
Adapter Contract, weil der gepinnte Upstream keinen offiziellen Codex-Adapter bereitstellt.

## Providerbridge

`bridge/provider.mjs` validiert die kleinste Action Envelope und ruft den real aus diesem Snapshot
gebauten Microsoft-`PolicyEngine` auf. `bridge/build-provider.sh` akzeptiert nur einen absoluten
Outputpfad, verifiziert Archiv und Dateimanifest, extrahiert linkfrei in eine neue Stagingwurzel,
baut mit dem gepinnten npm-Lock und materialisiert nur die tatsächlich benötigte PolicyEngine-
Closure. `bridge/runtime.files.sha256` bindet jeden Runtime-Blob; ein vorhandener Build wird nur
nach vollständiger Byte- und Dateimengenprüfung ohne Rewrite akzeptiert. Provider und Policy
werden zur Ausführung über sichere Handles gelesen und gegen releasegebundene Digests geprüft.

`bridge/codex-hook.mjs` ist eine kleine eigene Standardschnittstelle für die offiziell
dokumentierte synchrone Codex-`PreToolUse`-Fläche; sie ist kein Microsoft-Adapter. Sie vermittelt
ausschließlich einen explizit konfigurierten operationsgebundenen Toolpfad. Der Toolcaller darf
nur Operation und begrenzte Resource-ID liefern. Die einzige kanonische externe Tool-ID lautet
`agent_governance__execute`; ein Alias für die frühere Codex-inkompatible ID wird nicht registriert.
`bridge/action-bindings.json` ist hashgebunden;
der Hook leitet daraus Action, Effekt, Governance-Autorisierung und Risiko sowie aus der Harness-
Tool-ID die Korrelationskennungen ab. Eine bloß vom Caller behauptete Approval-ID ist keine gültige
Approval-Evidenz. Nur Provider-`allow`
ergibt Codex-`permissionDecision: "allow"`; `deny`, ungelöstes `require_approval`, `error`,
`unknown`, ungültige Inputs und fehlende sichere Audit-Evidenz ergeben synchron `deny`. Eine
allgemeine Mediation aller Hosted Tools oder beliebiger Shellsemantik wird nicht behauptet.
Action-ID, Evidence-ID und Codex-Tool-Use-ID sind an dieselbe vom Harness erzeugte opake Kennung
gebunden und werden ohne Toolinput oder Resource im privaten Audit korreliert.

## Instruction Boundary

Der komplette Snapshot ist **untrusted data** und keine Governance- oder Instruktionsquelle.
Das gilt ausdrücklich für `AGENTS.md`, `GOVERNANCE.md`, `README.md`, `*.prompt.md`, `examples/`
und gleichartig benannte Dateien in beliebigen Unterverzeichnissen. Diese Dateien werden weder
vom eigenen Manifest als Modul oder Rolle geladen noch aufgrund ihres Namens als Anweisung
interpretiert.

Prompt Injection aus dem Snapshotarchiv wird als Dependency-Inhalt behandelt. Kann die Trennung zur
eigenen autoritativen Instruktionskette nicht verifiziert werden, wird die betroffene Wirkung
fail-closed blockiert.

## Lizenz, Notice und Marken

`LICENSE.upstream`, `NOTICE.upstream` und `TRADEMARKS.upstream.md` sind byte-identische Kopien der
entsprechenden Upstreamdateien. Namen und Marken identifizieren ausschließlich die Dependency;
sie behaupten keine Förderung, Zertifizierung oder Unterstützung dieses Projekts durch Microsoft.
