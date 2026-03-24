from __future__ import annotations

import os
import subprocess
from typing import Any

import httpx

from cvm_testkit import (
    build_client,
    require_local_stack,
    unique_idempotency_key,
    wait_for_search_run,
    wait_for_temporal_diagnostic,
)


def read_json(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    return response.json()


def temporal_ui_base_url() -> str:
    override = os.getenv("CVM_TEMPORAL_UI_BASE_URL")
    if override:
        return override.rstrip("/")
    return f"http://127.0.0.1:{os.getenv('CVM_TEMPORAL_UI_PORT', '8080')}"


def assert_cli_visibility(workflow_id: str, namespace: str) -> None:
    command = [
        "docker",
        "compose",
        "exec",
        "-T",
        "temporal-admin-tools",
        "temporal",
        "workflow",
        "describe",
        "--namespace",
        namespace,
        "--workflow-id",
        workflow_id,
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            "Temporal CLI 无法查询 workflow。\n"
            f"command={' '.join(command)}\nstdout={result.stdout}\nstderr={result.stderr}"
        )


def assert_ui_visibility(workflow_id: str, namespace: str) -> None:
    endpoint = f"{temporal_ui_base_url()}/api/v1/namespaces/{namespace}/workflow-count"
    query = {"query": f"WorkflowId = '{workflow_id}'"}
    with httpx.Client(timeout=10.0, trust_env=False) as client:
        response = client.get(endpoint, params=query)
        response.raise_for_status()
        payload = response.json()
    count = int(payload.get("count", 0))
    if count < 1:
        raise RuntimeError(f"Temporal UI 未索引 workflow: {workflow_id}. response={payload}")


def main() -> int:
    require_local_stack()

    with build_client(timeout_seconds=20.0) as client:
        case_suffix = unique_idempotency_key("temporal-smoke-case")
        case = read_json(client.post("/api/v1/cases", json={"title": f"Temporal Visibility Smoke {case_suffix}", "ownerTeamId": "team-ops"}))
        version = read_json(client.post(
            f"/api/v1/cases/{case['caseId']}/jd-versions",
            json={"rawText": "Need Python FastAPI Angular Temporal search experience", "source": "smoke"},
        ))
        draft = read_json(client.post(
            f"/api/v1/cases/{case['caseId']}/keyword-draft-jobs",
            json={"jdVersionId": version["jdVersionId"], "modelVersion": "gpt-5.4-mini", "promptVersion": "draft-v1"},
        ))
        confirmed = read_json(client.post(
            f"/api/v1/condition-plans/{draft['planId']}:confirm",
            json={
                **draft["draft"],
                "mustTerms": ["Python"],
                "shouldTerms": ["Temporal"],
                "excludeTerms": [],
                "structuredFilters": {"page": 1, "pageSize": 3},
                "confirmedBy": "ops-smoke",
            },
        ))
        run = read_json(client.post(
            "/api/v1/search-runs",
            json={
                "caseId": case["caseId"],
                "planId": confirmed["planId"],
                "pageBudget": 1,
                "idempotencyKey": unique_idempotency_key("temporal-smoke-run"),
            },
        ))

        wait_for_search_run(client, str(run["runId"]))
        diagnostic = wait_for_temporal_diagnostic(client, str(run["runId"]))

    assert_cli_visibility(str(diagnostic["workflowId"]), str(diagnostic["namespace"]))
    assert_ui_visibility(str(diagnostic["workflowId"]), str(diagnostic["namespace"]))

    print(
        {
            "runId": diagnostic["runId"],
            "workflowId": diagnostic["workflowId"],
            "namespace": diagnostic["namespace"],
            "appStatus": diagnostic["appStatus"],
            "temporalExecutionFound": diagnostic["temporalExecutionFound"],
            "visibilityIndexed": diagnostic["visibilityIndexed"],
            "temporalUiUrl": diagnostic["temporalUiUrl"],
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
