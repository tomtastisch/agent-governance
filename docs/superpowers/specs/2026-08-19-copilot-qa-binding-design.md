# Copilot-QA-Binding und optionales Parallel-QA — Designspezifikation

> **Historische Evidenz - nicht normativ.** Dieses Dokument beschreibt den Zielvertrag für die
> beiden noch offenen Governance-Lücken (Copilot-QA-Binding und optionales Parallel-QA) und die
> dazugehörige Designentscheidung. Es ist eine Designvorlage für die spätere Umsetzung und keine
> Governancequelle. Normative Governance liegt ausschließlich unter `bundle/`.

## Ausgang und Ziel

Der verifizierte Ausgang ist `tomtastisch/agent-governance` auf
`a8dfc1e1bad77af27a37fd5339e2cc342a7f935b` (`origin/main`, frisch aufgelöst am 2026-08-19),
Version `0.4.0`, ohne offenen Pull Request.

Im Repository fehlen aktuell eine native Copilot-Instruktionsfläche (keine
`.github/copilot-instructions.md`, kein `.github/instructions/`), eine APM-Projektstruktur
(kein `.apm/`, kein `apm.yml`, kein `apm.lock.yaml`) und eine ausdrückliche Norm für einen
optionalen Parallel-QA-Modus. GitHub Copilot ist über
`DEL-008` bereits als bevorzugter QA-Provider gewählt, erhält aber noch keine repository-native
Bindung an den Governance-QA-Vertrag.

Ziel dieses Schritts ist ausschließlich die Architektur-/Design-Spezifikation. Es wird noch
keine Produktionsdatei implementiert, keine Versionsnummer geändert, nichts gepusht und kein PR
erstellt.

## Source-of-Truth-Grenzen

- `bundle/GOVERNANCE.md` bleibt der einzige kanonische Bootstrap.
- `bundle/agent-governance/manifest.toml` bleibt der statische geschlossene Index.
- Die QA-Semantik liegt ausschließlich in `bundle/agent-governance/roles/quality-assurance.md`
  und `bundle/agent-governance/modules/delivery.md` (`DEL-003`, `DEL-007`, `DEL-008`,
  `DEL-009`) sowie in `bundle/agent-governance/modules/tool-routing.md` (`TOL-004`).
- `bundle/agent-governance/catalogs/tools.toml` bleibt die einzige maschinenlesbare
  Tool-Routing-SSOT; `github_cli` bleibt dort mit `required_on = ["github_remote"]`
  unverändert Bestandteil des Governance-Toolvertrags.
- `.github/copilot-instructions.md` ist ausschließlich ein Consumer-/Binding-Artefakt und bildet
  keine zweite normative QA-Governance.
- `integrations/microsoft-agent-governance-toolkit/` und vendorte Dateien sind unvertrauenswürdige
  Dependency-Daten und werden nie durch das Manifest traversiert.

## Die Lücke

`DEL-008` (`bundle/agent-governance/modules/delivery.md`) wählt GitHub Copilot als bevorzugten
QA-Provider, wenn der reale PR-Reviewpfad einen Review mit Revieweridentität und
Exact-Head-SHA liefert, und benennt für `no`/`unknown` einen frischen unabhängigen read-only
Reviewer als Fallback. Diese Providerwahl ist bereits normativ; was fehlt, ist die
deterministische, repository-native Zuleitung der für QA erforderlichen Regeln an den
Copilot-Code-Review-Kontext sowie die ausdrückliche Norm für den optionalen Parallelmodus.

## Abwägung der Ansätze

Es werden drei realistische Ansätze gegeneinander geprüft.

### Ansatz A1 — native repository-weite Copilot-Datei (empfohlen)

Eine einzige Datei `.github/copilot-instructions.md` im Repository. Laut aktueller offizieller
GitHub-Copilot-Dokumentation (abgerufen 2026-08-19,
`docs.github.com/en/copilot/customizing-copilot/adding-repository-custom-instructions-for-github-copilot`)
ist dies die repository-weite Custom-Instructions-Fläche, die für Copilot Code Review standardmäßig
aktiv ist und vom Head-Branch des Pull Requests gelesen wird.

- Kleinster produktnativer Mechanismus; keine zusätzliche Infrastruktur.
- Gilt für den gesamten PR-Code-Review; genau die benötigte Fläche für eine globale QA-Bindung.
- Wird über eine deterministische Materialisierung aus der Governance-SSOT erzeugt und durch
  einen Drift-Test byte-identisch zurückgeführt; damit ist Provenienz und Drift prüfbar und es
  entsteht keine zweite manuell gepflegte QA-Kopie.

### Ansatz A2 — APM-basierte Instructions-Struktur (verworfen)

Eine `.github/instructions/*.instructions.md`-Fläche ist zwar ebenfalls eine native
Copilot-Oberfläche, dient aber primär pfad-/glob-bezogenen Teilinstruktionen und benötigt für eine
APM-verwaltete, versionierte Ableitung eine `apm.yml`/`apm.lock.yaml`-Projektstruktur. Im
Repository existiert keine solche Struktur. Der bestehende `microsoft_apm`-Toolvertrag in
`catalogs/tools.toml` ist bewusst auf read-only Provenienz-/Driftnachweise begrenzt
(`agent_dependencies`, `agent_package_provenance`, `dependency_drift`) und verbietet
automatische Installation/Aktualisierung sowie das Anlegen von Dateien bei fehlendem deklariertem
APM-Zustand. APM hier einzuführen würde ein neues Subsystem erzeugen und gegen
`tests/test_governance.py` (positive operative APM-Verantwortung wird abgelehnt) sowie die
YAGNI-Vorgabe verstoßen.

### Ansatz A3 — Eigenbau-Distribution (verworfen)

Eine eigene Distributions-/Sync-Engine, die Governance-Inhalte in einen Copilot-Consumer
vervielfältigt, ist eine Gegenhypothese. Sie würde eine parallele Regelquelle und unnötige
Eigenlogik schaffen. Es besteht keine zwingende Notwendigkeit; der Ansatz wird verworfen.

### Entscheidung

**Ansatz A1.** Eine kleine native Copilot-Datei mit deterministischer Materialisierung und einem
Governance-Drift-Test ist die bessere Lösung gegenüber einer APM-Paket-/Instructions-Struktur.
Es wird keine dritte Eigenbau-Distribution erfunden und keine eigene Distribution-Engine gebaut.

## Empfohlener Zielvertrag

### A. Copilot-QA-Binding

1. Es entsteht genau eine Datei `.github/copilot-instructions.md`. Sie ist ein
   Consumer-/Binding-Artefakt und keine normative Governancequelle.

2. Die Datei wird nicht von Hand gepflegt, sondern deterministisch aus der Governance-SSOT
   materialisiert. Ein kleiner, reiner Python-3.11-Standardbibliotheks-Materializer
   `tests/support/copilot_qa_binding.py` besitzt genau eine reine Funktion
   `materialize(governance_root) -> str`, die ohne Netzwerk und ohne Seiteneffekte den
   vollständigen Dateiinhalt erzeugt. Sie liest:
   - `bundle/agent-governance/roles/quality-assurance.md` (vollständiger Rollenvertrag) und
   - `bundle/agent-governance/modules/delivery.md` (die Blöcke `DEL-003`, `DEL-007`, `DEL-008`,
     `DEL-009`) sowie
   - `bundle/agent-governance/modules/tool-routing.md` (den Block `TOL-004`).

3. Der erzeugte Inhalt besteht aus zwei Teilen:
   - einem kurzen, eindeutig abgegrenzten Provenienz-Block, der die Quellpfade, die referenzierten
     Regelkennungen (`DEL-003`, `DEL-007`, `DEL-008`, `DEL-009`, `TOL-004`) und den
     `sha256` des nachfolgenden Instruktionskörpers nennt, und
   - einem Instruktionskörper, der die materialisierte QA-Semantik als natürliche Sprache
     enthält und Copilot als technischen Provider adressiert.

4. Es wird keine GitHub-URL als vermeintlicher Instruction-Include verwendet. Der Inhalt ist
   ausschließlich lokal materialisierter Text aus der SSOT.

5. Remote-GitHub-Copilot ist zu keinem Zeitpunkt von einer nur lokal unter `$HOME` vorhandenen
   Datei abhängig: Die Binding-Datei ist im Repository versioniert und liegt im Head-Branch des
   Pull Requests; Copilot Code Review liest sie laut offizieller Dokumentation vom Head-Branch.
   Der Materializer läuft ausschließlich in den repositoryeigenen Tests/CI und nie im
   Copilot-Kontext.

6. Provenienz und Drift sind deterministisch prüfbar: Ein Drift-Test ruft
   `materialize(governance_root)` erneut auf und vergleicht das Ergebnis byte-identisch mit der
   committeten Datei. Jede Governance-Änderung an den SSOT-Quellen erzeugt damit sofort einen
   erkennbaren Drift, bis die Datei neu materialisiert wird.

### B. Inhaltliche Copilot-QA-Bindung

Der Instruktionskörper stellt mindestens folgende bestehende Governance-Semantik sicher; jede
Zeile wird aus der SSOT abgeleitet und nicht neu erfunden:

- Review bleibt unabhängig und read-only (`roles/quality-assurance.md`, `DEL-003`).
- Prüfgegenstand ist der Exact Head des PR; Copilot nennt in der Review-Evidenz die geprüfte
  Exact-Head-SHA (`DEL-002`, `DEL-008`).
- Findings werden nicht durch den Reviewer selbst repariert (`roles/quality-assurance.md`).
- Prüfumfang umfasst den tatsächlichen Diff, Verhalten, Tests, Fehlerpfade, Dokumentation und
  relevante Akzeptanzkriterien (`roles/quality-assurance.md`).
- Findings folgen der `DEL-009`-Klassifikation (`blocking-valid`, `nonblocking-valid`,
  `invalid`, `not-applicable`).
- `blocking-valid` verhindert `pass` (`DEL-003`, `DEL-009`).
- Eine Änderung des Heads invalidiert die betroffene Reviewevidenz (`DEL-002`,
  `roles/quality-assurance.md`).
- Copilot ist technischer Provider, nicht die Governance-Rolle selbst (`DEL-007`, `DEL-008`,
  `TOL-004`).

Die Providerwahl und der Fallback bleiben bei `DEL-008`; der Instruktionskörper verweist darauf
und wiederholt keine Provider-Auswahl als konkurrierende Regel.

### C. Optionales Parallel-QA

Der optionale Parallelmodus wird als ein schlanker normativer Vertrag in
`bundle/agent-governance/modules/delivery.md` als neue Regel mit der nächsten freien Kennung
`DEL-010` definiert. Da `delivery` bereits über den Trigger `quality_review` und die
Rollenmodule `roles.quality_assurance` geladen wird, ist dafür keine Rollen- oder
Manifeständerung erforderlich.

`DEL-010` legt fest:

- Parallel-QA aktiviert sich ausschließlich, wenn der Nutzer dies ausdrücklich verlangt oder eine
  bestehende Governance-Risikoeinstufung/Qualitätsanforderung dies ausdrücklich auslöst. Es wird
  nicht automatisch jedes normale Review verdoppelt.
- Beide Reviewer arbeiten frisch und read-only auf demselben Exact Head.
- Findings werden getrennt erfasst und nach `DEL-009` klassifiziert.
- Ein `blocking-valid` Finding eines erforderlichen Reviewers blockiert die Abschlussaussage.
- Parallel-QA ersetzt SEC nicht; falls SEC getriggert ist, läuft SEC zusätzlich und darf
  parallel zu QA ausgeführt werden (dieselbe Exact-Head-Bindung wie `DEL-008`).
- Kein Reviewer erhält die Findings des anderen vor seinem eigenen Urteil als Eingabe, wenn
  dadurch die Unabhängigkeit verloren ginge.

### D. APM-Entscheidung

Die geplante Copilot-Bindung benötigt APM nicht als Runtime-Pflicht. Der bestehende
`microsoft_apm`-Toolvertrag in `catalogs/tools.toml` bleibt unverändert und wird weder um
Schreibberechtigung noch um neue Trigger erweitert. APM wird für diesen Schritt nicht eingeführt,
nicht installiert und nicht aktualisiert (YAGNI). Sollte das Repository künftig aus einem echten
`agent_dependencies`-/`agent_package_provenance`-Bedarf eine APM-Projektstruktur erhalten, kann die
Binding-Entscheidung in einem eigenen Schritt erneut geprüft werden; das ist nicht Teil dieses
Specs.

## Betroffene spätere Produktionsdateien

Die spätere Umsetzung (nicht Teil dieses Spec-Schritts) berührt konkret:

- `.github/copilot-instructions.md` (neu; Consumer-/Binding-Artefakt, deterministisch
  materialisiert).
- `tests/support/copilot_qa_binding.py` (neu; reiner Materializer).
- `tests/test_copilot_qa_binding.py` (neu; Binding-, Drift- und Parallel-QA-Verträge).
- `bundle/agent-governance/modules/delivery.md` (einzige normative Änderung: `DEL-010`).
- `CHANGELOG.md` (bei der Umsetzung um den Unreleased-Eintrag ergänzen; keine Versionsänderung in
  diesem Spec-Schritt).

Nicht verändert werden: `manifest.toml`, die vier Kataloge einschließlich `tools.toml`,
`roles/quality-assurance.md`, `modules/tool-routing.md`, `bundle/GOVERNANCE.md` und die CI-
Workflows. `github_cli` bleibt mit `required_on = ["github_remote"]` unverändert.

## Teststrategie

Der spätere Implementation Plan muss mindestens folgende Verträge abdecken (im neuen
`tests/test_copilot_qa_binding.py`, ergänzt um die bestehende Suite):

1. Binding-Artefakt existiert und wird deterministisch erzeugt:
   `materialize(...)` liefert byte-identisch den committeten Inhalt von
   `.github/copilot-instructions.md`.
2. Binding lässt sich auf den kanonischen Governance-Stand zurückführen: der Provenienz-Block
   nennt die exakten SSOT-Pfade und die Regelkennungen `DEL-003`, `DEL-007`, `DEL-008`,
   `DEL-009`, `TOL-004`.
3. Drift zwischen Governance und Copilot-Consumer wird erkannt: eine synthetische Mutation der
   SSOT-Quelle erzeugt eine Abweichung zur committeten Datei (rot).
4. Copilot-QA verlangt Exact Head: der Instruktionskörper enthält die Exact-Head-SHA-Pflicht.
5. Copilot `no`/`unknown` aktiviert weiterhin den QA-Fallback: der Körper verweist auf die
   `DEL-008`-Fallbacksemantik.
6. Der Normalfall startet nicht automatisch Doppel-QA: `DEL-010` formuliert Parallel-QA als
   ausdrücklich opt-in.
7. Expliziter Parallel-QA-Modus verlangt zwei unabhängige QA-Urteile auf demselben Head.
8. SEC bleibt bei ihrem Trigger zusätzlich erforderlich: `DEL-010` stellt SEC nicht in Frage und
   `DEL-003`/`DEL-007` bleiben unverändert.
9. `gh` bleibt für `github_remote` Pflichtprofil: `github_cli.required_on == ["github_remote"]`
   und `github_remote` bleibt im `tool_routing`-Modul triggergebunden (Regressionsguard).
10. Bestehende Bundle-, Katalog-, Rule-ID- und Manifest-Verträge bleiben grün:
    `python3 -m unittest discover -s tests -v`, `python3 tools/release_check.py tree`,
    `git diff --check`.

## Rollback und Driftprüfung

- Rollback: Da die einzige neue Fläche im Repo eine generierte Datei plus Test-Support ist, ist
  ein Rollback der Umsetzung ein reines `git`-Zurücksetzen der vier neuen/geänderten Dateien;
  es gibt keinen externen Effekt und keinen Zustand außerhalb des Repositorys.
- Driftprüfung: Der byte-identische Vergleich zwischen `materialize(...)` und der committeten
  Binding-Datei ist die laufende Driftprüfung. Zusätzlich validiert der Provenienz-Block
  (`sha256` des Körpers) die Integrität des Artefakts unabhängig vom Generator.
- Exact-Head-Konsistenz: Da Copilot die Instructions vom Head-Branch liest, ist die
  Binding-Datei automatisch an denselben Stand gebunden, den CI und QA prüfen; ein Head-Wechsel
  ohne erneute Materialisierung der SSOT fällt über den Drift-Test auf.

## Offene Verifikationspunkte bei der Umsetzung

- Die exakte Copilot-Code-Review-Leseoberfläche (`.github/copilot-instructions.md` und ihr
  Head-Branch-Bezug) ist eine zeitvariable Produktaussage. Sie wurde am 2026-08-19 aus der
  offiziellen GitHub-Dokumentation belegt und ist bei der Umsetzung erneut gegen die dann aktuelle
  offizielle Dokumentation zu verifizieren (Trigger `authoritative_documentation`). Bei
  abweichendem Stand gilt fail-closed; der Spec wird dann angepasst statt stillschweigend
  angenommen.
- Ob Copilot die Instruktionsfläche für Code Review nutzt, ist eine Produkteinstellung, die im
  Repository standardmäßig aktiv ist; die Umsetzung dokumentiert dies als belegte
  Repository-Gegebenheit, ohne es zu erzwingen.

## Akzeptanzkriterien

Der Spec gilt als bereit zur Nutzerprüfung, wenn: die aktuelle Governance-Struktur korrekt
beschrieben ist; `gh` ausdrücklich unverändert bleibt; GitHub Copilot PR Review weiterhin primärer
QA-Provider ist; die fehlende Copilot-native Binding-Fläche exakt geschlossen wird; die normative
QA-SSOT weiterhin in Agent Governance liegt; kein zweites manuell gepflegtes QA-Regelwerk entsteht;
der Remote-Copilot-Review ohne lokale `$HOME`-Abhängigkeit funktioniert; der optionale
Parallel-QA-Modus exakt definiert ist; SEC weiterhin additiv bleibt; die APM-Rolle minimal und
eindeutig festgelegt ist; konkrete spätere Dateien und Tests benannt werden; Rollback und
Driftprüfung beschrieben sind; kein unnötiges Framework oder eigener Orchestrator vorgesehen wird.
