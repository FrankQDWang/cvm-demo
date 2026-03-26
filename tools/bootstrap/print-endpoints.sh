#!/bin/sh
set -eu

if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

USER_WEB_PORT="${CVM_USER_WEB_PORT:-4200}"
OPS_WEB_PORT="${CVM_OPS_WEB_PORT:-4201}"
EVALS_WEB_PORT="${CVM_EVALS_WEB_PORT:-4202}"
API_PORT="${CVM_API_PORT:-8010}"
TEMPORAL_UI_PORT="${CVM_TEMPORAL_UI_PORT:-8080}"
TEMPORAL_PORT="${CVM_TEMPORAL_PORT:-7233}"
OPENSEARCH_PORT="${CVM_OPENSEARCH_PORT:-9200}"

printf '\n'
printf '可访问地址：\n'
printf '  User Web:    http://127.0.0.1:%s\n' "$USER_WEB_PORT"
printf '  Ops Web:     http://127.0.0.1:%s\n' "$OPS_WEB_PORT"
printf '  Langfuse UI: http://127.0.0.1:%s\n' "$EVALS_WEB_PORT"
printf '  API:         http://127.0.0.1:%s\n' "$API_PORT"
printf '  Temporal UI: http://127.0.0.1:%s\n' "$TEMPORAL_UI_PORT"
printf '  Temporal:    127.0.0.1:%s\n' "$TEMPORAL_PORT"
printf '  OpenSearch:  http://127.0.0.1:%s\n' "$OPENSEARCH_PORT"
printf '  Langfuse:    %s / %s\n' "${CVM_LANGFUSE_INIT_USER_EMAIL:-admin@local.test}" "${CVM_LANGFUSE_INIT_USER_PASSWORD:-local-admin-pass}"
printf '\n'
printf '常用命令：\n'
printf '  make status\n'
printf '  make down\n'
printf '  make up-build\n'
printf '  make rebuild-backend\n'
printf '  make rebuild-temporal-stack\n'
printf '  make temporal-visibility-smoke\n'
