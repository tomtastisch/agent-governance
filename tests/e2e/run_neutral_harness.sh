#!/usr/bin/env bash
set -euo pipefail

unset CODEX_HOME
python3 -m unittest \
  tests.test_local_rules_runtime \
  tests.test_neutral_harness \
  tests.test_offline_runtime \
  -v
