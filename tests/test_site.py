#!/usr/bin/env python3
"""Regression contracts for the GitHub Pages static-site projection (Issue #119).

The site is a projection of existing authorities (`VERSION`, `package.json`).
These tests prove that canonical values are derived — never independently
maintained — and that the base path, canonicals, sitemap, robots rules, and
structured data stay correct and fail closed on drift.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import site_build  # noqa: E402
from tools.site_build import SiteError  # noqa: E402

ROOT = site_build.ROOT

CORE_PAGES = ("", "docs", "ai-coding-agent-governance", "governance-as-code")


class SiteProjectionTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="agent-governance-site-")
        self.out = site_build.Path(self._tmp.name)
        self.values = site_build.canonical_values(ROOT)
        site_build.build(ROOT, self.out)

    def tearDown(self):
        self._tmp.cleanup()

    def _page(self, subpath: str) -> str:
        relative = subpath or "index.html"
        return (self.out / relative / "index.html").read_text(
            encoding="utf-8"
        ) if subpath else (self.out / "index.html").read_text(encoding="utf-8")

    def _internal_targets(self, html: str) -> set[str]:
        """Returns the set of base-path-prefixed internal link/asset targets."""
        return set(re.findall(r"(?:href|src)=\"(%s/(?:[^\"#]+))\"?" % re.escape(self.values["BASE_PATH"]), html))

    # ── Authority parity ──

    def test_version_is_derived_from_authority(self):
        self.assertEqual(self.values["VERSION"], (ROOT / "VERSION").read_text(encoding="utf-8").strip())
        home = self._page("")
        self.assertIn(f"v{self.values['VERSION']}", home)

    def test_install_command_matches_package_authority(self):
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(self.values["PACKAGE_NAME"], package["name"])
        self.assertEqual(self.values["BIN"], next(iter(package["bin"])))
        self.assertEqual(self.values["INSTALL"], f"npm i {package['name']}")
        self.assertEqual(self.values["INIT"], f"npx {next(iter(package['bin']))} init")

    def test_description_is_derived_not_duplicated(self):
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(self.values["DESCRIPTION"], package["description"])
        self.assertIn(self.values["DESCRIPTION"], self._page(""))

    # ── Base path ──

    def test_base_path_is_project_site_path(self):
        self.assertEqual(self.values["BASE_PATH"], "/agent-governance")
        self.assertEqual(self.values["PUBLIC_URL"], "https://tomtastisch.github.io/agent-governance")

    def test_no_root_relative_urls_escape_the_base_path(self):
        for subpath in CORE_PAGES:
            html = self._page(subpath)
            urls = re.findall(r"(?:href|src)=\"(/[^\"]*)\"", html)
            base = self.values["BASE_PATH"] + "/"
            offenders = [url for url in urls if not url.startswith(base)]
            self.assertEqual(offenders, [], f"{subpath or '/'}: root-relative URL outside base path")

    # ── Canonical and metadata ──

    def test_every_core_page_has_unique_title_and_meta_description(self):
        titles = []
        for subpath in CORE_PAGES:
            html = self._page(subpath)
            title = re.search(r"<title>([^<]+)</title>", html)
            self.assertIsNotNone(title, f"{subpath or '/'}: title missing")
            titles.append(title.group(1))
            self.assertRegex(html, r'<meta name="description" content="[^"]+"')
        self.assertEqual(len(set(titles)), len(titles), "titles are not unique")

    def test_every_core_page_has_a_correct_canonical(self):
        for subpath in CORE_PAGES:
            html = self._page(subpath)
            expected = site_build.canonical_url(subpath, self.values)
            self.assertIn(f'<link rel="canonical" href="{expected}">', html, subpath or "/")

    # ── Sitemap and robots ──

    def test_sitemap_contains_exactly_the_real_pages(self):
        sitemap = (self.out / "sitemap.xml").read_text(encoding="utf-8")
        urls = re.findall(r"<loc>([^<]+)</loc>", sitemap)
        expected = [site_build.canonical_url(subpath, self.values) for subpath in site_build.pages()]
        self.assertEqual(sorted(urls), sorted(expected))
        for url in urls:
            self.assertIn(f"{self.values['BASE_PATH']}/", url)

    def test_robots_allows_search_and_separates_training_crawlers(self):
        robots = (self.out / "robots.txt").read_text(encoding="utf-8")
        self.assertIn("Allow: /", robots)
        self.assertNotIn("Disallow: /", robots)
        self.assertIn("Sitemap: " + self.values["PUBLIC_URL"] + "/sitemap.xml", robots)
        self.assertRegex(robots, r"training", re.IGNORECASE)

    # ── Structured data ──

    def test_structured_data_is_valid_and_unembellished(self):
        home = self._page("")
        scripts = re.findall(r'<script type="application/ld\+json">(.*?)</script>', home, re.DOTALL)
        self.assertTrue(scripts)
        for raw in scripts:
            data = json.loads(raw)
            graph = data["@graph"] if "@graph" in data else [data]
            for node in graph:
                self.assertIn(node["@type"], {"SoftwareApplication", "SoftwareSourceCode", "BreadcrumbList"})
                if node["@type"] == "SoftwareApplication":
                    self.assertEqual(node["softwareVersion"], self.values["VERSION"])
                if node["@type"] == "SoftwareSourceCode":
                    self.assertEqual(node["version"], self.values["VERSION"])
                    self.assertEqual(node["codeRepository"], self.values["REPO_URL"])
        for forbidden in ("aggregateRating", "reviewCount", "userInteractionCount", "ratingValue"):
            self.assertNotIn(forbidden, home)

    # ── Links and assets ──

    def test_internal_links_and_assets_resolve(self):
        for subpath in CORE_PAGES:
            html = self._page(subpath)
            for target in self._internal_targets(html):
                path = self.out / target.removeprefix(self.values["BASE_PATH"] + "/")
                if path.is_dir():
                    path = path / "index.html"
                self.assertTrue(path.is_file(), f"{subpath or '/'}: broken internal target {target}")

    def test_branding_assets_are_projected(self):
        self.assertTrue((self.out / "assets" / "icon.png").is_file())
        self.assertTrue((self.out / "assets" / "terminal.png").is_file())

    # ── Package boundary ──

    def test_site_does_not_affect_npm_package_surface(self):
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        files = package.get("files", [])
        self.assertFalse(any(entry.startswith("site") or entry.startswith("_site") for entry in files))
        for export_path in package.get("exports", {}):
            self.assertFalse(export_path.startswith("./site"))
        dependencies = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
        self.assertFalse(any(name.startswith("site") for name in dependencies))

    def test_build_does_not_mutate_authorities(self):
        before_version = (ROOT / "VERSION").read_bytes()
        before_package = (ROOT / "package.json").read_bytes()
        site_build.build(ROOT, self.out)
        self.assertEqual((ROOT / "VERSION").read_bytes(), before_version)
        self.assertEqual((ROOT / "package.json").read_bytes(), before_package)


class SiteBuildFailClosedTest(unittest.TestCase):
    def test_unknown_token_fails_closed(self):
        with self.assertRaises(SiteError):
            site_build.substitute("{{NOT_A_REAL_TOKEN}}", {"VERSION": "1.0.0"}, "fixture")

    def test_missing_projected_asset_fails_closed(self):
        with tempfile.TemporaryDirectory(prefix="agent-governance-site-missing-") as directory:
            out = site_build.Path(directory)
            with mock.patch.object(site_build, "PROJECTED_ASSETS", {"assets/branding/missing.png": "x.png"}):
                with self.assertRaises(SiteError):
                    site_build.build(ROOT, out)

    def test_non_github_repository_fails_closed(self):
        bad_package = {
            "name": "@x/y", "bin": {"y": "dist/y.js"}, "description": "d",
            "repository": {"url": "git+https://gitlab.com/x/y.git"},
        }
        with mock.patch.object(site_build.json, "loads", return_value=bad_package):
            with self.assertRaises(SiteError):
                site_build.canonical_values(ROOT)

    def test_unsafe_description_fails_closed(self):
        bad_package = {
            "name": "@x/y", "bin": {"y": "dist/y.js"}, "description": 'a "quoted" description',
            "repository": {"url": "git+https://github.com/x/y.git"},
        }
        with mock.patch.object(site_build.json, "loads", return_value=bad_package):
            with self.assertRaises(SiteError):
                site_build.canonical_values(ROOT)


if __name__ == "__main__":
    unittest.main()
