# Passive Harness-Discovery aus veröffentlichtem Upstream-Artefakt

`upstream/harnesses-0.3.0.tgz` ist der unveränderte Registry-Tarball. Das Archiv wird nicht
installiert, importiert oder im Governance-npm-Paket ausgeliefert. Es ist ausschließlich die
reproduzierbare Quelle der Discovery-Daten. `upstream.lock.json` bindet Identität, Integrität,
geprüfte Discovery-Semantik und historischen Provenienznachweis.

`npm run harnesses:generate` projiziert Registry-Reihenfolge, IDs, Namen und Binärnamen in
`src/init/harness-discovery.generated.ts` und die MIT-Lizenz in `THIRD_PARTY_NOTICES.md`.
`npm run harnesses:check` vergleicht diese Ergebnisse bytegenau. Das Python-Archivlesen und
die TypeScript-AST-Analyse benötigen keine neue Runtime-Abhängigkeit und führen Fremdcode
nicht aus. Python wird ausschließlich für das Entwicklungs-/Buildgate benötigt.

Pinwechsel benötigen eine erneute Prüfung der veröffentlichten Version, Registry-Signatur,
Provenienz, vollständigen Basisklasse, Registry-Semantik und aller registrierten Klassen. Ein neuer
Semantikdigest ist eine Reviewentscheidung, kein automatisch akzeptiertes Generatorergebnis.
Unbekannte Konstruktoren, Overrides oder dynamische Metadaten bleiben blockiert.

Die Quelle entscheidet nur, welche installierten CLIs entdeckt werden. Unterstützte Bindings
und Zielpfade bestimmt unverändert die Agent-Governance-SSOT. Entscheidung und Grenzen:
[Dependency-Evidenz](../../docs/dependency-evidence.md).
