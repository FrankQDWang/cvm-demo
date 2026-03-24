from __future__ import annotations


def bootstrap_case_flow(client):
    case = client.post("/api/v1/cases", json={"title": "AI Native Recruiter", "ownerTeamId": "team-cn"}).json()
    version = client.post(
        f"/api/v1/cases/{case['caseId']}/jd-versions",
        json={"rawText": "Need Python FastAPI Angular Temporal search experience", "source": "manual"},
    ).json()
    draft = client.post(
        f"/api/v1/cases/{case['caseId']}/keyword-draft-jobs",
        json={"jdVersionId": version["jdVersionId"], "modelVersion": "stub-1", "promptVersion": "draft-v1"},
    ).json()
    return case, version, draft


def test_mainline_flow(client) -> None:
    case, _, draft = bootstrap_case_flow(client)
    confirmed = client.post(
        f"/api/v1/condition-plans/{draft['planId']}:confirm",
        json={**draft["draft"], "confirmedBy": "consultant-1"},
    ).json()
    run = client.post(
        "/api/v1/search-runs",
        json={
            "caseId": case["caseId"],
            "planId": confirmed["planId"],
            "pageBudget": 1,
            "idempotencyKey": "test-mainline-run",
        },
    ).json()
    run_status = client.get(f"/api/v1/search-runs/{run['runId']}").json()
    pages = client.get(f"/api/v1/search-runs/{run['runId']}/pages").json()
    candidate_id = pages["snapshots"][0]["candidates"][0]["candidateId"]
    detail = client.get(f"/api/v1/case-candidates/{candidate_id}").json()
    verdict = client.put(
        f"/api/v1/case-candidates/{candidate_id}/verdict",
        json={"verdict": "Match", "reasons": ["core fit"], "notes": "strong", "actorId": "consultant-1"},
    ).json()
    export = client.post(
        "/api/v1/exports",
        json={"caseId": case["caseId"], "maskPolicy": "masked", "reason": "weekly shortlist", "idempotencyKey": "exp-mainline"},
    ).json()

    assert run_status["status"] == "completed"
    assert len(pages["snapshots"]) == 1
    assert detail["candidate"]["candidateId"] == candidate_id
    assert verdict["latestVerdict"] == "Match"
    assert export["status"] == "completed"


def test_zero_results_and_parameter_anomaly_are_distinct(client) -> None:
    case, _, draft = bootstrap_case_flow(client)

    zero_plan = client.post(
        f"/api/v1/condition-plans/{draft['planId']}:confirm",
        json={
            **draft["draft"],
            "mustTerms": ["unlikely-non-match-term"],
            "shouldTerms": [],
            "confirmedBy": "consultant-1",
        },
    ).json()
    zero_run = client.post(
        "/api/v1/search-runs",
        json={
            "caseId": case["caseId"],
            "planId": zero_plan["planId"],
            "pageBudget": 1,
            "idempotencyKey": "zero-run",
        },
    ).json()
    zero_pages = client.get(f"/api/v1/search-runs/{zero_run['runId']}/pages").json()
    zero_status = client.get(f"/api/v1/search-runs/{zero_run['runId']}").json()

    assert zero_status["status"] == "completed"
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
    ).json()
    anomaly_run = client.post(
        "/api/v1/search-runs",
        json={
            "caseId": anomaly_case["caseId"],
            "planId": anomaly_plan["planId"],
            "pageBudget": 1,
            "idempotencyKey": "anomaly-run",
        },
    ).json()
    anomaly_status = client.get(f"/api/v1/search-runs/{anomaly_run['runId']}").json()
    anomaly_pages = client.get(f"/api/v1/search-runs/{anomaly_run['runId']}/pages").json()

    assert anomaly_status["status"] == "failed"
    assert anomaly_pages["snapshots"][0]["errorCode"] == "CTS_PARAM_ANOMALY"


def test_sensitive_export_is_blocked_in_local_mode(client) -> None:
    case, _, draft = bootstrap_case_flow(client)
    confirmed = client.post(
        f"/api/v1/condition-plans/{draft['planId']}:confirm",
        json={**draft["draft"], "confirmedBy": "consultant-1"},
    ).json()
    client.post(
        "/api/v1/search-runs",
        json={
            "caseId": case["caseId"],
            "planId": confirmed["planId"],
            "pageBudget": 1,
            "idempotencyKey": "export-run",
        },
    )
    pages = client.get("/api/v1/ops/summary").json()
    blocked = client.post(
        "/api/v1/exports",
        json={"caseId": case["caseId"], "maskPolicy": "sensitive", "reason": "need contact", "idempotencyKey": "exp-sensitive"},
    )

    assert pages["version"]["api"] == "0.1.0"
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "NO_CONTACT_PERMISSION"
