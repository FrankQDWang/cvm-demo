#!/usr/bin/env bash

set -euo pipefail

output_dir="${1:?usage: collect_compose_diagnostics.sh <output_dir>}"

mkdir -p "${output_dir}"

capture() {
  local name="$1"
  shift
  local command="$*"

  {
    echo "$ ${command}"
    bash -lc "${command}"
  } >"${output_dir}/${name}.txt" 2>&1 || true
}

{
  echo "CI=${CI:-}"
  echo "RUNNER_NAME=${RUNNER_NAME:-}"
  echo "RUNNER_OS=${RUNNER_OS:-}"
  echo "RUNNER_ARCH=${RUNNER_ARCH:-}"
  echo "GITHUB_WORKFLOW=${GITHUB_WORKFLOW:-}"
  echo "GITHUB_RUN_ID=${GITHUB_RUN_ID:-}"
  echo "GITHUB_REF=${GITHUB_REF:-}"
  echo "COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME:-}"
  echo "CVM_API_PORT=${CVM_API_PORT:-}"
  echo "CVM_TEMPORAL_PORT=${CVM_TEMPORAL_PORT:-}"
  echo "CVM_TEMPORAL_UI_PORT=${CVM_TEMPORAL_UI_PORT:-}"
  echo "CVM_OPENSEARCH_PORT=${CVM_OPENSEARCH_PORT:-}"
} >"${output_dir}/env_snapshot.txt"

capture docker-version "docker version"
capture docker-info "docker info"
capture compose-config "docker compose config"
capture compose-services "docker compose config --services"
capture compose-ps "docker compose ps --all"
capture compose-images "docker compose images"
capture compose-logs "docker compose logs --timestamps --no-color"

echo "Collected compose diagnostics in ${output_dir}"
