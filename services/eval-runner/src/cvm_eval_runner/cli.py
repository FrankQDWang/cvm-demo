from __future__ import annotations

import argparse
from pathlib import Path

from fastapi.testclient import TestClient


def run_blocking_suite() -> dict[str, object]:
    import os

    db_path = Path("var/eval-blocking.sqlite3")
    if db_path.exists():
        db_path.unlink()
    os.environ["CVM_DATABASE_URL"] = f"sqlite+pysqlite:///{db_path}"
    from cvm_platform.main import create_app

    client = TestClient(create_app())

    case = client.post("/api/v1/cases", json={"title": "AI Native Recruiter", "ownerTeamId": "team-cn"}).json()
    version = client.post(
        f"/api/v1/cases/{case['caseId']}/jd-versions",
        json={"rawText": "Need Python FastAPI Angular Temporal search experience", "source": "prd"},
    ).json()
    draft = client.post(
        f"/api/v1/cases/{case['caseId']}/keyword-draft-jobs",
        json={"jdVersionId": version["jdVersionId"], "modelVersion": "stub-1", "promptVersion": "draft-v1"},
    ).json()
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
            "idempotencyKey": "eval-blocking-run",
        },
    ).json()
    run_status = client.get(f"/api/v1/search-runs/{run['runId']}").json()
    pages = client.get(f"/api/v1/search-runs/{run['runId']}/pages").json()
    candidate = pages["snapshots"][0]["candidates"][0]
    verdict = client.put(
        f"/api/v1/case-candidates/{candidate['candidateId']}/verdict",
        json={"verdict": "Match", "reasons": ["core skill fit"], "notes": "strong match", "actorId": "consultant-1"},
    ).json()
    export = client.post(
        "/api/v1/exports",
        json={"caseId": case["caseId"], "maskPolicy": "masked", "reason": "weekly shortlist", "idempotencyKey": "eval-export"},
    ).json()

    passed = all(
        [
            run_status["status"] == "completed",
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
