from __future__ import annotations

import os
import time
from typing import cast
from uuid import uuid4

import httpx


def _read_json_object(response: httpx.Response) -> dict[str, object]:
    payload: object = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Expected JSON object response from the API.")
    return cast(dict[str, object], payload)


def api_base_url() -> str:
    override = os.getenv("CVM_TEST_API_BASE_URL") or os.getenv("CVM_API_BASE_URL")
    if override:
        return override.rstrip("/")
    return f"http://127.0.0.1:{os.getenv('CVM_API_PORT', '8010')}"


def build_client(timeout_seconds: float = 10.0) -> httpx.Client:
    return httpx.Client(base_url=api_base_url(), timeout=timeout_seconds, trust_env=False)


def require_local_stack(timeout_seconds: float = 5.0) -> None:
    try:
        with build_client(timeout_seconds=timeout_seconds) as client:
            response = client.get("/api/v1/ops/summary")
            response.raise_for_status()
    except Exception as exc:  # pragma: no cover - failure path only
        raise RuntimeError(
            "本地集成测试需要已启动的 postgres、temporal、api、worker。请先运行 `make up`。"
        ) from exc


def unique_idempotency_key(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def wait_for_agent_run(
    client: httpx.Client,
    run_id: str,
    timeout_seconds: float = 45.0,
    poll_interval_seconds: float = 0.5,
) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    latest_status: dict[str, object] | None = None

    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/agent-runs/{run_id}")
        response.raise_for_status()
        latest_status = _read_json_object(response)
        if latest_status.get("status") in {"completed", "failed"}:
            return latest_status
        time.sleep(poll_interval_seconds)

    raise RuntimeError(
        f"Agent run {run_id} 未在 {timeout_seconds:.0f} 秒内完成。"
        "请确认 api、worker、temporal、postgres 已启动且 worker 正在消费任务。"
    )


def wait_for_agent_temporal_diagnostic(
    client: httpx.Client,
    run_id: str,
    timeout_seconds: float = 45.0,
    poll_interval_seconds: float = 0.5,
) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    latest_diagnostic: dict[str, object] | None = None

    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/ops/temporal/agent-runs/{run_id}")
        response.raise_for_status()
        latest_diagnostic = _read_json_object(response)
        if latest_diagnostic.get("temporalExecutionFound") and latest_diagnostic.get("visibilityIndexed"):
            return latest_diagnostic
        time.sleep(poll_interval_seconds)

    raise RuntimeError(
        f"Agent run {run_id} 未在 {timeout_seconds:.0f} 秒内完成 Temporal visibility 索引。"
        "请确认 temporal、worker、opensearch 已启动。"
    )
