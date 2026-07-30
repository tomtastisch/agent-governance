# ADR 0003 — Kanonisches, harness-neutrales Governance-Bundle

- Status: angenommen
- Datum: 2026-07-30

## Kontext

Das bisherige Modell verteilt Governance auf Kern, Harness-Adapter, Bootstrap-Templates,
Rollenwrapper, Profil- und Installationsdateien. Die Quellen wiederholen und widersprechen
sich, verwenden installationsabhängige Pfade und vermischen normative Governance mit
operativen Plattform- und Providerzuständigkeiten.

## Entscheidung

Das auslieferbare Bundle erhält diese Struktur:

```text
bundle/
├── GOVERNANCE.md
└── agent-governance/
    ├── manifest.toml
    ├── modules/
    ├── roles/
    └── local/
        └── user-rules.example.md
```

`bundle/GOVERNANCE.md` ist die einzige Bootstrap-Quelle. Ein Installer kopiert ihre Bytes
unverändert unter den vom gewählten Harness erwarteten Einstiegspunktnamen. Nur der Dateiname
darf abweichen. Das Verzeichnis `agent-governance/` wird unverändert daneben installiert,
sodass alle Bundle-Verweise repository- und installationsrelativ auflösbar bleiben.

Harness-spezifische Governance-Adapter, Bootstrap-Varianten und Rollenwrapper entfallen.
Harness-Unterschiede sind ausschließlich Installationsmetadaten für Zielverzeichnis und
Einstiegspunktname. Ein benutzerdefinierter Harness erfordert beide Werte ausdrücklich.

`bundle/agent-governance/manifest.toml` ist ein statischer Bundle-Index. Es ordnet ausschließlich
geschlossene Trigger zu relativen Modulpfaden zu und darf optionale Modulabhängigkeiten sowie
Rollenpfade deklarieren. Es enthält keine Sessions, Laufzeitzustände, Provider,
Verfügbarkeiten, Queues, Leases, Delegationssteuerung oder dynamische Plattformlogik.
Unbekannte oder mehrdeutige Trigger laden nicht vorsorglich alle Module.

Normative Regeln werden genau einmal im Bootstrap oder einem Modul beziehungsweise Rollenmodul
definiert. Stabile Regel-IDs werden nur für mechanisch validierte, dateiübergreifend
referenzierte Regeln sowie zentrale Sicherheits- und Abschlussinvarianten vergeben. Andere
Absätze erhalten keine künstliche Einzel-ID.

Lokale Nutzerregeln liegen außerhalb der versionierten Normen. Die Migration behandelt nur
exakt belegte Legacy-Bytes oder eindeutig markierte Managed-Blöcke als alte
Governance-Verdrahtung. Jeder andere lesbare Inhalt bleibt unverändert erhalten. Vorhandene
Dateien werden gesichert; nicht deterministisch klassifizierbare Inhalte verhindern die
Aktivierung.

Operative Control-Plane-Zuständigkeiten gehören nicht in dieses Repository. Identity,
Authentifizierung, Provider- und Toolregistrierung, Gateways, Registry-Snapshots, Queue-,
Lease-, Workspace-, Deployment-, Update-, Aktivierungs-, Recovery- und Plattform-Auditbetrieb
werden weder vorausgesetzt noch implementiert. Providerneutrale Grundsätze wie Evidenzpflicht,
ausdrückliche Autorisierung, unabhängige Prüfung und Fail-closed-Verhalten dürfen als
Governance bestehen bleiben.

## Folgen

- Der Bootstrap bleibt kompakt und lädt nur durch geschlossene Trigger benötigte Module.
- Rollen besitzen jeweils genau eine normative Quelle.
- Installation und Migration werden durch eine nicht-interaktive, plattformübergreifende
  Standardbibliotheks-CLI ausgeführt; freie Agenteninterpretation beschreibt keinen zweiten
  Installationsweg.
- Symlinks, Inhalts- oder Pfadsubstitution sowie Verweise auf Dateien außerhalb des Bundles
  sind nicht erforderlich.
- Die [Migrationsmatrix](../audits/2026-07-30-source-migration.md) dokumentiert nur die
  Überführung der Altquellen; sie ist keine normative Quelle.

## Verworfene Alternativen

- Parallele Einstiegstexte je Harness wurden wegen unvermeidbarer Drift verworfen.
- Imports auf einen separaten Checkout wurden wegen fehlender Portabilität verworfen.
- Symlinks und Inhaltsmutation wurden wegen eingeschränkter Plattformkompatibilität und
  fehlender Byte-Identität verworfen.
- Ein Laufzeit- oder Providervertrag im Manifest wurde wegen der notwendigen Trennung von
  Governance und Control Plane verworfen.
