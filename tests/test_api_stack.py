from __future__ import annotations

import httpx
import pytest

from cvm_testkit import unique_idempotency_key, wait_for_search_run, wait_for_temporal_diagnostic
from tests.support.flow import read_json


@pytest.mark.stack
def test_stack_mainline_flow(stack_client: httpx.Client) -> None:
    case_suffix = unique_idempotency_key("case")
    case = read_json(
        stack_client.post(
            "/api/v1/cases",
            json={"title": f"AI Native Recruiter {case_suffix}", "ownerTeamId": "team-cn"},
        )
    )
    version = read_json(
        stack_client.post(
            f"/api/v1/cases/{case['caseId']}/jd-versions",
            json={
                "rawText": "Need Python FastAPI Angular Temporal search experience",
                "source": "manual",
            },
        )
    )
    draft = read_json(
        stack_client.post(
            f"/api/v1/cases/{case['caseId']}/keyword-draft-jobs",
            json={
                "jdVersionId": version["jdVersionId"],
                "modelVersion": "gpt-5.4-mini",
                "promptVersion": "draft-v1",
            },
        )
    )
    confirmed = read_json(
        stack_client.post(
            f"/api/v1/condition-plans/{draft['planId']}:confirm",
            json={
                **draft["draft"],
                "mustTerms": ["Python"],
                "shouldTerms": ["Agent"],
                "excludeTerms": [],
                "structuredFilters": {"page": 1, "pageSize": 5},
                "confirmedBy": "consultant-1",
            },
        )
    )
    run = read_json(
        stack_client.post(
            "/api/v1/search-runs",
            json={
                "caseId": case["caseId"],
                "planId": confirmed["planId"],
                "pageBudget": 1,
                "idempotencyKey": unique_idempotency_key("stack-mainline-run"),
            },
        )
    )

    run_status = wait_for_search_run(stack_client, run["runId"])
    diagnostic = wait_for_temporal_diagnostic(stack_client, run["runId"])
    pages = read_json(stack_client.get(f"/api/v1/search-runs/{run['runId']}/pages"))

    assert run_status["status"] == "completed"
    assert diagnostic["workflowId"] == f"search-run-{run['runId']}"
    assert diagnostic["temporalExecutionFound"] is True
    assert diagnostic["visibilityIndexed"] is True
    assert pages["snapshots"][0]["candidates"]
