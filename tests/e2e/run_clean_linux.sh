#!/usr/bin/env bash
set -euo pipefail

source_ref=HEAD
offline=false
verify_secrets=false
hostile_matrix=false
# Hostile contract markers: init.defaultBranch=master and HOME With Spaces.

while [[ $# -gt 0 ]]; do
  case $1 in
    --source)
      source_ref=${2:?--source requires a Git ref}
      shift 2
      ;;
    --offline)
      offline=true
      shift
      ;;
    --verify-secrets)
      verify_secrets=true
      shift
      ;;
    --hostile-matrix)
      hostile_matrix=true
      shift
      ;;
    *)
      echo "run_clean_linux: unknown option: $1" >&2
      exit 2
      ;;
  esac
done

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
docker_context=${AGENT_GOVERNANCE_DOCKER_CONTEXT:?AGENT_GOVERNANCE_DOCKER_CONTEXT is required}
auth_source=${CODEX_AUTH_FILE:?CODEX_AUTH_FILE is required}

if [[ $auth_source != /* || ! -f $auth_source || -L $auth_source ]]; then
  echo "run_clean_linux: CODEX_AUTH_FILE must be an absolute regular non-symlink file" >&2
  exit 1
fi

source_sha=$(git -C "$repository_root" rev-parse "$source_ref^{commit}")
resource_suffix=${source_sha:0:12}-$$
image=agent-governance-e2e:$resource_suffix
baseline=agent-governance-e2e-baseline-$resource_suffix
governed=agent-governance-e2e-governed-$resource_suffix
shared_tmp_root=${AGENT_GOVERNANCE_E2E_TMP_ROOT:-$(dirname -- "$repository_root")}
if [[ $shared_tmp_root != /* || ! -d $shared_tmp_root || -L $shared_tmp_root ]]; then
  echo "run_clean_linux: E2E temporary root must be an absolute existing non-symlink directory" >&2
  exit 1
fi
shared_tmp_root=$(CDPATH= cd -- "$shared_tmp_root" && pwd -P)
e2e_tmp=$(mktemp -d "$shared_tmp_root/agent-governance-e2e.XXXXXX")
e2e_tmp=$(CDPATH= cd -- "$e2e_tmp" && pwd -P)
release_dir=$e2e_tmp/release
auth_dir=$e2e_tmp/auth
output_dir=$e2e_tmp/output
mkdir -p "$release_dir" "$auth_dir" "$output_dir"

docker_cli() {
  docker --context "$docker_context" "$@"
}

cleanup() {
  docker_cli rm -f "$baseline" "$governed" >/dev/null 2>&1 || true
  docker_cli image rm -f "$image" >/dev/null 2>&1 || true
  rm -rf -- "$e2e_tmp"
  if [[ ! -e $e2e_tmp ]]; then
    echo 'auth_cleanup=PASS'
  else
    echo 'auth_cleanup=FAIL' >&2
  fi
}
trap cleanup EXIT

chmod 700 "$auth_dir"
cp "$auth_source" "$auth_dir/auth.json"
chmod 600 "$auth_dir/auth.json"

git -C "$repository_root" archive "$source_sha" | tar -x -C "$release_dir"

docker_cli build \
  --file "$release_dir/tests/e2e/Dockerfile" \
  --tag "$image" \
  "$release_dir/tests/e2e"

# Docker's built-in seccomp profile blocks the user-namespace syscall used by
# Codex's bubblewrap sandbox. The isolated containers remain non-privileged and
# receive no added capabilities; Codex still runs its workspace-write sandbox.
docker_cli run --name "$baseline" \
  --security-opt seccomp=unconfined \
  --mount "type=bind,source=$release_dir,target=/release,readonly" \
  --mount "type=bind,source=$auth_dir,target=/auth-source,readonly" \
  --mount "type=bind,source=$output_dir,target=/output" \
  --tmpfs /run/e2e:rw,exec,mode=1777 \
  "$image" \
  bash /release/tests/e2e/container_entrypoint.sh baseline

docker_cli run --name "$governed" \
  --security-opt seccomp=unconfined \
  --mount "type=bind,source=$release_dir,target=/release,readonly" \
  --mount "type=bind,source=$auth_dir,target=/auth-source,readonly" \
  --mount "type=bind,source=$output_dir,target=/output" \
  --tmpfs /run/e2e:rw,exec,mode=1777 \
  "$image" \
  bash /release/tests/e2e/container_entrypoint.sh governed

if [[ $offline == true ]]; then
  docker_cli run --rm --network none \
    --mount "type=bind,source=$release_dir,target=/release,readonly" \
    --tmpfs /tmp:rw,exec,mode=1777 \
    --workdir /release \
    --env LC_ALL=C \
    --env TZ=UTC \
    "$image" \
    bash tests/e2e/run_neutral_harness.sh
  echo 'offline_runtime=PASS'
fi

if [[ $hostile_matrix == true ]]; then
  docker_cli run --rm --network none \
    --mount "type=bind,source=$release_dir,target=/release,readonly" \
    --tmpfs /tmp:rw,exec,mode=1777 \
    --workdir /release \
    --env LC_ALL=C \
    --env TZ=UTC \
    --env GIT_CONFIG_GLOBAL=/tmp/synthetic-global-gitconfig \
    "$image" \
    bash -c 'set -euo pipefail; git config --global init.defaultBranch master; python3 -m unittest tests.test_bootstrap_contract tests.test_neutral_harness -v'
  echo 'hostile_matrix=PASS'
fi

if [[ $verify_secrets == true ]]; then
  if docker_cli image history --no-trunc "$image" | grep -Eiq 'auth\.json|TOKEN=|BEGIN [A-Z ]+PRIVATE KEY'; then
    echo 'secret_isolation=FAIL' >&2
    exit 1
  fi
  docker_cli run --rm "$image" sh -c 'test ! -e /root/.codex/auth.json && test ! -e /home/e2e/.codex/auth.json'
  docker_cli export "$governed" > "$e2e_tmp/governed-export.tar"
  if tar -tf "$e2e_tmp/governed-export.tar" | grep -Eq '(^|/)auth\.json$'; then
    echo 'secret_isolation=FAIL' >&2
    exit 1
  fi
  echo 'secret_isolation=PASS'
fi

printf '%s\n' \
  "source_sha=$source_sha" \
  'base_image=PASS' \
  'baseline=PASS' \
  'governed=PASS' \
  'FRESH=PASS' \
  'CURRENT=PASS' \
  'LEGACY=PASS'
