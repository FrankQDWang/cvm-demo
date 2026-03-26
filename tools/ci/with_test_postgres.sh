#!/usr/bin/env bash

set -euo pipefail

if [[ "$#" -eq 0 ]]; then
  echo "usage: with_test_postgres.sh <command> [args...]" >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "${ROOT_DIR}"

export COMPOSE_PROJECT_NAME="${CVM_TEST_COMPOSE_PROJECT_NAME:-${COMPOSE_PROJECT_NAME:-cvm-test-db}}"
export CVM_POSTGRES_PORT="${CVM_TEST_POSTGRES_PORT:-15432}"
export CVM_DATABASE_URL="postgresql+psycopg://${CVM_POSTGRES_USER:-cvm}:${CVM_POSTGRES_PASSWORD:-cvm}@127.0.0.1:${CVM_POSTGRES_PORT}/${CVM_POSTGRES_DB:-cvm}"

cleanup() {
  docker compose down --remove-orphans >/dev/null 2>&1 || true
}

wait_for_postgres() {
  local container_id status
  container_id="$(docker compose ps -q postgres)"
  if [[ -z "${container_id}" ]]; then
    echo "postgres container was not created" >&2
    exit 1
  fi

  for _ in {1..60}; do
    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${container_id}" 2>/dev/null || true)"
    if [[ "${status}" == "healthy" || "${status}" == "running" ]]; then
      return 0
    fi
    sleep 1
  done

  echo "postgres did not become ready in time" >&2
  docker compose logs postgres >&2 || true
  exit 1
}

trap cleanup EXIT

echo "Starting PostgreSQL test database on ${CVM_DATABASE_URL}"
docker compose up -d --remove-orphans postgres
wait_for_postgres
"$@"
