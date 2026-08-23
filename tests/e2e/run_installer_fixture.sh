#!/usr/bin/env bash
set -euo pipefail

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
fixture_root=$(mktemp -d "${TMPDIR:-/tmp}/agent-governance-installer.XXXXXX")
cleanup() {
  rm -rf -- "$fixture_root"
}
trap cleanup EXIT

codex_home="$fixture_root/Codex Home With Spaces"
install_root="$codex_home/governance"
mkdir -p -- "$codex_home"

common=(
  --harness codex
  --home "$codex_home"
  --allowed-root "$fixture_root"
  --release-root "$repository_root"
  --install-root "$install_root"
  --json
)

node "$repository_root/dist/cli.js" install "${common[@]}" --dry-run
test ! -e "$codex_home/AGENTS.md"
node "$repository_root/dist/cli.js" install "${common[@]}"
node "$repository_root/dist/cli.js" verify "${common[@]}"
node "$repository_root/dist/cli.js" status "${common[@]}"
node "$repository_root/dist/cli.js" rollback "${common[@]}"
node "$repository_root/dist/cli.js" rollback "${common[@]}"

echo "installer_fixture=PASS"
