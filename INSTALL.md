# Installationsstatus

> **Version:** siehe [`VERSION`](VERSION)

Für den kanonischen Bundle-Stand existiert noch kein freigegebener Installer und keine
implementierte Nutzerregelmigration. Diese Funktionen gehören zu Cluster 4 und wurden in der
aktuellen Cluster-3-Konsolidierung nicht begonnen.

`bundle/GOVERNANCE.md` ist die einzige im Repository gepflegte Bootstrap-Inhaltsquelle. Künftige
installierte Einstiegspunkte müssen byte-identische Kopien dieser Quelle sein; eigene
harness-spezifische Inhaltsquellen sind nicht zulässig.

Dieses Dokument ist kein Installationsskript und kein Agentenprompt. Es autorisiert weder das
Kopieren in Benutzerverzeichnisse noch Tool-, Plugin-, MCP-, Provider- oder Runtime-Änderungen.
Bis eine separat verifizierte Cluster-4-Implementierung vorliegt, ist die Installation offen und
muss fail-closed behandelt werden.
