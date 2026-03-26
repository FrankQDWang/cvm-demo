from __future__ import annotations

from cvm_platform.domain.types import SearchPageData
from cvm_eval_runner import cli
from cvm_eval_runner.cli import run_blocking_suite
from tests.support.api_harness import build_test_client, close_test_client


def test_blocking_suite_passes(tmp_path, monkeypatch) -> None:
    client = build_test_client(tmp_path, monkeypatch)
    monkeypatch.setattr(cli, "require_local_stack", lambda: None)
    monkeypatch.setattr(cli, "build_client", lambda timeout_seconds=15.0: client)

    try:
        result = run_blocking_suite()
    finally:
        close_test_client(client)
    assert result["passed"] is True


def test_blocking_suite_returns_failure_result_when_agent_run_fails(tmp_path, monkeypatch) -> None:
    class FailedResumeSource:
        def search_candidates(self, normalized_query, page_no: int, page_size: int) -> SearchPageData:
            del normalized_query
            return SearchPageData(
                status="failed",
                total=0,
                page_no=page_no,
                page_size=page_size,
                candidates=[],
                upstream_request={"page": page_no, "pageSize": page_size},
                upstream_response={"status": "fail"},
                error_code="CTS_RESPONSE_INVALID",
                error_message="CTS response did not match the validated schema.",
            )

    client = build_test_client(tmp_path, monkeypatch, resume_source=FailedResumeSource())
    monkeypatch.setattr(cli, "require_local_stack", lambda: None)
    monkeypatch.setattr(cli, "build_client", lambda timeout_seconds=15.0: client)

    try:
        result = run_blocking_suite()
    finally:
        close_test_client(client)

    assert result["passed"] is False
    assert result["checks"]["runCompleted"] is False
    assert result["checks"]["shortlistReturned"] is False
    assert "CTS response did not match the validated schema" in str(result["failureReason"])
