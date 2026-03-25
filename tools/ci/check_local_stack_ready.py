from __future__ import annotations

import os
import socket
import time
from collections.abc import Callable

import httpx


def api_base_url() -> str:
    override = os.getenv("CVM_TEST_API_BASE_URL") or os.getenv("CVM_API_BASE_URL")
    if override:
        return override.rstrip("/")
    host = os.getenv("CVM_API_HOST", "127.0.0.1")
    port = os.getenv("CVM_API_PORT", "8010")
    return f"http://{host}:{port}"


def temporal_target() -> tuple[str, int]:
    host = os.getenv("CVM_TEMPORAL_HOST")
    if host:
        raw_host, _, raw_port = host.partition(":")
        return raw_host or "127.0.0.1", int(raw_port or "7233")
    return "127.0.0.1", int(os.getenv("CVM_TEMPORAL_PORT", "7233"))


def opensearch_base_url() -> str:
    override = os.getenv("CVM_OPENSEARCH_BASE_URL")
    if override:
        return override.rstrip("/")
    host = os.getenv("CVM_OPENSEARCH_HOST", "127.0.0.1")
    port = os.getenv("CVM_OPENSEARCH_PORT", "9200")
    return f"http://{host}:{port}"


def _wait_until_ready(
    check: Callable[[], None],
    failure_message: str,
    *,
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            check()
            return
        except Exception as exc:  # pragma: no cover - retry orchestration only
            last_error = exc
            time.sleep(poll_interval_seconds)

    raise RuntimeError(failure_message) from last_error


def api_healthcheck() -> None:
    endpoint = f"{api_base_url()}/api/v1/ops/summary"
    with httpx.Client(timeout=3.0, trust_env=False) as client:
        response = client.get(endpoint)
        response.raise_for_status()


def temporal_port_check() -> None:
    host, port = temporal_target()
    with socket.create_connection((host, port), timeout=3.0):
        return


def opensearch_healthcheck() -> None:
    if os.getenv("CVM_TEMPORAL_VISIBILITY_BACKEND", "opensearch") != "opensearch":
        return
    endpoint = opensearch_base_url()
    with httpx.Client(timeout=3.0, trust_env=False) as client:
        response = client.get(endpoint)
        response.raise_for_status()


def main() -> int:
    timeout_seconds = float(os.getenv("CVM_STACK_READY_TIMEOUT_SECONDS", "90"))
    poll_interval_seconds = float(os.getenv("CVM_STACK_READY_POLL_INTERVAL_SECONDS", "2"))

    api_endpoint = f"{api_base_url()}/api/v1/ops/summary"
    temporal_host, temporal_port = temporal_target()
    opensearch_endpoint = opensearch_base_url()

    _wait_until_ready(
        api_healthcheck,
        f"API 未就绪：{api_endpoint} 无法访问。请先运行 `make up`，确认 postgres、temporal、api、worker 已启动。",
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )
    _wait_until_ready(
        temporal_port_check,
        f"Temporal 未就绪：{temporal_host}:{temporal_port} 无法连接。请先运行 `make up`。",
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )
    _wait_until_ready(
        opensearch_healthcheck,
        f"OpenSearch 未就绪：{opensearch_endpoint} 无法访问。请先运行 `make rebuild-temporal-stack` 或 `make up-build`。",
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )
    print("Local stack readiness check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
