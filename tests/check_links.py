#!/usr/bin/env python3
"""Advisory: prüft die Erreichbarkeit der im Katalog `tools/tools.md` verlinkten Quellen.

Netzabhängig und damit bewusst nicht-blockierend (Kern §13: Advisory-Checks sind als solche
gekennzeichnet). Der offline, blockierende Teil der Drift-Sicherung liegt in test_governance.py;
dieser Lauf meldet zusätzlich tote Links, damit tools.md nicht unbemerkt veraltet.

    python3 tests/check_links.py
Exit 0 = alle Links erreichbar, Exit 1 = mindestens ein toter Link (im CI advisory behandelt).
"""
import os
import re
import sys
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "agent-governance-linkcheck/1.0"}
TIMEOUT = 15


def urls_in(rel):
    text = open(os.path.join(ROOT, rel), encoding="utf-8").read()
    found = []
    for raw in re.findall(r"https?://\S+", text):
        found.append(raw.rstrip(">).,"))
    return sorted(set(found))


def reachable(url, retries=2):
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=UA, method="HEAD")
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                if resp.status < 400:
                    return True, resp.status
        except urllib.error.HTTPError as e:
            # Manche Hosts lehnen HEAD ab (405) — dann GET versuchen.
            if e.code in (403, 405, 501):
                try:
                    req = urllib.request.Request(url, headers=UA)
                    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                        if resp.status < 400:
                            return True, resp.status
                except Exception as inner:
                    last = f"GET {inner}"
                    continue
            last = f"HTTP {e.code}"
        except Exception as e:  # noqa: BLE001 — advisory, jede Netzstörung nur berichten
            last = str(e)
    return False, last


def main():
    dead = []
    for rel in ["tools/tools.md"]:
        for url in urls_in(rel):
            ok, info = reachable(url)
            mark = "OK " if ok else "TOT"
            print(f"[{mark}] {url} ({info})")
            if not ok:
                dead.append((rel, url, info))
    if dead:
        print(f"\n{len(dead)} nicht erreichbare(r) Link(s):")
        for rel, url, info in dead:
            print(f"  - {rel}: {url} — {info}")
        return 1
    print("\nAlle Links erreichbar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
