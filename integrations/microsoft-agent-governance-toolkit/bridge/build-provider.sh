#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: build-provider.sh ABSOLUTE_OUTPUT" >&2
  exit 2
fi

requested_output=$1
if [[ $requested_output != /* ]]; then
  echo "build-provider: output must be absolute" >&2
  exit 2
fi

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
integration_dir=$(CDPATH= cd -- "$script_dir/.." && pwd -P)
archive="$integration_dir/upstream/agent-governance-toolkit-v4.1.0.tar.gz"
manifest="$integration_dir/snapshot.files.sha256"
lock="$integration_dir/upstream.lock.toml"
extractor="$script_dir/extract-snapshot.py"

expected_hash=$(python3 - "$lock" <<'PY'
import sys
import tomllib
with open(sys.argv[1], "rb") as handle:
    print(tomllib.load(handle)["archive_sha256"])
PY
)

requested_parent=$(dirname -- "$requested_output")
output_name=$(basename -- "$requested_output")
if [[ $output_name == "." || $output_name == ".." || $output_name == */* ]]; then
  echo "build-provider: invalid output name" >&2
  exit 2
fi
if [[ ! -d $requested_parent ]]; then
  echo "build-provider: output parent does not exist" >&2
  exit 2
fi
physical_parent=$(CDPATH= cd -- "$requested_parent" && pwd -P)
output="$physical_parent/$output_name"

if [[ -L $output ]]; then
  echo "build-provider: output symlink is forbidden" >&2
  exit 1
fi
if [[ -e $output ]]; then
  if [[ -f $output/build.receipt && -f $output/microsoft-sdk/dist/policy.js ]] \
      && grep -Fxq "archive_sha256=$expected_hash" "$output/build.receipt"; then
    echo "build-provider: PASS (current)"
    exit 0
  fi
  echo "build-provider: existing output is not the current verified runtime" >&2
  exit 1
fi

stage=$(mktemp -d "$physical_parent/.agent-governance-provider.XXXXXX")
cleanup() {
  if [[ -n ${stage:-} && -d $stage ]]; then
    rm -rf -- "$stage"
  fi
}
trap cleanup EXIT

python3 "$extractor" "$archive" "$manifest" "$stage/source" "$expected_hash"
sdk_source="$stage/source/agent-governance-toolkit-4.1.0/agent-governance-typescript"
if [[ ! -f $sdk_source/package-lock.json || ! -f $sdk_source/src/policy.ts ]]; then
  echo "build-provider: pinned TypeScript SDK source is incomplete" >&2
  exit 1
fi

(
  cd "$sdk_source"
  npm ci --ignore-scripts --no-audit --no-fund
  npm run build
  npm prune --omit=dev --ignore-scripts --no-audit --no-fund
)

mkdir -p "$stage/runtime/microsoft-sdk"
cp -R "$sdk_source/dist" "$stage/runtime/microsoft-sdk/dist"
cp -R "$sdk_source/node_modules" "$stage/runtime/microsoft-sdk/node_modules"
cp "$sdk_source/package.json" "$stage/runtime/microsoft-sdk/package.json"
cp "$sdk_source/package-lock.json" "$stage/runtime/microsoft-sdk/package-lock.json"
printf 'archive_sha256=%s\nresolved_tag=v4.1.0\nresolved_commit=0de71ca6c95cf8b9b975ac96f48eaa7826bbe258\n' \
  "$expected_hash" > "$stage/runtime/build.receipt"
mv "$stage/runtime" "$output"

echo "build-provider: PASS"
