from __future__ import annotations

import argparse

from cvm_testkit import (
    build_client,
    require_local_stack,
    unique_idempotency_key,
    wait_for_search_run,
    wait_for_temporal_diagnostic,
)


def read_json(response) -> dict[str, object]:
    response.raise_for_status()
    return response.json()


def run_blocking_suite() -> dict[str, object]:
    require_local_stack()
    with build_client(timeout_seconds=15.0) as client:
        case = read_json(client.post("/api/v1/cases", json={"title": f"AI Native Recruiter {unique_idempotency_key('eval-case')}", "ownerTeamId": "team-cn"}))
        version = read_json(client.post(
            f"/api/v1/cases/{case['caseId']}/jd-versions",
            json={"rawText": "Need Python FastAPI Angular Temporal search experience", "source": "prd"},
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
                "idempotencyKey": unique_idempotency_key("eval-blocking-run"),
            },
        ))
        run_status = wait_for_search_run(client, str(run["runId"]))
        diagnostic = wait_for_temporal_diagnostic(client, str(run["runId"]))
        pages = read_json(client.get(f"/api/v1/search-runs/{run['runId']}/pages"))
        candidate = pages["snapshots"][0]["candidates"][0]
        verdict = read_json(client.put(
            f"/api/v1/case-candidates/{candidate['candidateId']}/verdict",
            json={"verdict": "Match", "reasons": ["core skill fit"], "notes": "strong match", "actorId": "consultant-1"},
        ))
        export = read_json(client.post(
            "/api/v1/exports",
            json={"caseId": case["caseId"], "maskPolicy": "masked", "reason": "weekly shortlist", "idempotencyKey": unique_idempotency_key("eval-export")},
        ))

    passed = all(
        [
            run_status["status"] == "completed",
            diagnostic["temporalExecutionFound"] is True,
            diagnostic["visibilityIndexed"] is True,
            len(pages["snapshots"]) == 1,
            verdict["latestVerdict"] == "Match",
            export["status"] == "completed",
        ]
    )
    return {
        "suite": "blocking",
        "passed": passed,
        "checks": {
            "runCompleted": run_status["status"] == "completed",
            "temporalExecutionFound": diagnostic["temporalExecutionFound"] is True,
            "temporalVisibilityIndexed": diagnostic["visibilityIndexed"] is True,
            "snapshotPersisted": len(pages["snapshots"]) == 1,
            "verdictSaved": verdict["latestVerdict"] == "Match",
            "maskedExportCompleted": export["status"] == "completed",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", default="blocking")
    args = parser.parse_args()
    if args.suite != "blocking":
        raise SystemExit("Only blocking suite is implemented.")
    result = run_blocking_suite()
    print(result)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
