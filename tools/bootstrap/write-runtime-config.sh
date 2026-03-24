#!/bin/sh
set -eu

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

APP_DIR="${1:-apps/web-user}"

if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

cat > "${APP_DIR}/public/runtime-config.js" <<EOF
window.__CVM_RUNTIME_CONFIG__ = {
  apiBaseUrl: ''
};
EOF
