#!/usr/bin/env bash

set -euo pipefail

set +e
make eval-critical
status="$?"
set -e

if [[ "${status}" -eq 0 ]]; then
  echo "Blocking eval gate passed."
  exit 0
fi

echo "EVAL_BLOCKING_FAILED: blocking eval suite failed." >&2
exit "${status}"
