from __future__ import annotations

import httpx

from cvm_testkit import unique_idempotency_key, wait_for_search_run, wait_for_temporal_diagnostic
from tests.support.flow import bootstrap_case_flow, read_json


def test_mainline_flow(client: httpx.Client) -> None:
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
    run = read_json(client.post(
        "/api/v1/search-runs",
        json={
            "caseId": case["caseId"],
            "planId": confirmed["planId"],
            "pageBudget": 1,
            "idempotencyKey": unique_idempotency_key("test-mainline-run"),
        },
    ))
    run_status = wait_for_search_run(client, run["runId"])
    diagnostic = wait_for_temporal_diagnostic(client, run["runId"])
    pages = read_json(client.get(f"/api/v1/search-runs/{run['runId']}/pages"))
    assert pages["snapshots"][0]["candidates"]
    candidate_id = pages["snapshots"][0]["candidates"][0]["candidateId"]
    detail = read_json(client.get(f"/api/v1/case-candidates/{candidate_id}"))
    verdict = read_json(client.put(
        f"/api/v1/case-candidates/{candidate_id}/verdict",
        json={"verdict": "Match", "reasons": ["core fit"], "notes": "strong", "actorId": "consultant-1"},
    ))
    export = read_json(client.post(
        "/api/v1/exports",
        json={"caseId": case["caseId"], "maskPolicy": "masked", "reason": "weekly shortlist", "idempotencyKey": unique_idempotency_key("exp-mainline")},
    ))

    assert run_status["status"] == "completed"
    assert diagnostic["workflowId"] == f"search-run-{run['runId']}"
    assert diagnostic["namespace"] == "default"
    assert diagnostic["temporalExecutionFound"] is True
    assert diagnostic["visibilityIndexed"] is True
    assert len(pages["snapshots"]) == 1
    assert detail["candidate"]["candidateId"] == candidate_id
    assert verdict["latestVerdict"] == "Match"
    assert export["status"] == "completed"


def test_zero_results_and_parameter_anomaly_are_distinct(client: httpx.Client) -> None:
    case, _, draft = bootstrap_case_flow(client)

    zero_plan = read_json(client.post(
        f"/api/v1/condition-plans/{draft['planId']}:confirm",
        json={
            **draft["draft"],
            "mustTerms": ["unlikely-non-match-term"],
            "shouldTerms": [],
            "structuredFilters": {"page": 1, "pageSize": 5},
            "confirmedBy": "consultant-1",
        },
    ))
    zero_run = read_json(client.post(
        "/api/v1/search-runs",
        json={
            "caseId": case["caseId"],
            "planId": zero_plan["planId"],
            "pageBudget": 1,
            "idempotencyKey": unique_idempotency_key("zero-run"),
        },
    ))
    zero_status = wait_for_search_run(client, zero_run["runId"])
    zero_diagnostic = wait_for_temporal_diagnostic(client, zero_run["runId"])
    zero_pages = read_json(client.get(f"/api/v1/search-runs/{zero_run['runId']}/pages"))

    assert zero_status["status"] == "completed"
    assert zero_diagnostic["temporalExecutionFound"] is True
    assert zero_diagnostic["visibilityIndexed"] is True
    assert zero_pages["snapshots"][0]["total"] == 0
    assert zero_pages["snapshots"][0]["errorCode"] is None

    anomaly_case, _, anomaly_draft = bootstrap_case_flow(client)
    anomaly_plan = client.post(
        f"/api/v1/condition-plans/{anomaly_draft['planId']}:confirm",
        json={
            **anomaly_draft["draft"],
            "structuredFilters": {"page": 1, "pageSize": 0},
            "confirmedBy": "consultant-1",
        },
    )

    assert anomaly_plan.status_code == 400
    assert anomaly_plan.json()["code"] == "INVALID_REQUEST"


def test_sensitive_export_is_blocked_in_local_mode(client: httpx.Client) -> None:
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
    run = read_json(client.post(
        "/api/v1/search-runs",
        json={
            "caseId": case["caseId"],
            "planId": confirmed["planId"],
            "pageBudget": 1,
            "idempotencyKey": unique_idempotency_key("export-run"),
        },
    ))
    wait_for_search_run(client, run["runId"])
    diagnostic = wait_for_temporal_diagnostic(client, run["runId"])
    pages = read_json(client.get("/api/v1/ops/summary"))
    blocked = client.post(
        "/api/v1/exports",
        json={"caseId": case["caseId"], "maskPolicy": "sensitive", "reason": "need contact", "idempotencyKey": unique_idempotency_key("exp-sensitive")},
    )

    assert pages["version"]["api"] == "0.1.0"
    assert pages["version"]["apiBuildId"]
    assert pages["version"]["temporalVisibilityBackend"] == "opensearch"
    assert diagnostic["workflowId"] == f"search-run-{run['runId']}"
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "NO_CONTACT_PERMISSION"
