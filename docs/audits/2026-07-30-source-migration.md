# Migrationsmatrix der Altquellen

- Analysierter Repository-Stand:
  `42efb7a6318fe756834f8b6c5a18114e83d09e53`
- Architekturentscheidung:
  [ADR 0003](../decisions/0003-canonical-governance-bundle.md)

## Zweck

Diese Matrix dokumentiert ausschließlich, wie die Altquellen in die beschlossene
Bundle-Struktur überführt oder entfernt werden. Sie ist keine normative Regelquelle.

Der Ausgangsstand enthält 32 versionierte Dateien. Der Referenzscan ergab parallele
Bootstrap- und Rollenquellen, statische Benutzerverzeichnispfade, begriffliche Zyklen zwischen
Kern und Rollen sowie eine zweite operative Vertragsfläche in `project.toml`. Die drei
ausführbaren Bootstrap-Imports sind zwar nicht rekursiv, die gesamte Regelautorität ist jedoch
über Kern, Adapter, Templates, Profil und Manifest verteilt.

## Quellenmigration

| Ausgangsquelle | Problem | Entscheidung | Zielort | Erforderlicher Regressionstest |
|---|---|---|---|---|
| `core/core.md:1-14,323-347` | Vorrang und Instruktionsgrenze widersprechen sich; Harness- und Profilquellen beanspruchen zusätzliche Autorität. | Eine eindeutige Bootstrap-Autorität und minimale Instruktionsgrenze konsolidieren. | `bundle/GOVERNANCE.md`, `modules/invariants.md` | genau eine Bootstrap-Quelle; keine widersprüchliche Vorrangregel |
| `core/core.md:15-54,78-149,348-361` | Arbeitsweise, Scope, Blocker und Befundrouting sind über Kern, Rollen und Adapter wiederholt. | Universelle Ablaufregeln bündeln; Rollendetails nur in der jeweiligen Rollenquelle. | `modules/workflow.md`, `roles/*.md` | keine exakten Absätze oder Regel-IDs doppelt; Rollen nur triggerbasiert |
| `core/core.md:55-77,150-164,381-389` | Evidenz-, Abschluss- und Selbstprüfungsregeln überschneiden sich. | Gemeinsam referenzierte Evidenz- und Abschlussinvarianten zusammenführen. | `modules/evidence.md` | zentrale IDs eindeutig; Abschlussregeln nicht in anderen Modulen definiert |
| `core/core.md:165-205` | SSOT-Grundsätze stehen neben technikspezifischen Runtime- und Service-Discovery-Vorgaben. | Allgemeine Architektur- und Schnittstellengrundsätze erhalten; konkrete Runtime-Muster entfernen. | `modules/architecture.md` | keine Runtime-, Provider- oder Control-Plane-Begriffe |
| `core/core.md:206-322` und `core/branch-tags.toml` | Tests, Dokumentation, CI, Definition of Done, Branches und Review sind mehrfach und positionsabhängig referenziert. | Zusammengehörige Delivery-Gates konsolidieren; historische Abschnittsnummern nicht als Identität fortführen. | `modules/delivery.md` | zentrale Abschluss-/Review-IDs eindeutig; keine zweite Tag-Normquelle |
| `core/core.md:323-347` | Sicherheitsgrundsätze und rollenbezogener Auditablauf sind vermischt. | Unverzichtbare Invarianten von triggerbaren Security-Prüfungen trennen. | `modules/invariants.md`, `modules/security.md`, `roles/security-review.md` | Security-Modul nur bei geschlossenem Trigger; unabhängige Rolle einmal definiert |
| `core/core.md:362-380` | Governance verlangt konkrete Tools, Plugins und Server. | Providerneutrales Modulrouting behalten; Tool- und Plattforminstallation entfernen. | `bundle/GOVERNANCE.md`, `manifest.toml` | Manifest enthält nur statische Pfade, Trigger, Abhängigkeiten und Rollenpfade |
| `core/roles/ak.md` | Rolle wird zusätzlich in Kern, Wrapper und Projektvertrag beschrieben. | Einmalig als Architekturrolle konsolidieren. | `roles/architecture.md` | genau eine normative Architekturrollenquelle |
| `core/roles/st.md` | Rolle wird zusätzlich in Kern und Wrapper beschrieben und fehlt im Projektvertrag. | Einmalig als Triagerolle konsolidieren. | `roles/triage.md` | genau eine normative Triagerollenquelle |
| `core/roles/qa.md` | Read-only- und Exact-Head-Regeln werden in Kern, Wrapper und Projektvertrag wiederholt. | Einmalig als QA-Rolle konsolidieren. | `roles/quality-assurance.md` | genau eine normative QA-Rollenquelle |
| `core/roles/sec.md` | Auditgrenzen werden in Kern, Wrapper und Projektvertrag wiederholt. | Einmalig als Security-Review-Rolle konsolidieren. | `roles/security-review.md` | genau eine normative Security-Rollenquelle |
| `adapters/codex.md`, `adapters/claude.md` | Harness-spezifische Normen, Toolkopplung und statische Installationspfade; zwei optionale Brewfile-Verweise sind nicht auflösbar. | Vollständig entfernen; nur Ziel-Home und Einstiegspunktname als Installerdaten führen. | Installer-Harnessmapping | keine Adapterdatei; benutzerdefinierter Harness verlangt explizite Ziele |
| `templates/AGENTS.md`, `templates/CLAUDE.md` | Inhaltlich unterschiedliche Bootstrap-Quellen. | Entfernen; Einstiegspunkt aus unveränderten `GOVERNANCE.md`-Bytes erzeugen. | `bundle/GOVERNANCE.md` | installierter Bootstrap byte-identisch; keine gepflegte `AGENTS.md`-/`CLAUDE.md`-Quelle |
| `templates/claude-agents/*.md` | Harness-spezifische Wiederholung der vier Rollen. | Vollständig entfernen. | `roles/*.md` | keine Rollenwrapper; jede Rolle einmal |
| `templates/README.md` | Beschreibt parallele Templates, Adapter und Pfadsubstitution. | Entfernen; reale Installation nur in Root-Dokumentation beschreiben. | `README.md`, `INSTALL.md` | Dokumentation referenziert ausschließlich vorhandene Zielstruktur |
| `profile/profile.example.md` | Versionierte Vorlage bindet private Regeln an das alte Profil- und Toolmodell. | Durch neutrale, nicht normative Beispielvorlage ersetzen. | `local/user-rules.example.md` | echte Nutzerregeln nicht versioniert; Installerlogs enthalten keine Inhalte |
| `project.toml` | Operative Provider-, Identity-, Registry-, Queue-, Lease-, Audit-, Runtime- und Rollenlogik bildet eine zweite SSOT. | Entfernen; ausschließlich statische Trigger- und Pfadzuordnung neu modellieren. | `manifest.toml` | verbotene Control-Plane-Felder und -Begriffe fehlen; unbekannter Trigger lädt nicht alles |
| `tools/tools.md`, `tools/Brewfile`, `tools/Brewfile.optional` | Installieren konkrete Werkzeuge, Plugins und Provider. | Entfernen; keine Migration in Governance oder Installer. | entfällt | keine Toolinstallation, Paketmanager- oder Providerliste |
| `INSTALL.md` | Freier Agentenprompt erkennt Harness und substituiert Inhalte/Pfade. | Durch dokumentierten, vollständigen CLI-Aufruf und reinen Verifikationsprompt ersetzen. | `INSTALL.md`, Installer-CLI | Prompt enthält keine parallele Installationslogik |
| `README.md`, `CHANGELOG.md`, `VERSION` | Beschreiben Altstruktur und Releasezustand; können Normen duplizieren. | README/Changelog an realen Zielstand anpassen; VERSION bleibt Release-SSOT. | Root-Dokumentation | Links auflösbar; keine normative Wiederholung |
| `.github/workflows/ci.yml` | Prüft nur die Altstruktur und eine unvollständige Plattformmatrix. | Auf Bundle-, Installer- und Migrationssuite unter den unterstützten Plattformen umstellen. | `.github/workflows/ci.yml` | Ubuntu, macOS, Windows; Python 3.11 und neuere unterstützte Version |
| `tests/test_governance.py` | Konserviert Adapter, Templates, Wrapper, Toolkatalog und Abschnittsnummern; scannt den Arbeitsbaum statt der Sollmenge. | Durch Manifest-/Bundle-basierte Strukturtests ersetzen. | `tests/` | Größe, Regel-IDs, Absatzduplikate, Links, Zyklen, Trigger und verbotene Begriffe |
| `tests/check_links.py` | Prüft nur externe Werkzeugkataloglinks. | In lokale Bundle- und Markdown-Linkprüfung überführen. | `tests/` | Repository- und simulierte Installationspfade case-sensitiv auflösbar |
| `tools/release_check.py`, `tests/test_release_check.py` | Repo-eigene Releaseprüfung ist teilweise an Altpfade gebunden. | Als Entwicklungsprüfung behalten, sofern sie nur Repository-Metadaten validiert; Zielpfade aktualisieren. | `tools/`, `tests/` | keine Runtime-/Providerfunktion; Tree-Prüfung bleibt grün |
| ADR 0001 und ADR 0002 | Historische Entscheidungen enthalten normnahe Formulierungen und Altpfade. | Als Entscheidungshistorie behalten, aber nicht als Laufzeitautorität behandeln. | `docs/decisions/` | Bootstrap/Manifest referenzieren ADRs nicht als Regelquelle |

## Kanonische Konfliktauflösung

| Konflikt | Migrationsentscheidung |
|---|---|
| „Kern nie überschreibbar“ gegen expliziten Nutzervorrang | genau eine Autoritätshierarchie im Bootstrap |
| Projektdateien als Regeln gegen pauschal unvertrauenswürdige Dateiinhalte | ausdrücklich geladene Governance-Quellen von sonstigen Daten unterscheiden |
| unbekannter Auftrag lädt vollständigen Kontext | unbekannte oder mehrdeutige Klassifikation blockiert ohne Vollimport |
| Rollen in Kern, Rollenmodulen, Wrappern und `project.toml` | Manifest routet auf genau eine Rollenquelle |
| Toolkatalog und Providerpool als konkurrierende SSOTs | beide vollständig aus Governance entfernen |
| statische Installationspfade und Pfadsubstitution | relative Bundle-Struktur unverändert kopieren |
| freier Installationsprompt | deterministische Standardbibliotheks-CLI |
| private Regeln im versionierten Profilmodell | unveränderte lokale Datei mit Backup und Provenienz |

## Versionierte Legacy-Fingerprints

Nur exakte Bytes werden als bekannte alte Verdrahtung klassifiziert:

| Quelle | SHA-256 |
|---|---|
| `templates/AGENTS.md` | `255afc1679ff52c7349fca705420772e8aff6dd2109704b56c22db2970f1423e` |
| `templates/CLAUDE.md` | `d4c4e3ed6719af69ed3eef8c6a7de91a2355295f08f3ff983f6426d67198c305` |

Die historisch belegte ungültige Signatur
`@~/agent-governance/adapters/AGENTS.md` ist eine exakte Regressionstest-Eingabe. Ihre
Erkennung belegt keine aktuelle aktive Installation. Weitere historische Varianten dürfen
nur mit exaktem Repository-Commit und Blob- beziehungsweise Inhaltshash aufgenommen werden.

## Zielprüfungen aus der Migration

- `GOVERNANCE.md` ist die einzige Bootstrap-Quelle und bleibt höchstens 8 KiB groß.
- Manifestpfade, Trigger, Abhängigkeiten und Rollenpfade sind geschlossen und azyklisch.
- Regel-IDs sind eindeutig; ID- und Absatzduplikate werden mechanisch erkannt.
- Kein Trigger lädt pauschal alle Module.
- Harness-Einstiegspunkte sind byte-identisch mit `GOVERNANCE.md`.
- Repository- und simulierte Installationslinks lösen relativ auf.
- Legacy-Klassifikation nutzt ausschließlich belegte Bytes oder Managed-Marker.
- Unbekannte Inhalte bleiben unverändert erhalten; exakte Duplikate werden nur hashbasiert
  dedupliziert.
- Backup, Staging, atomare Aktivierung, Idempotenz und vollständiger Rollback werden geprüft.
- Manifest und aktive Governance enthalten keine operative Control-Plane- oder Providerlogik.
