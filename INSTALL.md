# Installationsgrenze

> **Version:** siehe [`VERSION`](VERSION)

Diese Datei ist das Boundary- und Verantwortungsdokument für Installation und Betrieb. Sie ist
keine zweite Installationsanleitung. Der einzige ausführbare Installationsvertrag dieses
Repositorys ist [`Installation.bootstrap.prompt.md`](Installation.bootstrap.prompt.md); der
Mitarbeiterfluss steht im [Schnellstart der README](README.md#schnellstart).

Die normative Governance unter `bundle/` installiert, provisioniert, migriert, sichert,
restauriert oder deployt selbst nichts. Der Bootstrap ist ein einmaliger Distributionsconsumer:
Ein Agent führt ihn nur auf einem konkret autorisierten Zielsystem aus, erkennt dort Harness und
Installationszustand, sichert betroffene Ziele, materialisiert den veröffentlichten Release,
bindet Enforcement und verifiziert eine frische Session. Er ist weder Updater noch Daemon,
Package Manager, Deploymentwerkzeug oder Control Plane.

Das Repository liefert dafür die öffentliche Distribution, den generischen Vertrag, isolierte
Referenzfixtures, Tests, Providerintegration und Upstream-Provenienz. Produktive Benutzerregeln,
Harnesskonfigurationen und Authdaten bleiben Daten des Zielhosts und gehören nicht in Repository
oder Releaseartefakte. Bei unklarer Autorisierung, nicht verlustfrei zuordenbaren Regeln,
Pfadkonflikten oder fehlgeschlagener Verifikation stoppt der Bootstrap fail-closed oder stellt den
verifizierten Ausgangszustand wieder her.

Version 0.6.0 enthält dafür einen transaktionalen CLI-Consumer. Seine Zustandsmaschine,
Codex-Bindung, Exit-Codes und Recoverygrenzen sind nicht normativ in
[`docs/installer-architecture.md`](docs/installer-architecture.md) beschrieben. Produktiv
unterstützt ist ausschließlich Codex; andere Harnesses stoppen vor jeder Mutation. Die CLI ändert
keine MCP-Konfiguration und erweitert keine Auto-Approvals.

Serverdeployment, Azure-Ressourcen, Fleet-Orchestrierung, Telemetrie, Hintergrundupdates,
Credential Services und Änderungen fremder Systeme liegen außerhalb dieser Verantwortung.
