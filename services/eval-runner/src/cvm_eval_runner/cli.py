from __future__ import annotations

import argparse
import os
from collections.abc import Mapping
from typing import cast

import httpx

from cvm_testkit import (
    build_client,
    require_local_stack,
    wait_for_agent_temporal_diagnostic,
    wait_for_agent_run,
)


JsonObject = dict[str, object]


def read_json(response: httpx.Response) -> JsonObject:
    response.raise_for_status()
    payload: object = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Expected JSON object response from the API.")
    return cast(JsonObject, payload)


def _get_required_str(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"Expected non-empty string field: {key}")
    return value


def _get_required_list(payload: Mapping[str, object], key: str) -> list[object]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise RuntimeError(f"Expected list field: {key}")
    return cast(list[object], value)


def _get_optional_str(payload: Mapping[str, object], key: str) -> str | None:
    value = payload.get(key)
    if isinstance(value, str) and value:
        return value
    return None


def _step_has_type(step: object, expected_step_type: str) -> bool:
    if not isinstance(step, dict):
        return False
    step_payload = cast(Mapping[str, object], step)
    return step_payload.get("stepType") == expected_step_type


def _build_suite_result(
    *,
    run_status: Mapping[str, object],
    diagnostic: Mapping[str, object],
    shortlist_count: int,
    strategy_recorded: bool,
    finalize_recorded: bool,
    trace_available: bool,
    failure_reason: str | None = None,
) -> dict[str, object]:
    langfuse_required = _langfuse_trace_required()
    checks = {
        "runCompleted": _get_optional_str(run_status, "status") == "completed",
        "temporalExecutionFound": diagnostic.get("temporalExecutionFound") is True,
        "temporalVisibilityIndexed": diagnostic.get("visibilityIndexed") is True,
        "shortlistReturned": shortlist_count == 5,
        "strategyRecorded": strategy_recorded,
        "finalizeRecorded": finalize_recorded,
        "langfuseTraceAvailable": trace_available if langfuse_required else True,
    }
    result: dict[str, object] = {
        "suite": "blocking",
        "passed": all(checks.values()),
        "checks": checks,
    }
    if failure_reason is not None:
        result["failureReason"] = failure_reason
    return result


def _langfuse_trace_required() -> bool:
    public_key = os.getenv("CVM_LANGFUSE_PUBLIC_KEY", "").strip()
    secret_key = os.getenv("CVM_LANGFUSE_SECRET_KEY", "").strip()
    return bool(public_key and secret_key)


def run_blocking_suite() -> dict[str, object]:
    require_local_stack()
    with build_client(timeout_seconds=15.0) as client:
        confirmed = read_json(client.post(
            "/api/v1/agent-runs",
            json={
                "jdText": "Need AI agent engineer with Python, ReAct, workflow orchestration, and retrieval experience",
                "sourcingPreferenceText": "Prefer recruiting, evals, search systems, and shortlist reasoning experience",
            },
        ))
        run_id = _get_required_str(confirmed, "runId")
        run_status = wait_for_agent_run(client, run_id)
        diagnostic = wait_for_agent_temporal_diagnostic(client, run_id)
        status = _get_optional_str(run_status, "status") or "unknown"
        shortlist = _get_required_list(run_status, "finalShortlist")
        steps = _get_required_list(run_status, "steps")
        strategy_recorded = any(_step_has_type(step, "strategy") for step in steps)
        finalize_recorded = any(_step_has_type(step, "finalize") for step in steps)
        trace_available = _get_optional_str(run_status, "langfuseTraceUrl") is not None

        if status != "completed":
            return _build_suite_result(
                run_status=run_status,
                diagnostic=diagnostic,
                shortlist_count=len(shortlist),
                strategy_recorded=strategy_recorded,
                finalize_recorded=finalize_recorded,
                trace_available=trace_available,
                failure_reason=(
                    _get_optional_str(run_status, "errorMessage")
                    or f"Agent run finished with status={status}."
                ),
            )

    return _build_suite_result(
        run_status=run_status,
        diagnostic=diagnostic,
        shortlist_count=len(shortlist),
        strategy_recorded=strategy_recorded,
        finalize_recorded=finalize_recorded,
        trace_available=trace_available,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=("blocking",), default="blocking")
    args = parser.parse_args()
    if args.suite != "blocking":
        raise SystemExit("Only blocking suite is implemented.")
    result = run_blocking_suite()
    print(result)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
