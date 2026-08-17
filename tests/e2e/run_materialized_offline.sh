#!/usr/bin/env bash
set -euo pipefail

codex_state=${CODEX_HOME:?CODEX_HOME is required}
evidence=/run/e2e/offline-enforcement-evidence.jsonl
policy_module=$codex_state/runtime/microsoft-provider/microsoft-sdk/dist/policy.js
hook=$codex_state/integrations/microsoft-agent-governance-toolkit/bridge/codex-hook.mjs
provider=$codex_state/integrations/microsoft-agent-governance-toolkit/bridge/provider.mjs
bindings=$codex_state/integrations/microsoft-agent-governance-toolkit/bridge/action-bindings.json

test ! -e "$codex_state/auth.json"
cmp --silent "$codex_state/AGENTS.md" "$codex_state/GOVERNANCE.md"
test -f "$codex_state/agent-governance/manifest.toml"
test -f "$policy_module"
test -f "$hook"
test -f "$provider"
test -f "$bindings"

python3 - "$codex_state" <<'PY'
from pathlib import Path
import os
import sys
import tomllib

root = Path(sys.argv[1])
manifest_dir = root / "agent-governance"
with (manifest_dir / "manifest.toml").open("rb") as handle:
    manifest = tomllib.load(handle)
expected_catalogs = {
    "triggers": "catalogs/triggers.toml",
    "policy_tags": "catalogs/policy-tags.toml",
    "scopes": "catalogs/scopes.toml",
    "tools": "catalogs/tools.toml",
}
assert manifest["catalogs"] == expected_catalogs
for relative in expected_catalogs.values():
    catalog = manifest_dir / relative
    catalog.relative_to(manifest_dir)
    assert catalog.is_file() and not catalog.is_symlink(), relative
    with catalog.open("rb") as handle:
        assert tomllib.load(handle)["schema_version"] == 1, relative
local = Path(os.path.normpath(manifest_dir / manifest["local_rules"]))
local.relative_to(manifest_dir)
assert "SYNTHETIC_LOCAL_RULE_ACTIVE" in local.read_text(encoding="utf-8")
for relative in (
    "modules/invariants.md",
    "modules/enforcement.md",
    "modules/evidence.md",
    "roles/quality-assurance.md",
):
    assert (manifest_dir / relative).is_file(), relative
assert not any((root / legacy).exists() for legacy in ("core", "adapters", "profile"))
PY

install -m 600 /dev/null "$evidence"
export AGENT_GOVERNANCE_MSAGT_POLICY_MODULE="$policy_module"
export AGENT_GOVERNANCE_ENFORCED_TOOL_NAME=mcp__agent_governance__execute
export AGENT_GOVERNANCE_ACTION_BINDINGS="$bindings"
export AGENT_GOVERNANCE_EVIDENCE_LOG="$evidence"

run_hook() {
  local tool_use_id=$1
  local operation=$2
  local resource_id=$3
  node "$hook" <<EOF
{"hook_event_name":"PreToolUse","tool_name":"mcp__agent_governance__execute","tool_use_id":"$tool_use_id","tool_input":{"action_request":{"operation":"$operation","resource_id":"$resource_id"}}}
EOF
}

allow_result=$(run_hook offline-allow workspace_write offline-allow-effect)
deny_result=$(run_hook offline-deny external_write offline-deny-effect)
approval_result=$(run_hook offline-approval approval_write offline-approval-effect)

python3 - "$allow_result" "$deny_result" "$approval_result" "$evidence" <<'PY'
from pathlib import Path
import json
import sys

allow, deny, approval = (json.loads(value) for value in sys.argv[1:4])
assert allow["hookSpecificOutput"]["permissionDecision"] == "allow"
assert deny["hookSpecificOutput"]["permissionDecision"] == "deny"
assert approval["hookSpecificOutput"]["permissionDecision"] == "deny"
records = [json.loads(line) for line in Path(sys.argv[4]).read_text(encoding="utf-8").splitlines()]
assert [record["decision"] for record in records] == ["allow", "deny", "require_approval"]
assert all(record["provider_reached"] is True for record in records)
assert all(record["evaluated_before_effect"] is True for record in records)
PY

printf '%s\n' \
  'offline_governance_discovery=PASS' \
  'offline_manifest_routing=PASS' \
  'offline_local_rules_runtime=PASS' \
  'offline_materialized_provider=PASS' \
  'offline_allow=PASS' \
  'offline_deny=PASS' \
  'offline_require_approval=PASS' \
  'offline_audit=PASS'
