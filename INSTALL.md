# Installationsstatus

> **Version:** siehe [`VERSION`](VERSION)

Die folgenden Arbeiten sind in der aktuellen Cluster-3-Konsolidierung nicht begonnen:

- Cluster 4: Control-Plane-Kopplung entfernen und statische Tool-Allowlist erhalten.
- Cluster 5: deterministischen Installer implementieren.
- Cluster 6: verlustfreie Nutzerregelmigration mit Backup, Klassifikation, Aktivierung und
  Rollback durchführen.

Die enge Ignore-Regel für `profile/profile.md` bleibt bis zur vollständig verifizierten Behandlung
in Cluster 6 bestehen.

`bundle/GOVERNANCE.md` ist die einzige im Repository gepflegte Bootstrap-Inhaltsquelle. Künftige
installierte Einstiegspunkte müssen byte-identische Kopien dieser Quelle sein; eigene
harness-spezifische Inhaltsquellen sind nicht zulässig.

Dieses Dokument ist kein Installationsskript und kein Agentenprompt. Es autorisiert weder das
Kopieren in Benutzerverzeichnisse noch Tool-, Plugin-, MCP-, Provider- oder Runtime-Änderungen.
Bis eine separat verifizierte Cluster-5-Implementierung vorliegt, ist die Installation offen und
muss fail-closed behandelt werden. Eine Nutzerregelmigration bleibt bis zur separat verifizierten
Cluster-6-Implementierung ebenfalls offen.
