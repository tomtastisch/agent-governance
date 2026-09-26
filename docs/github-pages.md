# GitHub Pages: Projektion, Deployment und Search-Verifikation

Diese Referenz dokumentiert die statische öffentliche Website des Projekts als reine
Projektion der bestehenden Authorities. Sie ist keine zweite fachliche, Dokumentations-,
Versions- oder Command-Authority.

## Architektur

```text
Repository / Package / SSOT
        ↓
tools/site_build.py (deterministischer Build + Verifikation)
        ↓
_site/ (statische HTML-Ausgabe, gitignored)
        ↓
GitHub Pages (https://tomtastisch.github.io/agent-governance/)
```

- Quelle: `site/` (HTML-Templates mit `{{TOKEN}}`-Platzhaltern, `robots.txt`, CSS).
- Build: `tools/site_build.py build` leitet Version, Package-Name, Installationsweg,
  Repository-URL und Base-Path aus `VERSION` und `package.json` ab, ersetzt die Tokens,
  projiziert die Branding-Assets und erzeugt `sitemap.xml` deterministisch aus dem
  `site/`-Baum. Unbekannte oder unaufgelöste Tokens, fehlende Assets und Nicht-GitHub-
  Repository-URLs scheitern fail-closed.
- Verifikation: `tests/test_site.py` prüft Base-Path, Canonicals, Meta Descriptions,
  Sitemap, `robots.txt`, strukturierte Daten, interne Links, Branding-Assets und die
  Package-Grenze. Der Build mutiert keine npm-Runtime-Artefakte.
- Deployment: `.github/workflows/pages.yml` baut, verifiziert und deployt ausschließlich
  auf `main` über die offiziellen GitHub-Actions (`configure-pages`, `upload-pages-artifact`,
  `deploy-pages`) mit Least-Privilege-Berechtigungen (`contents: read`, `pages: write`,
  `id-token: write`). Ein fehlerhafter Build erzeugt kein Deployment.

## Suchmaschinen-Crawler

`robots.txt` erlaubt Search-Crawler explizit (`Allow: /`) und blockiert keine
`Disallow`-Regel. AI-Training-Crawler (z. B. `Google-Extended` für Gemini/Vertex AI) werden
fachlich getrennt behandelt und hier bewusst **nicht** über eine pauschale Regel gesteuert;
ob sie erlaubt werden, ist eine separate Entscheidung.

## Google Search Console

Die Site ist technisch für die Verifikation vorbereitet. Die eigentliche Property-Erstellung
und Verifikation ist eine **manuelle, kontogebundene Aktion** und wird nie während Build oder
Deployment ausgeführt.

1. Unter https://search.google.com/search-console/ die Property
   `https://tomtastisch.github.io/agent-governance/` (URL-Präfix) hinzufügen.
2. Einen der Verifikationswege wählen:
   - HTML-Datei: die von Google bereitgestellte Datei in `site/` ablegen und committen;
     sie wird beim Build nach `_site/` projiziert.
   - Meta-Tag: das bereitgestellte `<meta name="google-site-verification" ...>` in die
     relevanten `site/**/index.html`-Templates aufnehmen.
   - DNS-TXT: ausschließlich außerhalb des Repositorys (bei `tomtastisch.github.io` nicht
     anwendbar, da die DNS-Zone GitHub gehört — für ein Custom-Domain-Setup relevant).
3. Nach erfolgreicher Verifikation die Sitemap
   `https://tomtastisch.github.io/agent-governance/sitemap.xml` einreichen.

Es werden **keine** Verification-Werte, Accountdaten oder Secrets in dieses Repository
committet. Ein eventuell benötigter öffentlicher Verification-Wert (HTML-Datei oder
Meta-Tag-Inhalt) wird ausschließlich als öffentliche, von Google bereitgestellte Evidence
eingebracht.

## Bing Webmaster Tools

1. Unter https://www.bing.com/webmasters/ die Site `tomtastisch.github.io/agent-governance/`
   hinzufügen.
2. Verifikation über das Meta-Tag `<meta name="msvalidate.01" content="...">` in den
   Site-Templates oder über die XML-Datei `BingSiteAuth.xml` unter `site/`.
3. Optional IndexNow: Schlüsseldatei `<hex>.txt` unter `site/` ablegen (optionale,
   providerunabhängige Einreichung; kein zwingender Bestandteil der Erstumsetzung).

Wie bei Google wird die Verifikation manuell durchgeführt; keine Secrets im Repository.
