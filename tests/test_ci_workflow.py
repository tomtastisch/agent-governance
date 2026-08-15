#!/usr/bin/env python3
"""Regression contracts for release-critical GitHub Actions jobs."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
    encoding="utf-8"
)
CHECKOUT_SHA = "de0fac2e4500dabe0009e67214ff5f5447ce83dd"


def _job_block(job_name: str) -> str:
    match = re.search(
        rf"(?ms)^  {re.escape(job_name)}:\n(?P<body>.*?)(?=^  [a-z0-9_-]+:\n|\Z)",
        CI_WORKFLOW,
    )
    if match is None:
        raise AssertionError(f"CI job not found: {job_name}")
    return match.group("body")


class ReleaseCheckoutContract(unittest.TestCase):
    def test_release_jobs_preserve_annotated_tags_with_pinned_checkout(self):
        checkout_line = (
            f"      - uses: actions/checkout@{CHECKOUT_SHA} # v6.0.2"
        )
        for job_name in ("release-tag-check", "release-validate"):
            with self.subTest(job=job_name):
                block = _job_block(job_name)
                self.assertEqual(block.count("actions/checkout@"), 1)
                self.assertIn(checkout_line, block)
                self.assertRegex(
                    block,
                    re.escape(checkout_line)
                    + r"\n        with:\n(?:          [^\n]+\n)*"
                    + r"          fetch-depth: 0(?:\n|\Z)",
                )


if __name__ == "__main__":
    unittest.main()
