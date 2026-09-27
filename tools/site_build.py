#!/usr/bin/env python3
"""Deterministic static-site build for GitHub Pages.

Die Site ist ausschließlich eine Projektion bestehender Authorities
(`VERSION`, `package.json`, `README`/`docs`). Sie leitet kanonische Werte
(Version, Package-Name, Installationsweg, Repository-URL, Base-Path) beim
Build aus diesen Authorities ab, statt sie unabhängig zu pflegen. Kein Modus
mutiert das Repository, den npm-Runtime-Pfad oder externe Dienste.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, build_opener

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

class SiteError(Exception):
    """Deterministischer Build-/Verifikationsfehler der Site-Projektion."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_public_json(url: str) -> dict:
    """Begrenzter Read-only-Abruf; Redirects erweitern die Quellen nicht."""
    with build_opener(_NoRedirect()).open(url, timeout=20) as response:
        raw = response.read(1_000_001)
    if len(raw) > 1_000_000:
        raise SiteError("Metrikantwort überschreitet die Größenbegrenzung")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise SiteError("Metrikantwort ist kein JSON-Objekt")
    return value


def unavailable_metric(package: str) -> dict:
    return {
        "schemaVersion": 1, "label": "latest / 7d", "message": "nicht verfügbar",
        "color": "lightgrey", "isError": True, "package": package,
        "observedAt": datetime.now(timezone.utc).isoformat(),
        "period": "last-week",
    }


def npm_metrics(package: str) -> dict:
    """Projiziert Registry-latest und dessen npm-Zähler der letzten sieben Tage."""
    if not re.fullmatch(r"(?:@[a-z0-9._-]+/)?[a-z0-9._-]+", package):
        raise SiteError("Ungültiger npm-Paketname")
    metric = unavailable_metric(package)
    encoded = quote(package, safe="@")
    try:
        latest = read_public_json(f"https://registry.npmjs.org/{encoded}/latest")
        version = latest.get("version")
        if latest.get("name") != package or not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?", version):
            return metric
        metric["observedVersion"] = version
        counts = read_public_json(f"https://api.npmjs.org/versions/{encoded}/last-week")
        downloads = counts.get("downloads")
        if counts.get("package") != package or not isinstance(downloads, dict):
            return metric
        count = downloads.get(version)
        if type(count) is not int or count < 0:
            return metric
        metric.update(message=str(count), color="blue", isError=False)
    except (URLError, OSError, ValueError, SiteError):
        # Ein fehlender Zähler ist weder null noch die paketweite Gesamtzahl.
        pass
    return metric


def valid_metric(metric: object, package: str) -> bool:
    """Nur die erwartete Projektion, höchstens 24 Stunden alt, weiterreichen."""
    if not isinstance(metric, dict) or set(metric) - {"schemaVersion", "label", "message", "color", "isError", "package", "observedAt", "observedVersion", "period"}:
        return False
    if metric.get("package") != package or type(metric.get("schemaVersion")) is not int or metric["schemaVersion"] != 1 or metric.get("label") != "latest / 7d" or metric.get("period") != "last-week":
        return False
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(metric["observedAt"])).total_seconds()
    except (KeyError, ValueError, TypeError):
        return False
    if not 0 <= age <= 86400:
        return False
    if metric.get("isError") is True:
        return metric.get("message") == "nicht verfügbar" and metric.get("color") == "lightgrey"
    return (
        metric.get("isError") is False
        and metric.get("color") == "blue"
        and isinstance(metric.get("observedVersion"), str)
        and isinstance(metric.get("message"), str)
        and re.fullmatch(r"[0-9]+", metric["message"]) is not None
    )


def should_refresh_npm(event: str, attempt: str) -> bool:
    return event == "schedule" and attempt == "1"


def collect_npm_metric(refresh: bool) -> dict:
    values = canonical_values()
    package = values["PACKAGE_NAME"]
    if refresh:
        return npm_metrics(package)
    try:
        metric = read_public_json(f"{values['PUBLIC_URL']}/metrics/npm-latest-7d.json")
        if valid_metric(metric, package):
            return metric
    except (URLError, OSError, ValueError, SiteError):
        pass
    return unavailable_metric(package)


def _assert_web_safe(value: str, label: str) -> None:
    """Lehnt Zeichen ab, die HTML-Attribute oder eingebettetes JSON-LD korrumpieren würden."""
    if '"' in value or "\\" in value or "<" in value or ">" in value or "&" in value:
        raise SiteError(f"{label} enthält für die Site-Projektion ungeeignete Zeichen")
    if any(ord(ch) < 0x20 for ch in value):
        raise SiteError(f"{label} enthält Steuerzeichen")


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

    _assert_web_safe(description, "package.json description")
    _assert_web_safe(version, "VERSION")
    _assert_web_safe(package_name, "package name")

    base_path = f"/{repo_name}"
    public_url = f"https://{owner}.github.io/{repo_name}"

    values = {
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
    for key, value in values.items():
        _assert_web_safe(value, key)
    return values


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


def canonical_url(subpath: str, values: dict[str, str]) -> str:
    return f"{values['PUBLIC_URL']}/{subpath}/" if subpath else f"{values['PUBLIC_URL']}/"


def substitute(text: str, values: dict[str, str], context: str) -> str:
    """Ersetzt alle Tokens; jede verbleibende `{{...}}`-Syntax scheitert fail-closed."""
    for name, value in values.items():
        text = text.replace("{{" + name + "}}", value)
    if "{{" in text or "}}" in text:
        raise SiteError(f"{context}: nicht aufgelöster oder fehlerhafter Platzhalter")
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


def build(root: Path = ROOT, out: Path = DEFAULT_OUT, npm_metric: Path | None = None) -> None:
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

    if npm_metric is not None:
        metric = json.loads(npm_metric.read_text(encoding="utf-8"))
        if not valid_metric(metric, values["PACKAGE_NAME"]):
            raise SiteError("Ungültige npm-Metrikprojektion")
        target = out / "metrics/npm-latest-7d.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(metric, ensure_ascii=False) + "\n", encoding="utf-8")

    for subpath in page_subpaths:
        expected = out / "index.html" if not subpath else out / subpath / "index.html"
        if not expected.is_file():
            raise SiteError(f"Seite fehlt im Build-Ergebnis: {subpath or '/'}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("build", "npm-metrics"))
    parser.add_argument("--npm-metric", type=Path)
    parser.add_argument("--output", type=Path, default=Path("npm-latest-7d.json"))
    args = parser.parse_args(argv[1:])
    try:
        if args.mode == "npm-metrics":
            metric = collect_npm_metric(should_refresh_npm(os.environ.get("GITHUB_EVENT_NAME", ""), os.environ.get("GITHUB_RUN_ATTEMPT", "")))
            args.output.write_text(json.dumps(metric, ensure_ascii=False) + "\n", encoding="utf-8")
            print("OK: npm metric projection prepared")
        else:
            build(npm_metric=args.npm_metric)
            print("OK: site projection built from authorities")
        return 0
    except (SiteError, OSError, ValueError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
