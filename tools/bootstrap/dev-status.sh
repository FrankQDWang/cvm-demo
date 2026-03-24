#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

show_pid_status() {
  local name="$1"
  local pid_file="var/run/${name}.pid"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file")"
    if kill -0 "$pid" >/dev/null 2>&1; then
      echo "$name: running (pid $pid)"
      return
    fi
    echo "$name: stale pid file ($pid)"
    return
  fi
  echo "$name: stopped"
}

show_pid_status api
show_pid_status worker
show_pid_status web-user
show_pid_status web-ops
show_pid_status web-evals
echo
docker compose ps
