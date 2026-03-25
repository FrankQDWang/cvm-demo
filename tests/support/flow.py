from __future__ import annotations

import httpx

from cvm_testkit import unique_idempotency_key


def read_json(response: httpx.Response) -> dict[str, object]:
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise TypeError(f"Expected JSON object response, got {payload!r}")
    return payload


def bootstrap_case_flow(client: httpx.Client) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    case_suffix = unique_idempotency_key("case")
    case = read_json(client.post("/api/v1/cases", json={"title": f"AI Native Recruiter {case_suffix}", "ownerTeamId": "team-cn"}))
    version = read_json(client.post(
        f"/api/v1/cases/{case['caseId']}/jd-versions",
        json={"rawText": "Need Python FastAPI Angular Temporal search experience", "source": "manual"},
    ))
    draft = read_json(client.post(
        f"/api/v1/cases/{case['caseId']}/keyword-draft-jobs",
        json={"jdVersionId": version["jdVersionId"], "modelVersion": "gpt-5.4-mini", "promptVersion": "draft-v1"},
    ))
    return case, version, draft
