from __future__ import annotations

import pytest

from cvm_testkit import unique_idempotency_key
from cvm_platform.infrastructure.adapters import MisconfiguredLLMAdapter
from tests.support.api_harness import build_test_client, close_test_client
from tests.support.flow import bootstrap_case_flow, read_json


@pytest.mark.parametrize(
    ("method", "path", "payload", "expected_code"),
    [
        (
            "post",
            "/api/v1/cases/case_missing/jd-versions",
            {"rawText": "Need Python", "source": "manual"},
            "CASE_NOT_FOUND",
        ),
        ("get", "/api/v1/search-runs/run_missing", None, "RUN_NOT_FOUND"),
        ("get", "/api/v1/case-candidates/candidate_missing", None, "CANDIDATE_NOT_FOUND"),
    ],
)
def test_missing_resources_return_not_found_envelope(client, method: str, path: str, payload: dict[str, object] | None, expected_code: str) -> None:
    kwargs = {"json": payload} if payload is not None else {}
    response = getattr(client, method)(path, **kwargs)
    assert response.status_code == 404
    assert response.json() == {
        "code": expected_code,
        "message": response.json()["message"],
        "retryable": False,
    }


def test_keyword_draft_failure_returns_contract_error(tmp_path, monkeypatch) -> None:
    client = build_test_client(
        tmp_path,
        monkeypatch,
        llm=MisconfiguredLLMAdapter("OPENAI_API_KEY is required when CVM_LLM_MODE is not stub."),
    )
    try:
        case = read_json(client.post("/api/v1/cases", json={"title": "AI Native Recruiter", "ownerTeamId": "team-cn"}))
        version = read_json(client.post(
            f"/api/v1/cases/{case['caseId']}/jd-versions",
            json={"rawText": "Need Python FastAPI", "source": "manual"},
        ))
        response = client.post(
            f"/api/v1/cases/{case['caseId']}/keyword-draft-jobs",
            json={"jdVersionId": version["jdVersionId"], "modelVersion": "gpt-5.4-mini", "promptVersion": "draft-v1"},
        )
        assert response.status_code == 400
        assert response.json()["code"] == "LLM_NOT_CONFIGURED"
        assert response.json()["retryable"] is False
    finally:
        close_test_client(client)


def test_temporal_dispatch_failure_returns_contract_error(tmp_path, monkeypatch) -> None:
    async def failing_connect(*args, **kwargs) -> object:
        del args, kwargs
        raise OSError("temporal unavailable")

    client = build_test_client(tmp_path, monkeypatch, temporal_connect=failing_connect)
    try:
        case, _, draft = bootstrap_case_flow(client)
        confirmed = read_json(client.post(
            f"/api/v1/condition-plans/{draft['planId']}:confirm",
            json={
                **draft["draft"],
                "mustTerms": ["Python"],
                "shouldTerms": ["Agent"],
                "excludeTerms": [],
                "structuredFilters": {"page": 1, "pageSize": 5},
                "confirmedBy": "consultant-1",
            },
        ))
        response = client.post(
            "/api/v1/search-runs",
            json={
                "caseId": case["caseId"],
                "planId": confirmed["planId"],
                "pageBudget": 1,
                "idempotencyKey": unique_idempotency_key("temporal-dispatch"),
            },
        )

        assert response.status_code == 503
        assert response.json()["code"] == "TEMPORAL_START_FAILED"
        assert response.json()["retryable"] is True
    finally:
        close_test_client(client)
