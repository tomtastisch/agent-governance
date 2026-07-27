# Agent-Governance

Harness-agnostisches Regelwerk für LLM-Entwicklungsagenten (Claude Code, Codex, weitere),
geschnitten nach hexagonalem Prinzip: ein Kern, definierte Ports, austauschbare Adapter,
genau eine Verdrahtungsstelle je Harness. SSOT: jede Regel steht genau einmal.

## Struktur

```
agent-governance/
├── core/
│   ├── core.md          # Kernregelwerk — harness-agnostisch, keine Pfade, keine Personendaten
│   ├── branch-tags.toml # Branch-/PR-Tags (SSOT): tag/name/description je Änderungstyp
│   ├── review-routing.toml # Reviewmatrix, Risikoschwellen und Pflichtchecks (SSOT)
│   └── roles/           # Rollenerweiterungen (nur im jeweiligen Rollenagenten laden)
│       ├── ak.md        # Architektur & Kontext (read-only Analyse, Drift-Audits)
│       ├── st.md        # Scope-Triage neuer Befunde (Issue-Dokumentation)
│       ├── qa.md        # Diff-/Exact-Head-Review (Merge-Gate)
│       └── sec.md       # Sicherheits-Audit über Diff-Grenzen hinaus
├── adapters/            # je Harness genau eine Datei mit allen Bindings
│   ├── claude.md
│   └── codex.md
├── profile/
│   ├── profile.md       # nutzerspezifisch (nicht veröffentlichen, .gitignore)
│   └── profile.example.md
├── tools/
│   ├── tools.md         # Werkzeug-Katalog (SSOT): Beschreibung, Governance-Nutzen, Install-Weg
│   └── Brewfile         # deterministische CLI-Installation (brew bundle)
├── templates/           # kopierfertige Verdrahtungsdateien für die Harness-Homes
│   ├── README.md        # Zuordnungstabelle Vorlage → Zielort + Root-Pfad-Regeln
│   ├── CLAUDE.md        # → ~/.claude/CLAUDE.md
│   ├── AGENTS.md        # → ~/.codex/AGENTS.md
│   └── claude-agents/   # → ~/.claude/agents/ (Subagent-Wrapper AK/ST/QA/SEC)
├── tests/               # Konsistenz-/Drift-Tests + advisory Link-Check (Kern §9/§11/§13)
├── review_routing/      # read-only Probe, Vorplanung und Exact-Head-Validierung
├── docs/decisions/      # Entscheidungssätze (ADR): Begründung struktureller Änderungen
├── .github/workflows/   # CI-Pipeline (ci.yml)
└── INSTALL.md           # gehärteter Install-Prompt (ein Prompt für alle Harnesse)
```

Die Verdrahtungsdateien selbst liegen bewusst nicht aktiv im Repo, sondern im jeweiligen
Harness-Home (`~/.claude/`, `~/.codex/`) — nur dort werden sie automatisch geladen; im Repo
wären sie totes Duplikat (Drift-Quelle). `templates/` enthält die kopierfertigen Vorlagen.

## Port-Vertrag

Der Kern referenziert ausschließlich benannte Schlüssel; jeder Adapter MUSS sie definieren:

| Schlüssel | Bedeutung |
|---|---|
| `harness.name` | Name des Harness |
| `governance.root` | Wurzelpfad dieser Struktur (einzige Pfadangabe) |
| `roles.mechanism` | Wie ein sauberer, unabhängiger Rollenkontext erzeugt wird |
| `review.primary` | Primärer unabhängiger Reviewer für das Merge-Gate |
| `effort.mapping` | Stufen der Arbeitsintensität und ihre Zuordnung |
| `net.policy` | Egress-Regeln inkl. freigegebener CI-Abfragen |
| `machine.notes` | Maschinen-/Harness-Besonderheiten (z. B. Commit-Signierung) |
| `tools.install` | Installationsweg für den Werkzeug-Katalog `tools/tools.md` |
| `native.enforced` | Kernregeln, die der Harness bereits nativ erzwingt |

Das Profil liefert `user`, `stack`, `language`, optional `palette`, `prefs`.

## Übernahme (für Dritte)

Schnellster Weg: den Install-Prompt aus [INSTALL.md](INSTALL.md) unverändert an den Agenten des
Ziel-Harness geben — ein Prompt für alle Harnesse; er erkennt den Harness, legt die Dateien laut
[templates/README.md](templates/README.md) ab, substituiert abweichende Root-Pfade und
verifiziert fail-closed. Manuell:

1. Verzeichnis nach `~/agent-governance` klonen/kopieren (abweichendes Root: Pfad-Liste in
   `templates/README.md`, Abschnitt „Root-Pfad" beachten).
2. `profile/profile.example.md` → `profile/profile.md` kopieren und ausfüllen.
3. Werkzeuge: `brew bundle --file=tools/Brewfile` installiert nur die Pflichtwerkzeuge (bzw.
   Paketmanager des Systems); Katalog `tools/tools.md` durchgehen — optional empfohlene erst nach
   Freigabe (Kern §19), CLI-seitig über `tools/Brewfile.optional`.
4. Harness verdrahten (genau eine Stelle, Vorlagen in `templates/`):
   - Claude Code: `templates/CLAUDE.md` → `~/.claude/CLAUDE.md` kopieren und
     `templates/claude-agents/*` → `~/.claude/agents/` (Subagent-Wrapper AK/ST/QA/SEC).
   - Codex: `templates/AGENTS.md` → `~/.codex/AGENTS.md` kopieren.
   - Anderer Harness: neuen Adapter nach dem Port-Vertrag schreiben und eine analoge
     Einstiegsdatei im Home des Harness anlegen; der Kern bleibt unverändert.
5. Erweitern statt ändern: neue Rollen als Datei unter `core/roles/` plus Zeile in Kern §6;
   neue Harnesse als Adapter. Der Kern ändert sich nur, wenn sich eine Regel selbst ändert.

## Deterministisches Review-Routing

Die einzige normative Routingmatrix, sämtliche Risikoschwellen, Pfadmarker und erwarteten
Pflichtchecks stehen in `core/review-routing.toml`. Kern, Rollen, Adapter und Vorlagen wiederholen
keine Matrixzellen. Der unveränderliche Prosa-Vertrag steht in Kern §16; die Begründung und
verworfenen Alternativen in `docs/decisions/0003-review-routing.md`.

Das stdlib-only Paket `review_routing` trennt drei read-only Schritte:

- `probe` erhebt technische GitHub-/Copilot-Signale und klassifiziert
  `copilot_usable` fail-closed;
- `route` erstellt den konservativen Task-5-Vorplan aus aktuellem PR-State, Basispolicy und
  vollständigem lokalem Git-Diff;
- `validate` ist der Task-6-Validator: Er erhebt PR-State, Basispolicy, Diff, Probe und
  Reviewer-Verfügbarkeit erneut und prüft die Exact-Head-Evidenz.

Eine `route`-Ausgabe ist stets `decision_stage = preliminary`, nicht gate-fähig und keine
Dispatch-Freigabe. Task 5 liefert ausschließlich diesen Vorplan; erst Task 6 berechnet im
Validator die evidenzgebundene Reviewer-Menge neu.
Auch dessen lokale Ausgabe veröffentlicht keinen GitHub-Check und ist ohne die externe
Publisher-/Ruleset-Grenze aus Issue #3 keine serverseitige Merge-Evidenz.

### CLI-Aufrufe

Die CLI besitzt einen geschlossenen JSON-Vertrag und keinen interaktiven Modus. Manuelle und
automatische Kontexte werden ausdrücklich unterschieden:

```bash
python3 -m review_routing probe \
  --repo OWNER/REPO \
  --review-mode manual \
  --requester USER \
  --json

python3 -m review_routing probe \
  --repo OWNER/REPO \
  --review-mode automatic \
  --pull-request NUMBER \
  --json
```

`route` lädt den PR-State selbst. Bei `manual` ist `--requester` Pflicht; bei `automatic` ist die
Option verboten und der PR-Autor wird über GitHub bestimmt:

```bash
python3 -m review_routing route \
  --repo OWNER/REPO \
  --pull-request NUMBER \
  --review-mode manual \
  --requester USER \
  --purpose final_exact_head \
  --repo-path /absolute/path/to/checkout \
  --json

python3 -m review_routing route \
  --repo OWNER/REPO \
  --pull-request NUMBER \
  --review-mode automatic \
  --purpose checkpoint \
  --repo-path /absolute/path/to/checkout \
  --json
```

`validate` liest den Task-5-Vorplan und einen geschlossenen Evidenzsnapshot, rekonstruiert den
aktuellen Kontext und bewertet den Exact Head erneut:

```bash
python3 -m review_routing validate \
  --route-file ROUTE.json \
  --evidence-file EVIDENCE.json \
  --repo OWNER/REPO \
  --pull-request NUMBER \
  --review-mode manual \
  --requester USER \
  --repo-path /absolute/path/to/checkout \
  --json
```

Optionale Kontextargumente sind `--organization`, `--enterprise`, `--cost-center` und die
nicht vertrauenswürdige Referenz `--capability-reference`. Es existieren bewusst keine
CLI-Schalter für Billing, Budget, Trust, Issuer, Runtime-Digest oder erwartete Digests.
Reviewer-Verfügbarkeit, Runtime-Trust und Digest-Pins sind ausschließlich programmatisch
injizierbar.

### GitHub-Rechte und Kontextgrenzen

Die bestehende `gh`-Anmeldung muss mindestens den authentifizierten Benutzer sowie
Repository-, Pull-Request-, Review- und Check-Metadaten lesen dürfen. Der persönliche
AI-Credit-/Premium-Usage-Zugriff erfordert bei GitHub `Plan: read`; Organisationskontexte
erfordern zusätzlich belegbaren Zugriff auf die Copilot-Sitz- und Billing-Usage-Endpunkte der
Organisation. Fehlende Rechte werden als `permission_denied` klassifiziert und ergeben
`copilot_usable = false`, nie einen optimistischen Versuch.

Der manuelle Kontext bindet den Requester, der automatische Kontext den API-erhobenen PR-Autor.
Organisationsmitgliedschaft oder ein Seat-`404` beweist keinen Billing-Principal.
Enterprise- und Cost-Center-Zuordnungen sind ohne eine dafür autoritative API-/Konfigurationsquelle
`unknown`. Usage und ein historisches Review allein sind keine positive Capability.

Positive Capability benötigt ein zeitlich gültiges Operator-Artefakt, dessen kanonischer Digest
außerhalb der CLI durch eine Publisher-App oder installierte Konfiguration gepinnt ist. Ein
Source-Checkout besitzt keinen solchen Pin und bleibt `runtime_trust = development`; er kann
weder `installed` noch `gate_eligible = true` per Flag behaupten.

### Basispolicy, Bootstrap und Issue #3

`route` und `validate` lesen `core/review-routing.toml` aus dem API-erhobenen vollständigen
Base-SHA, nicht aus Arbeitsbaum oder PR-Head. Eine Kandidatenänderung kann das eigene Gate damit
nicht abschwächen. Für PR #5 fehlt diese Policy einmalig am Base-Commit; der fachliche Befund
lautet `trusted_base_policy_missing`. Die öffentliche CLI gibt ihn absichtlich nur als
sanitisiertes `invalid_input` mit Exitcode `31` aus und erzeugt keinen positiven GateResult.
Die Bootstrap-Freigabe von PR #5 erfolgt nach dem bisherigen Kernvertrag durch unabhängige
Exact-Head-Reviews und die ausdrückliche Mergeentscheidung des Nutzers. Erst ein Folge-PR kann
den Task-6-Vertrag gegen eine vorhandene Basispolicy vollständig ausführen.

Issue #3 bleibt die Grenze für den autoritativen Publisher, dessen Ledger, GitHub-App,
Required-Check-Regel, erwarteten Base-Ref und Branch Protection beziehungsweise Ruleset.
Bis diese Grenze umgesetzt ist, sind lokale Ergebnisse Diagnoseevidenz und die Governance
nicht serverseitig vollständig erzwungen.

### Live-Positivtest nach Behebung des Billing-Problems

Der Live-Positivtest beginnt erst nach ausdrücklicher Bestätigung, dass das Billing-Problem
behoben ist:

1. Exact Head, Repository und Pull Request read-only neu feststellen.
2. Für genau diesen GitHub-Copilot-Review eine explizite Einzelfreigabe des Nutzers einholen.
3. Den kostenpflichtigen Review außerhalb von `probe`, `route` und `validate` einmal auslösen.
4. Ein abgeschlossenes `COMMENTED`-Review auf demselben Head samt Review-ID, Bot-Identität,
   Zeitpunkt, Dateiabdeckung und null offenen Findings read-only belegen.
5. Das Ergebnis über ein extern digest-gepinntes `completed_review_context` revalidieren und den
   Probe-/Routing-/Validierungspfad erneut ausführen. Ändert sich der Head, beginnt die Evidenzkette
   von vorn.
6. GitHub-CI, alle policygeforderten Reviewer und null ungelöste Threads am identischen Head
   separat nachweisen.

Ohne explizite Einzelfreigabe findet kein bezahlter Dispatch statt. Ist Copilot nicht verwendbar,
kommt ausschließlich der berechnete QA-/SEC-Pfad zum Einsatz; es gibt keinen Retry.

## Konsistenz-Sicherung (CI)

Die SSOT- und Driftfreiheits-Zusagen (Kern §9) sind mechanisch überprüft, nicht nur Konvention —
Governance-Artefakte müssen real greifen (§9, §11). `tests/test_governance.py` (stdlib-`unittest`,
ohne Fremdabhängigkeiten) fällt aus, sobald eine Quelle gegen eine andere driftet:

- jede im Kern genutzte `[BINDING:*]`/`[PROFILE:*]` ist im Port-Vertrag bzw. Profil deklariert und
  in jedem Adapter realisiert (kein nicht deklarierter oder unrealisierter Port);
- jeder `§`-Verweis in Kern, Rollen und Katalog zeigt auf einen existierenden Abschnitt;
- alle Rollen (AK/ST/QA/SEC) haben Erweiterung und Subagent-Wrapper und stehen in §6;
- Kern, Rollen, Adapter, Vorlagen und Betriebsdokumentation verweisen auf
  `core/review-routing.toml`, ohne deren Matrix zu duplizieren;
- der Kern bleibt pfadfrei (Root-Pfad nur in Adaptern/Templates);
- `tools/tools.md` bleibt ohne Handpflege synchron: jedes `Brewfile`-Paket ist dort dokumentiert,
  jeder Werkzeug-Eintrag trägt Freigabe-Kennzeichnung und Installationsblock, kein Verweis auf das
  entfernte alte Manifest bleibt zurück;
- `core/branch-tags.toml` ist wohlgeformt und git-ref-sicher: Tags eindeutig, Zeichensatz
  ref-tauglich, `tag`/`name`/`description` je Eintrag gesetzt, `default` verweist auf einen
  existierenden Tag, der Kern verweist auf die Datei, und der abgelöste Agenten-Präfix-Port taucht
  in Kern, Port-Vertrag und Adaptern nicht mehr auf (nutzt stdlib-`tomllib`, Python 3.11+; auf
  älteren Interpretern überspringt sich nur dieser Block, CI pinnt 3.11 und erzwingt ihn).

`tests/check_links.py` prüft zusätzlich die Erreichbarkeit der Katalog-Links — netzabhängig und
daher advisory (§13). Die Pipeline (`.github/workflows/ci.yml`) trennt beides klar: blockierende
Konsistenz-Tests, advisory Link-Check. Lokal: `python3 -m unittest discover -s tests`.

## Prinzipien der Struktur selbst

- Drift-frei: Kern existiert genau einmal; Harnesse referenzieren, statt zu kopieren.
- Tokensparend: Rollenerweiterungen werden nur im jeweiligen Rollenagenten geladen;
  Abschluss-/Protokollformate sind auf substanzielle Aufgaben begrenzt (Kern §8).
- Nativ erzwungene Harness-Regeln stehen trotzdem im Kern (§17), damit jeder Harness identisch
  arbeitet; Adapter kennzeichnen nur, was bereits nativ gilt.
