# ADR 0006 — Socket.dev als externe, nicht-autoritative Security-Evidence

> **Historische Evidenz - nicht normativ.** Diese Architekturbegründung wird vom aktuellen
> Governance-Bundle nicht geladen. Sie beschreibt Entscheidungen zu Supply-Chain-Prüfschicht
> und externer Index-Freshness und ist keine ausführbare Anleitung.

- Status: angenommen
- Datum: 2026-09-26

## Kontext

Das Repository soll Socket.dev als externe Supply-Chain-Prüfschicht nutzen, ohne Socket zu einer
Runtime-Dependency, einer Release-Authority oder einer zweiten Dependency-SSOT zu machen. Die
beobachtete Drift zwischen dem real veröffentlichten npm-Paketstand und der öffentlichen
Socket-Paketansicht muss diagnostizierbar sein, ohne einen korrekt veröffentlichten Release
rückwirkend zu invalidieren.

## Entscheidung

Die bestehende Socket-GitHub-App (`socket-security`, Check `Socket Security: Project Report`)
wird unverändert als einzige Socket-Integration weiterverwendet. Es wird keine zweite
Scanner-, Dependency- oder Security-Authority eingeführt und keine Socket-GitHub-Action oder
-CLI zusätzlich integriert. Daher gibt es keine ausführbare Socket-Komponente, die immutable
gepinnt werden müsste; der kontrollierte Update-Pfad (immutable Pin N → Update-PR → Gates →
Pin N+1) entfällt folgerichtig.

Eine minimale Root-`socket.yml` (Schema `version: 2`) begrenzt die Socket-Ingestion auf die
veröffentlichten Root-Manifeste `package.json` und `package-lock.json`. Das e2e-Testfixture
`tests/e2e/package.json` ist kein produktives Manifest und wird nicht ingestiert.

Die Freshness der externen Socket-Projektion wird über einen read-only, deterministischen
Vergleich klassifiziert: `tools/socket_freshness.py` liest die autoritative npm-Version aus
`dist-tags.latest` und die von Socket bekannten Versionen über die offizielle API
`GET /v1/orgs/{org_slug}/purl/versions/{purl}` (Token-Scope `packages:list`, Least Privilege,
begrenzte Retries). Die Klassifikation ist `CURRENT | STALE | UNAVAILABLE`.

Der zugehörige Workflow `.github/workflows/socket-freshness.yml` läuft nur auf
`workflow_dispatch` und einem wöchentlichen `schedule`, niemals als Blocking-Gate eines
Release-Pfads. Jede Klassifikation verlässt den Job mit Exit 0; der Token wird ausschließlich
über den Secret Store (`SOCKET_SECURITY_API_KEY`) als Step-Env eingebunden.

## Authority- und Freshness-Vertrag

```text
npm dist-tags.latest == veröffentlichte Version
AND Socket zeigt älteren Stand
-> SOCKET_FRESHNESS=STALE   (Projektion, niemals Release-Fehler)
```

- `VERSION`/`package.json` am veröffentlichten Stand, der signierte GitHub-Release/Tag,
  npm `dist-tags.latest` sowie npm Integrity/Signatur/Provenance-Readbacks bleiben
  Release- und Versions-Authority.
- Socket ist ausschließlich externe Security-Evidence; seine öffentliche Paketansicht und
  der GitHub-App-Projektreport werden getrennt behandelt.
- Ein dauerhaft veralteter Socket-Index führt zu Diagnose und Evidenz, niemals zu blindem
  Re-Publish oder Dist-Tag-Mutation.

## Folgen

- Socket erzeugt keine Runtime-Dependency und keine zweite Dependency-SSOT.
- Der Release-Pfad bleibt unverändert; Socket-Index-Lag blockiert keinen Release.
- Die Drift ist deterministisch diagnostizierbar und wird kontrolliert überwacht.

## Verworfene Alternativen

- Eine zusätzliche Socket-GitHub-Action oder -CLI wurde wegen Redundanz ohne nachgewiesene
  Lücke verworfen.
- Ein HTML-Scraping der öffentlichen Socket-Paketansicht wurde wegen fehlender Stabilität
  und fehlender offizieller Schnittstellen-Garantie verworfen.
- Ein blockierender Socket-Freshness-Check im Release-Pfad wurde verworfen, weil ohne
  dokumentierte Freshness-SLA ein externer Index-Lag keinen erfolgreichen Publish
  rückwirkend invalidieren darf.
