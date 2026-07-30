# Architektur

### ARC-001 — Eine autoritative Quelle

Jede fachliche Regel, Konfiguration und Zustandsdefinition besitzt genau einen autoritativen
Ort. Andere Dateien verweisen auf diese Quelle, statt denselben Inhalt zu kopieren oder
abgewandelt neu zu formulieren. Entscheidungshistorie und beschreibende Dokumentation sind
keine parallelen Laufzeitverträge.

### ARC-002 — Verantwortungsgrenzen

Komponenten werden nach genau einer fachlichen Verantwortung geschnitten. Governance
definiert Invarianten und Arbeitsverträge; Installation materialisiert das Bundle; operative
Identität, Providerauflösung, Toolbetrieb, Deployment und Plattformsteuerung bleiben außerhalb
dieser Grenze.

### ARC-003 — Portable Schnittstellen

Bundle-interne Schnittstellen verwenden relative, installationsstabile Pfade und explizite
Schemen. Externe Formate und APIs werden an schmalen Grenzen validiert. Implementierungsdetails
eines Harnesses, Betriebssystems oder Providers dürfen keine normative Regel verändern.

### ARC-004 — Entscheidung vor Bestand

Bestehende Implementierung ist Evidenz für den Ist-Zustand, aber keine höhere Wahrheit als
eine ausdrücklich korrigierende Architekturentscheidung. Migration bewahrt gültige fachliche
Regeln und Nutzerdaten; Redundanz, Widerspruch und veraltete Kopplung werden nicht allein aus
Kompatibilitätsgründen fortgeführt.

## Architekturprüfung

Architekturentscheidungen belegen Annahmen und Gegenhypothesen nach
[EVD-003](evidence.md#evd-003--falsifizierbare-hypothesen). Neue Quellen werden gegen
[ARC-001](#arc-001--eine-autoritative-quelle) geprüft, bevor sie als dauerhaftes Artefakt
aufgenommen werden.
