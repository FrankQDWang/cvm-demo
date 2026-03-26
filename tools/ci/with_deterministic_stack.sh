#!/usr/bin/env bash

set -euo pipefail

if [[ "$#" -eq 0 ]]; then
  echo "usage: with_deterministic_stack.sh <command> [args...]" >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "${ROOT_DIR}"

export COMPOSE_PROJECT_NAME="${CVM_TEST_COMPOSE_PROJECT_NAME:-cvm-test}"
export CVM_RESUME_SOURCE_MODE="mock"
export CVM_AGENT_PROFILE="deterministic"
export CVM_AGENT_MODEL="${CVM_AGENT_MODEL:-gpt-5.4-mini}"
export CVM_AGENT_MODEL_TIMEOUT_SECONDS="${CVM_AGENT_MODEL_TIMEOUT_SECONDS:-30}"
export CVM_AGENT_MIN_ROUNDS="${CVM_AGENT_MIN_ROUNDS:-3}"
export CVM_AGENT_MAX_ROUNDS="${CVM_AGENT_MAX_ROUNDS:-5}"
export CVM_AGENT_ROUND_FETCH_SCHEDULE="${CVM_AGENT_ROUND_FETCH_SCHEDULE:-10,5,5}"
export CVM_AGENT_FINAL_TOP_K="${CVM_AGENT_FINAL_TOP_K:-5}"
export CVM_POSTGRES_PORT="${CVM_TEST_POSTGRES_PORT:-15432}"
export CVM_API_PORT="${CVM_TEST_API_PORT:-18010}"
export CVM_TEMPORAL_PORT="${CVM_TEST_TEMPORAL_PORT:-17233}"
export CVM_TEMPORAL_UI_PORT="${CVM_TEST_TEMPORAL_UI_PORT:-18080}"
export CVM_OPENSEARCH_PORT="${CVM_TEST_OPENSEARCH_PORT:-19200}"
export CVM_TEST_API_BASE_URL="http://127.0.0.1:${CVM_API_PORT}"
export CVM_TEMPORAL_HOST="127.0.0.1:${CVM_TEMPORAL_PORT}"
export CVM_TEMPORAL_UI_BASE_URL="http://127.0.0.1:${CVM_TEMPORAL_UI_PORT}"
export CVM_OPENSEARCH_BASE_URL="http://127.0.0.1:${CVM_OPENSEARCH_PORT}"
export CVM_LANGFUSE_PUBLIC_KEY=""
export CVM_LANGFUSE_SECRET_KEY=""
export CVM_LANGFUSE_HOST=""
export CVM_LANGFUSE_BASE_URL=""

cleanup() {
  docker compose down --remove-orphans >/dev/null 2>&1 || true
}

trap cleanup EXIT

echo "Starting deterministic test stack (project=${COMPOSE_PROJECT_NAME}, api=${CVM_TEST_API_BASE_URL})"
docker compose up -d --build --remove-orphans postgres opensearch temporal temporal-ui temporal-admin-tools api worker
"$@"
