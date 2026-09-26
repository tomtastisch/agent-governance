#!/usr/bin/env python3
"""Tests für tools/socket_freshness.py und die Socket-Konfiguration.

Abdeckung:
  - Deterministische Klassifikation CURRENT | STALE | UNAVAILABLE.
  - npm-latest-Readback (Authority) und Socket-API-Parsing (Projektion).
  - Prozent-Kodierung des PURL als einzelnes Pfadsegment.
  - Fail-closed UNAVAILABLE bei fehlendem Token, HTTP-/Netzwerkfehlern, ungültigem JSON.
  - Nicht-blockierender Advisory-Charakter: jede Klassifikation verlässt main() mit Exit 0.
  - socket.yml (Root, Schema v2) und socket-freshness.yml (immutable Pins, Least Privilege).
"""

import io
import json
import os
import re
import sys
import unittest
from contextlib import redirect_stdout
from email.message import Message
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools.socket_freshness as sf  # noqa: E402

import http.client  # noqa: E402
import urllib.error  # noqa: E402
import urllib.request  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._payload


def _json_response(obj):
    return _Response(json.dumps(obj).encode("utf-8"))


def _http_error(code):
    fp = io.BytesIO(b"{}")
    error = urllib.error.HTTPError(
        "https://api.socket.dev/", code, "error", Message(), fp
    )
    fp.close()
    return error


class ClassificationContract(unittest.TestCase):
    def test_current_when_npm_latest_is_known_by_socket(self):
        self.assertEqual(sf.classify("1.7.1", {"1.7.1", "1.6.0"}), sf.CURRENT)

    def test_stale_when_socket_does_not_know_npm_latest(self):
        self.assertEqual(sf.classify("1.7.1", {"1.6.0", "1.5.2"}), sf.STALE)

    def test_stale_when_socket_knows_nothing(self):
        self.assertEqual(sf.classify("1.7.1", set()), sf.STALE)

    def test_unavailable_when_npm_latest_unreadable(self):
        self.assertEqual(sf.classify(None, {"1.7.1"}), sf.UNAVAILABLE)

    def test_unavailable_when_socket_projection_unavailable(self):
        self.assertEqual(sf.classify("1.7.1", None), sf.UNAVAILABLE)

    def test_unavailable_when_both_unreadable(self):
        self.assertEqual(sf.classify(None, None), sf.UNAVAILABLE)

    def test_classification_never_mutates_inputs(self):
        known = {"1.6.0"}
        sf.classify("1.7.1", known)
        self.assertEqual(known, {"1.6.0"})


class SocketKnownVersionsContract(unittest.TestCase):
    def test_returns_none_without_token(self):
        self.assertIsNone(sf.socket_known_versions("org", "pkg:npm/a", None))

    def test_returns_known_versions(self):
        with mock.patch(
            "tools.socket_freshness._urlopen",
            return_value=_json_response(
                {
                    "purl": "pkg:npm/a",
                    "versions": [
                        {"version": "1.7.1", "publishedAt": "2026-09-26T10:00:00Z", "prerelease": False},
                        {"version": "1.6.0", "publishedAt": "2026-09-25T10:00:00Z", "prerelease": False},
                    ],
                }
            ),
        ):
            self.assertEqual(
                sf.socket_known_versions("org", "pkg:npm/a", "token"),
                {"1.7.1", "1.6.0"},
            )

    def test_returns_none_on_http_401(self):
        with mock.patch("tools.socket_freshness._urlopen", side_effect=_http_error(401)):
            self.assertIsNone(sf.socket_known_versions("org", "pkg:npm/a", "token"))

    def test_returns_none_on_http_404(self):
        with mock.patch("tools.socket_freshness._urlopen", side_effect=_http_error(404)):
            self.assertIsNone(sf.socket_known_versions("org", "pkg:npm/a", "token"))

    def test_returns_none_on_network_failure(self):
        with mock.patch(
            "tools.socket_freshness._urlopen",
            side_effect=urllib.error.URLError("connection refused"),
        ):
            self.assertIsNone(sf.socket_known_versions("org", "pkg:npm/a", "token"))

    def test_returns_none_on_invalid_json(self):
        with mock.patch("tools.socket_freshness._urlopen", return_value=_Response(b"not json")):
            self.assertIsNone(sf.socket_known_versions("org", "pkg:npm/a", "token"))

    def test_returns_none_on_invalid_encoding(self):
        with mock.patch("tools.socket_freshness._urlopen", return_value=_Response(b"\xff\xff\xff\xff")):
            self.assertIsNone(sf.socket_known_versions("org", "pkg:npm/a", "token"))

    def test_returns_none_on_incomplete_read(self):
        def fake_open(request, timeout=None):
            raise http.client.IncompleteRead(partial=b"{}")

        with mock.patch("tools.socket_freshness._urlopen", side_effect=fake_open):
            self.assertIsNone(sf.socket_known_versions("org", "pkg:npm/a", "token"))

    def test_returns_none_on_malformed_version_entry(self):
        with mock.patch(
            "tools.socket_freshness._urlopen",
            return_value=_json_response({"purl": "pkg:npm/a", "versions": ["not-a-dict"]}),
        ):
            self.assertIsNone(sf.socket_known_versions("org", "pkg:npm/a", "token"))

    def test_returns_none_on_version_entry_missing_version(self):
        with mock.patch(
            "tools.socket_freshness._urlopen",
            return_value=_json_response(
                {"purl": "pkg:npm/a", "versions": [{"publishedAt": "2026-09-26T10:00:00Z"}]}
            ),
        ):
            self.assertIsNone(sf.socket_known_versions("org", "pkg:npm/a", "token"))

    def test_client_http_errors_are_not_retried(self):
        for code in (401, 404, 429):
            with self.subTest(code=code):
                calls = []

                def fake_open(request, timeout=None):
                    calls.append(1)
                    raise _http_error(code)

                with mock.patch("tools.socket_freshness._urlopen", side_effect=fake_open):
                    self.assertIsNone(sf.socket_known_versions("org", "pkg:npm/a", "token"))
                self.assertEqual(
                    len(calls), 1,
                    f"client HTTP error {code} must not be retried",
                )

    def test_transient_server_errors_are_retried_bounded(self):
        calls = []

        def fake_open(request, timeout=None):
            calls.append(1)
            raise _http_error(503)

        with mock.patch("tools.socket_freshness._urlopen", side_effect=fake_open):
            self.assertIsNone(sf.socket_known_versions("org", "pkg:npm/a", "token"))
        self.assertEqual(len(calls), sf.RETRY_ATTEMPTS)

    def test_transient_network_errors_are_retried_bounded(self):
        calls = []

        def fake_open(request, timeout=None):
            calls.append(1)
            raise urllib.error.URLError("transient")

        with mock.patch("tools.socket_freshness._urlopen", side_effect=fake_open):
            self.assertIsNone(sf.socket_known_versions("org", "pkg:npm/a", "token"))
        self.assertEqual(len(calls), sf.RETRY_ATTEMPTS)

    def test_percent_encodes_purl_as_single_path_segment(self):
        captured = {}

        def fake_open(request, timeout=None):
            captured["url"] = request.full_url
            return _json_response({"purl": "pkg:npm/@tomtastisch/agent-governance", "versions": []})

        with mock.patch("tools.socket_freshness._urlopen", side_effect=fake_open):
            sf.socket_known_versions(
                "tomtastisch-8rpr5",
                "pkg:npm/@tomtastisch/agent-governance",
                "token",
            )

        expected_path = "pkg%3Anpm%2F%40tomtastisch%2Fagent-governance"
        self.assertIn(
            "/v1/orgs/tomtastisch-8rpr5/purl/versions/" + expected_path,
            captured["url"],
        )
        self.assertNotIn("/", captured["url"].split("/versions/", 1)[1])

    def test_percent_encodes_org_slug_as_single_path_segment(self):
        captured = {}

        def fake_open(request, timeout=None):
            captured["url"] = request.full_url
            return _json_response({"purl": "pkg:npm/a", "versions": []})

        with mock.patch("tools.socket_freshness._urlopen", side_effect=fake_open):
            sf.socket_known_versions("org/slug", "pkg:npm/a", "token")

        self.assertIn("/v1/orgs/org%2Fslug/purl/versions/", captured["url"])

    def test_authorization_header_is_bearer_token(self):
        captured = {}

        def fake_open(request, timeout=None):
            captured["headers"] = dict(request.headers)
            return _json_response({"purl": "pkg:npm/a", "versions": []})

        with mock.patch("tools.socket_freshness._urlopen", side_effect=fake_open):
            sf.socket_known_versions("org", "pkg:npm/a", "secret-token")

        self.assertEqual(captured["headers"].get("Authorization"), "Bearer secret-token")


class NpmLatestContract(unittest.TestCase):
    def test_reads_latest_dist_tag(self):
        with mock.patch(
            "tools.socket_freshness._urlopen",
            return_value=_json_response({"latest": "1.7.1"}),
        ):
            self.assertEqual(sf.npm_latest_version("@tomtastisch/agent-governance"), "1.7.1")

    def test_returns_none_when_latest_missing(self):
        with mock.patch("tools.socket_freshness._urlopen", return_value=_json_response({})):
            self.assertIsNone(sf.npm_latest_version("@tomtastisch/agent-governance"))

    def test_returns_none_on_http_error(self):
        with mock.patch("tools.socket_freshness._urlopen", side_effect=_http_error(500)):
            self.assertIsNone(sf.npm_latest_version("@tomtastisch/agent-governance"))

    def test_returns_none_on_network_failure(self):
        with mock.patch(
            "tools.socket_freshness._urlopen",
            side_effect=urllib.error.URLError("dns failure"),
        ):
            self.assertIsNone(sf.npm_latest_version("@tomtastisch/agent-governance"))


class NonBlockingMainContract(unittest.TestCase):
    def _run_main(self, npm_version, known):
        with mock.patch.object(sf, "npm_latest_version", return_value=npm_version), \
             mock.patch.object(sf, "socket_known_versions", return_value=known):
            out = io.StringIO()
            with redirect_stdout(out):
                code = sf.main(
                    ["--package", "pkg", "--org-slug", "org", "--purl", "pkg:npm/a"]
                )
            return code, out.getvalue()

    def test_current_exits_zero(self):
        code, out = self._run_main("1.7.1", {"1.7.1"})
        self.assertEqual(code, 0)
        self.assertIn("SOCKET_FRESHNESS=CURRENT", out)

    def test_stale_exits_zero(self):
        code, out = self._run_main("1.7.1", {"1.6.0"})
        self.assertEqual(code, 0)
        self.assertIn("SOCKET_FRESHNESS=STALE", out)

    def test_unavailable_exits_zero(self):
        code, out = self._run_main(None, None)
        self.assertEqual(code, 0)
        self.assertIn("SOCKET_FRESHNESS=UNAVAILABLE", out)

    def test_output_is_single_deterministic_line(self):
        _, out = self._run_main("1.7.1", {"1.7.1"})
        lines = out.strip().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertTrue(
            re.match(
                r"^SOCKET_FRESHNESS=(CURRENT|STALE|UNAVAILABLE) "
                r"npm_latest=[^ ]+ socket_purl=[^ ]+ socket_versions=\d+$",
                lines[0],
            ),
            lines[0],
        )

    def test_purl_derives_from_package_override(self):
        with mock.patch.object(sf, "npm_latest_version", return_value="1.7.1") as npm_mock, \
             mock.patch.object(sf, "socket_known_versions", return_value={"1.7.1"}) as socket_mock:
            out = io.StringIO()
            with redirect_stdout(out):
                code = sf.main(["--package", "@foo/bar", "--org-slug", "org"])
        self.assertEqual(code, 0)
        npm_mock.assert_called_once_with("@foo/bar")
        socket_mock.assert_called_once_with("org", "pkg:npm/@foo/bar", mock.ANY)
        self.assertIn("socket_purl=pkg:npm/@foo/bar", out.getvalue())


class RedirectSafetyContract(unittest.TestCase):
    def test_redirect_strips_authorization(self):
        handler = sf._StripAuthRedirectHandler()
        request = urllib.request.Request(
            "https://api.socket.dev/v1/orgs/o/purl/versions/x",
            headers={"Accept": "application/json", "Authorization": "Bearer secret"},
        )
        redirected = handler.redirect_request(
            request,
            io.BytesIO(b""),
            302,
            "Found",
            http.client.HTTPMessage(),
            "https://evil.example.net/collect",
        )
        self.assertIsNotNone(redirected)
        assert redirected is not None
        lowered = {key.lower() for key in redirected.headers}
        self.assertNotIn("authorization", lowered)
        self.assertIn("accept", lowered)


class SocketConfigContract(unittest.TestCase):
    def test_socket_yml_exists_with_schema_version_2(self):
        path = Path(ROOT) / "socket.yml"
        self.assertTrue(path.is_file(), "socket.yml fehlt im Repository-Root")
        text = path.read_text(encoding="utf-8")
        self.assertIn("version: 2", text)
        self.assertIn("enabled: true", text)
        for manifest in ("package.json", "package-lock.json"):
            self.assertIn(f'"{manifest}"', text)

    def test_socket_freshness_workflow_is_advisory_and_pinned(self):
        path = Path(ROOT) / ".github" / "workflows" / "socket-freshness.yml"
        self.assertTrue(path.is_file(), "socket-freshness.yml fehlt")
        workflow = path.read_text(encoding="utf-8")

        for action in re.findall(r"(?m)^\s*- uses:\s+([^\s#]+)", workflow):
            self.assertRegex(
                action,
                r"^[^@]+@[0-9a-f]{40}$",
                f"unpinned action in socket-freshness.yml: {action}",
            )

        self.assertIn("contents: read", workflow)
        self.assertNotIn("id-token: write", workflow)
        self.assertNotIn("npm publish", workflow)
        self.assertIn("tools/socket_freshness.py", workflow)
        self.assertNotIn("continue-on-error", workflow)

        # Der Token ist ausschließlich Step-env-gebunden (Least Privilege), nie Job-env.
        self.assertIn(
            "        env:\n"
            "          SOCKET_SECURITY_API_KEY: ${{ secrets.SOCKET_SECURITY_API_KEY }}\n",
            workflow,
        )
        self.assertNotRegex(workflow, r"(?m)^    env:\n")
        self.assertNotIn("set -x", workflow)
        self.assertNotIn("printenv", workflow)

    def test_socket_is_not_a_runtime_dependency(self):
        package_json = json.loads(
            (Path(ROOT) / "package.json").read_text(encoding="utf-8")
        )
        dependencies = package_json.get("dependencies", {})
        self.assertNotIn("socket", " ".join(dependencies.keys()).lower())
        self.assertNotIn("socket.dev", " ".join(dependencies.keys()).lower())


if __name__ == "__main__":
    unittest.main()
