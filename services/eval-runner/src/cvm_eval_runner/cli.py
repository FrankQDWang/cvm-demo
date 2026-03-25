from __future__ import annotations

import argparse
from collections.abc import Mapping
from typing import cast

import httpx

from cvm_testkit import (
    build_client,
    require_local_stack,
    unique_idempotency_key,
    wait_for_search_run,
    wait_for_temporal_diagnostic,
)


JsonObject = dict[str, object]


def read_json(response: httpx.Response) -> JsonObject:
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Expected JSON object response from the API.")
    return cast(JsonObject, payload)


def _get_required_str(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"Expected non-empty string field: {key}")
    return value


def _get_required_object(payload: Mapping[str, object], key: str) -> JsonObject:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected object field: {key}")
    return cast(JsonObject, value)


def _get_required_list(payload: Mapping[str, object], key: str) -> list[object]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise RuntimeError(f"Expected list field: {key}")
    return cast(list[object], value)


def _get_optional_str(payload: Mapping[str, object], key: str) -> str | None:
    value = payload.get(key)
    if isinstance(value, str) and value:
        return value
    return None


def _build_suite_result(
    *,
    run_status: Mapping[str, object],
    diagnostic: Mapping[str, object],
    snapshot_count: int,
    candidate_available: bool,
    verdict_saved: bool,
    export_completed: bool,
    failure_reason: str | None = None,
) -> dict[str, object]:
    checks = {
        "runCompleted": _get_optional_str(run_status, "status") == "completed",
        "temporalExecutionFound": diagnostic.get("temporalExecutionFound") is True,
        "temporalVisibilityIndexed": diagnostic.get("visibilityIndexed") is True,
        "snapshotPersisted": snapshot_count == 1,
        "candidateAvailable": candidate_available,
        "verdictSaved": verdict_saved,
        "maskedExportCompleted": export_completed,
    }
    result: dict[str, object] = {
        "suite": "blocking",
        "passed": all(checks.values()),
        "checks": checks,
    }
    if failure_reason is not None:
        result["failureReason"] = failure_reason
    return result


def run_blocking_suite() -> dict[str, object]:
    require_local_stack()
    with build_client(timeout_seconds=15.0) as client:
        case = read_json(
            client.post(
                "/api/v1/cases",
                json={"title": f"AI Native Recruiter {unique_idempotency_key('eval-case')}", "ownerTeamId": "team-cn"},
            )
        )
        case_id = _get_required_str(case, "caseId")
        version = read_json(client.post(
            f"/api/v1/cases/{case_id}/jd-versions",
            json={"rawText": "Need Python FastAPI Angular Temporal search experience", "source": "prd"},
        ))
        version_id = _get_required_str(version, "jdVersionId")
        draft = read_json(client.post(
            f"/api/v1/cases/{case_id}/keyword-draft-jobs",
            json={"jdVersionId": version_id, "modelVersion": "gpt-5.4-mini", "promptVersion": "draft-v1"},
        ))
        plan_id = _get_required_str(draft, "planId")
        draft_payload = _get_required_object(draft, "draft")
        confirmed = read_json(client.post(
            f"/api/v1/condition-plans/{plan_id}:confirm",
            json={
                **draft_payload,
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
                "caseId": case_id,
                "planId": _get_required_str(confirmed, "planId"),
                "pageBudget": 1,
                "idempotencyKey": unique_idempotency_key("eval-blocking-run"),
            },
        ))
        run_id = _get_required_str(run, "runId")
        run_status = wait_for_search_run(client, run_id)
        diagnostic = wait_for_temporal_diagnostic(client, run_id)
        pages = read_json(client.get(f"/api/v1/search-runs/{run_id}/pages"))
        snapshots = _get_required_list(pages, "snapshots")
        status = _get_optional_str(run_status, "status") or "unknown"
        snapshot_count = len(snapshots)

        if status != "completed":
            return _build_suite_result(
                run_status=run_status,
                diagnostic=diagnostic,
                snapshot_count=snapshot_count,
                candidate_available=False,
                verdict_saved=False,
                export_completed=False,
                failure_reason=(
                    _get_optional_str(run_status, "errorSummary")
                    or f"Search run finished with status={status}."
                ),
            )

        if snapshot_count != 1:
            return _build_suite_result(
                run_status=run_status,
                diagnostic=diagnostic,
                snapshot_count=snapshot_count,
                candidate_available=False,
                verdict_saved=False,
                export_completed=False,
                failure_reason=f"Expected exactly 1 snapshot, got {snapshot_count}.",
            )

        first_snapshot = cast(JsonObject, snapshots[0])
        candidates = _get_required_list(first_snapshot, "candidates")
        if not candidates:
            return _build_suite_result(
                run_status=run_status,
                diagnostic=diagnostic,
                snapshot_count=snapshot_count,
                candidate_available=False,
                verdict_saved=False,
                export_completed=False,
                failure_reason="Search run completed but returned no candidates.",
            )

        candidate = cast(JsonObject, candidates[0])
        verdict = read_json(client.put(
            f"/api/v1/case-candidates/{_get_required_str(candidate, 'candidateId')}/verdict",
            json={"verdict": "Match", "reasons": ["core skill fit"], "notes": "strong match", "actorId": "consultant-1"},
        ))
        export = read_json(client.post(
            "/api/v1/exports",
            json={"caseId": case_id, "maskPolicy": "masked", "reason": "weekly shortlist", "idempotencyKey": unique_idempotency_key("eval-export")},
        ))

    return _build_suite_result(
        run_status=run_status,
        diagnostic=diagnostic,
        snapshot_count=snapshot_count,
        candidate_available=True,
        verdict_saved=_get_required_str(verdict, "latestVerdict") == "Match",
        export_completed=_get_required_str(export, "status") == "completed",
    )


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
