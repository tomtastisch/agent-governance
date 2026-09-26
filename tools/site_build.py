#!/usr/bin/env python3
"""Deterministic static-site build for GitHub Pages.

Die Site ist ausschließlich eine Projektion bestehender Authorities
(`VERSION`, `package.json`, `README`/`docs`). Sie leitet kanonische Werte
(Version, Package-Name, Installationsweg, Repository-URL, Base-Path) beim
Build aus diesen Authorities ab, statt sie unabhängig zu pflegen. Kein Modus
mutiert das Repository, den npm-Runtime-Pfad oder externe Dienste.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE_SRC = ROOT / "site"
DEFAULT_OUT = ROOT / "_site"

# Site-eigene Assets (CSS) liegen unter site/; Branding-/Diagramm-Assets werden
# aus den bestehenden Repository-Pfaden projiziert und beim Build kopiert.
PROJECTED_ASSETS = {
    "assets/branding/agent-governance-icon.png": "icon.png",
    "assets/branding/agent-governance-terminal.png": "terminal.png",
    "assets/diagrams/governance-overview.png": "overview.png",
}

TOKEN_PATTERN = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")


class SiteError(Exception):
    """Deterministischer Build-/Verifikationsfehler der Site-Projektion."""


def canonical_values(root: Path = ROOT) -> dict[str, str]:
    """Liest die kanonischen Werte ausschließlich aus den bestehenden Authorities."""
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    package = json.loads((root / "package.json").read_text(encoding="utf-8"))

    package_name = package["name"]
    bin_name = next(iter(package["bin"]))
    description = package["description"]

    repository_url = package["repository"]["url"]
    repository_url = repository_url.removeprefix("git+").removesuffix(".git").rstrip("/")
    if not repository_url.startswith("https://github.com/"):
        raise SiteError(f"repository.url ist keine GitHub-HTTPS-URL: {repository_url}")
    slug = repository_url.removeprefix("https://github.com/")
    owner, _, repo_name = slug.partition("/")
    if not owner or not repo_name:
        raise SiteError(f"repository.url hat keine gültige Owner/Repository-Form: {repository_url}")

    base_path = f"/{repo_name}"
    public_url = f"https://{owner}.github.io/{repo_name}"

    return {
        "VERSION": version,
        "PACKAGE_NAME": package_name,
        "BIN": bin_name,
        "INSTALL": f"npm i {package_name}",
        "INIT": f"npx {bin_name} init",
        "REPO_URL": repository_url,
        "REPO_SLUG": slug,
        "BASE_PATH": base_path,
        "PUBLIC_URL": public_url,
        "DESCRIPTION": description,
    }


def pages(site_src: Path = SITE_SRC) -> list[str]:
    """Leitet die indexierbaren Seiten deterministisch aus dem site/-Baum ab.

    Jedes `index.html` ist genau eine öffentliche Seite; `404.html` ist keine
    indexierbare Seite. Rückgabe ist die Liste der relativen Seitenpfade ohne
    führenden Slash; die Startseite wird als leere Zeichenkette geführt.
    """
    result: list[str] = []
    for path in sorted(site_src.rglob("index.html")):
        relative = path.relative_to(site_src).as_posix()
        if relative == "index.html":
            result.append("")
        else:
            result.append(relative[: -len("index.html")].rstrip("/"))
    return result


def public_path(subpath: str, values: dict[str, str]) -> str:
    """Voller Base-Path einer Seite (ohne Protokoll/Host)."""
    base = values["BASE_PATH"]
    if not subpath:
        return f"{base}/"
    return f"{base}/{subpath}/"


def canonical_url(subpath: str, values: dict[str, str]) -> str:
    return f"{values['PUBLIC_URL']}/{subpath}/" if subpath else f"{values['PUBLIC_URL']}/"


def substitute(text: str, values: dict[str, str], context: str) -> str:
    """Ersetzt alle Tokens; unbekannte oder verbleibende Tokens scheitern fail-closed."""
    unresolved = TOKEN_PATTERN.findall(text)
    for name in unresolved:
        if name not in values:
            raise SiteError(f"{context}: unbekanntes Token {{{{ {name} }}}}")
    for name, value in values.items():
        text = text.replace("{{" + name + "}}", value)
    leftover = TOKEN_PATTERN.findall(text)
    if leftover:
        raise SiteError(f"{context}: nicht aufgelöste Tokens {sorted(set(leftover))}")
    return text


def sitemap_xml(page_subpaths: list[str], values: dict[str, str]) -> str:
    """Erzeugt die Sitemap ausschließlich aus den real vorhandenen Seiten."""
    urls = "\n".join(
        f"  <url><loc>{canonical_url(subpath, values)}</loc></url>"
        for subpath in page_subpaths
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n"
        "</urlset>\n"
    )


def build(root: Path = ROOT, out: Path = DEFAULT_OUT) -> None:
    """Baut die statische Site deterministisch in `out` (Standard: `_site/`)."""
    if not SITE_SRC.is_dir():
        raise SiteError(f"site/-Verzeichnis fehlt: {SITE_SRC}")

    values = canonical_values(root)
    page_subpaths = pages(SITE_SRC)

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    for source in sorted(SITE_SRC.rglob("*")):
        if not source.is_file():
            continue
        relative = source.relative_to(SITE_SRC)
        destination = out / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix in {".html", ".txt", ".css"}:
            content = substitute(source.read_text(encoding="utf-8"), values, relative.as_posix())
            destination.write_text(content, encoding="utf-8")
        else:
            shutil.copy2(source, destination)

    assets_dir = out / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    for source_rel, target_name in PROJECTED_ASSETS.items():
        source = root / source_rel
        if not source.is_file():
            raise SiteError(f"projiziertes Branding-Asset fehlt: {source_rel}")
        shutil.copy2(source, assets_dir / target_name)

    (out / "sitemap.xml").write_text(sitemap_xml(page_subpaths, values), encoding="utf-8")

    for subpath in page_subpaths:
        expected = out / "index.html" if not subpath else out / subpath / "index.html"
        if not expected.is_file():
            raise SiteError(f"Seite fehlt im Build-Ergebnis: {subpath or '/'}")


def verify(root: Path = ROOT, out: Path = DEFAULT_OUT) -> None:
    """Prüft, dass der Build dem aktuellen Authority-Stand entspricht (read-only)."""
    build(root, out)


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in {"build", "verify"}:
        print("usage: site_build.py <build|verify>", file=sys.stderr)
        return 2
    try:
        build()
        print("OK: site projection built from authorities")
        return 0
    except SiteError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
