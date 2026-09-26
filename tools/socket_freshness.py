#!/usr/bin/env python3
"""Deterministische Socket.dev-Paketindex-Freshness-Projektion (read-only, advisory).

Authority: npm `dist-tags.latest` und der signierte GitHub-Release/Tag.
Socket.dev ist ausschließlich externe Security-Evidence; seine öffentliche
Paketprojektion ist niemals Release- oder Versions-Authority.

Klassifikation der Socket-Paketprojektion gegen die autoritative npm-`latest`-Version:

  CURRENT      Socket kennt die veröffentlichte `latest`-Version.
  STALE        Socket antwortet, kennt die `latest`-Version aber (noch) nicht.
  UNAVAILABLE  Socket-API nicht erreichbar/nicht autorisiert oder npm-`latest` nicht lesbar.

Advisory-Vertrag: Jede Klassifikation verlässt das Programm mit Exit 0. Ein
veralteter externer Index darf einen korrekt veröffentlichten npm-Release niemals
rückwirkend invalidieren. Es gibt kein HTML-Scraping; genutzt wird ausschließlich
die offizielle Socket-API (`GET /v1/orgs/{org_slug}/purl/versions/{purl}`) und die
npm-Registry (`/-/package/{name}/dist-tags`).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

CURRENT = "CURRENT"
STALE = "STALE"
UNAVAILABLE = "UNAVAILABLE"

NPM_REGISTRY = "https://registry.npmjs.org"
SOCKET_API_BASE = "https://api.socket.dev"

DEFAULT_ORG_SLUG = "tomtastisch-8rpr5"
DEFAULT_PACKAGE = "@tomtastisch/agent-governance"
DEFAULT_PURL = "pkg:npm/@tomtastisch/agent-governance"

TOKEN_ENV = "SOCKET_SECURITY_API_KEY"

RETRY_ATTEMPTS = 3
REQUEST_TIMEOUT = 30


def _is_retryable_http_error(error):
    """Transiente Serverfehler (5xx) sind retrybar; 4xx sind es nicht."""
    return isinstance(error.code, int) and 500 <= error.code <= 599


def _read_json(url, headers, attempts=RETRY_ATTEMPTS, timeout=REQUEST_TIMEOUT):
    """Liest ein JSON-Dokument mit begrenzten Retries bei transienten Fehlern.

    Retried werden transiente Transportfehler sowie transiente Serverfehler (5xx).
    Client-Fehler (4xx, einschließlich 401/403/404/429) und nicht dekodierbare
    Antworten (ungültiges JSON/Encoding) werden nicht retried, sondern propagiert.
    """
    last_error = None
    for _ in range(attempts):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if _is_retryable_http_error(error):
                last_error = error
                continue
            raise error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = error
    assert last_error is not None  # RETRY_ATTEMPTS >= 1 garantiert einen Durchlauf
    raise last_error


def npm_latest_version(package=DEFAULT_PACKAGE, registry=NPM_REGISTRY):
    """Autoritative npm-`dist-tags.latest`-Version oder None bei Lesefehler."""
    encoded = urllib.parse.quote(package, safe="")
    url = f"{registry}/-/package/{encoded}/dist-tags"
    try:
        payload = _read_json(url, headers={"Accept": "application/json"})
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
        return None
    latest = payload.get("latest") if isinstance(payload, dict) else None
    if not isinstance(latest, str) or not latest:
        return None
    return latest


def socket_known_versions(org_slug, purl, token, api_base=SOCKET_API_BASE):
    """Menge der Socket bekannten Versionsstrings für einen PURL oder None.

    None bedeutet: Projektion nicht verfügbar (fehlender Token, Netz-/HTTP-/JSON-Fehler).
    """
    if not token:
        return None
    encoded_org = urllib.parse.quote(org_slug, safe="")
    encoded = urllib.parse.quote(purl, safe="")
    url = f"{api_base}/v1/orgs/{encoded_org}/purl/versions/{encoded}"
    try:
        payload = _read_json(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
        return None

    versions = payload.get("versions") if isinstance(payload, dict) else None
    if not isinstance(versions, list):
        return None

    known = set()
    for item in versions:
        if isinstance(item, dict):
            version = item.get("version")
            if isinstance(version, str) and version:
                known.add(version)
    return known


def classify(npm_version, socket_known):
    """Deterministische Klassifikation CURRENT | STALE | UNAVAILABLE."""
    if npm_version is None or socket_known is None:
        return UNAVAILABLE
    if npm_version in socket_known:
        return CURRENT
    return STALE


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Socket-Paketindex-Freshness deterministisch klassifizieren (advisory)."
    )
    parser.add_argument("--org-slug", default=DEFAULT_ORG_SLUG)
    parser.add_argument("--purl", default=DEFAULT_PURL)
    parser.add_argument("--package", default=DEFAULT_PACKAGE)
    args = parser.parse_args(argv)

    token = os.environ.get(TOKEN_ENV)
    npm_version = npm_latest_version(args.package)
    known = socket_known_versions(args.org_slug, args.purl, token)
    state = classify(npm_version, known)

    print(
        f"SOCKET_FRESHNESS={state} "
        f"npm_latest={npm_version or 'unknown'} "
        f"socket_purl={args.purl} "
        f"socket_versions={len(known) if known is not None else 'unknown'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
