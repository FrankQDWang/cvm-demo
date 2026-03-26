#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

mkdir -p var/log var/run var/exports

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "created .env from .env.example"
fi

set -a
source .env
set +a

api_port="${CVM_API_PORT:-8010}"
user_web_port="${CVM_USER_WEB_PORT:-4200}"
ops_web_port="${CVM_OPS_WEB_PORT:-4201}"
evals_web_port="${CVM_EVALS_WEB_PORT:-4202}"

./tools/bootstrap/write-runtime-config.sh apps/web-user
./tools/bootstrap/write-runtime-config.sh apps/web-ops

runner=()
if command -v mise >/dev/null 2>&1; then
  mise install >/dev/null
  runner=(mise exec --)
fi

run_with_runtime() {
  if (( ${#runner[@]} )); then
    "${runner[@]}" "$@"
  else
    "$@"
  fi
}

wait_for_service() {
  local service_name="$1"
  local expected="${2:-healthy}"
  local container_id=""
  local current_state=""
  local attempt=0
  while (( attempt < 60 )); do
    container_id="$(docker compose ps -q "$service_name" 2>/dev/null || true)"
    current_state="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id" 2>/dev/null || true)"
    if [[ "$current_state" == "$expected" ]]; then
      return 0
    fi
    sleep 2
    (( attempt += 1 ))
  done
  echo "service $service_name did not reach $expected, last=$current_state" >&2
  return 1
}

ensure_running() {
  local name="$1"
  shift
  local pid_file="var/run/${name}.pid"
  local log_file="var/log/${name}.log"
  if [[ -f "$pid_file" ]]; then
    local existing_pid
    existing_pid="$(cat "$pid_file")"
    if kill -0 "$existing_pid" >/dev/null 2>&1; then
      echo "$name already running with pid $existing_pid"
      return 0
    fi
    rm -f "$pid_file"
  fi
  if command -v setsid >/dev/null 2>&1; then
    nohup setsid "$@" </dev/null >"$log_file" 2>&1 &
  else
    nohup "$@" </dev/null >"$log_file" 2>&1 &
  fi
  local pid=$!
  echo "$pid" >"$pid_file"
  sleep 2
  if ! kill -0 "$pid" >/dev/null 2>&1; then
    echo "$name failed to start, check $log_file" >&2
    return 1
  fi
  echo "started $name pid=$pid"
}

run_with_runtime uv sync
run_with_runtime pnpm install
run_with_runtime make codegen

docker compose up -d
wait_for_service postgres healthy
wait_for_service temporal healthy
wait_for_service web-evals healthy

ensure_running api "${runner[@]}" uv run uvicorn cvm_platform.main:app --factory --app-dir services/platform-api/src --host 0.0.0.0 --port "$api_port"
ensure_running worker "${runner[@]}" uv run python -m cvm_worker.main
ensure_running web-user "${runner[@]}" pnpm --dir apps/web-user exec ng serve --host 0.0.0.0 --port "$user_web_port"
ensure_running web-ops "${runner[@]}" pnpm --dir apps/web-ops exec ng serve --host 0.0.0.0 --port "$ops_web_port"

echo
echo "CVM started:"
echo "- User Web: http://localhost:${user_web_port}"
echo "- Ops Web: http://localhost:${ops_web_port}"
echo "- Langfuse UI: http://localhost:${evals_web_port}"
echo "- Langfuse Login: ${CVM_LANGFUSE_INIT_USER_EMAIL:-admin@local.test} / ${CVM_LANGFUSE_INIT_USER_PASSWORD:-local-admin-pass}"
echo "- API: http://localhost:${api_port}"
echo "- Temporal UI: http://localhost:8080"
echo "- Logs: var/log/"
