from __future__ import annotations

import httpx

from cvm_testkit import unique_idempotency_key, wait_for_agent_run, wait_for_agent_temporal_diagnostic
from tests.support.flow import read_json


def test_mainline_agent_flow(client: httpx.Client) -> None:
    created = read_json(client.post(
        "/api/v1/agent-runs",
        json={
            "jdText": "需要一名 AI Agent 工程师，熟悉 Python、ReAct、workflow orchestration、search systems。",
            "sourcingPreferenceText": "优先有 agent、eval、retrieval、招聘或流程编排经验，最好在上海或杭州。",
        },
    ))
    run = wait_for_agent_run(client, created["runId"])
    diagnostic = wait_for_agent_temporal_diagnostic(client, created["runId"])

    assert run["status"] == "completed"
    assert run["workflowId"] == f"agent-run-{created['runId']}"
    assert len(run["finalShortlist"]) == 5
    assert len({candidate["externalIdentityId"] for candidate in run["finalShortlist"]}) == 5
    assert any(step["stepType"] == "strategy" for step in run["steps"])
    assert any(step["stepType"] == "search" for step in run["steps"])
    assert any(step["stepType"] == "analysis" for step in run["steps"])
    assert any(step["stepType"] == "reflection" for step in run["steps"])
    assert any(step["stepType"] == "finalize" for step in run["steps"])
    assert run["langfuseTraceUrl"] is not None
    assert diagnostic["workflowId"] == f"agent-run-{created['runId']}"
    assert diagnostic["temporalExecutionFound"] is True
    assert diagnostic["visibilityIndexed"] is True
    assert diagnostic["currentRound"] >= 1
    assert diagnostic["finalShortlistCount"] == 5
    assert diagnostic["langfuseTraceUrl"] == run["langfuseTraceUrl"]


def test_sensitive_export_is_blocked_in_local_mode(client: httpx.Client) -> None:
    case = read_json(client.post("/api/v1/cases", json={"title": "AI Native Recruiter", "ownerTeamId": "team-cn"}))
    pages = read_json(client.get("/api/v1/ops/summary"))
    blocked = client.post(
        "/api/v1/exports",
        json={"caseId": case["caseId"], "maskPolicy": "sensitive", "reason": "need contact", "idempotencyKey": unique_idempotency_key("exp-sensitive")},
    )

    assert pages["version"]["api"] == "0.1.0"
    assert pages["version"]["apiBuildId"]
    assert pages["version"]["temporalVisibilityBackend"] == "opensearch"
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "NO_CONTACT_PERMISSION"


def test_agent_run_list_returns_latest_run_first(client: httpx.Client) -> None:
    first = read_json(client.post(
        "/api/v1/agent-runs",
        json={
            "jdText": "Need Python AI agent engineer with retrieval experience",
            "sourcingPreferenceText": "Prefer agent tooling background",
        },
    ))
    second = read_json(client.post(
        "/api/v1/agent-runs",
        json={
            "jdText": "Need recruiter tooling engineer with Python and workflow experience",
            "sourcingPreferenceText": "Prefer evals and search systems background",
        },
    ))

    wait_for_agent_run(client, first["runId"])
    wait_for_agent_run(client, second["runId"])
    listing = read_json(client.get("/api/v1/agent-runs"))

    assert listing["runs"][0]["runId"] == second["runId"]
    assert listing["runs"][1]["runId"] == first["runId"]
