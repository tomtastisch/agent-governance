#!/usr/bin/env bash
set -euo pipefail

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
fixture_root=$(mktemp -d "${TMPDIR:-/tmp}/agent-governance-package.XXXXXX")
fixture_root=$(CDPATH= cd -- "$fixture_root" && pwd -P)
cleanup() { rm -rf -- "$fixture_root"; }
trap cleanup EXIT

version=$(node -p "require('$repository_root/package.json').version")
tarball="$fixture_root/tomtastisch-agent-governance-$version.tgz"
consumer="$fixture_root/consumer"
target_root="$fixture_root/target"
mkdir -p -- "$consumer" "$target_root"

cd "$repository_root"
npm pack --pack-destination "$fixture_root" >/dev/null
test -f "$tarball"
npm install --ignore-scripts --no-audit --no-fund --prefix "$consumer" "$tarball"
cd "$consumer"

spawn_log="$fixture_root/init-spawn.log"
manager_shims="$fixture_root/manager-shims"
mkdir -p -- "$manager_shims"
for manager in npm pnpm yarn bun; do
  printf '%s\n' '#!/bin/sh' 'printf "%s\\n" "$0" >> "$AGENT_GOVERNANCE_INIT_SPAWN_LOG"' 'exit 73' > "$manager_shims/$manager"
  chmod 755 "$manager_shims/$manager"
done

consumer_bin="$consumer/node_modules/.bin/agent-governance"
"$consumer_bin" init --help >/dev/null
if init_output=$(AGENT_GOVERNANCE_INIT_SPAWN_LOG="$spawn_log" PATH="$manager_shims:$PATH" "$consumer_bin" init </dev/null 2>&1); then
  init_status=0
else
  init_status=$?
fi
test "$init_status" -eq 2
case "$init_output" in
  *'"outcome":"INVALID_INVOCATION"'*) ;;
  *) echo "init returned an unexpected non-TTY result: $init_output" >&2; exit 1 ;;
esac
test ! -s "$spawn_log"

common=(
  --scope global
  --target-root "$target_root"
  --entry-file AGENTS.md
  --non-interactive
  --json
)

install_output=$("$consumer/node_modules/.bin/agent-governance" install "${common[@]}" --installation-root "$fixture_root/direct-installation")
verify_output=$("$consumer/node_modules/.bin/agent-governance" verify "${common[@]}" --installation-root "$fixture_root/direct-installation")
node -e 'for (const value of process.argv.slice(1)) { const parsed=JSON.parse(value); if(parsed.outcome!=="SUCCESS") process.exit(1) }' "$install_output" "$verify_output"
test -f "$target_root/AGENTS.md"

missing_native_consumer="$fixture_root/missing-native-consumer"
missing_native_target="$fixture_root/missing-native-target"
mkdir -p -- "$missing_native_consumer" "$missing_native_target"
npm install --ignore-scripts --no-audit --no-fund --prefix "$missing_native_consumer" "$tarball"
rm -f -- "$missing_native_consumer/node_modules/@tomtastisch/agent-governance/prebuilds/$(node -p 'process.platform+"-"+process.arch')/agent_governance_fs.node"
if "$missing_native_consumer/node_modules/.bin/agent-governance" install \
  --scope global --target-root "$missing_native_target" --entry-file AGENTS.md \
  --installation-root "$fixture_root/missing-native-installation" --non-interactive --json >/dev/null 2>&1; then
  echo "install unexpectedly succeeded without its native capability" >&2
  exit 1
fi
test ! -e "$missing_native_target/AGENTS.md"
test ! -e "$fixture_root/missing-native-installation"

npx --yes --package "$tarball" agent-governance inspect "${common[@]}" --installation-root "$fixture_root/npx-installation"
npx --yes --package pnpm@10.15.0 pnpm dlx "$tarball" inspect "${common[@]}" --installation-root "$fixture_root/pnpm-installation"

echo "package_consumers=PASS"
