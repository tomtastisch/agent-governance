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

common=(
  --scope global
  --target-root "$target_root"
  --entry-file AGENTS.md
  --non-interactive
  --json
)

"$consumer/node_modules/.bin/agent-governance" install "${common[@]}" --installation-root "$fixture_root/direct-installation"
"$consumer/node_modules/.bin/agent-governance" verify "${common[@]}" --installation-root "$fixture_root/direct-installation"
npx --yes --package "$tarball" agent-governance inspect "${common[@]}" --installation-root "$fixture_root/npx-installation"
npx --yes --package pnpm@10.15.0 pnpm dlx "$tarball" inspect "${common[@]}" --installation-root "$fixture_root/pnpm-installation"

echo "package_consumers=PASS"
