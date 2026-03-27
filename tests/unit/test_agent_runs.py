from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path

import pytest
from pydantic_ai.usage import RunUsage

from cvm_platform.application.agent_runs import (
    AgentRunsCoordinator,
    append_agent_run_step,
    build_agent_runtime_config,
    build_compact_round_ledger,
    build_query_delta,
    build_search_strategy,
    effective_agent_runtime_config,
    normalize_agent_run_config,
)
from cvm_platform.application.dto import AgentRunRecord
from cvm_platform.application.runtime import PlatformRuntimeConfig
from cvm_platform.domain.errors import NotFoundError, ValidationError
from cvm_platform.infrastructure.mock_catalog import MOCK_CANDIDATES
from cvm_platform.settings.config import Settings
from cvm_worker.execution import _execute_agent_run
from cvm_worker.models import (
    AgentRunSnapshotModel,
    AgentRunStepModel,
    AgentRuntimeConfigModel,
    CtsSearchRequestModel,
    PersistCandidateSnapshotsRequestModel,
    PersistCandidateSnapshotsResultModel,
    PersistResumeAnalysesRequestModel,
    PersistedCandidateRefModel,
    ResumeMatcherOutputModel,
    RunPersistencePatchModel,
    SearchQueryModel,
    SearchReflectorOutputModel,
    ShortlistCandidateModel,
    StrategyExtractorOutputModel,
    StructuredFiltersModel,
    TracePublicationModel,
    WorkerCandidateModel,
    WorkerSearchPageModel,
)


def _runtime_config(*, min_rounds: int = 3, max_rounds: int = 5) -> PlatformRuntimeConfig:
    return PlatformRuntimeConfig(
        temporal_namespace="default",
        temporal_task_queue="cvm-agent-runs",
        allow_sensitive_export=False,
        exports_dir=Path("var/exports"),
        app_version="0.1.0",
        build_id="test-build",
        temporal_ui_base_url="http://127.0.0.1:8080",
        temporal_visibility_backend="opensearch",
        default_agent_model="gpt-5.4-mini",
        default_agent_thinking="low",
        agent_model_overrides={"searchReflector": "gpt-5.4"},
        agent_thinking_overrides={"searchReflector": "medium"},
        default_agent_prompt_version="agent-loop-v1",
        agent_profile="deterministic",
        default_agent_min_rounds=min_rounds,
        default_agent_max_rounds=max_rounds,
        default_agent_round_fetch_schedule=[10, 5, 5],
        default_agent_final_top_k=5,
    )


def _runtime_settings(*, min_rounds: int = 3, max_rounds: int = 5) -> Settings:
    return Settings(
        _env_file=None,
        agent_profile="deterministic",
        agent_thinking="low",
        agent_model_search_reflector="gpt-5.4",
        agent_thinking_search_reflector="medium",
        agent_min_rounds=min_rounds,
        agent_max_rounds=max_rounds,
        agent_round_fetch_schedule="10,5,5",
        agent_final_top_k=5,
    )


def _candidate(index: int) -> WorkerCandidateModel:
    payload = MOCK_CANDIDATES[index]
    return WorkerCandidateModel(
        externalIdentityId=payload["external_identity_id"],
        name=payload["name"],
        title=payload["title"],
        company=payload["company"],
        location=payload["location"],
        summary=payload["summary"],
        email=payload["email"],
        phone=payload["phone"],
        resumeProjection=dict(payload["resumeProjection"]),
    )


def _search_page(candidate_index: int, *, page_no: int, page_size: int) -> WorkerSearchPageModel:
    candidate = _candidate(candidate_index)
    return WorkerSearchPageModel(
        status="completed",
        total=1,
        pageNo=page_no,
        pageSize=page_size,
        candidates=[candidate],
        upstreamRequest={"page": page_no, "pageSize": page_size},
        upstreamResponse={"status": "ok", "candidateIds": [candidate.externalIdentityId]},
    )


def _snapshot(*, max_rounds: int, schedule: list[int]) -> AgentRunSnapshotModel:
    return AgentRunSnapshotModel(
        id="agent_123",
        caseId="case_agent_123",
        status="queued",
        jdText="需要 AI Agent 工程师，熟悉 Python、ReAct、workflow orchestration。",
        sourcingPreferenceText="优先上海，优先 agent 和 eval 背景。",
        config={"maxRounds": max_rounds, "roundFetchSchedule": schedule, "finalTopK": 5},
        currentRound=0,
        modelVersion="gpt-5.4-mini",
        agentRuntimeConfig={
            "strategyExtractor": {"modelVersion": "gpt-5.4-mini", "thinkingEffort": "low"},
            "resumeMatcher": {"modelVersion": "gpt-5.4-mini", "thinkingEffort": "low"},
            "searchReflector": {"modelVersion": "gpt-5.4", "thinkingEffort": "medium"},
        },
        promptVersion="agent-loop-v1",
        workflowId="agent-run-agent_123",
        temporalNamespace="default",
        temporalTaskQueue="cvm-agent-runs",
        langfuseTraceId=None,
        langfuseTraceUrl=None,
        steps=[],
        finalShortlist=[],
        seenResumeIds=[],
        errorCode=None,
        errorMessage=None,
    )


def _strategy_output() -> StrategyExtractorOutputModel:
    return StrategyExtractorOutputModel(
        mustRequirements=["Python", "Agent"],
        coreRequirements=["ReAct"],
        bonusRequirements=["eval"],
        excludeSignals=[],
        round1Query=SearchQueryModel(
            keyword="Python Agent ReAct",
            mustTerms=["Python", "Agent"],
            shouldTerms=["ReAct"],
            excludeTerms=[],
            structuredFilters=StructuredFiltersModel(page=1, pageSize=10, location=["上海"]),
        ),
        summary="已提炼出首轮 CTS 查询。",
    )


def _reflection_output(*, continue_search: bool) -> SearchReflectorOutputModel:
    return SearchReflectorOutputModel(
        continueSearch=continue_search,
        reason="当前 top 5 已经足够强，建议停止。" if not continue_search else "继续补充更多候选。",
        nextRoundGoal="停止并输出当前 shortlist。" if not continue_search else "继续补充候选。",
        nextRoundQuery=SearchQueryModel(
            keyword="Python Agent ReAct",
            mustTerms=["Python", "Agent"],
            shouldTerms=["ReAct"],
            excludeTerms=[],
            structuredFilters=StructuredFiltersModel(page=1, pageSize=10, location=["上海"]),
        ),
    )


@dataclass
class _QueuedAgent:
    outputs: list[object]

    def __post_init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    @staticmethod
    def _output_payload(output: object) -> dict[str, object]:
        if hasattr(output, "model_dump"):
            return output.model_dump(mode="json")
        if isinstance(output, dict):
            return output
        raise TypeError(f"Unsupported fake output payload: {output!r}")

    async def run(
        self,
        prompt: str,
        *,
        model: str | None,
        model_settings: object | None = None,
        output_type: object,
    ) -> "_FakeAgentRunResult":
        self.calls.append(
            {
                "prompt": prompt,
                "model": model,
                "model_settings": model_settings,
                "output_type": output_type,
            }
        )
        index = min(len(self.calls) - 1, len(self.outputs) - 1)
        usage = RunUsage(
            requests=1,
            input_tokens=32 + index,
            output_tokens=9 + index,
            details={"reasoning_tokens": 5 + index},
        )
        return _FakeAgentRunResult(
            output=self.outputs[index],
            prompt=prompt,
            model_name=str(model or "deterministic"),
            usage_value=usage,
        )


@dataclass
class _FakeAgentRunResult:
    output: object
    prompt: str
    model_name: str
    usage_value: RunUsage
    created_at: datetime = datetime(2026, 3, 27, 9, 0, 0)

    def all_messages_json(self, *, output_tool_return_content: str | None = None) -> bytes:
        del output_tool_return_content
        payload = _QueuedAgent._output_payload(self.output)
        messages = [
            {
                "kind": "request",
                "parts": [
                    {
                        "part_kind": "user-prompt",
                        "content": self.prompt,
                    }
                ],
            },
            {
                "kind": "response",
                "model_name": self.model_name,
                "usage": {
                    "input_tokens": self.usage_value.input_tokens,
                    "output_tokens": self.usage_value.output_tokens,
                    "details": dict(self.usage_value.details),
                },
                "parts": [
                    {
                        "part_kind": "tool-call",
                        "args": payload,
                    }
                ],
            },
            {
                "kind": "request",
                "parts": [
                    {
                        "part_kind": "tool-return",
                        "content": payload,
                    }
                ],
            },
        ]
        return json.dumps(messages, ensure_ascii=False).encode("utf-8")

    def usage(self) -> RunUsage:
        return self.usage_value

    def timestamp(self) -> datetime:
        return self.created_at


@dataclass
class _FakeAgentBundle:
    strategy_extractor: _QueuedAgent
    resume_matcher: _QueuedAgent
    search_reflector: _QueuedAgent


class _MemoryExecutionIO:
    def __init__(
        self,
        snapshot: AgentRunSnapshotModel,
        pages: list[WorkerSearchPageModel],
        *,
        publish_error: Exception | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.pages = pages
        self.publish_error = publish_error
        self.patches: list[RunPersistencePatchModel] = []
        self.requests: list[CtsSearchRequestModel] = []
        self.persisted_candidates: list[PersistCandidateSnapshotsRequestModel] = []
        self.persisted_analyses: list[PersistResumeAnalysesRequestModel] = []
        self.published: list[str] = []

    async def load_run_snapshot(self, run_id: str) -> AgentRunSnapshotModel:
        assert run_id == self.snapshot.id
        return self.snapshot.compact_for_workflow()

    async def persist_run_patch(self, patch: RunPersistencePatchModel) -> AgentRunSnapshotModel:
        self.patches.append(patch)
        if patch.clearError:
            self.snapshot.errorCode = None
            self.snapshot.errorMessage = None
        if patch.status is not None:
            self.snapshot.status = patch.status
        if patch.currentRound is not None:
            self.snapshot.currentRound = patch.currentRound
        if patch.appendSteps:
            self.snapshot.steps.extend(step.model_copy(deep=True) for step in patch.appendSteps)
        if patch.finalShortlist is not None:
            self.snapshot.finalShortlist = [
                candidate.model_copy(deep=True) if isinstance(candidate, ShortlistCandidateModel) else candidate
                for candidate in patch.finalShortlist
            ]
        if patch.seenResumeIds is not None:
            self.snapshot.seenResumeIds = list(patch.seenResumeIds)
        if patch.errorCode is not None:
            self.snapshot.errorCode = patch.errorCode
        if patch.errorMessage is not None:
            self.snapshot.errorMessage = patch.errorMessage
        if patch.langfuseTraceId is not None:
            self.snapshot.langfuseTraceId = patch.langfuseTraceId
        if patch.langfuseTraceUrl is not None:
            self.snapshot.langfuseTraceUrl = patch.langfuseTraceUrl
        return self.snapshot.compact_for_workflow()

    async def search_candidates(self, request: CtsSearchRequestModel) -> WorkerSearchPageModel:
        self.requests.append(request)
        index = min(len(self.requests) - 1, len(self.pages) - 1)
        page = self.pages[index]
        return page.model_copy(deep=True)

    async def persist_candidate_snapshots(
        self,
        request: PersistCandidateSnapshotsRequestModel,
    ) -> PersistCandidateSnapshotsResultModel:
        self.persisted_candidates.append(request)
        return PersistCandidateSnapshotsResultModel(
            persisted=[
                PersistedCandidateRefModel(
                    candidateId=f"cand_{candidate.externalIdentityId}",
                    externalIdentityId=candidate.externalIdentityId,
                    resumeSnapshotId=f"snap_{candidate.externalIdentityId}",
                )
                for candidate in request.candidates
            ]
        )

    async def persist_resume_analyses(self, request: PersistResumeAnalysesRequestModel) -> int:
        self.persisted_analyses.append(request)
        return len(request.analyses)

    async def publish_trace(self, run_id: str) -> TracePublicationModel:
        self.published.append(run_id)
        if self.publish_error is not None:
            raise self.publish_error
        return TracePublicationModel(traceId=f"trace-{run_id}", traceUrl=f"http://langfuse/{run_id}")


@dataclass
class _FakeCasesRepository:
    saved_cases: list[object] | None = None

    def __post_init__(self) -> None:
        if self.saved_cases is None:
            self.saved_cases = []

    def save(self, case) -> object:
        self.saved_cases.append(case)
        return case


@dataclass
class _FakePlansRepository:
    saved_versions: list[object] | None = None
    deactivated_case_ids: list[str] | None = None

    def __post_init__(self) -> None:
        if self.saved_versions is None:
            self.saved_versions = []
        if self.deactivated_case_ids is None:
            self.deactivated_case_ids = []

    def deactivate_versions(self, case_id: str) -> None:
        self.deactivated_case_ids.append(case_id)

    def save_jd_version(self, version) -> object:
        self.saved_versions.append(version)
        return version


@dataclass
class _FakeAgentRunRepository:
    run: AgentRunRecord | None = None

    def __post_init__(self) -> None:
        self.lookup_ids: list[str] = []
        self.saved_runs: list[AgentRunRecord] = []

    def find_by_idempotency_key(self, idempotency_key: str) -> AgentRunRecord | None:
        if self.run is not None and self.run.idempotency_key == idempotency_key:
            return self.run
        return None

    def get_run(self, run_id: str) -> AgentRunRecord | None:
        self.lookup_ids.append(run_id)
        if self.run is not None and self.run.id == run_id:
            return self.run
        return None

    def save_run(self, run: AgentRunRecord) -> None:
        self.saved_runs.append(run)
        self.run = run

    def list_runs(self) -> list[AgentRunRecord]:
        return [self.run] if self.run is not None else []


@dataclass
class _FakeAuditLogRepository:
    entries: list[object] | None = None

    def __post_init__(self) -> None:
        if self.entries is None:
            self.entries = []

    def save_audit_log(self, audit) -> None:
        self.entries.append(audit)


@dataclass
class _FakeUow:
    agent_runs: _FakeAgentRunRepository

    def __post_init__(self) -> None:
        self.cases = _FakeCasesRepository()
        self.plans = _FakePlansRepository()
        self.audit_logs = _FakeAuditLogRepository()
        self.commit_count = 0

    def commit(self) -> None:
        self.commit_count += 1


def test_normalize_agent_run_config_extends_schedule_to_max_rounds() -> None:
    normalized = normalize_agent_run_config(
        {"maxRounds": 5, "roundFetchSchedule": [10, 5, 5], "finalTopK": 5},
        _runtime_config(),
    )

    assert normalized == {
        "maxRounds": 5,
        "roundFetchSchedule": [10, 5, 5, 5, 5],
        "finalTopK": 5,
    }


def test_build_agent_runtime_config_applies_default_and_role_overrides() -> None:
    frozen = build_agent_runtime_config(
        baseline_model_version="gpt-5.4-mini",
        runtime_config=_runtime_config(),
    )

    assert frozen == {
        "strategyExtractor": {"modelVersion": "gpt-5.4-mini", "thinkingEffort": "low"},
        "resumeMatcher": {"modelVersion": "gpt-5.4-mini", "thinkingEffort": "low"},
        "searchReflector": {"modelVersion": "gpt-5.4", "thinkingEffort": "medium"},
    }


def test_effective_agent_runtime_config_synthesizes_legacy_runs() -> None:
    effective = effective_agent_runtime_config(None, fallback_model_version="gpt-5.4-mini")

    assert effective == {
        "strategyExtractor": {"modelVersion": "gpt-5.4-mini", "thinkingEffort": None},
        "resumeMatcher": {"modelVersion": "gpt-5.4-mini", "thinkingEffort": None},
        "searchReflector": {"modelVersion": "gpt-5.4-mini", "thinkingEffort": None},
    }


def test_effective_agent_runtime_config_repairs_malformed_entry() -> None:
    effective = effective_agent_runtime_config(
        {
            "strategyExtractor": "bad-entry",
            "resumeMatcher": {"modelVersion": "gpt-5.4-mini", "thinkingEffort": "LOW"},
            "searchReflector": {"modelVersion": "", "thinkingEffort": None},
        },  # type: ignore[arg-type]
        fallback_model_version="gpt-5.4-mini",
    )

    assert effective["strategyExtractor"] == {"modelVersion": "gpt-5.4-mini", "thinkingEffort": None}
    assert effective["resumeMatcher"] == {"modelVersion": "gpt-5.4-mini", "thinkingEffort": "low"}
    assert effective["searchReflector"] == {"modelVersion": "gpt-5.4-mini", "thinkingEffort": None}


def test_agent_runtime_config_models_round_trip_payload() -> None:
    payload = {
        "strategyExtractor": {"modelVersion": "gpt-5.4-mini", "thinkingEffort": "low"},
        "resumeMatcher": {"modelVersion": "gpt-5.4-mini", "thinkingEffort": "low"},
        "searchReflector": {"modelVersion": "gpt-5.4", "thinkingEffort": "medium"},
    }

    config_model = AgentRuntimeConfigModel.from_payload(payload)

    assert config_model.strategyExtractor.to_payload() == payload["strategyExtractor"]
    assert config_model.to_payload() == payload


def test_normalize_agent_run_config_rejects_invalid_min_max() -> None:
    with pytest.raises(ValidationError, match="maxRounds must be between 4 and 5"):
        normalize_agent_run_config(
            {"maxRounds": 3, "roundFetchSchedule": [10, 5, 5], "finalTopK": 5},
            _runtime_config(min_rounds=4, max_rounds=5),
        )


def test_build_query_delta_reports_structured_filter_changes() -> None:
    previous = {
        "keyword": "python agent",
        "mustTerms": ["Python"],
        "shouldTerms": ["Agent"],
        "excludeTerms": [],
        "structuredFilters": {"location": ["Shanghai"]},
    }
    next_query = {
        "keyword": "python react",
        "mustTerms": ["Python", "ReAct"],
        "shouldTerms": [],
        "excludeTerms": ["Outsource"],
        "structuredFilters": {"location": ["Beijing"]},
    }

    delta = build_query_delta(previous, next_query)

    assert delta["setKeyword"] == "python react"
    assert delta["addedMustTerms"] == ["ReAct"]
    assert delta["removedShouldTerms"] == ["Agent"]
    assert delta["addedExcludeTerms"] == ["Outsource"]
    assert delta["changedStructuredFilters"]["location"]["before"] == ["Shanghai"]
    assert delta["changedStructuredFilters"]["location"]["after"] == ["Beijing"]


def test_append_agent_run_step_normalizes_naive_timestamp() -> None:
    step = append_agent_run_step(
        [],
        round_no=1,
        step_type="stop",
        title="Stop",
        status="completed",
        summary="Reached stop condition.",
        payload={"reason": "done"},
        occurred_at=datetime(2026, 3, 26, 12, 0, 0),
    )

    assert step["occurredAt"].endswith("+00:00")


def test_build_compact_round_ledger_includes_strategy_and_stop_entries() -> None:
    steps = [
        append_agent_run_step(
            [],
            round_no=None,
            step_type="strategy",
            title="Strategy",
            status="completed",
            summary="Extracted strategy.",
            payload={
                "mustRequirements": ["Python"],
                "coreRequirements": ["ReAct"],
                "bonusRequirements": ["Evals"],
                "excludeSignals": [],
                "round1Query": {"keyword": "python", "mustTerms": ["Python"]},
            },
        ),
        append_agent_run_step(
            [],
            round_no=1,
            step_type="stop",
            title="Stop",
            status="completed",
            summary="Stopped after reflection.",
            payload={"reason": "reflector said stop"},
        ),
    ]

    ledger = build_compact_round_ledger(steps)

    assert ledger[0]["extraction"]["mustRequirements"] == ["Python"]
    assert ledger[1]["stop"]["reason"] == "reflector said stop"
    assert ledger[1]["stop"]["summary"] == "Stopped after reflection."


def test_build_compact_round_ledger_returns_rounds_without_extraction_step() -> None:
    steps = [
        append_agent_run_step(
            [],
            round_no=1,
            step_type="shortlist",
            title="Shortlist",
            status="completed",
            summary="Retained top candidates.",
            payload={"retainedCount": 1, "retainedCandidates": [{"externalIdentityId": "resume_1"}]},
        )
    ]

    ledger = build_compact_round_ledger(steps)

    assert ledger == [
        {
            "roundNo": 1,
            "shortlist": {
                "retainedCount": 1,
                "retainedCandidates": [{"externalIdentityId": "resume_1"}],
            },
        }
    ]


def test_agent_run_snapshot_compact_for_workflow_strips_large_trace_payloads() -> None:
    snapshot = _snapshot(max_rounds=3, schedule=[10, 5, 5])
    strategy_step = append_agent_run_step(
        [],
        round_no=None,
        step_type="strategy",
        title="Strategy",
        status="completed",
        summary="Extracted strategy.",
        payload={
            "mustRequirements": ["Python"],
            "coreRequirements": ["Java"],
            "bonusRequirements": ["Vue"],
            "excludeSignals": [],
            "round1Query": {"keyword": "Python Java", "mustTerms": ["Python", "Java"]},
            "promptText": "very large prompt",
            "trace": {"observationType": "generation"},
        },
    )
    analysis_step = append_agent_run_step(
        [strategy_step],
        round_no=1,
        step_type="analysis",
        title="Analysis",
        status="completed",
        summary="Analyzed candidates.",
        payload={
            "analyses": [
                {
                    "candidateId": "cand_1",
                    "externalIdentityId": "cts_001",
                    "name": "张晨",
                    "score": 0.92,
                    "reason": "强匹配",
                    "evidence": ["Python"],
                    "concerns": [],
                    "promptText": "very large prompt",
                    "trace": {"observationType": "generation"},
                }
            ],
            "trace": {"observationType": "span"},
        },
    )
    snapshot.steps = [
        AgentRunStepModel.from_payload(strategy_step),
        AgentRunStepModel.from_payload(analysis_step),
    ]

    compact = snapshot.compact_for_workflow()

    assert "promptText" not in compact.steps[0].payload
    assert "trace" not in compact.steps[0].payload
    assert compact.steps[0].payload["mustRequirements"] == ["Python"]
    assert "trace" not in compact.steps[1].payload
    assert "promptText" not in compact.steps[1].payload["analyses"][0]
    assert compact.steps[1].payload["analyses"][0]["reason"] == "强匹配"


def test_build_search_strategy_rejects_blank_keyword_and_terms() -> None:
    with pytest.raises(ValidationError, match="did not contain any keyword"):
        build_search_strategy(
            jd_text="JD",
            keyword=" ",
            must_terms=[" "],
            should_terms=[" "],
            exclude_terms=[],
            structured_filters={},
        )


def test_build_search_strategy_derives_keyword_from_terms() -> None:
    strategy = build_search_strategy(
        jd_text="JD",
        keyword=" ",
        must_terms=["Python", "Python"],
        should_terms=[" ReAct ", "Python"],
        exclude_terms=[" Outsource "],
        structured_filters={"location": ["Shanghai"]},
    )

    assert strategy["keyword"] == "Python Python ReAct"
    assert strategy["mustTerms"] == ["Python", "Python"]
    assert strategy["shouldTerms"] == ["ReAct"]
    assert strategy["excludeTerms"] == ["Outsource"]


def test_get_run_rejects_invalid_identifier_before_repository_lookup() -> None:
    repo = _FakeAgentRunRepository()
    coordinator = AgentRunsCoordinator(uow=_FakeUow(repo), runtime_config=_runtime_config())

    with pytest.raises(NotFoundError) as exc_info:
        coordinator.get_run("bad\0id")

    assert exc_info.value.code == "AGENT_RUN_NOT_FOUND"
    assert repo.lookup_ids == []


def test_create_run_reuses_existing_run_and_backfills_temporal_identifiers() -> None:
    existing = AgentRunRecord(
        id="agent_123",
        case_id="case_existing",
        status="queued",
        jd_text="JD",
        sourcing_preference_text="pref",
        idempotency_key="idem_1",
        config={"maxRounds": 5, "roundFetchSchedule": [10, 5, 5, 5, 5], "finalTopK": 5},
        current_round=0,
        model_version="gpt-5.4-mini",
        prompt_version="agent-loop-v1",
        agent_runtime_config=None,
        workflow_id=None,
        temporal_namespace=None,
        temporal_task_queue=None,
        langfuse_trace_id=None,
        langfuse_trace_url=None,
        steps=[],
        final_shortlist=[],
        seen_resume_ids=[],
        error_code=None,
        error_message=None,
        created_at=datetime(2026, 3, 26, 12, 0, 0),
        started_at=datetime(2026, 3, 26, 12, 0, 0),
        finished_at=None,
    )
    repo = _FakeAgentRunRepository(run=existing)
    uow = _FakeUow(repo)
    coordinator = AgentRunsCoordinator(uow=uow, runtime_config=_runtime_config())

    result = coordinator.create_run(
        jd_text="JD",
        sourcing_preference_text="pref",
        model_version="",
        prompt_version="agent-loop-v1",
        idempotency_key="idem_1",
        config=None,
    )

    assert result is existing
    assert existing.workflow_id == "agent-run-agent_123"
    assert existing.temporal_namespace == "default"
    assert existing.temporal_task_queue == "cvm-agent-runs"
    assert repo.saved_runs == [existing]
    assert uow.commit_count == 1


def test_execute_agent_run_forces_minimum_rounds_before_reflection_stop() -> None:
    io = _MemoryExecutionIO(
        _snapshot(max_rounds=5, schedule=[10, 5, 5, 5, 5]),
        [
            _search_page(0, page_no=1, page_size=10),
            _search_page(1, page_no=1, page_size=5),
            _search_page(2, page_no=1, page_size=5),
        ],
    )
    agents = _FakeAgentBundle(
        strategy_extractor=_QueuedAgent([_strategy_output()]),
        resume_matcher=_QueuedAgent(
            [
                ResumeMatcherOutputModel(score=0.92, summary="强匹配", evidence=["Python"], concerns=[]),
                ResumeMatcherOutputModel(score=0.88, summary="匹配良好", evidence=["Agent"], concerns=[]),
                ResumeMatcherOutputModel(score=0.85, summary="可进入 shortlist", evidence=["ReAct"], concerns=[]),
            ]
        ),
        search_reflector=_QueuedAgent(
            [
                _reflection_output(continue_search=False),
                _reflection_output(continue_search=False),
                _reflection_output(continue_search=False),
            ]
        ),
    )

    result = asyncio.run(
        _execute_agent_run(
            io=io,
            run_id="agent_123",
            agents=agents,
            runtime_settings=_runtime_settings(min_rounds=3, max_rounds=5),
        )
    )

    reflection_steps = [step for step in io.snapshot.steps if step.stepType == "reflection"]
    stop_steps = [step for step in io.snapshot.steps if step.stepType == "stop"]

    assert result == "completed"
    assert [request.pageSize for request in io.requests] == [10, 5, 5]
    assert len(reflection_steps) == 3
    assert reflection_steps[0].payload["minimumRoundsOverrideApplied"] is True
    assert reflection_steps[1].payload["minimumRoundsOverrideApplied"] is True
    assert reflection_steps[2].payload["minimumRoundsOverrideApplied"] is False
    assert reflection_steps[0].payload["executionConfig"]["minRounds"] == 3
    assert stop_steps[-1].roundNo == 3
    assert stop_steps[-1].payload["source"] == "reflection"
    assert io.snapshot.status == "completed"
    assert io.published == ["agent_123"]


def test_execute_agent_run_persists_trace_facts_for_replay() -> None:
    io = _MemoryExecutionIO(
        _snapshot(max_rounds=3, schedule=[10, 5, 5]),
        [
            _search_page(0, page_no=1, page_size=10),
            _search_page(1, page_no=1, page_size=5),
            _search_page(2, page_no=1, page_size=5),
        ],
    )
    agents = _FakeAgentBundle(
        strategy_extractor=_QueuedAgent([_strategy_output()]),
        resume_matcher=_QueuedAgent(
            [
                ResumeMatcherOutputModel(score=0.92, summary="强匹配", evidence=["Python"], concerns=[]),
                ResumeMatcherOutputModel(score=0.88, summary="匹配良好", evidence=["Agent"], concerns=[]),
                ResumeMatcherOutputModel(score=0.85, summary="可进入 shortlist", evidence=["ReAct"], concerns=[]),
            ]
        ),
        search_reflector=_QueuedAgent(
            [
                _reflection_output(continue_search=False),
                _reflection_output(continue_search=False),
                _reflection_output(continue_search=False),
            ]
        ),
    )

    result = asyncio.run(
        _execute_agent_run(
            io=io,
            run_id="agent_123",
            agents=agents,
            runtime_settings=_runtime_settings(min_rounds=3, max_rounds=3),
        )
    )

    strategy_step = next(step for step in io.snapshot.steps if step.stepType == "strategy")
    first_search_step = next(step for step in io.snapshot.steps if step.stepType == "search")
    first_analysis_step = next(step for step in io.snapshot.steps if step.stepType == "analysis")
    first_reflection_step = next(step for step in io.snapshot.steps if step.stepType == "reflection")
    finalize_step = next(step for step in io.snapshot.steps if step.stepType == "finalize")
    first_analysis_item = first_analysis_step.payload["analyses"][0]
    persisted_analysis = io.persisted_analyses[0].analyses[0]

    assert result == "completed"
    assert strategy_step.payload["trace"]["observationType"] == "generation"
    assert strategy_step.payload["trace"]["prompt"]["name"] == "cvm.strategy-extractor"
    assert strategy_step.payload["trace"]["input"]["promptText"] == strategy_step.payload["promptText"]
    assert strategy_step.payload["trace"]["output"]["structuredOutput"]["summary"] == strategy_step.summary
    assert first_search_step.payload["upstreamRequest"] == {"page": 1, "pageSize": 10}
    assert first_search_step.payload["upstreamResponse"]["candidateIds"] == first_search_step.payload["candidateIds"]
    assert first_search_step.payload["trace"]["observationType"] == "tool"
    assert first_search_step.payload["trace"]["input"]["upstreamRequest"] == {"page": 1, "pageSize": 10}
    assert (
        first_search_step.payload["trace"]["output"]["upstreamResponse"]["candidateIds"]
        == first_search_step.payload["candidateIds"]
    )
    assert first_analysis_step.payload["trace"]["observationType"] == "span"
    assert first_analysis_item["trace"]["prompt"]["name"] == "cvm.resume-matcher"
    assert first_analysis_item["trace"]["usageDetails"]["prompt_tokens"] > 0
    assert persisted_analysis.trace is not None
    assert persisted_analysis.trace.prompt is not None
    assert persisted_analysis.trace.prompt.name == "cvm.resume-matcher"
    assert first_reflection_step.payload["trace"]["prompt"]["name"] == "cvm.search-reflector"
    assert first_reflection_step.payload["trace"]["output"]["structuredOutput"]["reason"] == first_reflection_step.summary
    assert finalize_step.payload["trace"]["observationType"] == "span"
    assert finalize_step.payload["trace"]["output"]["stopReason"] is not None


def test_execute_agent_run_keeps_successful_completion_when_trace_publication_fails() -> None:
    io = _MemoryExecutionIO(
        _snapshot(max_rounds=3, schedule=[10, 5, 5]),
        [
            _search_page(0, page_no=1, page_size=10),
            _search_page(1, page_no=1, page_size=5),
            _search_page(2, page_no=1, page_size=5),
        ],
        publish_error=RuntimeError("langfuse unavailable"),
    )
    agents = _FakeAgentBundle(
        strategy_extractor=_QueuedAgent([_strategy_output()]),
        resume_matcher=_QueuedAgent(
            [
                ResumeMatcherOutputModel(score=0.92, summary="强匹配", evidence=["Python"], concerns=[]),
                ResumeMatcherOutputModel(score=0.88, summary="匹配良好", evidence=["Agent"], concerns=[]),
                ResumeMatcherOutputModel(score=0.85, summary="可进入 shortlist", evidence=["ReAct"], concerns=[]),
            ]
        ),
        search_reflector=_QueuedAgent(
            [
                _reflection_output(continue_search=False),
                _reflection_output(continue_search=False),
                _reflection_output(continue_search=False),
            ]
        ),
    )

    result = asyncio.run(
        _execute_agent_run(
            io=io,
            run_id="agent_123",
            agents=agents,
            runtime_settings=_runtime_settings(min_rounds=3, max_rounds=3),
        )
    )

    observability_warning = next(step for step in io.snapshot.steps if step.stepType == "observability-warning")

    assert result == "completed"
    assert io.snapshot.status == "completed"
    assert io.snapshot.finalShortlist
    assert io.snapshot.errorCode is None
    assert io.published == ["agent_123"]
    assert observability_warning.status == "failed"
    assert observability_warning.payload["warningCode"] == "LANGFUSE_TRACE_PUBLICATION_FAILED"
    assert observability_warning.payload["terminalStatus"] == "completed"
    assert observability_warning.payload["trace"]["level"] == "ERROR"


def test_execute_agent_run_honors_extended_schedule_until_max_rounds() -> None:
    io = _MemoryExecutionIO(
        _snapshot(max_rounds=5, schedule=[10, 5, 5, 5, 5]),
        [
            _search_page(0, page_no=1, page_size=10),
            _search_page(1, page_no=1, page_size=5),
            _search_page(2, page_no=1, page_size=5),
            _search_page(3, page_no=1, page_size=5),
            _search_page(4, page_no=1, page_size=5),
        ],
    )
    agents = _FakeAgentBundle(
        strategy_extractor=_QueuedAgent([_strategy_output()]),
        resume_matcher=_QueuedAgent(
            [
                ResumeMatcherOutputModel(score=0.91, summary="round-1", evidence=["Python"], concerns=[]),
                ResumeMatcherOutputModel(score=0.89, summary="round-2", evidence=["Agent"], concerns=[]),
                ResumeMatcherOutputModel(score=0.87, summary="round-3", evidence=["ReAct"], concerns=[]),
                ResumeMatcherOutputModel(score=0.85, summary="round-4", evidence=["eval"], concerns=[]),
                ResumeMatcherOutputModel(score=0.83, summary="round-5", evidence=["workflow"], concerns=[]),
            ]
        ),
        search_reflector=_QueuedAgent([_reflection_output(continue_search=True)] * 4),
    )

    result = asyncio.run(
        _execute_agent_run(
            io=io,
            run_id="agent_123",
            agents=agents,
            runtime_settings=_runtime_settings(min_rounds=3, max_rounds=5),
        )
    )

    stop_steps = [step for step in io.snapshot.steps if step.stepType == "stop"]

    assert result == "completed"
    assert [request.pageSize for request in io.requests] == [10, 5, 5, 5, 5]
    assert io.snapshot.currentRound == 5
    assert stop_steps[-1].payload["source"] == "rule"
    assert stop_steps[-1].summary == "已达到配置的最大轮次，停止继续检索。"


def test_execute_agent_run_uses_per_agent_model_and_thinking_in_live_profile() -> None:
    io = _MemoryExecutionIO(
        _snapshot(max_rounds=3, schedule=[10, 5, 5]),
        [_search_page(0, page_no=1, page_size=10)],
    )
    agents = _FakeAgentBundle(
        strategy_extractor=_QueuedAgent([_strategy_output()]),
        resume_matcher=_QueuedAgent(
            [ResumeMatcherOutputModel(score=0.92, summary="强匹配", evidence=["Python"], concerns=[])]
        ),
        search_reflector=_QueuedAgent([_reflection_output(continue_search=False)]),
    )
    runtime_settings = Settings(
        _env_file=None,
        agent_profile="live",
        openai_api_key="test-key",
        agent_thinking="low",
        agent_model_search_reflector="gpt-5.4",
        agent_thinking_search_reflector="medium",
        agent_min_rounds=3,
        agent_max_rounds=3,
        agent_round_fetch_schedule="10,5,5",
    )

    result = asyncio.run(
        _execute_agent_run(
            io=io,
            run_id="agent_123",
            agents=agents,
            runtime_settings=runtime_settings,
        )
    )

    strategy_step = next(step for step in io.snapshot.steps if step.stepType == "strategy")
    analysis_step = next(step for step in io.snapshot.steps if step.stepType == "analysis")
    reflection_step = next(step for step in io.snapshot.steps if step.stepType == "reflection")

    assert result == "completed"
    assert agents.strategy_extractor.calls[0]["model"] == "openai-responses:gpt-5.4-mini"
    assert agents.strategy_extractor.calls[0]["model_settings"] == {"thinking": "low"}
    assert agents.resume_matcher.calls[0]["model"] == "openai-responses:gpt-5.4-mini"
    assert agents.resume_matcher.calls[0]["model_settings"] == {"thinking": "low"}
    assert agents.search_reflector.calls[0]["model"] == "openai-responses:gpt-5.4"
    assert agents.search_reflector.calls[0]["model_settings"] == {"thinking": "medium"}
    assert strategy_step.payload["thinkingEffort"] == "low"
    assert analysis_step.payload["analyses"][0]["thinkingEffort"] == "low"
    assert reflection_step.payload["thinkingEffort"] == "medium"
