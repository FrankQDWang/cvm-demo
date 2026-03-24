#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

stop_pid() {
  local name="$1"
  local pid_file="var/run/${name}.pid"
  if [[ ! -f "$pid_file" ]]; then
    echo "$name not running"
    return 0
  fi
  local pid
  pid="$(cat "$pid_file")"
  if kill -0 "$pid" >/dev/null 2>&1; then
    kill "$pid" >/dev/null 2>&1 || true
    sleep 1
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill -9 "$pid" >/dev/null 2>&1 || true
    fi
    echo "stopped $name pid=$pid"
  else
    echo "$name pid file was stale"
  fi
  rm -f "$pid_file"
}

stop_pid web-evals
stop_pid web-ops
stop_pid web-user
stop_pid worker
stop_pid api

docker compose down
