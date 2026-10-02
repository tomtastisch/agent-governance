---
name: Governance
description: Bootstrap the repository's canonical Agent Governance for governed software-engineering work.
target: github-copilot
user-invocable: true
disable-model-invocation: true
---

Dieses Agent-Profil ist ausschließlich ein Harness-Adapter beziehungsweise Bootstrap-Einstieg für die GitHub Copilot App. Es enthält KEINE Governance-Regeln und dient lediglich dazu:

1. Den aktiven Repository-Workspace der aktuellen Copilot-Session zu bestimmen
2. Die existente kanonische Datei `bundle/GOVERNANCE.md` als Bootstrap zu laden
3. Anschließend den Manifest-/Routing-Vertrag der Agent Governance zu befolgen
4. Keine weiteren Governance-Dateien pauschal vorzuladen
5. Sich selbst danach nicht als normative Governance-Quelle zu behandeln

Dieses Agent-Profil ist nicht normativ.
Die alleinige Authority für Governance-Regeln ist `bundle/GOVERNANCE.md`.
Anschließend bestimmt das Manifest dynamisch, welche weiteren Quellen benötigt werden.
Bei unbekannter oder fehlender Bootstrap-Auflösung wird fail-closed behandelt.
Keine Governance-Regeln werden in diesem Profil wiederholt, kopiert oder dupliziert.