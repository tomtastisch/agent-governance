#!/usr/bin/env bash
set -euo pipefail

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
fixture_root=$(mktemp -d "${TMPDIR:-/tmp}/agent-governance-installer.XXXXXX")
fixture_root=$(CDPATH= cd -- "$fixture_root" && pwd -P)
cleanup() { rm -rf -- "$fixture_root"; }
trap cleanup EXIT

target_root="$fixture_root/Global Target With Spaces"
installation_root="$fixture_root/installation"
entry_file="AGENTS.md"
mkdir -p -- "$target_root"
printf 'personal bytes without newline' >"$target_root/$entry_file"
original=$(od -An -tx1 "$target_root/$entry_file")

common=(
  --scope global
  --installation-root "$installation_root"
  --target-root "$target_root"
  --entry-file "$entry_file"
  --non-interactive
  --json
)

node "$repository_root/dist/cli.js" plan "${common[@]}" --dry-run
test ! -e "$installation_root"
node "$repository_root/dist/cli.js" install "${common[@]}"
node "$repository_root/dist/cli.js" verify "${common[@]}"
node "$repository_root/dist/cli.js" status "${common[@]}"
node "$repository_root/dist/cli.js" update "${common[@]}"
node "$repository_root/dist/cli.js" uninstall "${common[@]}"
test "$(od -An -tx1 "$target_root/$entry_file")" = "$original"
node "$repository_root/dist/cli.js" rollback "${common[@]}"
node "$repository_root/dist/cli.js" rollback "${common[@]}"
node "$repository_root/dist/cli.js" install "${common[@]}"
node "$repository_root/dist/cli.js" verify "${common[@]}"

echo "installer_fixture=PASS"
