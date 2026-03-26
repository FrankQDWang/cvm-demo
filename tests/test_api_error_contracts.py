from __future__ import annotations

import pytest

from tests.support.api_harness import build_test_client, close_test_client
from tests.support.flow import read_json


@pytest.mark.parametrize(
    ("method", "path", "payload", "expected_code"),
    [
        (
            "post",
            "/api/v1/cases/case_missing/jd-versions",
            {"rawText": "Need Python", "source": "manual"},
            "CASE_NOT_FOUND",
        ),
        ("get", "/api/v1/agent-runs/agent_missing", None, "AGENT_RUN_NOT_FOUND"),
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


def test_jd_version_creation_still_works_with_explicit_case(tmp_path, monkeypatch) -> None:
    client = build_test_client(tmp_path, monkeypatch)
    try:
        case = read_json(client.post("/api/v1/cases", json={"title": "AI Native Recruiter", "ownerTeamId": "team-cn"}))
        version = read_json(client.post(
            f"/api/v1/cases/{case['caseId']}/jd-versions",
            json={"rawText": "Need Python FastAPI", "source": "manual"},
        ))
        assert version["status"] == "active"
    finally:
        close_test_client(client)


def test_temporal_dispatch_failure_returns_contract_error(tmp_path, monkeypatch) -> None:
    async def failing_connect(*args, **kwargs) -> object:
        del args, kwargs
        raise OSError("temporal unavailable")

    client = build_test_client(tmp_path, monkeypatch, temporal_connect=failing_connect)
    try:
        response = client.post(
            "/api/v1/agent-runs",
            json={
                "jdText": "Need Python AI agent engineer",
                "sourcingPreferenceText": "Prefer agent and retrieval experience",
            },
        )

        assert response.status_code == 503
        assert response.json()["code"] == "TEMPORAL_START_FAILED"
        assert response.json()["retryable"] is True
    finally:
        close_test_client(client)
