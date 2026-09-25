# Resume und Evidence-Wiederverwendung

Dieses Modul definiert den zustandsgebundenen Resume Fast-Path für bereits begonnene,
unveränderte Arbeitsaufträge. Es ergänzt die Kontextkontinuität
([CTX-001](context.md#ctx-001--kanonische-arbeitswahrheit)) und die Liefergrenzen
([DEL-002](verification.md#del-002--exakter-stand)) um eine präzise, bindungsbasierte
Wiederaufnahme. Grundprinzipien:

```text
Resume statt Reconstruct.
Revalidate only what may have changed.
Reuse only what is still provably bound.
Chat context is transport, not authority.
State transition != evidence invalidation.
```

### RES-001 — Resume-Fall und Trigger

Der Trigger `resume_continuation` bezeichnet ausschließlich die technische, kontextuelle oder
Session-Fortsetzung eines bereits begonnenen, unveränderten Auftrags. Ein natürlichsprachliches
Signal wie `weiter` oder `fortsetzen` ist nur ein möglicher Auslöser zur Prüfung und niemals ein
Identitätsnachweis. Der Fast-Path wird erst aktiviert, wenn der aktuelle kanonische Zustand
bestätigt, dass tatsächlich derselbe Auftrag fortgeführt wird.

### RES-002 — Trennung vom Work-Item-Lifecycle

`resume_continuation` ist keine fachliche Statusänderung; es gilt strikt `resume_continuation`
ungleich `work_resumed`. Ein technischer Resume verändert keinen Work-Item-Lifecycle, kein Label,
keinen Issue-Status und keinen fachlichen Blocker. Existiert noch keine
Work-Item-Lifecycle-Capability, bleibt diese Trennung als Architekturgrenze bestehen; es werden
keine Lifecycle-Stubs erzeugt.

### RES-003 — Deterministische Zustandsidentität und Fingerprints

Der Fast-Path bindet den fortzusetzenden Arbeitsstand an getrennte, deterministische Identitäten;
ein einzelner globaler Hash über den gesamten Projektzustand ist dafür unzureichend. Getrennt
gebunden werden soweit erforderlich: Auftragsidentität, Ziel und Scope, Repository, Branch und
Worktree, der Exact Git State, relevante Inhaltsidentität, Dependency- und Lockfilezustand,
Konfiguration, Governancezustand, Evidence-Inputs, Environment sowie die Identität externer
Sources of Truth. Vorhandene Git-Objektidentitäten werden bevorzugt und nicht durch parallele
Hashlogik ersetzt. Fingerprints dienen der Identifikation und Invalidation; sie ersetzen nicht den
semantischen Checkpointinhalt.

### RES-004 — Minimaler Resume-Preflight

Bei einem möglichen Resume-Fall wird nicht der vollständige normale Projekt-Preflight ausgeführt,
sondern ausschließlich das geprüft, was den letzten Checkpoint tatsächlich invalidieren könnte:
erwartetes Repository, Worktree und Branch, aktueller Exact Head, Clean-/Dirty-Status, Ziel- und
Scope-Identität, letzter aktiver Task und relevante laufende Prozesse. Signatur-, Remote-, Auth-
und andere freshness-sensitive Zustände werden nur bei fachlichem Bedarf erneut gelesen; die
verbindliche Freshness-Policy folgt
[RES-009](#res-009--freshness-sensitive-evidence).

### RES-005 — Checkpoint-Auflösung und kanonische Wahrheit

Der Resume-Zustand wird aus persistenten kanonischen Quellen beziehungsweise daraus deterministisch
ableitbaren Checkpoints aufgelöst. Der vorherige Chat ist Arbeitskontext, aber keine erforderliche
Source of Truth. Die verbindliche Form ist die
[Resume-Checkpoint](#resume-checkpoint)-Vorlage; deren Semantik folgt
[CTX-002](context.md#ctx-002--sitzungsledger-und-checkpoints). Persistiert werden keine
vollständigen Chattranskripte und keine ungefilterten Logs.

### RES-006 — Evidence-Identität und granulare Bindung

Evidence ist niemals nur `PASS`. Sie wird an diejenigen Identitäten gebunden, die ihr Ergebnis
fachlich bestimmen: geprüfter Inhaltsstand, relevante Dateimenge, Konfiguration, Dependency- und
Lockfilezustand, Tool- und Testidentität, Parameter, Plattform, externe Source-of-Truth-Identität
sowie Freshness-Klasse. Die Bindung ist so eng wie erforderlich und so klein wie möglich; ein
einzelner globaler Resume-Digest, der unabhängige Evidence unnötig gemeinsam invalidiert, ist
unzulässig.

### RES-007 — Evidence-Reuse und -Invalidation

Deterministisch gilt: unveränderte relevante Bindung und vollständige Evidence → `REUSE`;
unvollständige Evidence → `RERUN`; geänderte relevante Bindung → `INVALIDATE`; unabhängige
Änderung → keine unnötige Invalidierung; Scopeänderung → betroffene Bindungen neu bestimmen. Eine
technische Unterbrechung allein invalidiert keine Evidence; ebenso wenig macht derselbe Chat
bestehende Evidence weiterhin gültig. Widersprüchliche Sources of Truth werden aufgelöst, statt
Evidence blind zu übernehmen.

### RES-008 — INCOMPLETE-Semantik

Ein Test, Build, Scan, Reviewer, Subagent oder Toolprozess ohne belastbares Abschlussartefakt hat
den Status `INCOMPLETE` und niemals `PASS`. Ein unterbrochener Reviewer oder Subagent liefert kein
Teilverdikt als Abschluss. Bei unverändertem Input wird ausschließlich der unvollständige atomare
Schritt erneut ausgeführt; davon unabhängige abgeschlossene Implementierungs-, Test-, Build- oder
Reviewschritte werden nicht wiederholt. Die Statuswahrheit folgt
[EVD-002](evidence.md#evd-002--statuswahrheit).

### RES-009 — Freshness-sensitive Evidence

Zustände, die sich ohne Codeänderung verändern können — Authentifizierung, Berechtigungen,
GitHub-Remotezustand, CI, Registry, Releasezustand, Security-Advisories, Netzwerk- und
Connectorzustand sowie laufende Prozesse — werden nach ihrer zuständigen Freshness-Policy erneut
gelesen. Der Fast-Path umgeht keine Freshness-Anforderung; sessiongebundene Auth- und
Permission-Evidence wird nicht blind wiederverwendet.

### RES-010 — Duplicate-Execution Guard

Vor dem Neustart einer möglicherweise unterbrochenen Aktion wird der tatsächliche Zustand
aufgelöst, ob der Prozess noch läuft oder seine Wirkung bereits eingetreten ist. Für externe oder
nicht idempotente Wirkungen — Publish, Release, Merge, Deployment, externe Mutationen — gilt
fail-closed: Ist unklar, ob die Wirkung bereits erfolgt ist, wird zuerst die Source of Truth
gelesen; eine zweite Ausführung wird nicht blind gestartet. Idempotente lokale Read-only-Prozesse
dürfen wiederholt werden. Externe Wirkungen bleiben an
[GOV-003](../../GOVERNANCE.md#gov-003--externe-wirkung) gebunden.

### RES-011 — Dirty-Worktree-Identität

`HEAD` gleich `erwarteter HEAD` ist kein hinreichender Gleichheitsnachweis. Relevante staged,
unstaged und untracked Inhalte werden deterministisch mitgebunden; zwei unterschiedliche relevante
Dirty-Zustände dürfen nicht denselben Resume-Zustand erhalten. Symlink-, Race-, Pfad- und
TOCTOU-Grenzen folgen [SEC-003](security.md#sec-003--unvertrauenswürdige-eingaben) und
[DEL-002](verification.md#del-002--exakter-stand).

### RES-012 — Context-Compaction und Fresh-Chat-Resume

Context-Compaction ist ein möglicher Resume-Auslöser und kein vollständiger Verlust des
Arbeitsstands. Nach einer Compaction wird der kleinste belastbare Checkpoint aufgelöst, der Exact
State minimal revalidiert und nur die unmittelbar benötigte Evidence geladen. Ein vollständig
frischer Chat muss denselben unveränderten Auftrag ohne Zugriff auf den vorherigen Chatverlauf
deterministisch wieder aufnehmen können; der vorherige Chat ist nie eine erforderliche Source of
Truth des Resume-Vertrags.

### RES-013 — TOON-Projektion

Der bestätigte Resume-Zustand wird für die Wiederaufnahme durch eine LLM als kompakte,
deterministisch erzeugbare Projektion im Format Token-Oriented Object Notation (TOON) kodiert und
beim Einlesen strikt dekodiert und fail-closed validiert. Der Datenfluss bleibt: kanonische Sources
of Truth, Checkpoint-Auflösung, Identitäts- und Gültigkeitsprüfung, minimaler Resume-Kontext,
deterministische TOON-Projektion, neuer LLM-Kontext. Die Formatkodierung nutzt die offizielle
Referenzimplementierung; eine eigene allgemeine TOON-Implementierung wird nicht gebaut. Die
Domänenvalidierung verantwortet weiterhin erlaubte Felder, erwartete Struktur, Checkpoint-Bindung,
State- und Evidence-Identität, Freshness und Staleness. TOON besitzt keine eigene Wahrheit, erfindet
keinen Zustand, ersetzt keine kanonische Checkpointdatei und ist keine zweite State-, Checkpoint-
oder Evidence-Source of Truth. Manipulierte, beschädigte, veraltete oder nicht eindeutig zum
Checkpoint passende Projektionen werden fail-closed abgelehnt; unbekannte oder geheime Felder werden
zurückgewiesen.

### RES-014 — Progressive Context Loading

Beim Resume wird zunächst nur der kleinste Kontext geladen, der erforderlich ist, um Auftrag,
Zustand, gültige Evidence, offene Arbeit und die nächste atomare Aktion zu bestimmen. Detaillierte
Evidence, Projekthistorie, Logs und Testresultate werden über stabile Referenzen beziehungsweise
kanonische Sources of Truth bedarfsgesteuert nachgeladen. Datenminimierung folgt
[CTX-005](context.md#ctx-005--quellenrouting-widerspruch-und-datenminimierung).

### RES-015 — Nächste atomare Aktion und Fail-Closed-Fallback

Der Resume endet deterministisch bei der ersten noch offenen atomaren Aktion. Kann eine relevante
Identität nicht sicher bestätigt werden, ist der Checkpoint unbekannt oder widersprüchlich oder die
Evidence-Bindung nicht belegbar, wird der Fast-Path fail-closed verlassen und in den kanonischen
normalen Workflow zurückgefallen; es wird weder probabilistisch fortgesetzt noch Embeddings oder
LLM-Memory als Identitätsnachweis verwendet. Wiederholtes Resume bei unverändertem Zustand erzeugt
keine zunehmende Rekonstruktion und keine doppelte externe Wirkung. Der Fallback bleibt
[GOV-004](../../GOVERNANCE.md#gov-004--fail-closed).

### RES-016 — Delivery-Übergänge invalidieren Evidence nicht

Ein reiner Delivery-Übergang — insbesondere `git push` desselben verifizierten Commit und die
Erstellung eines Pull Request für denselben Head — verändert den bereits lokal geprüften
Commitinhalt nicht und gilt daher nicht als Evidence-Invalidierung: `State transition != evidence
invalidation`. Bereits vollständig abgeschlossene lokale Prüfungen — Tests, Build, Typecheck,
Packcheck und ein identischer lokaler QA-Check — bleiben gültig, solange ihre relevanten
Bindungen unverändert sind. Ein Übergang der Workflowphase allein bestimmt nicht über die
Gültigkeit; diese richtet sich ausschließlich nach den relevanten Inputs und Bindungen gemäß
[RES-007](#res-007--evidence-reuse-und--invalidation).

### RES-017 — Deterministischer Evidence-Key

Evidence wird nicht lediglich als `PASS` oder pauschal an einen Git-SHA gebunden. Für jede
Prüfung ist eine deterministische fachliche Identität bestimmbar:

```text
Evidence-Key = content identity + check identity + relevant configuration
             + relevant environment + scope + freshness class + base/diff identity
```

Der Exact Head ist bei Repository-Arbeit eine zentrale, aber nicht immer allein ausreichende
Identität. Zusätzliche relevante Bindungen sind: Dirty-Worktree-Zustand, staged/unstaged
relevante Änderungen, Dependency-/Lockfilezustand, Tool-/Testversion, Konfiguration, Plattform,
Security-/Policy-Kontext, PR-Base beziehungsweise Diff, wenn die Prüfung davon abhängt, sowie
freshness-sensitive externe Zustände. Keine globale Invalidierung, wenn nur eine fachlich
unabhängige Bindung geändert wurde.

### RES-018 — Remote-Readback vor Reuse

Nach externen Delivery-Aktionen wird vorhandene Evidence nicht neu erzeugt, aber die relevante
externe Source of Truth vor der Wiederverwendung frisch gelesen. Nach `git push` wird mindestens
der erwartete lokale Head gegen den Remote-Branch-Head geprüft; nach der PR-Erstellung wird der
erwartete verifizierte Head gegen den frisch gelesenen PR-Head geprüft. Bei Abweichung wird keine
Evidence blind übernommen und fail-closed aufgelöst. Ein Readback bestätigt lediglich die externe
Identität und ersetzt keine davon unabhängige CI-, Security- oder Review-Evidence gemäß
[DEL-002](verification.md#del-002--exakter-stand).

### RES-019 — Identische versus unabhängige Prüfung

Die Orchestrierung unterscheidet explizit eine identische von einer unabhängigen Prüfung.
Identisch heißt: gleicher Input, gleicher Exact State, gleicher Checktyp, gleicher Checker,
gleiche Konfiguration und gleicher relevanter Environment-Kontext; dann wird vorhandene
vollständige Evidence wiederverwendet. Unabhängig sind etwa lokale Tests gegenüber GitHub CI,
ein lokaler QA-Reviewer gegenüber einem unabhängigen GitHub-Reviewer oder `darwin-arm64`
gegenüber `linux-x64`; sie erzeugen eigenständige Evidence. Ziel ist nicht, die Zahl unabhängiger
Prüfungen zu reduzieren, sondern identische Prüfungen ohne geänderte relevante Inputs nicht
mehrfach auszuführen. Ein abgeschlossener Review von Checker A ersetzt nicht automatisch einen
unabhängigen Review durch Checker B.

### RES-020 — Base-/Diff-gebundene Evidence

Gleicher Head bedeutet nicht automatisch, dass jede Review-Evidence unverändert gültig bleibt.
Base-unabhängige Evidence — etwa ein Test, der ausschließlich den Inhalt eines Heads prüft —
darf bei unverändertem Head wiederverwendet werden. Base-/Diff-gebundene Evidence — etwa ein
Review, dessen Aussage auf dem konkreten Diff gegen die Base beruht — wird bei einer relevanten
Base-Änderung gezielt invalidiert und neu erzeugt. Es erfolgt keine pauschale Invalidierung
sämtlicher Evidence allein aufgrund einer Base-Änderung.

### RES-021 — Remote-Gates bleiben unangetastet

Die Same-SHA-Wiederverwendung ersetzt oder schwächt keine unabhängigen Remote-Gates ab.
GitHub CI, Required Checks, Plattformmatrizen, Branch-/Ruleset-Gates, Mergeability,
GitHub-native Security-/Trust-Checks, unabhängige Remote-Reviewer, PR-spezifische
Review-Kommentare und freshness-sensitive externe Zustände werden weiterhin ausgeführt
beziehungsweise frisch ausgelesen. Required Checks, Branch Protection, Security-, Approval-
und Signing-Gates werden nicht umgangen oder abgeschwächt; dies folgt
[DEL-003](delivery.md#del-003--unabhängige-prüfung) und
[SEC-001](security.md#sec-001--risikobasiertes-security-gate).

### RES-022 — Ereignisgebundene Materialisierung

Bestätigter Resume-Zustand wird während der Arbeit materialisiert, bevor Kontext entbehrlich
wird. Materialisierungsrelevant sind Auftragsidentität, Scope, aktiver atomarer Task,
Taskstart/-abschluss/-fehler/INCOMPLETE, bestätigte Entscheidungen, Evidence-Start/-Abschluss/
Invalidation, geöffnete/geschlossene Findings, Exact-State- und Next-Action-Änderungen,
Handoff/Pause, vorbereitete/ausgeführte/zurückgelesene externe Wirkungen, angekündigte Compaction
und kontrolliertes Sessionende. Chatnachrichten allein sind kein Trigger. Identische Zustände
brauchen keine neue Generation. Die Workflowintegration verwendet den vorhandenen
Resume-Checkpoint-Vertrag; eine Work-Item-Identity wird nur referenziert.

Checkpoint-Projektionen tragen Schema-Version, Generation, Vorgänger- und Inhaltsbindung sowie
die erforderlichen granularen Identitäten. Sichere vorhandene Dateisystemprimitive veröffentlichen
vollständige Generationen atomar und exklusiv; stale Writer oder konkurrierende Updates dürfen
keinen neueren Zustand überschreiben. Eine idempotente Wiederholung muss dieselbe Event-ID,
Vorgängerbindung und denselben Inhalt besitzen. Partielle Staging-Dateien sind kein Checkpoint;
beschädigte publizierte Zustände, ungültige Schemas und widersprüchliche Ketten scheitern fail-closed.
Fehlgeschlagene Persistenz gilt niemals als erfolgreich. Ein Prozessabbruch lässt ausschließlich
einen vollständig validierbaren alten oder neuen Checkpoint zurück.

### RES-023 — Persistiertes Write-ahead und Readback

Vor einer nicht sicher wiederholbaren Wirkung werden Operation-ID, Ziel, Aktion und sichere
Input-Bindungen als `PREPARED` persistiert. Die Ausführung beansprucht die Operation exklusiv;
bis zu einem bestätigten Source-of-Truth-Readback bleibt ihr Resultat `UNKNOWN`.
`COMMITTED` setzt gebundenen Readback voraus. Eine bestätigte Nichtausführung darf erst als
`NOT_APPLIED` gelten, wenn auch kein noch aktiver Prozess oder ausstehender externer Vorgang
die Wirkung später auslösen kann. Ein bloß momentan fehlendes Ziel genügt nicht.

Recovery fragt ausschließlich die zuständige Authority ab. Unklarheit führt niemals zur blinden
Wiederholung. Nach `NOT_APPLIED` erfordert ein Versuch eine explizite erneute Vorbereitung und
weiterhin aktuelle Autorisierung. Operation-Identitäten und Bindungen werden nicht entfernt oder
umgedeutet. Persistenz erteilt keine Approval und übernimmt keine externe Authority.

### RES-024 — Persistenzgebundene Kontextprojektion und optionaler Flush

Die ausführbare Kette lautet: persistierten Checkpoint auflösen/lesen, vollständiges Schema,
Generationskette und Inhalt validieren, daraus `ResumeProjection` ableiten, dann TOON erzeugen.
Strukturvalidierung einer frei übergebenen `ResumeProjection` allein erfüllt diesen Vertrag nicht.
Zwischengespeichertes TOON muss sowohl an die erwartete Checkpoint-Identität als auch an den
abgeleiteten Inhalt gebunden sein; ein kopierter Fingerprint legitimiert keine manipulierten Felder.
Detail-Evidence wird ausschließlich bei Bedarf über ihre Referenz aufgelöst; fehlende benötigte
Artefakte blockieren ihre Wiederverwendung. Integritätsprüfung ersetzt weder Authentizität noch
den bestehenden Resume-Preflight und verlängert keine freshness-sensitive Evidence.

Ereignisgebundene atomare Materialisierung ist der primäre Schutz bei Compaction ohne Hook,
Crash und Sessionabbruch. Ein `checkpoint.flush()`-Adapter darf ausschließlich eine tatsächlich
vorhandene belastbare Lifecycle-Oberfläche ergänzen. Ohne solche Oberfläche wird kein Hook
erfunden und keine Startup-/Readiness-Semantik übernommen. Der Kern bleibt harnessneutral.

## Resume-Checkpoint

Domain-spezifische Form der Wiederaufnahme, Owner ist diese Resume-Capability
([RES-005](#res-005--checkpoint-auflösung-und-kanonische-wahrheit)). Sie ist bewusst kein
generisches `context/handoff`-Template: Resume bindet zusätzlich Task-/Scope-Identität, Dirty-State,
die Evidence-Bindungsmatrix (`REUSE`/`RERUN`/`INVALIDATE`/`INCOMPLETE`) und die TOON-Projektion,
die der generische Handoff-Vertrag nicht ausdrückt.

```text
Auftrag: <task-id> — <bounded objective>
Checkpoint: <schema identity> <generation> <previous checkpoint> <checkpoint fingerprint>
Scope: <included / excluded>
Task-Identität: <task_identity fingerprint>
Scope-Identität: <scope_identity fingerprint>
Repository/Worktree/Branch: <repository> <worktree> <branch>
Exact state: <branch> <head-SHA> <clean|dirty>
Dirty state: <staged / unstaged / untracked fingerprints>
Kanonische SSOT: <paths/objects and precedence>
Aktiver atomarer Task: <task> <RUNNING|COMPLETED|FAILED|INCOMPLETE>
Bestätigte Entscheidungen: <minimierte Referenzen>
Externe Wirkungen: <operation identity, safe bindings, PREPARED|UNKNOWN|COMMITTED|NOT_APPLIED, readback reference>
Abgeschlossene Evidence:
| Evidence-ID | Binding-Fingerprints | Ergebnis |
| <id> | <fingerprints> | <REUSE|INVALIDATE> |
Unvollständige Evidence: <INCOMPLETE Liste>
Offene Findings/Blocker: <classified list>
Nächste atomare Aktion: <one actionable continuation>
TOON-Projektion: <deterministisch abgeleitete .toon-Referenz>
Nicht übernehmen: <stale, secret oder out-of-scope>
```

## Grenzen

Der Fast-Path führt keine neue Datenbank ausschließlich für Resume, keinen permanenten Daemon,
keinen Netzwerkdienst und keine neue Credential-Infrastruktur ein und kodiert keine provider- oder
modellspezifische Limitlogik. Reproduzierbarkeit folgt
[INV-004](invariants.md#inv-004--reproduzierbarkeit).

Die Delivery-Boundary-Reuse erweitert die bestehende Evidence-Reuse-Authority. Es entstehen keine
zweite Evidence-Registry, keine zweite Resume-Engine, kein paralleler Delivery-State, kein
zusätzlicher permanenter Cache, kein separates PR-Evidence-System, keine zweite
Checkpoint-Authority und keine zweite PR-Contract-Authority. Eine ereignisgebundene persistente
Materialisierung des Resume-/Evidence-Zustands und ein kanonischer PR-Contract werden, sofern real
vorhanden, wiederverwendet; ihr Fehlen ist keine harte Abhängigkeit.
