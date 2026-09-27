"""Die Latest-Kennzahl projiziert npm-Daten, keine lokalen Versionsannahmen."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import URLError

from tools import site_build


class NpmMetricsTest(unittest.TestCase):
    package = "@tomtastisch/agent-governance"

    def metric(self, latest=None, counts=None):
        responses = [
            latest if latest is not None else {"name": self.package, "version": "9.8.7"},
            counts if counts is not None else {"package": self.package, "downloads": {"9.8.7": 23, "1.0.0": 900}},
        ]
        with mock.patch.object(site_build, "read_public_json", side_effect=responses) as fetch:
            result = site_build.npm_metrics(self.package)
        return result, fetch

    def test_registry_latest_selects_only_its_version_count(self):
        metric, fetch = self.metric()
        self.assertEqual(metric["message"], "23")
        self.assertEqual(metric["label"], "latest / 7d")
        self.assertEqual(metric["schemaVersion"], 1)
        self.assertEqual(metric["observedVersion"], "9.8.7")
        self.assertEqual(metric["package"], self.package)
        self.assertIn("observedAt", metric)
        self.assertEqual(fetch.call_args_list, [
            mock.call("https://registry.npmjs.org/@tomtastisch%2Fagent-governance/latest"),
            mock.call("https://api.npmjs.org/versions/@tomtastisch%2Fagent-governance/last-week"),
        ])

    def test_explicit_zero_is_valid(self):
        metric, _ = self.metric(counts={"package": self.package, "downloads": {"9.8.7": 0}})
        self.assertEqual(metric["message"], "0")
        self.assertNotEqual(metric.get("isError"), True)

    def test_missing_latest_never_falls_back_to_total_or_zero(self):
        metric, _ = self.metric(counts={"package": self.package, "downloads": {"1.0.0": 900}})
        self.assertEqual(metric["message"], "nicht verfügbar")
        self.assertTrue(metric["isError"])

    def test_invalid_counts_are_unavailable(self):
        for value in (-1, True, 1.5, "23", None):
            with self.subTest(value=value):
                metric, _ = self.metric(counts={"package": self.package, "downloads": {"9.8.7": value}})
                self.assertTrue(metric["isError"])

    def test_wrong_package_is_not_projected(self):
        metric, _ = self.metric(counts={"package": "other", "downloads": {"9.8.7": 23}})
        self.assertTrue(metric["isError"])

    def test_transport_error_is_explicitly_unavailable(self):
        with mock.patch.object(site_build, "read_public_json", side_effect=URLError("offline")):
            self.assertTrue(site_build.npm_metrics(self.package)["isError"])

    def test_invalid_registry_response_does_not_query_downloads(self):
        for latest in ({}, {"name": "other", "version": "9.8.7"}, {"name": self.package, "version": "https://elsewhere.example"}):
            with self.subTest(latest=latest):
                metric, fetch = self.metric(latest=latest)
                self.assertTrue(metric["isError"])
                self.assertEqual(fetch.call_count, 1)

    def test_public_json_is_bounded_and_must_be_an_object(self):
        for raw in (b"[]", b"not json", b" " * 1_000_001):
            with self.subTest(length=len(raw)):
                response = mock.MagicMock()
                response.__enter__.return_value.read.return_value = raw
                with mock.patch.object(site_build, "build_opener") as opener:
                    opener.return_value.open.return_value = response
                    with self.assertRaises((ValueError, site_build.SiteError)):
                        site_build.read_public_json("https://api.npmjs.org/fixture")
                    response.__enter__.return_value.read.assert_called_once_with(1_000_001)

    def test_redirects_do_not_expand_the_source_boundary(self):
        self.assertIsNone(site_build._NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.example"))

    def test_build_projects_supplied_metric_without_network(self):
        metric, _ = self.metric()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "metric.json"
            source.write_text(json.dumps(metric))
            with mock.patch.object(site_build, "read_public_json", side_effect=AssertionError("Netzwerk im Offline-Build")):
                site_build.build(out=root / "site", npm_metric=source)
            self.assertEqual(json.loads((root / "site/metrics/npm-latest-7d.json").read_text()), metric)

    def test_push_reuses_published_snapshot_without_resolving_npm(self):
        metric, _ = self.metric()
        with mock.patch.object(site_build, "read_public_json", return_value=metric) as fetch:
            self.assertEqual(site_build.collect_npm_metric(refresh=False), metric)
        fetch.assert_called_once_with("https://tomtastisch.github.io/agent-governance/metrics/npm-latest-7d.json")

    def test_missing_snapshot_does_not_trigger_npm_fetch(self):
        with mock.patch.object(site_build, "read_public_json", side_effect=URLError("missing")) as fetch:
            self.assertTrue(site_build.collect_npm_metric(refresh=False)["isError"])
        self.assertEqual(fetch.call_count, 1)

    def test_old_or_invalid_snapshot_is_not_published_as_current(self):
        metric, _ = self.metric()
        for override in ({"observedAt": "2000-01-01T00:00:00+00:00"}, {"package": "other"}, {"message": ""}, {"message": 23}, {"message": "-23"}, {"logoSvg": "unexpected"}):
            with self.subTest(override=override):
                with mock.patch.object(site_build, "read_public_json", return_value={**metric, **override}):
                    self.assertTrue(site_build.collect_npm_metric(refresh=False)["isError"])

    def test_invalid_observed_version_is_not_a_success_snapshot(self):
        metric, _ = self.metric()
        for version in ("", "invalid-version", "https://other.example", 123):
            with self.subTest(version=version):
                self.assertFalse(site_build.valid_metric({**metric, "observedVersion": version}, self.package))

    def test_snapshot_expiring_before_build_becomes_unavailable(self):
        metric, _ = self.metric()
        metric["observedAt"] = "2000-01-01T00:00:00+00:00"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "metric.json"
            source.write_text(json.dumps(metric))
            site_build.build(out=root / "site", npm_metric=source)
            projected = json.loads((root / "site/metrics/npm-latest-7d.json").read_text())
            self.assertTrue(projected["isError"])
            self.assertEqual(projected["message"], "nicht verfügbar")

    def test_only_first_scheduled_attempt_refreshes_npm(self):
        for event, attempt, expected in (("schedule", "1", True), ("schedule", "2", False), ("push", "1", False), ("workflow_dispatch", "1", False)):
            with self.subTest(event=event, attempt=attempt):
                self.assertEqual(site_build.should_refresh_npm(event, attempt), expected)

    def test_metrics_command_uses_the_real_workflow_event_boundary(self):
        for event, attempt, expected in (("schedule", "1", True), ("schedule", "2", False), ("push", "1", False)):
            with self.subTest(event=event, attempt=attempt), tempfile.TemporaryDirectory() as directory:
                with mock.patch.dict(site_build.os.environ, {"GITHUB_EVENT_NAME": event, "GITHUB_RUN_ATTEMPT": attempt}):
                    with mock.patch.object(site_build, "collect_npm_metric", return_value={}) as collect:
                        self.assertEqual(site_build.main(["site_build.py", "npm-metrics", "--output", str(Path(directory) / "metric.json")]), 0)
                collect.assert_called_once_with(expected)

    def test_readme_uses_distinct_dynamic_endpoints_and_visible_labels(self):
        readme = (site_build.ROOT / "README.md").read_text()
        self.assertIn("npm/dw/@tomtastisch/agent-governance?style=flat-square&label=downloads%20%2F%207d", readme)
        self.assertIn("img.shields.io/endpoint?url=", readme)
        self.assertIn("npm-latest-7d.json", readme)


if __name__ == "__main__":
    unittest.main()
