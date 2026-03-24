from __future__ import annotations

import os
import socket

import httpx


def api_base_url() -> str:
    override = os.getenv("CVM_TEST_API_BASE_URL") or os.getenv("CVM_API_BASE_URL")
    if override:
        return override.rstrip("/")
    return f"http://127.0.0.1:{os.getenv('CVM_API_PORT', '8010')}"


def temporal_target() -> tuple[str, int]:
    host = os.getenv("CVM_TEMPORAL_HOST")
    if host:
        raw_host, _, raw_port = host.partition(":")
        return raw_host or "127.0.0.1", int(raw_port or "7233")
    return "127.0.0.1", int(os.getenv("CVM_TEMPORAL_PORT", "7233"))


def api_healthcheck() -> None:
    endpoint = f"{api_base_url()}/api/v1/ops/summary"
    try:
        with httpx.Client(timeout=3.0, trust_env=False) as client:
            response = client.get(endpoint)
            response.raise_for_status()
    except Exception as exc:  # pragma: no cover - failure path only
        raise RuntimeError(
            f"API 未就绪：{endpoint} 无法访问。请先运行 `make up`，确认 postgres、temporal、api、worker 已启动。"
        ) from exc


def temporal_port_check() -> None:
    host, port = temporal_target()
    try:
        with socket.create_connection((host, port), timeout=3.0):
            return
    except OSError as exc:  # pragma: no cover - failure path only
        raise RuntimeError(
            f"Temporal 未就绪：{host}:{port} 无法连接。请先运行 `make up`。"
        ) from exc


def opensearch_healthcheck() -> None:
    if os.getenv("CVM_TEMPORAL_VISIBILITY_BACKEND", "opensearch") != "opensearch":
        return
    port = os.getenv("CVM_OPENSEARCH_PORT", "9200")
    endpoint = f"http://127.0.0.1:{port}"
    try:
        with httpx.Client(timeout=3.0, trust_env=False) as client:
            response = client.get(endpoint)
            response.raise_for_status()
    except Exception as exc:  # pragma: no cover - failure path only
        raise RuntimeError(
            f"OpenSearch 未就绪：{endpoint} 无法访问。请先运行 `make rebuild-temporal-stack` 或 `make up-build`。"
        ) from exc


def main() -> int:
    api_healthcheck()
    temporal_port_check()
    opensearch_healthcheck()
    print("Local stack readiness check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
