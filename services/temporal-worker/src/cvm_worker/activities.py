from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Callable, cast

from sqlalchemy.orm import Session
from temporalio import activity

from cvm_domain_kernel import now_utc
from cvm_platform.application.agent_tracing import (
    AgentRunTraceHandle,
    AgentRunTracer,
    AgentTraceObservation,
    TraceObservationType,
)
from cvm_platform.application.dto import AgentRunRecord
from cvm_platform.domain.errors import NotFoundError
from cvm_platform.domain.ports import ResumeSourcePort
from cvm_platform.domain.types import JsonObject, JsonValue, to_json_object, to_json_value
from cvm_platform.infrastructure.adapters import build_resume_source
from cvm_platform.infrastructure.agent_tracing import build_agent_run_tracer
from cvm_platform.infrastructure.db import SessionLocal
from cvm_platform.infrastructure.sqlalchemy_uow import SqlAlchemyPlatformUnitOfWork
from cvm_platform.settings.config import Settings, settings
from cvm_worker.models import (
    AgentRunSnapshotModel,
    AgentRunStepModel,
    CtsSearchRequestModel,
    RunPersistencePatchModel,
    TracePublicationModel,
    WorkerSearchPageModel,
)

SessionFactory = Callable[[], Session]
ResumeSourceFactory = Callable[[Settings], ResumeSourcePort]
AgentRunTracerFactory = Callable[[Settings], AgentRunTracer]


@contextmanager
def _session_scope(
    session_factory: SessionFactory | None = None,
) -> Iterator[SqlAlchemyPlatformUnitOfWork]:
    factory = session_factory or SessionLocal
    session = factory()
    try:
        yield SqlAlchemyPlatformUnitOfWork(session)
    finally:
        session.close()


def load_agent_run_snapshot_impl(
    run_id: str,
    *,
    session_factory: SessionFactory | None = None,
) -> AgentRunSnapshotModel:
    with _session_scope(session_factory) as uow:
        run = _require_run(uow, run_id)
        return AgentRunSnapshotModel.from_record(run)


def persist_agent_run_patch_impl(
    patch: RunPersistencePatchModel,
    runtime_settings: Settings,
    *,
    session_factory: SessionFactory | None = None,
) -> AgentRunSnapshotModel:
    with _session_scope(session_factory) as uow:
        run = _require_run(uow, patch.runId)
        previous_status = run.status

        if patch.clearError:
            run.error_code = None
            run.error_message = None
        if "status" in patch.model_fields_set and patch.status is not None:
            run.status = patch.status
        if "currentRound" in patch.model_fields_set and patch.currentRound is not None:
            run.current_round = patch.currentRound
        if patch.appendSteps:
            run.steps = [*run.steps, *[step.to_payload() for step in patch.appendSteps]]
        if "finalShortlist" in patch.model_fields_set:
            run.final_shortlist = [item.to_payload() for item in patch.finalShortlist or []]
        if "seenResumeIds" in patch.model_fields_set:
            run.seen_resume_ids = list(patch.seenResumeIds or [])
        if "errorCode" in patch.model_fields_set:
            run.error_code = patch.errorCode
        if "errorMessage" in patch.model_fields_set:
            run.error_message = patch.errorMessage
        if "langfuseTraceId" in patch.model_fields_set:
            run.langfuse_trace_id = patch.langfuseTraceId
        if "langfuseTraceUrl" in patch.model_fields_set:
            run.langfuse_trace_url = patch.langfuseTraceUrl
        if patch.markFinished:
            run.finished_at = now_utc()

        uow.agent_runs.save_run(run)
        if previous_status != run.status:
            _audit_status_transition(uow, run, runtime_settings)
        uow.commit()
        return AgentRunSnapshotModel.from_record(run)


def cts_search_candidates_impl(
    request: CtsSearchRequestModel,
    runtime_settings: Settings,
    *,
    resume_source_factory: ResumeSourceFactory | None = None,
) -> WorkerSearchPageModel:
    source_builder = resume_source_factory or build_resume_source
    resume_source = source_builder(runtime_settings)
    page = resume_source.search_candidates(
        request.normalizedStrategy.to_payload(),
        request.pageNo,
        request.pageSize,
    )
    return WorkerSearchPageModel.from_domain(page)


def publish_langfuse_trace_impl(
    run_id: str,
    runtime_settings: Settings,
    *,
    session_factory: SessionFactory | None = None,
    agent_run_tracer_factory: AgentRunTracerFactory | None = None,
) -> TracePublicationModel:
    with _session_scope(session_factory) as uow:
        run = _require_run(uow, run_id)
        tracer_builder = agent_run_tracer_factory or build_agent_run_tracer
        tracer = tracer_builder(runtime_settings)
        with tracer.trace_run(
            run_id=run.id,
            jd_text=run.jd_text,
            sourcing_preference_text=run.sourcing_preference_text,
            model_version=run.model_version,
            prompt_version=run.prompt_version,
        ) as trace_handle:
            _replay_trace(run, trace_handle, runtime_settings)
            run.langfuse_trace_id = trace_handle.trace_id
            run.langfuse_trace_url = trace_handle.trace_url
        uow.agent_runs.save_run(run)
        uow.commit()
        return TracePublicationModel(
            traceId=run.langfuse_trace_id,
            traceUrl=run.langfuse_trace_url,
        )


@activity.defn(name="load_agent_run_snapshot")
def load_agent_run_snapshot(run_id: str) -> AgentRunSnapshotModel:
    return load_agent_run_snapshot_impl(run_id)


@activity.defn(name="persist_agent_run_patch")
def persist_agent_run_patch(patch: RunPersistencePatchModel) -> AgentRunSnapshotModel:
    return persist_agent_run_patch_impl(patch, settings)


@activity.defn(name="cts_search_candidates")
def cts_search_candidates(request: CtsSearchRequestModel) -> WorkerSearchPageModel:
    return cts_search_candidates_impl(request, settings)


@activity.defn(name="publish_langfuse_trace")
def publish_langfuse_trace(run_id: str) -> TracePublicationModel:
    return publish_langfuse_trace_impl(run_id, settings)


def _require_run(uow: SqlAlchemyPlatformUnitOfWork, run_id: str) -> AgentRunRecord:
    run = uow.agent_runs.get_run(run_id)
    if run is None:
        raise NotFoundError("AGENT_RUN_NOT_FOUND", f"Agent run {run_id} not found.")
    return run


def _audit_status_transition(
    uow: SqlAlchemyPlatformUnitOfWork,
    run: AgentRunRecord,
    runtime_settings: Settings,
) -> None:
    execution_config = {
        "minRounds": runtime_settings.agent_min_rounds,
        "maxRounds": int(run.config["maxRounds"]),
        "roundFetchSchedule": list(run.config["roundFetchSchedule"]),
        "finalTopK": int(run.config["finalTopK"]),
    }
    if run.status == "completed":
        metadata = {
            "rounds": run.current_round,
            "finalShortlistCount": len(run.final_shortlist),
            "profile": runtime_settings.agent_profile,
            "executionConfig": execution_config,
        }
        result = "success"
        action = "agent_run.completed"
    elif run.status == "failed":
        metadata = {
            "errorCode": run.error_code,
            "errorMessage": run.error_message,
            "profile": runtime_settings.agent_profile,
            "executionConfig": execution_config,
        }
        result = "failure"
        action = "agent_run.failed"
    else:
        return
    from cvm_domain_kernel import new_id, now_utc
    from cvm_platform.application.dto import AuditLogRecord

    uow.audit_logs.save_audit_log(
        AuditLogRecord(
            id=new_id("audit"),
            actor_id="system",
            target_type="agent_run",
            target_id=run.id,
            action=action,
            result=result,
            metadata_json=to_json_object(metadata),
            occurred_at=now_utc(),
        )
    )


def _replay_trace(
    run: AgentRunRecord,
    trace_handle: AgentRunTraceHandle,
    runtime_settings: Settings,
) -> None:
    steps = [AgentRunStepModel.from_payload(step) for step in run.steps]
    strategy_step = next((step for step in steps if step.stepType == "strategy" and step.roundNo is None), None)
    if strategy_step is not None:
        with trace_handle.start_observation(
            name="extract-search-strategy",
            as_type="generation",
            input=to_json_value(strategy_step.payload.get("promptText")),
            metadata=to_json_object({
                "summary": strategy_step.summary,
                "stepType": strategy_step.stepType,
            }),
            model=cast(str | None, strategy_step.payload.get("modelVersion")),
            version=cast(str | None, strategy_step.payload.get("promptVersion")),
        ) as observation:
            observation.update(output=to_json_object(strategy_step.payload))

    round_steps: dict[int, list[AgentRunStepModel]] = defaultdict(list)
    for step in steps:
        if step.roundNo is not None:
            round_steps[step.roundNo].append(step)

    for round_no in sorted(round_steps):
        current_steps = round_steps[round_no]
        current_query = next(
            (
                step.payload.get("roundQuery") or step.payload.get("normalizedQuery")
                for step in current_steps
                if step.stepType == "search"
            ),
            None,
        )
        with trace_handle.start_observation(
            name=f"round-{round_no}",
            as_type="chain",
            input=to_json_object({"roundNo": round_no, "currentQuery": current_query}),
            metadata=to_json_object({"stepCount": len(current_steps)}),
        ) as round_observation:
            _replay_round_steps(current_steps, round_observation)

    finalize_step = next((step for step in steps if step.stepType == "finalize"), None)
    if finalize_step is not None:
        with trace_handle.start_observation(
            name="finalize",
            as_type="span",
            input=to_json_object({"currentRound": run.current_round}),
            metadata=to_json_object({"summary": finalize_step.summary}),
        ) as observation:
            observation.update(output=to_json_object(finalize_step.payload))

    root_output = to_json_object({
        "status": run.status,
        "currentRound": run.current_round,
        "finalShortlist": run.final_shortlist,
    })
    if run.error_code is not None:
        root_output["errorCode"] = run.error_code
    if run.error_message is not None:
        root_output["errorMessage"] = run.error_message
    trace_handle.update_root(
        output=root_output,
        metadata=to_json_object({
            "seenResumeCount": len(run.seen_resume_ids),
            "executionConfig": {
                "minRounds": runtime_settings.agent_min_rounds,
                "maxRounds": int(run.config["maxRounds"]),
                "roundFetchSchedule": list(run.config["roundFetchSchedule"]),
                "finalTopK": int(run.config["finalTopK"]),
            },
        }),
        level="ERROR" if run.status == "failed" else None,
        status_message=run.error_message if run.status == "failed" else None,
    )


def _replay_round_steps(
    steps: list[AgentRunStepModel],
    round_observation: AgentTraceObservation,
) -> None:
    for step in steps:
        if step.stepType == "analysis":
            _replay_analysis_step(step, round_observation)
            continue
        name, as_type = _step_trace_shape(step.stepType)
        step_input: JsonValue = (
            to_json_value(step.payload.get("promptText"))
            if step.payload.get("promptText") is not None
            else to_json_object({"summary": step.summary})
        )
        with round_observation.start_observation(
            name=name,
            as_type=as_type,
            input=step_input,
            metadata=to_json_object({"stepType": step.stepType, "title": step.title}),
            model=cast(str | None, step.payload.get("modelVersion")),
            version=cast(str | None, step.payload.get("promptVersion")),
            level="WARNING" if step.stepType == "stop" else None,
            status_message=step.summary if step.stepType == "stop" else None,
        ) as observation:
            observation.update(output=to_json_object(step.payload))


def _replay_analysis_step(
    step: AgentRunStepModel,
    round_observation: AgentTraceObservation,
) -> None:
    analyses = cast(list[JsonObject], to_json_value(step.payload.get("analyses", [])))
    with round_observation.start_observation(
        name="analysis",
        as_type="chain",
        input=to_json_object({"summary": step.summary, "analyzedCount": len(analyses)}),
        metadata=to_json_object({"title": step.title}),
    ) as analysis_observation:
        for analysis in analyses:
            with analysis_observation.start_observation(
                name=f"analyze-resume-{analysis['candidateId']}",
                as_type="generation",
                input=to_json_value(analysis.get("promptText")),
                metadata=to_json_object({
                    "candidateId": analysis["candidateId"],
                    "candidateName": analysis.get("name"),
                }),
                model=cast(str | None, analysis.get("modelVersion")),
                version=cast(str | None, analysis.get("promptVersion")),
            ) as observation:
                observation.update(output=analysis)
        analysis_observation.update(
            output=to_json_object({"analyzedCount": len(analyses), "analyses": analyses}),
        )


def _step_trace_shape(step_type: str) -> tuple[str, TraceObservationType]:
    if step_type == "search":
        return "cts-search", "tool"
    if step_type == "dedupe":
        return "dedupe", "span"
    if step_type == "shortlist":
        return "shortlist", "span"
    if step_type == "reflection":
        return "reflect", "generation"
    if step_type == "stop":
        return "stop", "span"
    return step_type, "span"
