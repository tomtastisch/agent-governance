# Ereignisgebundene Resume-Materialisierung (#87)

## Auftrag und IST-Zustand

Authority: [Issue #87](https://github.com/tomtastisch/agent-governance/issues/87),
Repository/Git, installierte Governance und bestehender RES-Vertrag. Basis:
`4e50cbffd75866deaa37b263ebe4d99442420a70` (`origin/main`, Stable 1.5.2).
Kein vorhandener #87-Worktree oder Checkpoint. #50 ist geschlossen und liefert
`modules/resume.md`, den exportierten `resume-toon`-Codec und Contracttests.
Ein ausführbarer Resume-Resolver existiert nicht: RES-003 bis RES-015 definieren
den durch den Agenten auszuführenden Resolver. Dieser wird nicht dupliziert.
#79, #64 und #65 sind offen; vorhandene Work-Item-Klassifikation ist keine
Execution-Persistenz. Installer-Receipts und Locks gehören der Installation.
Native Create-/Rename-Primitiven sowie sichere Snapshots sind vorhanden.
Es gibt keine belastbare Pre-Compaction-/Harness-Lifecycle-Oberfläche im Repository.

## Entscheidung

Ein neuer Paket-Subpfad `resume-checkpoint` materialisiert bestätigte, minimierte
Resume-Metadaten. Der bestehende TOON-Vertrag bleibt unverändert. Eine Datei mit
atomarem Replace und Installer-Lock wäre kleiner, hinterließe aber bei Abbruch
zwischen Lock-Verzeichnis und Owner-Datei einen manuellen Recoveryfall. Stattdessen
werden vollständige Checkpoint-Generationen mit der vorhandenen exklusiven nativen
Rename-Primitive veröffentlicht. Eine Datenbank oder ein Hintergrunddienst ist
nicht erforderlich. Staging-Dateien sind niemals Checkpoints.

Der explizite, private Speicherordner enthält fortlaufende Generationen. Der Writer
bindet sich an die erwartete Generation und deren Fingerprint. Genau ein Writer
kann die nächste Generation publizieren. Vor und nach der Veröffentlichung werden
Schema, Payload, Vorgängerbindung und Verzeichnisidentität geprüft. Datei und
Verzeichnis werden vor Erfolg synchronisiert. Ein Abbruch hinterlässt entweder
den alten oder einen vollständig validierbaren neuen Zustand; ein beschädigter
publizierter Zustand wird nicht still durch einen älteren ersetzt.

## Daten- und Integrationsvertrag

Der Inhalt erweitert den bestehenden ResumeProjection-Inhalt um granulare
Identitäten, priorisierte Authority-Referenzen, aktiven Task/Status, bestätigte
Entscheidungsreferenzen, Detail-Evidence-Referenzen und externe Operationszustände.
Ein vorhandenes Work Item wird ausschließlich referenziert. Schemafelder sind
geschlossen, Größen begrenzt; keine generischen Payloads, Toolausgaben, Chats,
Credentials oder Credential-Derivate. Der Aufrufer liefert ausschließlich bereits
minimierte öffentliche Metadaten; Struktur- und Credential-Musterprüfung ersetzt
nicht die fachliche Auswahl sicherer Metadaten. Keine Netzwerkzugriffe.

Alle im Issue benannten relevanten Übergänge sind explizite Trigger; irrelevante
Ereignisse schreiben nichts. Identische Wiederholung ist idempotent, stale Writer
und widersprüchliche Event-IDs scheitern. Flush validiert den letzten bestätigten
Zustand; fehlende Hooks verändern die Funktion nicht.

Eine externe Wirkung wird vor dem Callback mit Operation-ID, Ziel, Aktion und
sicheren Input-Bindungen PREPARED persistiert. Danach gilt UNKNOWN bis zum
Source-of-Truth-Readback. COMMITTED benötigt bestätigtes Readback, NOT_APPLIED
einen bestätigten Nichtvollzug. Recovery führt nur Readback aus, niemals blind
erneut den Effekt. Wiederholungsversuche benötigen NOT_APPLIED und eine neue
Vorbereitung derselben unveränderten Operation. Ungeklärte Operationen dürfen
weder verschwinden noch durch eine geänderte Bindung ersetzt werden.

TOON-Erzeugung liest den bestätigten Checkpoint erneut; Decoderbindung plus
Inhaltsvergleich lehnen auch manipulierte Projektionen mit kopiertem Fingerprint
ab. Detail-Evidence bleibt referenziert und wird bedarfsgesteuert durch die
zuständige Authority aufgelöst. Persistenz verlängert keine Freshness. Der
bestehende RES-Preflight prüft Task/Scope, Dirty-State, Exact Head und alle
relevanten Bindungen vor Wiederaufnahme; die Speicherschicht erteilt keine Freigabe.

## Akzeptanz und Risiken

Contract-, echte Prozessabbruch-/Parallel-Writer-, Negativ-, Security-,
TOON-/Fresh-Chat- und External-Effect-Tests decken Issue #87 ab. Gesamtsuite,
Typecheck/Lint/Build, Packaging, Audit/Lizenzen, Python-/Repository-Gates und
Remote-Plattform-CI bleiben erforderlich. QA und SEC prüfen denselben Lieferhead.
Der Ordner gehört dem aufrufenden Benutzer; feindlicher Zugriff mit identischen
OS-Rechten liegt wie beim Installer außerhalb einer manipulationssicheren Authority.
Prüfsummen belegen Konsistenz, keine Authentizität. SemVer: rückwärtskompatible neue
Capability, minor; kein Versionsbump oder Release im Implementierungs-PR.
