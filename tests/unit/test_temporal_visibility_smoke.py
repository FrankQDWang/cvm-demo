from __future__ import annotations

import httpx
import pytest

from tools.smoke import temporal_visibility_smoke as smoke


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


class FakeClient:
    def __init__(self) -> None:
        self._responses = iter(
            [
                {"caseId": "case_1"},
                {"jdVersionId": "jd_1"},
                {"planId": "plan_1", "draft": {}},
                {"planId": "plan_1"},
                {"runId": "run_1"},
            ]
        )

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def post(self, path: str, json: dict[str, object]) -> FakeResponse:
        del path, json
        return FakeResponse(next(self._responses))


class RetryingUiClient:
    def __init__(self, outcomes: list[object]) -> None:
        self._outcomes = outcomes

    def __enter__(self) -> "RetryingUiClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def get(self, path: str, params: dict[str, object]) -> FakeResponse:
        del path, params
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        assert isinstance(outcome, dict)
        return FakeResponse(outcome)


def test_temporal_visibility_smoke_requires_completed_run(monkeypatch) -> None:
    monkeypatch.setattr(smoke, "require_local_stack", lambda: None)
    monkeypatch.setattr(smoke, "build_client", lambda timeout_seconds=20.0: FakeClient())
    monkeypatch.setattr(smoke, "unique_idempotency_key", lambda prefix: f"{prefix}-1")
    monkeypatch.setattr(
        smoke,
        "wait_for_search_run",
        lambda client, run_id: {"status": "failed", "errorSummary": "CTS response invalid"},
    )
    monkeypatch.setattr(
        smoke,
        "wait_for_temporal_diagnostic",
        lambda client, run_id: {
            "runId": run_id,
            "workflowId": "search-run-run_1",
            "namespace": "default",
            "appStatus": "failed",
            "temporalExecutionFound": True,
            "visibilityIndexed": True,
            "temporalUiUrl": "http://127.0.0.1:8080",
        },
    )
    monkeypatch.setattr(smoke, "assert_cli_visibility", lambda workflow_id, namespace: None)
    monkeypatch.setattr(smoke, "assert_ui_visibility", lambda workflow_id, namespace: None)

    with pytest.raises(RuntimeError, match="未成功完成"):
        smoke.main()


def test_temporal_visibility_smoke_rejects_failed_app_status(monkeypatch) -> None:
    monkeypatch.setattr(smoke, "require_local_stack", lambda: None)
    monkeypatch.setattr(smoke, "build_client", lambda timeout_seconds=20.0: FakeClient())
    monkeypatch.setattr(smoke, "unique_idempotency_key", lambda prefix: f"{prefix}-1")
    monkeypatch.setattr(smoke, "wait_for_search_run", lambda client, run_id: {"status": "completed"})
    monkeypatch.setattr(
        smoke,
        "wait_for_temporal_diagnostic",
        lambda client, run_id: {
            "runId": run_id,
            "workflowId": "search-run-run_1",
            "namespace": "default",
            "appStatus": "failed",
            "temporalExecutionFound": True,
            "visibilityIndexed": True,
            "temporalUiUrl": "http://127.0.0.1:8080",
        },
    )
    monkeypatch.setattr(smoke, "assert_cli_visibility", lambda workflow_id, namespace: None)
    monkeypatch.setattr(smoke, "assert_ui_visibility", lambda workflow_id, namespace: None)

    with pytest.raises(RuntimeError, match="appStatus=failed"):
        smoke.main()


def test_assert_ui_visibility_retries_transient_ui_errors(monkeypatch) -> None:
    request = httpx.Request("GET", "http://127.0.0.1:18080/api/v1/namespaces/default/workflow-count")
    outcomes: list[object] = [
        httpx.ReadError("connection reset", request=request),
        {"count": 1},
    ]

    monkeypatch.setattr(smoke, "temporal_ui_base_url", lambda: "http://127.0.0.1:18080")
    monkeypatch.setattr(smoke.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(smoke.httpx, "Client", lambda timeout=10.0, trust_env=False: RetryingUiClient(outcomes))

    smoke.assert_ui_visibility("search-run-run_1", "default")
