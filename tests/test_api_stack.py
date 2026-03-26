from __future__ import annotations

import httpx
import pytest

from cvm_testkit import wait_for_agent_run, wait_for_agent_temporal_diagnostic
from tests.support.flow import read_json


@pytest.mark.stack
def test_stack_agent_run_flow(stack_client: httpx.Client) -> None:
    created = read_json(
        stack_client.post(
            "/api/v1/agent-runs",
            json={
                "jdText": "Need AI agent engineer with Python, ReAct, workflow orchestration, and retrieval experience",
                "sourcingPreferenceText": "Prefer recruiting, evals, search systems, and shortlist reasoning experience",
            },
        )
    )
    run = wait_for_agent_run(stack_client, created["runId"])
    diagnostic = wait_for_agent_temporal_diagnostic(stack_client, created["runId"])

    assert run["status"] == "completed"
    assert run["workflowId"] == f"agent-run-{created['runId']}"
    assert run["agentRuntimeConfig"]["searchReflector"]["modelVersion"]
    assert len(run["finalShortlist"]) == 5
    assert any(step["stepType"] == "strategy" for step in run["steps"])
    assert any(step["stepType"] == "analysis" for step in run["steps"])
    assert any(step["stepType"] == "finalize" for step in run["steps"])
    assert diagnostic["workflowId"] == f"agent-run-{created['runId']}"
    assert diagnostic["temporalExecutionFound"] is True
    assert diagnostic["visibilityIndexed"] is True
    assert diagnostic["finalShortlistCount"] == 5
