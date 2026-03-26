from __future__ import annotations

import argparse

import pytest

from cvm_eval_runner import cli as eval_cli
from cvm_testkit import integration


def test_api_base_url_prefers_explicit_override(monkeypatch) -> None:
    monkeypatch.setenv("CVM_TEST_API_BASE_URL", "http://example.test:9999")
    assert integration.api_base_url() == "http://example.test:9999"


def test_require_local_stack_raises_clear_error(monkeypatch) -> None:
    class BrokenClient:
        def __enter__(self) -> "BrokenClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def get(self, path: str):
            raise RuntimeError("unavailable")

    monkeypatch.setattr(integration, "build_client", lambda timeout_seconds=5.0: BrokenClient())

    with pytest.raises(RuntimeError, match="本地集成测试需要已启动的 postgres、temporal、api、worker"):
        integration.require_local_stack()


def test_wait_helpers_timeout_with_clear_message(monkeypatch) -> None:
    timeline = iter([0.0, 100.0])
    monkeypatch.setattr(integration.time, "monotonic", lambda: next(timeline))
    monkeypatch.setattr(integration.time, "sleep", lambda _: None)

    class PendingResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"status": "running", "temporalExecutionFound": False, "visibilityIndexed": False}

    class PendingClient:
        def get(self, path: str) -> PendingResponse:
            return PendingResponse()

    with pytest.raises(RuntimeError, match="未在 1 秒内完成"):
        integration.wait_for_agent_run(PendingClient(), "run_1", timeout_seconds=1.0, poll_interval_seconds=0.1)

    timeline = iter([0.0, 100.0])
    monkeypatch.setattr(integration.time, "monotonic", lambda: next(timeline))
    with pytest.raises(RuntimeError, match="Temporal visibility 索引"):
        integration.wait_for_agent_temporal_diagnostic(
            PendingClient(),
            "run_1",
            timeout_seconds=1.0,
            poll_interval_seconds=0.1,
        )


def test_eval_runner_main_supports_success_failure_and_invalid_suite(monkeypatch) -> None:
    monkeypatch.setattr(eval_cli.argparse.ArgumentParser, "parse_args", lambda self: argparse.Namespace(suite="blocking"))
    monkeypatch.setattr(eval_cli, "run_blocking_suite", lambda: {"passed": True})
    assert eval_cli.main() == 0

    monkeypatch.setattr(eval_cli, "run_blocking_suite", lambda: {"passed": False})
    assert eval_cli.main() == 1

    monkeypatch.setattr(eval_cli.argparse.ArgumentParser, "parse_args", lambda self: argparse.Namespace(suite="custom"))
    with pytest.raises(SystemExit, match="Only blocking suite is implemented."):
        eval_cli.main()
