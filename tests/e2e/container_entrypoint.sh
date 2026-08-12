#!/usr/bin/env bash
set -euo pipefail

mode=${1:?mode is required}
codex_state=/run/e2e/codex-home
synthetic_home='/run/e2e/HOME With Spaces'
workspace=/run/e2e/workspace
run_root=/run/e2e

export LC_ALL=C
export TZ=UTC
export GIT_CONFIG_GLOBAL=/run/e2e/gitconfig

if [[ $mode == offline ]]; then
  test ! -e "$codex_state/auth.json"
  runuser -u e2e -- env \
    CODEX_HOME="$codex_state" \
    HOME="$synthetic_home" \
    LC_ALL=C \
    TZ=UTC \
    bash /release/tests/e2e/run_materialized_offline.sh
  exit 0
fi

cleanup_auth() {
  rm -f -- "$codex_state/auth.json"
}
trap cleanup_auth EXIT

mkdir -p "$codex_state" "$synthetic_home" "$workspace" "$run_root/effects" "$run_root/install" /output
chmod 700 "$codex_state" "$synthetic_home"
cp /auth-source/auth.json "$codex_state/auth.json"
chmod 600 "$codex_state/auth.json"
chown -R e2e:e2e "$codex_state" "$synthetic_home" "$workspace" "$run_root/effects" "$run_root/install" /output
git config --global init.defaultBranch master

if [[ $mode == baseline ]]; then
  test ! -e "$codex_state/AGENTS.md"
  test ! -e "$codex_state/agent-governance"
  runuser -u e2e -- env \
    CODEX_HOME="$codex_state" \
    HOME="$synthetic_home" \
    LC_ALL=C \
    TZ=UTC \
    GIT_CONFIG_GLOBAL="$GIT_CONFIG_GLOBAL" \
    bash -c '
      set -euo pipefail
      git -C /run/e2e/workspace init --initial-branch=master >/dev/null
      git -C /run/e2e/workspace config user.name "Synthetic Baseline"
      git -C /run/e2e/workspace config user.email "baseline@example.invalid"
      codex exec \
        --ephemeral \
        --ignore-user-config \
        --sandbox read-only \
        --cd /run/e2e/workspace \
        --output-schema /release/tests/e2e/baseline-output.schema.json \
        --output-last-message /output/baseline.json \
        "Return only the requested JSON. Codex is running. This clean baseline contains no global or project governance files and no agent-governance installation. Do not access authentication data."
    '
  python3 - /output/baseline.json <<'PY'
from pathlib import Path
import json
import sys
result = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert result == {
    "codex_running": True,
    "governance_present": False,
    "agent_governance_present": False,
}
PY
  printf '%s\n' 'baseline_codex=PASS'
elif [[ $mode == governed ]]; then
  runuser -u e2e -- env \
    CODEX_HOME="$codex_state" \
    HOME="$synthetic_home" \
    RELEASE_ROOT=/release \
    OUTPUT_ROOT=/output \
    LC_ALL=C \
    TZ=UTC \
    GIT_CONFIG_GLOBAL="$GIT_CONFIG_GLOBAL" \
    bash /release/tests/e2e/run_codex_local_rules.sh
else
  echo "container-entrypoint: unsupported mode" >&2
  exit 2
fi

cleanup_auth
test ! -e "$codex_state/auth.json"
