# Persistente Resume-Checkpoints

Der Paket-Subpfad `@tomtastisch/agent-governance/resume-checkpoint` materialisiert
den bestehenden [Resume-Vertrag](../bundle/agent-governance/modules/resume.md).
Er ersetzt weder Repository/Git/GitHub/Governance als Authority noch deren
Revalidierung. Er entscheidet keine Readiness, startet keinen Harness und führt
keinen Work-Item-Lifecycle. Die additive öffentliche API erfordert SemVer minor;
vor Veröffentlichung ist die Klassifikation erneut am dann aktuellen Vertrag zu prüfen.

## Verwendung während der Arbeit

Der Aufrufer erstellt einen expliziten privaten Ordner (`0700`, eigener Benutzer,
absoluter kanonischer Pfad ohne Symlinks). Dateien werden mit `0600` angelegt.
Ein Ordner gehört genau einem Auftrag. Die vorhandenen nativen Primitiven
unterstützen macOS und Linux auf arm64/x64; fehlt diese Capability, scheitert
die Schreibwirkung. Es gibt keine Fallback-Schreibtechnik mit schwächeren Garantien.

```ts
import { ResumeCheckpointStore } from "@tomtastisch/agent-governance/resume-checkpoint";
import type { ResumeState } from "@tomtastisch/agent-governance/resume-checkpoint";

const checkpoint = await ResumeCheckpointStore.open("/absolute/private/resume-task");
const previous = await checkpoint.read();
// state kommt aus bestätigten Authorities, nicht aus Chat oder TOON.
const state: ResumeState = {
  projection: {
    taskId: "issue-87", objective: "Resume materialisieren", scope: ["resume"],
    exactHead: "confirmed-git-object", evidence: [], incompleteEvidence: [],
    openFindings: [], nextAtomicAction: "gezielte-tests",
  },
  identities: {
    scope: "scope-identity", repository: "repository-identity", worktree: "worktree-identity",
    branch: "branch-identity", dirty: "staged-unstaged-untracked-identity",
    dependencies: "lockfile-identity", configuration: "configuration-identity",
    governance: "governance-identity", environment: "environment-identity",
  },
  authorities: ["git:repository", "github:issue-87"], // in Prioritätsordnung
  activeTask: "tests", taskStatus: "RUNNING", decisions: [],
  evidenceReferences: [], workItem: "github:issue-87", externalEffects: [],
};
const confirmed = await checkpoint.materialize({
  eventId: "task-tests-started", trigger: "task_started", expected: previous, state,
});
// Eine neue Instanz muss ohne vorherigen Chat dieselben persistenten Bytes verwenden.
const fresh = await ResumeCheckpointStore.open("/absolute/private/resume-task");
const toon = await fresh.toToon(confirmed!);
await fresh.validateToon(toon, confirmed!);
```

`MATERIALIZATION_TRIGGERS` exportiert die 21 Ereignisklassen aus RES-022.
`message` ist explizit irrelevant und erzeugt keinen Checkpoint; unbekannte Trigger
scheitern. Identischer Zustand erzeugt keine unnötige Generation. `eventId` ist eine
stabile fachliche Ereigniskennung; ihre Wiederholung mit derselben Vorgängerbindung,
demselben Trigger und Inhalt ist idempotent. Eine bereits überholte oder widersprüchliche
Event-ID wird abgelehnt. `expected` bindet Generation **und** Fingerprint; nach einem
Konflikt müssen Authorities und letzter Checkpoint erneut gelesen werden.

Ein real vorhandener Lifecycle-Adapter könnte `await checkpoint.flush()` aufrufen.
Das Repository installiert keinen Compaction-Hook. `flush()` synchronisiert und
validiert ausschließlich bereits materialisierten Zustand; es errät keinen noch
nicht übergebenen Modellzustand. Jeder relevante Übergang muss vorher `materialize`
verwenden. Compaction ohne Hook, Sessionwechsel und Prozessabbruch verwenden denselben
Speichervertrag.

## Recovery, Atomicität und Datenhygiene

Jede Generation ist eine vollständige kanonische JSON-Projektion mit Schema-Version,
Event-ID, Vorgängerbindung und Inhaltsfingerprint. Eine private Staging-Datei wird
vollständig geschrieben und synchronisiert. Die vorhandene exklusive native Rename-
Primitive veröffentlicht sie unter der Folgegeneration (`1.json`, `2.json`, ...).
Danach wird der Ordner synchronisiert und der publizierte Checkpoint zurückgelesen.
Der Erfolg wird erst danach zurückgegeben. Ein Fehler nach Publikation ist kein
Erfolgsnachweis für den Aufruf; Recovery kann die vollständige Generation erneut
validieren. Ein Abbruch vor Publikation lässt die vorherige Generation nutzbar.

Konkurrierende Writer können denselben Generationsnamen nicht ersetzen. Abgebrochene
`.stage-<UUID>`-Dateien bleiben unpubliziert und werden nie als Checkpoint akzeptiert.
Der Store entfernt weder diese Artefakte noch alte Generationen automatisch. Ein
beschädigter publizierter Zustand, eine Lücke oder falsche Vorgängerbindung führt
zum Abbruch statt zu stiller Rückstufung. Diese Historie ist Checkpoint-Versionierung,
keine zweite fachliche Source of Truth. Prüfsummen belegen Konsistenz, keine
Authentizität gegen einen Angreifer mit denselben OS-Rechten. Die Autorität bleibt
bei den revalidierten Quellen. Persistierte Dateien nicht manuell umschreiben.

Schemafelder sind geschlossen; pro Checkpoint gelten 256 KiB, pro Textfeld 8192
Zeichen und pro Liste 1024 Elemente als Obergrenzen. Keine Rohdaten-Payloads,
Chattranskripte, Logs, Credentials oder Credential-Derivate übergeben. Der Aufrufer
ist verantwortlich für die Auswahl ausschließlich nicht sensitiver Metadaten und
Referenzen. Zusätzliche Musterprüfungen erkennen bekannte Credential-Formen, können
aber nicht jeden beliebigen geheimen Wert als solchen erkennen. Auch generierte
Fingerprints dürfen ausschließlich nicht sensitive Metadaten binden. Es gibt keine
Netzwerkzugriffe oder Telemetrie durch den Store.

## Resume, Evidence und TOON

`read(expected?)` prüft sämtliche publizierten Generationen, Schema, Größen,
Dateitypen/-rechte, Vorgängerbindungen und Inhaltsfingerprints. Eine erwartete
Identität verhindert die Verwendung einer inzwischen überholten Generation.
Danach führt der Konsument den bestehenden RES-003..015-Preflight aus: Auftrag,
Scope, Repository/Worktree/Branch, Exact Head und Dirty-State sowie relevante
Konfiguration, Dependencies, Governance und Environment an ihren Authorities prüfen.
Bei geänderten Bindungen werden betroffene Ergebnisse gemäß RES-007 invalidiert;
der Store übernimmt diese fachliche Entscheidung nicht und baselinet nie implizit neu.

Die Evidence-Bindungsmatrix bleibt die vorhandene `ResumeProjection`. `INCOMPLETE`
wird separat geführt und darf nicht zugleich `REUSE` sein. Details bleiben in
`evidenceReferences`; `evidenceReference(expected, id, exists)` fragt nur die benötigte
Referenz über den vom Konsumenten gelieferten Authority-Callback ab. Ein fehlendes
Artefakt scheitert. Existenz allein belegt keine fachliche Gültigkeit. Auth, CI,
Registry, Security-Advisories und andere volatile Quellen benötigen frischen Readback.

`toToon(expected)` nimmt keinen frei konstruierten Projektionsinhalt entgegen:

```text
persistierter Checkpoint → lesen → vollständig validieren
→ ResumeProjection ableiten → bestehender TOON-Codec
```

`validateToon(text, expected)` prüft zusätzlich zur Codec-Struktur und Fingerprint-
Bindung den vollständigen abgeleiteten Projektionsinhalt gegen den erneut gelesenen
Checkpoint. Ein kopierter Fingerprint kann manipulierte TOON-Felder nicht legitimieren.
Der bisherige `resume-toon`-Export bleibt unverändert als Codec verfügbar; sein
`encodeResumeProjection()` allein ist kein Persistenznachweis. Granulare Evidence-
Bindings werden durch die globale Checkpoint-Integritätsbindung nicht ersetzt.

## Externe Wirkungen

Zuerst wird mit Trigger `effect_prepared` eine Operation in `externalEffects`
materialisiert: `operationId`, `target`, `action`, sichere `inputBindings`,
`state: "PREPARED"`, `readbackReference: null`. Alle früheren Operationsidentitäten
bleiben erhalten. Ziel, Aktion und Inputs einer Operation sind unveränderlich.

`executeEffect(expected, operationId, execute, readback)` beansprucht die vorbereitete
Operation exklusiv durch einen vorab persistierten `UNKNOWN`-Zustand. Erst dann läuft
der bereits autorisierte `execute`-Callback. Bei Throw/Abbruch bleibt `UNKNOWN`;
eine erneute Ausführung ist gesperrt. Der Readback-Callback liefert die exakt gleiche
Operation-Bindung, `outcome: "APPLIED" | "NOT_APPLIED" | "UNKNOWN"` und eine sichere
`reference` (`null` bei UNKNOWN). Nur gebundener Readback erzeugt COMMITTED.

`recoverEffect(expected, operationId, readback)` fragt ausschließlich die externe
Authority ab und besitzt keinen Effect-Callback. Ein Readback darf NOT_APPLIED nur
melden, wenn er Nichtvollzug **und** fehlende aktive/ausstehende Ausführung belegt.
Bei einem noch laufenden Prozess, eventual consistency oder unklarem Remotezustand
muss er UNKNOWN liefern. Der Store kann diese fachspezifische Authority nicht ersetzen.
Nach NOT_APPLIED ist eine explizite neue PREPARED-Generation für dieselbe Operation
möglich; Autorisierung, frische Inputs und Prozesse sind erneut zu prüfen. Bereits
COMMITTED führt bei wiederholtem `executeEffect` zu keiner weiteren Wirkung.

Ein nebenläufiger Scope-/Checkpoint-Wechsel während der Wirkung blockiert den
veralteten Abschluss. Recovery muss den neuen Zustand lesen und ausschließlich
den Readback nachholen. Niemals den Effekt wegen eines Persistenzfehlers wiederholen.
