#!/usr/bin/env bash
set -euo pipefail

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
fixture_root=$(mktemp -d "${TMPDIR:-/tmp}/agent-governance-release-verifier.XXXXXX")
fixture_root=$(CDPATH= cd -- "$fixture_root" && pwd -P)
cleanup() { rm -rf -- "$fixture_root"; }
trap cleanup EXIT

target_root="$fixture_root/target"
installation_root="$fixture_root/installation"
entry_file="AGENTS.md"
mkdir -p -- "$target_root"

common=(
  --scope global
  --installation-root "$installation_root"
  --target-root "$target_root"
  --entry-file "$entry_file"
  --non-interactive
  --json
)

node "$repository_root/dist/cli.js" install "${common[@]}"

version=$(tr -d '\r\n' < "$repository_root/VERSION")
installed_bundle="$installation_root/releases/$version/bundle"

# Benigne Betriebssystem-Metadaten werden toleriert und lösen keinen TAMPERED-Zustand aus.
printf 'benign OS metadata\n' > "$installed_bundle/.DS_Store"
printf 'benign OS metadata\n' > "$installed_bundle/agent-governance/.DS_Store"
node "$repository_root/dist/cli.js" verify "${common[@]}"
node "$repository_root/dist/cli.js" status "${common[@]}"

# Ein beliebiger anderer, nicht gelisteter Zusatzpfad bleibt fail-closed.
printf 'stray content\n' > "$installed_bundle/stray.md"
if node "$repository_root/dist/cli.js" verify "${common[@]}" >/dev/null 2>&1; then
  echo "expected a stray non-benign file to fail release verification" >&2
  exit 1
fi

rm -f "$installed_bundle/stray.md"
node "$repository_root/dist/cli.js" verify "${common[@]}"

echo "release_verifier_benign_metadata=PASS"
