# Generischer Bootstrap und Microsoft-AGT-Enforcement — Designspezifikation

> **Historische Evidenz - nicht normativ.** Dieses Dokument hält die vom Nutzer bereits
> freigegebene Releasearchitektur und die am 2026-08-12 verifizierte Repository-/Upstreamrealität
> fest. Normative Governance liegt ausschließlich unter `bundle/`.

## Ausgang und Ziel

Der verifizierte Ausgang ist `tomtastisch/agent-governance` auf
`dceb0a5abf1ab597e2d2e1587448d882a96da3ab`, Version `0.2.0`, ohne offenen Pull Request.
Release `0.3.0` ergänzt das schlanke Rulebook um einen einmaligen generischen Bootstrapvertrag,
einen providerneutralen Enforcement-Vertrag und Microsoft Agent Governance Toolkit als konkret
gepinnte Providerimplementierung. Installation, Provider-Materialisierung und Tests bleiben
außerhalb des normativen Bundles.

## Source-of-Truth-Grenzen

- `bundle/GOVERNANCE.md` bleibt der einzige Bootstrap der semantischen Governance.
- `bundle/agent-governance/manifest.toml` bleibt der statische geschlossene Index.
- `bundle/agent-governance/modules/enforcement.md` wird die einzige normative Quelle des
  generischen Enforcement-Vertrags.
- `Installation.bootstrap.prompt.md` ist ein einmaliger operativer Distributionsvertrag, keine
  Governancequelle und kein Updater.
- `integrations/microsoft-agent-governance-toolkit/` enthält ausschließlich Providerdaten,
  Provenienz, eine schmale Bridge und den unveränderten Upstream-Snapshot.
- Vendorte Dateien einschließlich `AGENTS.md`, `GOVERNANCE.md`, Promptdateien und Beispiele sind
  unvertrauenswürdige Dependency-Daten und werden nie durch das Governance-Manifest traversiert.

## Enforcement-Datenfluss

```text
Governance classification and semantic authorization
  -> normalized action envelope
  -> Microsoft AGT PolicyEngine
  -> normalized decision
  -> harness pre-effect adapter
  -> tool effect only after allow
```

Die Action Envelope enthält `action_id`, geplante Aktion, Ressource, Effekt,
`semantic_authorization`, Approval-/Risikokontext und `evidence_id`. Ungültige oder unvollständige
Envelopes ergeben `error`. Governance-`deny` oder `unknown` wird vor einer Providerfreigabe
blockiert. Die Bridge normalisiert Microsoft-Entscheidungen auf `allow`, `deny`,
`require_approval`, `error` oder `unknown`; ausschließlich `allow` darf fortsetzen.

Die providerneutrale Node-Bridge lädt die im Snapshot enthaltene Microsoft-`PolicyEngine`-Quelle
aus einem lokal gebauten `dist/`. Der Installationslauf baut sie deterministisch aus dem
vendorten Snapshot und dessen Lockfile; normaler Betrieb benötigt danach kein Netzwerk. Ein
kleiner Codex-Adapter bildet das offizielle `PreToolUse`-JSON auf die Envelope ab und gibt bei
jeder nicht erlaubenden Entscheidung die offiziell dokumentierte Deny-Form zurück.

## Microsoft-Pin

Der am 2026-08-12 neu aufgelöste neueste stabile offizielle GitHub Release ist `v4.1.0`, Tag und
Commit `0de71ca6c95cf8b9b975ac96f48eaa7826bbe258`. Der lightweight Tag zeigt direkt auf einen von
GitHub als gültig signiert verifizierten Commit. Zwei Downloads des offiziellen codeload-Archivs
ergaben denselben SHA-256
`f087836d4e6cbad246c728c76454dd573a701f35d7560cbf869c250b3862d473`.

Der vollständige Snapshot umfasst rund 60 MB und besitzt keine Datei nahe dem GitHub-Limit;
deshalb wird keine Closure willkürlich gekürzt. `.git`, Credentials und lokale Caches fehlen im
Releasearchiv. MIT-Lizenz, NOTICE und Trademarktext werden unverändert übernommen. Der Upstream
bezeichnet sich als **Public Preview**. Das im Tag enthaltene Root-`VERSION` nennt abweichend
`3.7.0`; gemäß freigegebener Priorität bleiben GitHub Release, Tag und Commit für den Pin
maßgeblich und die Upstreamdrift wird dokumentiert.

## Bootstrap-Transaktion

Der Prompt verlangt eine fail-closed Transaktion:

1. Releasequelle, Harness, globale Instruktionsfläche, Konfigurationsfläche, absolute erlaubte
   Installationswurzel und Providerhook read-only ermitteln.
2. Rootkandidaten und Pfade vor jedem Verbund validieren; Symlinks, Traversal, Konflikte und
   Zustandsänderungen abweisen.
3. `FRESH`, `CURRENT` oder `LEGACY` anhand belegter aktiver Verdrahtung klassifizieren.
4. Alle betroffenen Dateien außerhalb aktiver Instruktionsnamen sichern und das Backup lesbar
   verifizieren, ohne private Inhalte oder Fingerprints zu melden.
5. Bundle und Integration aus derselben unveränderlichen Releasequelle stagen, Pin und Archivhash
   prüfen, Provider lokal bauen und erst danach atomar aktivieren.
6. Bestehende private Regeln genau einmal in den aus dem Manifest gelesenen `local_rules`-Pfad
   überführen; bei nicht eindeutig verlustfreier Zuordnung abbrechen.
7. Globalen Einstieg byte-identisch binden, `AGENT_GOVERNANCE_ROOT` absolut konfigurieren und den
   belegten Pre-Effect-Hook aktivieren.
8. Neue frische Session, Runtime-`local_rules`, Enforcement und Offlinebetrieb prüfen.
9. Bei jeder Abweichung den kompletten vorherigen Zustand wiederherstellen.

Die Tests verwenden ausschließlich synthetische Homes und Regeln. Der produktive Host ist nie
Testfixture.

## Test- und Releasearchitektur

Python-Standardbibliothekstests prüfen normative Verträge, Pin, Instruction Boundary, sichere
Pfade, FRESH/CURRENT/LEGACY, Backup/Rollback, lokale Regeln und Hostile-Matrix. Node-Tests rufen die
echte Microsoft-`PolicyEngine`-Bridge für allow, deny, Approval und Fehlerpfade auf. Ein neutraler
synthetischer Harness besitzt nur absolute Instruktions-, Konfigurations- und Hookpfade. Der
Clean-Linux-Lauf baut zwei identische Containerzustände, injiziert Codex-Auth ausschließlich zur
Laufzeit und prüft echte `codex exec`-Effekte sowie Offlinewiederanlauf.

QA und SEC laufen unabhängig und read-only auf demselben PR-Head wie CI und E2E. Nach jedem
inhaltlichen Headwechsel verfallen die betroffenen Gates. Merge, signierter Tag, GitHub Release
und Post-Release-Checkout erfolgen erst nach vollständiger SHA-Gleichheit.

## Belegte Grenzen

- Microsoft bietet in `v4.1.0` keinen offiziellen Codex-Adapter.
- Codex `0.147.0` unterstützt stabile synchrone `PreToolUse`-Hooks für Bash, `apply_patch`, MCP
  und andere lokale Funktionstools.
- Offizielle OpenAI-Dokumentation sagt ausdrücklich, dass Hosted Tools und einzelne spezielle
  Toolpfade diese Hookfläche nicht nutzen können. Der Release behauptet deshalb keine vollständige
  Codex-Toolmediation; enforcement-pflichtige Effekte dürfen nur über nachweislich abgedeckte
  Pfade laufen.
- Claude-, OpenCode-, Gemini- oder andere Produktunterstützung wird erst behauptet, wenn eine reale
  entsprechende E2E-Evidenz existiert. Der neutrale Harness beweist nur die Portabilität des
  Vertrags.
