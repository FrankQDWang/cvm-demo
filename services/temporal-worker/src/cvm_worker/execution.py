from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import timedelta
import logging
from typing import Protocol, cast

from pydantic_ai.run import AgentRunResult
from pydantic_ai.usage import RunUsage
from sqlalchemy.orm import Session
from temporalio import workflow

from cvm_platform.application.agent_runs import (
    MAX_AGENT_ROUNDS,
    MIN_AGENT_ROUNDS,
    append_agent_run_step,
    build_query_delta,
    strategy_signature,
    strategy_to_query_payload,
)
from cvm_platform.application.agent_tracing import AgentRunTracer, TraceObservationLevel
from cvm_platform.domain.ports import ResumeSourcePort
from cvm_platform.domain.errors import ExternalDependencyError
from cvm_platform.domain.types import AgentRunConfigPayload, JsonObject, JsonValue, to_json_object, to_json_value
from cvm_platform.settings.config import Settings
from cvm_worker.activities import (
    cts_search_candidates,
    cts_search_candidates_impl,
    load_agent_run_snapshot,
    load_agent_run_snapshot_impl,
    persist_agent_run_patch,
    persist_agent_run_patch_impl,
    persist_candidate_snapshots,
    persist_candidate_snapshots_impl,
    persist_resume_analyses,
    persist_resume_analyses_impl,
    publish_langfuse_trace,
    publish_langfuse_trace_impl,
)
from cvm_worker.agents import (
    AgentBundle,
    RESUME_MATCH_PROMPT_NAME,
    ResolvedAgentInvocation,
    SEARCH_REFLECTION_PROMPT_NAME,
    STRATEGY_PROMPT_NAME,
    build_resume_match_prompt,
    build_search_reflection_prompt,
    build_strategy_prompt,
    build_temporal_agents,
    resolve_agent_invocation,
)
from cvm_worker.models import (
    AgentRunSnapshotModel,
    AgentRunStepModel,
    CtsSearchRequestModel,
    NormalizedStrategyModel,
    ObservationTraceFactModel,
    PersistCandidateSnapshotsRequestModel,
    PersistCandidateSnapshotsResultModel,
    PersistResumeAnalysesRequestModel,
    PersistResumeAnalysisItemModel,
    PersistedCandidateRefModel,
    ResumeMatcherOutputModel,
    RunPersistencePatchModel,
    SearchReflectorOutputModel,
    ShortlistCandidateModel,
    StrategyExtractorOutputModel,
    TracePromptReferenceModel,
    TracePublicationModel,
    WorkerCandidateModel,
    WorkerSearchPageModel,
)

SessionFactory = Callable[[], Session]
ResumeSourceFactory = Callable[[Settings], ResumeSourcePort]
AgentRunTracerFactory = Callable[[Settings], AgentRunTracer]
LOGGER = logging.getLogger("cvm_worker.execution")


class _ExecutionIO(Protocol):
    async def load_run_snapshot(self, run_id: str) -> AgentRunSnapshotModel: ...

    async def persist_run_patch(self, patch: RunPersistencePatchModel) -> AgentRunSnapshotModel: ...

    async def search_candidates(self, request: CtsSearchRequestModel) -> WorkerSearchPageModel: ...

    async def persist_candidate_snapshots(
        self,
        request: PersistCandidateSnapshotsRequestModel,
    ) -> PersistCandidateSnapshotsResultModel: ...

    async def persist_resume_analyses(self, request: PersistResumeAnalysesRequestModel) -> int: ...

    async def publish_trace(self, run_id: str) -> TracePublicationModel: ...


@dataclass(slots=True)
class _ShortlistedCandidate:
    candidate_id: str
    candidate: WorkerCandidateModel
    score: float
    reason: str
    source_round: int

    def to_model(self) -> ShortlistCandidateModel:
        return ShortlistCandidateModel(
            candidateId=self.candidate_id,
            externalIdentityId=self.candidate.externalIdentityId,
            name=self.candidate.name,
            title=self.candidate.title,
            company=self.candidate.company,
            location=self.candidate.location,
            summary=self.candidate.summary,
            reason=self.reason,
            score=round(self.score, 4),
            sourceRound=self.source_round,
        )


@dataclass(slots=True)
class _AnalyzedCandidate:
    shortlisted: _ShortlistedCandidate
    resume_snapshot_id: str
    prompt_text: str
    model_version: str
    prompt_version: str
    thinking_effort: str | None
    evidence: list[str]
    concerns: list[str]
    trace_fact: ObservationTraceFactModel


@dataclass(slots=True)
class _ExecutionState:
    run: AgentRunSnapshotModel
    retained_candidates: list[_ShortlistedCandidate] = field(default_factory=list)
    persisted_candidates: dict[str, PersistedCandidateRefModel] = field(default_factory=dict)
    strategy_offsets: dict[str, int] = field(default_factory=dict)
    no_progress_rounds: int = 0
    previous_shortlist_signature: tuple[str, ...] = ()
    stop_reason: str | None = None


def _normalize_usage_details(usage: RunUsage) -> dict[str, int] | None:
    usage_details: dict[str, int] = {
        "prompt_tokens": usage.input_tokens,
        "completion_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
    }
    if usage.cache_write_tokens:
        usage_details["cache_write_tokens"] = usage.cache_write_tokens
    if usage.cache_read_tokens:
        usage_details["cache_read_tokens"] = usage.cache_read_tokens
    if usage.input_audio_tokens:
        usage_details["input_audio_tokens"] = usage.input_audio_tokens
    if usage.cache_audio_read_tokens:
        usage_details["cache_audio_read_tokens"] = usage.cache_audio_read_tokens
    if usage.output_audio_tokens:
        usage_details["output_audio_tokens"] = usage.output_audio_tokens
    if usage.requests:
        usage_details["requests"] = usage.requests
    if usage.tool_calls:
        usage_details["tool_calls"] = usage.tool_calls
    for key, value in usage.details.items():
        usage_details[key] = value
    if not any(value > 0 for value in usage_details.values()):
        return None
    return usage_details


def _parse_message_history(result: AgentRunResult[object]) -> list[JsonValue]:
    raw_messages = result.all_messages_json()
    loaded_messages = json.loads(raw_messages.decode("utf-8"))
    return cast(list[JsonValue], to_json_value(loaded_messages))


def _extract_response_message(message_history: list[JsonValue]) -> JsonValue | None:
    for message in reversed(message_history):
        if isinstance(message, dict) and message.get("kind") == "response":
            return cast(JsonValue, message)
    return None


def _generation_input_payload(
    *,
    prompt_text: str,
    message_history: list[JsonValue],
) -> JsonObject:
    return to_json_object(
        {
            "promptText": prompt_text,
            "messageHistory": message_history,
        }
    )


def _generation_output_payload(
    *,
    structured_output: JsonObject,
    response_message: JsonValue | None,
) -> JsonObject:
    payload: JsonObject = {"structuredOutput": structured_output}
    if response_message is not None:
        payload["response"] = response_message
    return payload


def _build_generation_trace_fact(
    *,
    prompt_name: str,
    prompt_label: str,
    prompt_text: str,
    result: AgentRunResult[object],
    structured_output: JsonObject,
    model_version: str,
    thinking_effort: str | None,
    metadata: JsonObject | None = None,
) -> ObservationTraceFactModel:
    message_history = _parse_message_history(result)
    response_message = _extract_response_message(message_history)
    trace_metadata = dict(metadata or {})
    trace_metadata["thinkingEffort"] = thinking_effort
    trace_metadata["messageCount"] = len(message_history)
    return ObservationTraceFactModel(
        observationType="generation",
        input=_generation_input_payload(prompt_text=prompt_text, message_history=message_history),
        output=_generation_output_payload(
            structured_output=structured_output,
            response_message=response_message,
        ),
        metadata=cast(dict[str, object], cast(object, to_json_object(trace_metadata))),
        messageHistory=cast(list[object], cast(object, message_history)),
        response=response_message,
        model=model_version,
        version=prompt_label,
        prompt=TracePromptReferenceModel(
            name=prompt_name,
            label=prompt_label,
            text=prompt_text,
            type="text",
        ),
        usageDetails=_normalize_usage_details(result.usage()),
        completionStartTime=result.timestamp().isoformat(),
    )


def _build_span_trace_fact(
    *,
    input_payload: JsonObject,
    output_payload: JsonObject,
    metadata: JsonObject | None = None,
    level: TraceObservationLevel | None = None,
    status_message: str | None = None,
) -> ObservationTraceFactModel:
    return ObservationTraceFactModel(
        observationType="span",
        input=input_payload,
        output=output_payload,
        metadata=cast(dict[str, object], cast(object, to_json_object(metadata or {}))),
        level=level,
        statusMessage=status_message,
    )


def _build_search_trace_fact(
    *,
    request: CtsSearchRequestModel,
    page: WorkerSearchPageModel,
    offset: int,
) -> ObservationTraceFactModel:
    output_payload: JsonObject = {
        "status": page.status,
        "pageNo": page.pageNo,
        "pageSize": page.pageSize,
        "offset": offset,
        "total": page.total,
        "returnedCount": len(page.candidates),
        "candidateIds": [candidate.externalIdentityId for candidate in page.candidates],
        "upstreamResponse": to_json_object(page.upstreamResponse),
    }
    if page.errorCode is not None:
        output_payload["errorCode"] = page.errorCode
    if page.errorMessage is not None:
        output_payload["errorMessage"] = page.errorMessage
    return ObservationTraceFactModel(
        observationType="tool",
        input=to_json_object(
            {
                "searchRequest": request.model_dump(mode="json"),
                "upstreamRequest": to_json_object(page.upstreamRequest),
            }
        ),
        output=output_payload,
        metadata=cast(dict[str, object], cast(object, to_json_object({"tool": "cts.search_candidates"}))),
        level="ERROR" if page.errorCode is not None else None,
        statusMessage=page.errorMessage if page.errorCode is not None else None,
    )


def _trace_payload(trace_fact: ObservationTraceFactModel) -> dict[str, object]:
    return cast(dict[str, object], cast(object, trace_fact.model_dump(mode="json")))


def _max_rounds(config: AgentRunConfigPayload) -> int:
    return config["maxRounds"]


def _final_top_k(config: AgentRunConfigPayload) -> int:
    return config["finalTopK"]


def _round_fetch_schedule(config: AgentRunConfigPayload) -> list[int]:
    return list(config["roundFetchSchedule"])


def _effective_min_rounds(runtime_settings: Settings, run: AgentRunSnapshotModel) -> int:
    return min(
        _max_rounds(run.config),
        max(MIN_AGENT_ROUNDS, min(runtime_settings.agent_min_rounds, MAX_AGENT_ROUNDS)),
    )


def _execution_config_payload(
    runtime_settings: Settings,
    run: AgentRunSnapshotModel,
) -> dict[str, object]:
    return {
        "minRounds": _effective_min_rounds(runtime_settings, run),
        "maxRounds": _max_rounds(run.config),
        "roundFetchSchedule": _round_fetch_schedule(run.config),
        "finalTopK": _final_top_k(run.config),
    }


async def _publish_trace_quietly(
    *,
    io: _ExecutionIO,
    state: _ExecutionState,
    run_id: str,
    terminal_status: str,
) -> None:
    try:
        await io.publish_trace(run_id)
    except Exception as exc:  # pragma: no cover - exercised by focused failure-path tests
        warning_message = str(exc) or "Langfuse trace publication failed."
        LOGGER.warning(
            "Langfuse trace publication failed for run %s after terminal status %s: %s",
            run_id,
            terminal_status,
            warning_message,
        )
        try:
            warning_step = _append_step(
                state,
                round_no=state.run.currentRound or None,
                step_type="observability-warning",
                title="Langfuse trace publication failed",
                status="failed",
                summary="Langfuse trace publication failed after the run had already reached a terminal state.",
                payload={
                    "warningCode": "LANGFUSE_TRACE_PUBLICATION_FAILED",
                    "terminalStatus": terminal_status,
                    "errorMessage": warning_message,
                    "trace": _trace_payload(
                        _build_span_trace_fact(
                            input_payload=to_json_object(
                                {
                                    "runId": run_id,
                                    "terminalStatus": terminal_status,
                                }
                            ),
                            output_payload=to_json_object(
                                {
                                    "warningCode": "LANGFUSE_TRACE_PUBLICATION_FAILED",
                                    "errorMessage": warning_message,
                                }
                            ),
                            metadata=to_json_object({"stepType": "observability-warning"}),
                            level="ERROR",
                            status_message=warning_message,
                        )
                    ),
                },
            )
            state.run = await io.persist_run_patch(
                RunPersistencePatchModel(
                    runId=run_id,
                    appendSteps=[warning_step],
                )
            )
        except Exception as warning_exc:  # pragma: no cover - defensive, should not affect terminal status
            LOGGER.warning(
                "Failed to persist observability warning for run %s after Langfuse export failure: %s",
                run_id,
                warning_exc,
            )


class _WorkflowExecutionIO:
    async def load_run_snapshot(self, run_id: str) -> AgentRunSnapshotModel:
        return await workflow.execute_activity(
            load_agent_run_snapshot,
            run_id,
            start_to_close_timeout=timedelta(seconds=30),
        )

    async def persist_run_patch(self, patch: RunPersistencePatchModel) -> AgentRunSnapshotModel:
        return await workflow.execute_activity(
            persist_agent_run_patch,
            patch,
            start_to_close_timeout=timedelta(seconds=30),
        )

    async def search_candidates(self, request: CtsSearchRequestModel) -> WorkerSearchPageModel:
        return await workflow.execute_activity(
            cts_search_candidates,
            request,
            start_to_close_timeout=timedelta(seconds=45),
        )

    async def persist_candidate_snapshots(
        self,
        request: PersistCandidateSnapshotsRequestModel,
    ) -> PersistCandidateSnapshotsResultModel:
        return await workflow.execute_activity(
            persist_candidate_snapshots,
            request,
            start_to_close_timeout=timedelta(seconds=30),
        )

    async def persist_resume_analyses(self, request: PersistResumeAnalysesRequestModel) -> int:
        return await workflow.execute_activity(
            persist_resume_analyses,
            request,
            start_to_close_timeout=timedelta(seconds=30),
        )

    async def publish_trace(self, run_id: str) -> TracePublicationModel:
        return await workflow.execute_activity(
            publish_langfuse_trace,
            run_id,
            start_to_close_timeout=timedelta(seconds=45),
        )


class _LocalExecutionIO:
    def __init__(
        self,
        runtime_settings: Settings,
        *,
        session_factory: SessionFactory | None = None,
        resume_source_factory: ResumeSourceFactory | None = None,
        agent_run_tracer_factory: AgentRunTracerFactory | None = None,
    ) -> None:
        self._runtime_settings = runtime_settings
        self._session_factory = session_factory
        self._resume_source_factory = resume_source_factory
        self._agent_run_tracer_factory = agent_run_tracer_factory

    async def load_run_snapshot(self, run_id: str) -> AgentRunSnapshotModel:
        return load_agent_run_snapshot_impl(run_id, session_factory=self._session_factory)

    async def persist_run_patch(self, patch: RunPersistencePatchModel) -> AgentRunSnapshotModel:
        return persist_agent_run_patch_impl(
            patch,
            self._runtime_settings,
            session_factory=self._session_factory,
        )

    async def search_candidates(self, request: CtsSearchRequestModel) -> WorkerSearchPageModel:
        return cts_search_candidates_impl(
            request,
            self._runtime_settings,
            resume_source_factory=self._resume_source_factory,
        )

    async def persist_candidate_snapshots(
        self,
        request: PersistCandidateSnapshotsRequestModel,
    ) -> PersistCandidateSnapshotsResultModel:
        return persist_candidate_snapshots_impl(
            request,
            session_factory=self._session_factory,
        )

    async def persist_resume_analyses(self, request: PersistResumeAnalysesRequestModel) -> int:
        return persist_resume_analyses_impl(
            request,
            session_factory=self._session_factory,
        )

    async def publish_trace(self, run_id: str) -> TracePublicationModel:
        return publish_langfuse_trace_impl(
            run_id,
            self._runtime_settings,
            session_factory=self._session_factory,
            agent_run_tracer_factory=self._agent_run_tracer_factory,
        )


async def execute_agent_run_workflow(
    *,
    run_id: str,
    agents: AgentBundle,
    runtime_settings: Settings,
) -> str:
    io = _WorkflowExecutionIO()
    return await _execute_agent_run(io=io, run_id=run_id, agents=agents, runtime_settings=runtime_settings)


async def run_agent_run_locally(
    run_id: str,
    *,
    runtime_settings: Settings,
    session_factory: SessionFactory | None = None,
    resume_source_factory: ResumeSourceFactory | None = None,
    agent_run_tracer_factory: AgentRunTracerFactory | None = None,
) -> str:
    agents = build_temporal_agents(runtime_settings)
    io = _LocalExecutionIO(
        runtime_settings,
        session_factory=session_factory,
        resume_source_factory=resume_source_factory,
        agent_run_tracer_factory=agent_run_tracer_factory,
    )
    return await _execute_agent_run(io=io, run_id=run_id, agents=agents, runtime_settings=runtime_settings)


async def _execute_agent_run(
    *,
    io: _ExecutionIO,
    run_id: str,
    agents: AgentBundle,
    runtime_settings: Settings,
) -> str:
    run = await io.load_run_snapshot(run_id)
    state = _ExecutionState(run=run)
    minimum_rounds = _effective_min_rounds(runtime_settings, state.run)
    state.run = await io.persist_run_patch(
        RunPersistencePatchModel(
            runId=run_id,
            status="running",
            clearError=True,
        )
    )

    strategy_invocation = resolve_agent_invocation(
        runtime_settings,
        model_version=state.run.agentRuntimeConfig.strategyExtractor.modelVersion,
        thinking_effort=state.run.agentRuntimeConfig.strategyExtractor.thinkingEffort,
    )
    resume_invocation = resolve_agent_invocation(
        runtime_settings,
        model_version=state.run.agentRuntimeConfig.resumeMatcher.modelVersion,
        thinking_effort=state.run.agentRuntimeConfig.resumeMatcher.thinkingEffort,
    )
    reflection_invocation = resolve_agent_invocation(
        runtime_settings,
        model_version=state.run.agentRuntimeConfig.searchReflector.modelVersion,
        thinking_effort=state.run.agentRuntimeConfig.searchReflector.thinkingEffort,
    )
    try:
        strategy_prompt = build_strategy_prompt(
            jd_text=state.run.jdText,
            sourcing_preference_text=state.run.sourcingPreferenceText,
            prompt_version=state.run.promptVersion,
        )
        strategy_result = await agents.strategy_extractor.run(
            strategy_prompt,
            model=strategy_invocation.model,
            model_settings=strategy_invocation.model_settings,
            output_type=StrategyExtractorOutputModel,
        )
        strategy_output = strategy_result.output
        strategy = strategy_output.to_normalized_strategy(state.run.jdText)
        strategy_trace = _build_generation_trace_fact(
            prompt_name=STRATEGY_PROMPT_NAME,
            prompt_label=state.run.promptVersion,
            prompt_text=strategy_prompt,
            result=cast(AgentRunResult[object], strategy_result),
            structured_output=cast(JsonObject, strategy_output.model_dump(mode="json")),
            model_version=strategy_invocation.model_version,
            thinking_effort=strategy_invocation.thinking_effort,
            metadata=to_json_object({"stepType": "strategy", "summary": strategy_output.summary}),
        )
        strategy_step = _append_step(
            state,
            round_no=None,
            step_type="strategy",
            title="Extract search strategy",
            status="completed",
            summary=strategy_output.summary,
            payload={
                "mustRequirements": strategy_output.mustRequirements,
                "coreRequirements": strategy_output.coreRequirements,
                "bonusRequirements": strategy_output.bonusRequirements,
                "excludeSignals": strategy_output.excludeSignals,
                "round1Query": strategy_output.round1Query.model_dump(mode="json"),
                "promptText": strategy_prompt,
                "modelVersion": strategy_invocation.model_version,
                "thinkingEffort": strategy_invocation.thinking_effort,
                "promptVersion": state.run.promptVersion,
                "executionConfig": _execution_config_payload(runtime_settings, state.run),
                "trace": _trace_payload(strategy_trace),
            },
        )
        state.run = await io.persist_run_patch(
            RunPersistencePatchModel(runId=run_id, appendSteps=[strategy_step])
        )

        for round_no, fetch_size in enumerate(
            _round_fetch_schedule(state.run.config),
            start=1,
        ):
            state.run = await io.persist_run_patch(
                RunPersistencePatchModel(runId=run_id, currentRound=round_no)
            )
            search_request, strategy_key, offset = _build_search_request(
                strategy=strategy,
                fetch_size=fetch_size,
                strategy_offsets=state.strategy_offsets,
            )
            search_page = await io.search_candidates(search_request)
            state.strategy_offsets[strategy_key] = offset + len(search_page.candidates)
            search_trace = _build_search_trace_fact(
                request=search_request,
                page=search_page,
                offset=offset,
            )
            search_step = _append_step(
                state,
                round_no=round_no,
                step_type="search",
                title=f"Round {round_no} CTS search",
                status=search_page.status,
                summary=f"CTS 返回 {len(search_page.candidates)} 份候选（total={search_page.total}）。",
                payload={
                    "roundQuery": strategy_to_query_payload(strategy.to_payload()),
                    "normalizedQuery": strategy.model_dump(mode="json"),
                    "pageNo": search_page.pageNo,
                    "pageSize": search_page.pageSize,
                    "offset": offset,
                    "total": search_page.total,
                    "returnedCount": len(search_page.candidates),
                    "candidateIds": [candidate.externalIdentityId for candidate in search_page.candidates],
                    "upstreamRequest": to_json_object(search_page.upstreamRequest),
                    "upstreamResponse": to_json_object(search_page.upstreamResponse),
                    "errorCode": search_page.errorCode,
                    "errorMessage": search_page.errorMessage,
                    "trace": _trace_payload(search_trace),
                },
            )
            state.run = await io.persist_run_patch(
                RunPersistencePatchModel(runId=run_id, appendSteps=[search_step])
            )
            if search_page.errorCode:
                raise ExternalDependencyError(
                    search_page.errorCode,
                    search_page.errorMessage or "CTS search failed.",
                )

            new_candidates, duplicate_ids, updated_seen_ids = _dedupe_candidates(
                state.run.seenResumeIds,
                search_page.candidates,
            )
            dedupe_trace = _build_span_trace_fact(
                input_payload=to_json_object(
                    {
                        "candidateIds": [candidate.externalIdentityId for candidate in search_page.candidates],
                        "seenResumeCountBefore": len(state.run.seenResumeIds),
                    }
                ),
                output_payload=to_json_object(
                    {
                        "admittedResumeIds": [candidate.externalIdentityId for candidate in new_candidates],
                        "duplicateResumeIds": duplicate_ids,
                        "seenResumeCount": len(updated_seen_ids),
                    }
                ),
                metadata=to_json_object({"stepType": "dedupe"}),
            )
            dedupe_step = _append_step(
                state,
                round_no=round_no,
                step_type="dedupe",
                title=f"Round {round_no} dedupe",
                status="completed",
                summary=f"跳过 {len(duplicate_ids)} 份重复简历，放行 {len(new_candidates)} 份新简历进入分析。",
                payload={
                    "admittedResumeIds": [candidate.externalIdentityId for candidate in new_candidates],
                    "duplicateResumeIds": duplicate_ids,
                    "seenResumeCount": len(updated_seen_ids),
                    "trace": _trace_payload(dedupe_trace),
                },
            )
            state.run = await io.persist_run_patch(
                RunPersistencePatchModel(
                    runId=run_id,
                    appendSteps=[dedupe_step],
                    seenResumeIds=updated_seen_ids,
                )
            )
            if new_candidates:
                persisted_candidates = await io.persist_candidate_snapshots(
                    PersistCandidateSnapshotsRequestModel(
                        caseId=state.run.caseId,
                        candidates=new_candidates,
                    )
                )
                state.persisted_candidates.update(
                    {
                        item.externalIdentityId: item
                        for item in persisted_candidates.persisted
                    }
                )

            analyzed_candidates = await _analyze_round_candidates(
                agents=agents,
                run=state.run,
                round_no=round_no,
                strategy=strategy,
                candidates=new_candidates,
                persisted_candidates=state.persisted_candidates,
                invocation=resume_invocation,
            )
            if analyzed_candidates:
                await io.persist_resume_analyses(
                    PersistResumeAnalysesRequestModel(
                        analyses=[
                            PersistResumeAnalysisItemModel(
                                candidateId=analyzed.shortlisted.candidate_id,
                                externalIdentityId=analyzed.shortlisted.candidate.externalIdentityId,
                                resumeSnapshotId=analyzed.resume_snapshot_id,
                                modelVersion=analyzed.model_version,
                                promptVersion=analyzed.prompt_version,
                                summary=analyzed.shortlisted.reason,
                                evidence=analyzed.evidence,
                                concerns=analyzed.concerns,
                                trace=analyzed.trace_fact,
                            )
                            for analyzed in analyzed_candidates
                        ]
                    )
                )
            analysis_trace = _build_span_trace_fact(
                input_payload=to_json_object(
                    {"summary": "resume-analysis", "analyzedCount": len(analyzed_candidates)}
                ),
                output_payload=to_json_object(
                    {
                        "analyzedCount": len(analyzed_candidates),
                        "candidateIds": [
                            analyzed.shortlisted.candidate.externalIdentityId for analyzed in analyzed_candidates
                        ],
                    }
                ),
                metadata=to_json_object({"stepType": "analysis", "title": f"Round {round_no} analysis"}),
            )
            analysis_step = _append_step(
                state,
                round_no=round_no,
                step_type="analysis",
                title=f"Round {round_no} analysis",
                status="completed",
                summary=(
                    "本轮没有新的候选进入分析。"
                    if not analyzed_candidates
                    else f"已完成 {len(analyzed_candidates)} 份新简历的匹配分析。"
                ),
                payload={
                    "analyses": [
                        {
                            "candidateId": analyzed.shortlisted.candidate_id,
                            "externalIdentityId": analyzed.shortlisted.candidate.externalIdentityId,
                            "name": analyzed.shortlisted.candidate.name,
                            "score": round(analyzed.shortlisted.score, 4),
                            "reason": analyzed.shortlisted.reason,
                            "evidence": analyzed.evidence,
                            "concerns": analyzed.concerns,
                            "promptText": analyzed.prompt_text,
                            "modelVersion": analyzed.model_version,
                            "thinkingEffort": analyzed.thinking_effort,
                            "promptVersion": analyzed.prompt_version,
                            "trace": _trace_payload(analyzed.trace_fact),
                        }
                        for analyzed in analyzed_candidates
                    ],
                    "trace": _trace_payload(analysis_trace),
                },
            )
            retained_count_before = len(state.retained_candidates)
            state.retained_candidates = _rank_candidates(
                retained_candidates=state.retained_candidates,
                analyzed_candidates=analyzed_candidates,
                final_top_k=_final_top_k(state.run.config),
            )
            shortlist_trace = _build_span_trace_fact(
                input_payload=to_json_object(
                    {
                        "analyzedCandidateIds": [
                            analyzed.shortlisted.candidate.externalIdentityId for analyzed in analyzed_candidates
                        ],
                        "retainedCountBefore": retained_count_before,
                    }
                ),
                output_payload=to_json_object(
                    {
                        "retainedCount": len(state.retained_candidates),
                        "retainedCandidateIds": [
                            candidate.candidate.externalIdentityId for candidate in state.retained_candidates
                        ],
                    }
                ),
                metadata=to_json_object({"stepType": "shortlist", "title": f"Round {round_no} shortlist"}),
            )
            shortlist_step = _append_step(
                state,
                round_no=round_no,
                step_type="shortlist",
                title=f"Round {round_no} shortlist",
                status="completed",
                summary=f"第 {round_no} 轮保留了 {len(state.retained_candidates)} 份候选，本轮新增分析 {len(analyzed_candidates)} 份。",
                payload={
                    "retainedCount": len(state.retained_candidates),
                    "retainedCandidates": [candidate.to_model().model_dump(mode="json") for candidate in state.retained_candidates],
                    "analyzedCandidateIds": [
                        analyzed.shortlisted.candidate.externalIdentityId for analyzed in analyzed_candidates
                    ],
                    "analyzedCaseCandidateIds": [
                        analyzed.shortlisted.candidate_id for analyzed in analyzed_candidates
                    ],
                    "retainedCandidateIds": [
                        candidate.candidate.externalIdentityId for candidate in state.retained_candidates
                    ],
                    "retainedCaseCandidateIds": [
                        candidate.candidate_id for candidate in state.retained_candidates
                    ],
                    "trace": _trace_payload(shortlist_trace),
                },
            )
            state.run = await io.persist_run_patch(
                RunPersistencePatchModel(
                    runId=run_id,
                    appendSteps=[analysis_step, shortlist_step],
                    finalShortlist=[candidate.to_model() for candidate in state.retained_candidates],
                )
            )

            shortlist_signature = tuple(
                candidate.candidate.externalIdentityId for candidate in state.retained_candidates
            )
            if len(new_candidates) == 0 or shortlist_signature == state.previous_shortlist_signature:
                state.no_progress_rounds += 1
            else:
                state.no_progress_rounds = 0
            state.previous_shortlist_signature = shortlist_signature

            should_stop, rule_stop_reason = _should_stop_after_round(
                config=state.run.config,
                min_rounds=minimum_rounds,
                round_no=round_no,
                no_progress_rounds=state.no_progress_rounds,
            )
            if should_stop:
                state.stop_reason = rule_stop_reason
                stop_trace = _build_span_trace_fact(
                    input_payload=to_json_object({"roundNo": round_no, "source": "rule"}),
                    output_payload=to_json_object({"reason": rule_stop_reason, "source": "rule"}),
                    metadata=to_json_object({"stepType": "stop"}),
                    level="WARNING",
                    status_message=rule_stop_reason,
                )
                stop_step = _append_step(
                    state,
                    round_no=round_no,
                    step_type="stop",
                    title=f"Round {round_no} stop",
                    status="completed",
                    summary=rule_stop_reason,
                    payload={
                        "reason": rule_stop_reason,
                        "source": "rule",
                        "trace": _trace_payload(stop_trace),
                    },
                )
                state.run = await io.persist_run_patch(
                    RunPersistencePatchModel(runId=run_id, appendSteps=[stop_step])
                )
                break

            reflection_prompt = build_search_reflection_prompt(
                jd_text=state.run.jdText,
                sourcing_preference_text=state.run.sourcingPreferenceText,
                strategy=strategy,
                steps=state.run.steps,
                min_rounds=minimum_rounds,
                round_no=round_no,
                max_rounds=_max_rounds(state.run.config),
                new_candidate_count=len(new_candidates),
                seen_candidate_count=len(state.run.seenResumeIds),
                prompt_version=state.run.promptVersion,
            )
            reflection_result = await agents.search_reflector.run(
                reflection_prompt,
                model=reflection_invocation.model,
                model_settings=reflection_invocation.model_settings,
                output_type=SearchReflectorOutputModel,
            )
            minimum_round_override_applied = False
            reflection_result_output = reflection_result.output
            if not reflection_result_output.continueSearch and round_no < minimum_rounds:
                reflection_output = SearchReflectorOutputModel(
                    continueSearch=True,
                    reason=f"{reflection_result_output.reason}；未达到最少 {minimum_rounds} 轮，系统继续执行下一轮。",
                    nextRoundGoal="继续执行直到达到最少轮次，再评估是否提前停止。",
                    nextRoundQuery=reflection_result_output.nextRoundQuery,
                )
                minimum_round_override_applied = True
            else:
                reflection_output = reflection_result_output
            next_strategy = reflection_output.to_normalized_strategy(state.run.jdText)
            current_query = strategy_to_query_payload(strategy.to_payload())
            next_query = strategy_to_query_payload(next_strategy.to_payload())
            reflection_trace = _build_generation_trace_fact(
                prompt_name=SEARCH_REFLECTION_PROMPT_NAME,
                prompt_label=state.run.promptVersion,
                prompt_text=reflection_prompt,
                result=cast(AgentRunResult[object], reflection_result),
                structured_output=cast(JsonObject, reflection_output.model_dump(mode="json")),
                model_version=reflection_invocation.model_version,
                thinking_effort=reflection_invocation.thinking_effort,
                metadata=to_json_object(
                    {
                        "stepType": "reflection",
                        "summary": reflection_output.reason,
                        "minimumRoundsOverrideApplied": minimum_round_override_applied,
                    }
                ),
            )
            reflection_step = _append_step(
                state,
                round_no=round_no,
                step_type="reflection",
                title=f"Round {round_no} reflection",
                status="completed",
                summary=reflection_output.reason,
                payload={
                    "continueSearch": reflection_output.continueSearch,
                    "reason": reflection_output.reason,
                    "nextRoundGoal": reflection_output.nextRoundGoal,
                    "nextRoundQuery": next_query,
                    "queryDelta": build_query_delta(current_query, next_query),
                    "minimumRoundsOverrideApplied": minimum_round_override_applied,
                    "promptText": reflection_prompt,
                    "modelVersion": reflection_invocation.model_version,
                    "thinkingEffort": reflection_invocation.thinking_effort,
                    "promptVersion": state.run.promptVersion,
                    "executionConfig": _execution_config_payload(runtime_settings, state.run),
                    "trace": _trace_payload(reflection_trace),
                },
            )
            state.run = await io.persist_run_patch(
                RunPersistencePatchModel(runId=run_id, appendSteps=[reflection_step])
            )
            if not reflection_output.continueSearch:
                state.stop_reason = reflection_output.reason
                stop_trace = _build_span_trace_fact(
                    input_payload=to_json_object({"roundNo": round_no, "source": "reflection"}),
                    output_payload=to_json_object({"reason": reflection_output.reason, "source": "reflection"}),
                    metadata=to_json_object({"stepType": "stop"}),
                    level="WARNING",
                    status_message=reflection_output.reason,
                )
                stop_step = _append_step(
                    state,
                    round_no=round_no,
                    step_type="stop",
                    title=f"Round {round_no} stop",
                    status="completed",
                    summary=reflection_output.reason,
                    payload={
                        "reason": reflection_output.reason,
                        "source": "reflection",
                        "trace": _trace_payload(stop_trace),
                    },
                )
                state.run = await io.persist_run_patch(
                    RunPersistencePatchModel(runId=run_id, appendSteps=[stop_step])
                )
                break
            if (
                round_no >= minimum_rounds
                and strategy_signature(next_strategy.to_payload()) == strategy_signature(strategy.to_payload())
                and state.no_progress_rounds >= 1
            ):
                state.stop_reason = "下一轮查询与上一轮实质相同且没有新增价值，系统停止继续检索。"
                duplicate_stop_trace = _build_span_trace_fact(
                    input_payload=to_json_object({"roundNo": round_no, "source": "duplicate-strategy"}),
                    output_payload=to_json_object(
                        {
                            "reason": state.stop_reason,
                            "source": "duplicate-strategy",
                            "duplicateStrategy": next_query,
                        }
                    ),
                    metadata=to_json_object({"stepType": "stop"}),
                    level="WARNING",
                    status_message=state.stop_reason,
                )
                stop_step = _append_step(
                    state,
                    round_no=round_no,
                    step_type="stop",
                    title=f"Round {round_no} duplicate strategy blocked",
                    status="completed",
                    summary=state.stop_reason,
                    payload={
                        "reason": state.stop_reason,
                        "source": "duplicate-strategy",
                        "duplicateStrategy": next_query,
                        "trace": _trace_payload(duplicate_stop_trace),
                    },
                )
                state.run = await io.persist_run_patch(
                    RunPersistencePatchModel(runId=run_id, appendSteps=[stop_step])
                )
                break
            strategy = next_strategy

        finalize_trace = _build_span_trace_fact(
            input_payload=to_json_object({"currentRound": state.run.currentRound or None}),
            output_payload=to_json_object(
                {
                    "finalShortlist": [candidate.to_model().model_dump(mode="json") for candidate in state.retained_candidates],
                    "stopReason": state.stop_reason,
                }
            ),
            metadata=to_json_object({"stepType": "finalize"}),
        )
        finalize_step = _append_step(
            state,
            round_no=state.run.currentRound or None,
            step_type="finalize",
            title="Finalize shortlist",
            status="completed",
            summary=f"最终 shortlist 选出了 {len(state.retained_candidates)} 份简历。",
            payload={
                "finalShortlist": [candidate.to_model().model_dump(mode="json") for candidate in state.retained_candidates],
                "stopReason": state.stop_reason,
                "executionConfig": _execution_config_payload(runtime_settings, state.run),
                "trace": _trace_payload(finalize_trace),
            },
        )
        state.run = await io.persist_run_patch(
            RunPersistencePatchModel(
                runId=run_id,
                status="completed",
                appendSteps=[finalize_step],
                finalShortlist=[candidate.to_model() for candidate in state.retained_candidates],
                markFinished=True,
            )
        )
        await _publish_trace_quietly(
            io=io,
            state=state,
            run_id=run_id,
            terminal_status="completed",
        )
        return "completed"
    except Exception as exc:
        error_code = getattr(exc, "code", "AGENT_RUN_FAILED")
        error_message = getattr(exc, "message", str(exc))
        state.run = await io.persist_run_patch(
            RunPersistencePatchModel(
                runId=run_id,
                status="failed",
                errorCode=error_code,
                errorMessage=error_message,
                markFinished=True,
            )
        )
        await _publish_trace_quietly(
            io=io,
            state=state,
            run_id=run_id,
            terminal_status="failed",
        )
        return "failed"


def _append_step(
    state: _ExecutionState,
    *,
    round_no: int | None,
    step_type: str,
    title: str,
    status: str,
    summary: str,
    payload: dict[str, object],
) -> AgentRunStepModel:
    step_payload = append_agent_run_step(
        [step.to_payload() for step in state.run.steps],
        round_no=round_no,
        step_type=step_type,
        title=title,
        status=status,
        summary=summary,
        payload=payload,
    )
    step = AgentRunStepModel.from_payload(step_payload)
    state.run.steps.append(step.compact_for_workflow())
    return step


def _build_search_request(
    *,
    strategy: NormalizedStrategyModel,
    fetch_size: int,
    strategy_offsets: dict[str, int],
) -> tuple[CtsSearchRequestModel, str, int]:
    signature = strategy_signature(strategy.to_payload())
    offset = strategy_offsets.get(signature, 0)
    page_no = (offset // fetch_size) + 1
    return (
        CtsSearchRequestModel(
            normalizedStrategy=strategy,
            pageNo=page_no,
            pageSize=fetch_size,
        ),
        signature,
        offset,
    )


def _dedupe_candidates(
    seen_resume_ids: list[str],
    candidates: list[WorkerCandidateModel],
) -> tuple[list[WorkerCandidateModel], list[str], list[str]]:
    seen_ids = set(seen_resume_ids)
    duplicate_ids: list[str] = []
    admitted: list[WorkerCandidateModel] = []
    round_seen: set[str] = set()
    ordered_seen = list(seen_resume_ids)
    for candidate in candidates:
        candidate_id = candidate.externalIdentityId
        if candidate_id in seen_ids or candidate_id in round_seen:
            duplicate_ids.append(candidate_id)
            continue
        admitted.append(candidate)
        round_seen.add(candidate_id)
        seen_ids.add(candidate_id)
        ordered_seen.append(candidate_id)
    return admitted, duplicate_ids, ordered_seen


async def _analyze_round_candidates(
    *,
    agents: AgentBundle,
    run: AgentRunSnapshotModel,
    round_no: int,
    strategy: NormalizedStrategyModel,
    candidates: list[WorkerCandidateModel],
    persisted_candidates: dict[str, PersistedCandidateRefModel],
    invocation: ResolvedAgentInvocation,
) -> list[_AnalyzedCandidate]:
    if not candidates:
        return []
    prompts = [
        build_resume_match_prompt(
            jd_text=run.jdText,
            sourcing_preference_text=run.sourcingPreferenceText,
            strategy=strategy,
            candidate=candidate,
            prompt_version=run.promptVersion,
        )
        for candidate in candidates
    ]
    tasks: list[Awaitable[AgentRunResult[ResumeMatcherOutputModel]]] = [
        cast(
            Awaitable[AgentRunResult[ResumeMatcherOutputModel]],
            agents.resume_matcher.run(
                prompt,
                model=invocation.model,
                model_settings=invocation.model_settings,
                output_type=ResumeMatcherOutputModel,
            ),
        )
        for prompt in prompts
    ]
    results = await asyncio.gather(*tasks)
    analyzed_candidates: list[_AnalyzedCandidate] = []
    for candidate, prompt, result in zip(candidates, prompts, results, strict=True):
        persisted_candidate = persisted_candidates.get(candidate.externalIdentityId)
        if persisted_candidate is None:
            raise RuntimeError(
                f"Persisted candidate reference missing for {candidate.externalIdentityId}."
            )
        output = result.output
        trace_fact = _build_generation_trace_fact(
            prompt_name=RESUME_MATCH_PROMPT_NAME,
            prompt_label=run.promptVersion,
            prompt_text=prompt,
            result=cast(AgentRunResult[object], result),
            structured_output=cast(JsonObject, output.model_dump(mode="json")),
            model_version=invocation.model_version,
            thinking_effort=invocation.thinking_effort,
            metadata=to_json_object(
                {
                    "candidateId": persisted_candidate.candidateId,
                    "externalIdentityId": candidate.externalIdentityId,
                    "candidateName": candidate.name,
                }
            ),
        )
        analyzed_candidates.append(
            _AnalyzedCandidate(
                shortlisted=_ShortlistedCandidate(
                    candidate_id=persisted_candidate.candidateId,
                    candidate=candidate,
                    score=max(0.0, min(output.score, 0.99)),
                    reason=output.summary,
                    source_round=round_no,
                ),
                resume_snapshot_id=persisted_candidate.resumeSnapshotId,
                prompt_text=prompt,
                model_version=invocation.model_version,
                prompt_version=run.promptVersion,
                thinking_effort=invocation.thinking_effort,
                evidence=list(output.evidence),
                concerns=list(output.concerns),
                trace_fact=trace_fact,
            )
        )
    return analyzed_candidates


def _rank_candidates(
    *,
    retained_candidates: list[_ShortlistedCandidate],
    analyzed_candidates: list[_AnalyzedCandidate],
    final_top_k: int,
) -> list[_ShortlistedCandidate]:
    merged = retained_candidates + [item.shortlisted for item in analyzed_candidates]
    merged.sort(
        key=lambda item: (
            -item.score,
            item.source_round,
            item.candidate.externalIdentityId,
        )
    )
    deduped: list[_ShortlistedCandidate] = []
    seen_ids: set[str] = set()
    for candidate in merged:
        candidate_id = candidate.candidate.externalIdentityId
        if candidate_id in seen_ids:
            continue
        seen_ids.add(candidate_id)
        deduped.append(candidate)
        if len(deduped) >= final_top_k:
            break
    return deduped


def _should_stop_after_round(
    *,
    config: AgentRunConfigPayload,
    min_rounds: int,
    round_no: int,
    no_progress_rounds: int,
) -> tuple[bool, str]:
    if round_no >= _max_rounds(config):
        return True, "已达到配置的最大轮次，停止继续检索。"
    if round_no >= min_rounds and no_progress_rounds >= 2:
        return True, "连续两轮没有新增价值，停止继续检索。"
    return False, ""
