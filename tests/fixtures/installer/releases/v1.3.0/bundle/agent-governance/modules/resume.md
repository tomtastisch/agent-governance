# Resume und Evidence-Wiederverwendung

Dieses Modul definiert den zustandsgebundenen Resume Fast-Path für bereits begonnene,
unveränderte Arbeitsaufträge. Es ergänzt die Kontextkontinuität
([CTX-001](context.md#ctx-001--kanonische-arbeitswahrheit)) und die Liefergrenzen
([DEL-002](delivery.md#del-002--exakter-stand)) um eine präzise, bindungsbasierte
Wiederaufnahme. Grundprinzipien:

```text
Resume statt Reconstruct.
Revalidate only what may have changed.
Reuse only what is still provably bound.
Chat context is transport, not authority.
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
[DEL-002](delivery.md#del-002--exakter-stand).

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

## Resume-Checkpoint

Domain-spezifische Form der Wiederaufnahme, Owner ist diese Resume-Capability
([RES-005](#res-005--checkpoint-auflösung-und-kanonische-wahrheit)). Sie ist bewusst kein
generisches `context/handoff`-Template: Resume bindet zusätzlich Task-/Scope-Identität, Dirty-State,
die Evidence-Bindungsmatrix (`REUSE`/`RERUN`/`INVALIDATE`/`INCOMPLETE`) und die TOON-Projektion,
die der generische Handoff-Vertrag nicht ausdrückt.

```text
Auftrag: <task-id> — <bounded objective>
Scope: <included / excluded>
Task-Identität: <task_identity fingerprint>
Scope-Identität: <scope_identity fingerprint>
Repository/Worktree/Branch: <repository> <worktree> <branch>
Exact state: <branch> <head-SHA> <clean|dirty>
Dirty state: <staged / unstaged / untracked fingerprints>
Kanonische SSOT: <paths/objects and precedence>
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
