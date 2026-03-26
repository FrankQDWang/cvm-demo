from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from cvm_domain_kernel import new_id, now_utc
from cvm_platform.application.agent_tracing import NoOpAgentRunTracer
from cvm_platform.application.dto import AgentRunRecord, CandidateRecord
from cvm_platform.domain.errors import NotFoundError
from tests.support.api_harness import build_test_service


def _candidate(*, case_id: str, snapshot_id: str | None = None, verdict: str | None = None) -> CandidateRecord:
    timestamp = now_utc()
    return CandidateRecord(
        id=new_id("cand"),
        case_id=case_id,
        external_identity_id=new_id("resume"),
        latest_resume_snapshot_id=snapshot_id,
        latest_verdict=verdict,
        dedupe_status="unique",
        name="Alice Agent",
        title="Senior Agent Engineer",
        company="CVM",
        location="Shanghai",
        summary="Built agent systems",
        email="alice@example.com",
        phone="13800001234",
        created_at=timestamp,
        updated_at=timestamp,
    )


def test_get_candidate_detail_raises_when_snapshot_is_missing(tmp_path) -> None:
    service, session, engine, _settings = build_test_service(tmp_path, agent_run_tracer=NoOpAgentRunTracer())
    try:
        case = service.create_case("Agent Role", "team-cn")
        candidate = _candidate(case_id=case.id, snapshot_id=None)
        service.uow.candidates.save_candidate(candidate)
        service.uow.commit()

        with pytest.raises(NotFoundError) as exc_info:
            service.get_candidate_detail(candidate.id)

        assert exc_info.value.code == "RESUME_SNAPSHOT_NOT_FOUND"
    finally:
        session.close()
        engine.dispose()


def test_save_verdict_persists_history_and_updates_candidate(tmp_path) -> None:
    service, session, engine, _settings = build_test_service(tmp_path)
    try:
        case = service.create_case("Agent Role", "team-cn")
        candidate = _candidate(case_id=case.id, snapshot_id="snap_existing")
        service.uow.candidates.save_candidate(candidate)
        service.uow.commit()

        updated = service.save_verdict(
            candidate.id,
            verdict="Match",
            reasons=["python", "react"],
            notes="Strong shortlist fit",
            actor_id="reviewer_1",
            resume_snapshot_id="snap_existing",
        )

        history = service.uow.candidates.list_verdict_history(candidate.id)
        assert updated.latest_verdict == "Match"
        assert len(history) == 1
        assert history[0].reasons == ["python", "react"]
        assert history[0].actor_id == "reviewer_1"
    finally:
        session.close()
        engine.dispose()


def test_create_export_writes_masked_file_and_reuses_idempotency_key(tmp_path) -> None:
    service, session, engine, _settings = build_test_service(tmp_path)
    try:
        case = service.create_case("Agent Role", "team-cn")
        candidate = _candidate(case_id=case.id, verdict="Match")
        service.uow.candidates.save_candidate(candidate)
        service.uow.commit()

        first = service.create_export(
            case_id=case.id,
            mask_policy="masked",
            reason="share shortlist",
            idempotency_key="idem-export-1",
        )
        second = service.create_export(
            case_id=case.id,
            mask_policy="masked",
            reason="share shortlist",
            idempotency_key="idem-export-1",
        )

        assert first.id == second.id
        assert first.status == "completed"
        assert first.file_path is not None
        exported = (tmp_path / "exports" / f"{case.id}-{first.id}.csv").read_text(encoding="utf-8")
        assert "al***@example.com" in exported
        assert "138****1234" in exported
        assert "alice@example.com" not in exported
    finally:
        session.close()
        engine.dispose()


def test_get_ops_summary_and_create_eval_run_report_agent_run_metrics(tmp_path) -> None:
    service, session, engine, _settings = build_test_service(tmp_path)
    try:
        case = service.create_case("Agent Role", "team-cn")
        service.uow.candidates.save_candidate(_candidate(case_id=case.id, verdict="Match"))
        finished_at = datetime.now(tz=UTC)
        started_at = finished_at - timedelta(seconds=12)
        service.uow.agent_runs.save_run(
            AgentRunRecord(
                id="agent_done",
                status="completed",
                jd_text="Need Python agent engineer",
                sourcing_preference_text="Prefer evals",
                idempotency_key="idem-agent-done",
                config={"maxRounds": 3, "roundFetchSchedule": [10, 5, 5], "finalTopK": 5},
                current_round=2,
                model_version="gpt-5.4-mini",
                prompt_version="agent-loop-v1",
                workflow_id="agent-run-agent_done",
                temporal_namespace="default",
                temporal_task_queue="cvm-agent-runs",
                langfuse_trace_id="trace-agent_done",
                langfuse_trace_url="http://127.0.0.1:4202/project/project-cvm-local/traces/trace-agent_done",
                steps=[],
                final_shortlist=[],
                seen_resume_ids=[],
                error_code=None,
                error_message=None,
                created_at=started_at,
                started_at=started_at,
                finished_at=finished_at,
            )
        )
        failed = service.create_agent_run(
            jd_text="Need recruiter",
            sourcing_preference_text="Prefer sourcing ops",
        )
        service.fail_agent_run_dispatch(failed.id, "TEMPORAL_START_FAILED", "worker unavailable")
        summary = service.get_ops_summary()
        eval_run = service.create_eval_run("blocking", "dataset_local", "main")

        assert summary.queue["agentRuns"]
        assert summary.failures["agentRuns"]
        assert summary.latency["avgAgentRunSeconds"] >= 6.0
        assert any(metric.name == "agentRunsTotal" and metric.value == 2.0 for metric in summary.metrics)
        assert any(metric.name == "candidateCount" and metric.value == 1.0 for metric in summary.metrics)
        assert eval_run.blocking_result is True
        assert eval_run.summary_metrics["passedChecks"] == 3
    finally:
        session.close()
        engine.dispose()
