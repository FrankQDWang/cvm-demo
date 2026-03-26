from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from cvm_platform.application.agent_runs import normalize_agent_run_config
from cvm_platform.application.runtime import PlatformRuntimeConfig
from cvm_platform.domain.errors import ValidationError
from cvm_platform.infrastructure.mock_catalog import MOCK_CANDIDATES
from cvm_platform.settings.config import Settings
from cvm_worker.execution import _execute_agent_run
from cvm_worker.models import (
    AgentRunSnapshotModel,
    CtsSearchRequestModel,
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
        status="queued",
        jdText="需要 AI Agent 工程师，熟悉 Python、ReAct、workflow orchestration。",
        sourcingPreferenceText="优先上海，优先 agent 和 eval 背景。",
        config={"maxRounds": max_rounds, "roundFetchSchedule": schedule, "finalTopK": 5},
        currentRound=0,
        modelVersion="deterministic",
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

    async def run(self, prompt: str, *, model: str | None, output_type: object) -> SimpleNamespace:
        self.calls.append({"prompt": prompt, "model": model, "output_type": output_type})
        index = min(len(self.calls) - 1, len(self.outputs) - 1)
        return SimpleNamespace(output=self.outputs[index])


@dataclass
class _FakeAgentBundle:
    strategy_extractor: _QueuedAgent
    resume_matcher: _QueuedAgent
    search_reflector: _QueuedAgent


class _MemoryExecutionIO:
    def __init__(self, snapshot: AgentRunSnapshotModel, pages: list[WorkerSearchPageModel]) -> None:
        self.snapshot = snapshot
        self.pages = pages
        self.patches: list[RunPersistencePatchModel] = []
        self.requests: list[CtsSearchRequestModel] = []
        self.published: list[str] = []

    async def load_run_snapshot(self, run_id: str) -> AgentRunSnapshotModel:
        assert run_id == self.snapshot.id
        return self.snapshot.model_copy(deep=True)

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
        return self.snapshot.model_copy(deep=True)

    async def search_candidates(self, request: CtsSearchRequestModel) -> WorkerSearchPageModel:
        self.requests.append(request)
        index = min(len(self.requests) - 1, len(self.pages) - 1)
        page = self.pages[index]
        return page.model_copy(deep=True)

    async def publish_trace(self, run_id: str) -> TracePublicationModel:
        self.published.append(run_id)
        return TracePublicationModel(traceId=f"trace-{run_id}", traceUrl=f"http://langfuse/{run_id}")


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


def test_normalize_agent_run_config_rejects_invalid_min_max() -> None:
    with pytest.raises(ValidationError, match="maxRounds must be between 4 and 5"):
        normalize_agent_run_config(
            {"maxRounds": 3, "roundFetchSchedule": [10, 5, 5], "finalTopK": 5},
            _runtime_config(min_rounds=4, max_rounds=5),
        )


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
