from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from cvm_platform.application.dto import AgentRunRecord
from cvm_platform.application.agent_tracing import AgentTraceObservation, TraceObservationType
from cvm_platform.domain.errors import ExternalDependencyError, TransientDependencyError
from cvm_platform.domain.types import (
    AgentSearchStrategyData,
    CandidateData,
    JsonValue,
    NormalizedQueryPayload,
    ResumeMatchData,
    SearchPageData,
    SearchReflectionData,
    to_json_object,
)
from cvm_platform.infrastructure.mock_catalog import MOCK_CANDIDATES
from tests.support.api_harness import build_test_service


def _candidate(index: int) -> CandidateData:
    payload = MOCK_CANDIDATES[index]
    return CandidateData(
        external_identity_id=payload["external_identity_id"],
        name=payload["name"],
        title=payload["title"],
        company=payload["company"],
        location=payload["location"],
        summary=payload["summary"],
        email=payload["email"],
        phone=payload["phone"],
        resume_projection=payload["resumeProjection"],
    )


def _search_page(
    candidates: list[CandidateData],
    *,
    page_no: int,
    page_size: int,
    error_code: str | None = None,
    error_message: str | None = None,
) -> SearchPageData:
    return SearchPageData(
        status="failed" if error_code else "completed",
        total=len(candidates),
        page_no=page_no,
        page_size=page_size,
        candidates=candidates,
        upstream_request=to_json_object({"page": page_no, "pageSize": page_size}),
        upstream_response=to_json_object(
            {
                "status": "fail" if error_code else "ok",
                "errorCode": error_code,
                "errorMessage": error_message,
                "candidateIds": [candidate.external_identity_id for candidate in candidates],
            }
        ),
        error_code=error_code,
        error_message=error_message,
    )


@dataclass
class _RecordedObservation:
    name: str
    as_type: str
    input: object | None
    metadata: object | None
    model: str | None
    version: str | None
    level: str | None = None
    status_message: str | None = None
    updates: list[dict[str, object]] = field(default_factory=list)
    children: list["_RecordedObservation"] = field(default_factory=list)

    @contextmanager
    def start_observation(
        self,
        *,
        name: str,
        as_type: TraceObservationType,
        input: JsonValue | None = None,
        metadata: JsonValue | None = None,
        model: str | None = None,
        version: str | None = None,
        level: str | None = None,
        status_message: str | None = None,
    ) -> Iterator[AgentTraceObservation]:
        observation = _RecordedObservation(
            name=name,
            as_type=as_type,
            input=input,
            metadata=metadata,
            model=model,
            version=version,
            level=level,
            status_message=status_message,
        )
        self.children.append(observation)
        yield observation

    def update(
        self,
        *,
        input: JsonValue | None = None,
        output: JsonValue | None = None,
        metadata: JsonValue | None = None,
        model: str | None = None,
        version: str | None = None,
        level: str | None = None,
        status_message: str | None = None,
    ) -> None:
        self.updates.append(
            {
                "input": input,
                "output": output,
                "metadata": metadata,
                "model": model,
                "version": version,
                "level": level,
                "status_message": status_message,
            }
        )


class _RecordingTraceHandle:
    def __init__(self, run_id: str) -> None:
        self.trace_id = f"trace-{run_id}"
        self.trace_url = f"http://127.0.0.1:4202/project/project-cvm-local/traces/{self.trace_id}"
        self.root = _RecordedObservation(
            name="agent-run",
            as_type="agent",
            input=None,
            metadata=None,
            model=None,
            version=None,
        )

    @contextmanager
    def start_observation(
        self,
        *,
        name: str,
        as_type: TraceObservationType,
        input: JsonValue | None = None,
        metadata: JsonValue | None = None,
        model: str | None = None,
        version: str | None = None,
        level: str | None = None,
        status_message: str | None = None,
    ) -> Iterator[AgentTraceObservation]:
        with self.root.start_observation(
            name=name,
            as_type=as_type,
            input=input,
            metadata=metadata,
            model=model,
            version=version,
            level=level,
            status_message=status_message,
        ) as observation:
            yield observation

    def update_root(
        self,
        *,
        output: JsonValue | None = None,
        metadata: JsonValue | None = None,
        level: str | None = None,
        status_message: str | None = None,
    ) -> None:
        self.root.update(
            output=output,
            metadata=metadata,
            level=level,
            status_message=status_message,
        )


class _RecordingTracer:
    def __init__(self) -> None:
        self.handles: list[_RecordingTraceHandle] = []

    @contextmanager
    def trace_run(
        self,
        *,
        run_id: str,
        jd_text: str,
        sourcing_preference_text: str,
        model_version: str,
        prompt_version: str,
    ) -> Iterator[_RecordingTraceHandle]:
        del jd_text, sourcing_preference_text, model_version, prompt_version
        handle = _RecordingTraceHandle(run_id)
        self.handles.append(handle)
        yield handle


@dataclass
class _SequenceResumeSource:
    pages: list[SearchPageData]

    def __post_init__(self) -> None:
        self.calls: list[tuple[NormalizedQueryPayload, int, int]] = []

    def search_candidates(
        self,
        normalized_query: NormalizedQueryPayload,
        page_no: int,
        page_size: int,
    ) -> SearchPageData:
        self.calls.append((normalized_query, page_no, page_size))
        index = min(len(self.calls) - 1, len(self.pages) - 1)
        page = self.pages[index]
        return SearchPageData(
            status=page.status,
            total=page.total,
            page_no=page_no,
            page_size=page_size,
            candidates=page.candidates,
            upstream_request=page.upstream_request,
            upstream_response=page.upstream_response,
            error_code=page.error_code,
            error_message=page.error_message,
        )


class _FallbackExerciseLLM:
    def draft_keywords(self, jd_text: str, model_version: str, prompt_version: str):
        raise AssertionError("draft_keywords should not be called by the fallback path")

    def extract_agent_search_strategy(
        self,
        jd_text: str,
        sourcing_preference_text: str,
        model_version: str,
        prompt_version: str,
    ) -> AgentSearchStrategyData:
        del jd_text, sourcing_preference_text, model_version, prompt_version
        raise ExternalDependencyError("OPENAI_HTTP_ERROR", "strategy extraction degraded")

    def analyze_resume_match(
        self,
        jd_text: str,
        sourcing_preference_text: str,
        strategy: NormalizedQueryPayload,
        candidate: CandidateData,
        model_version: str,
        prompt_version: str,
    ) -> ResumeMatchData:
        del jd_text, sourcing_preference_text, strategy, candidate, model_version, prompt_version
        raise TransientDependencyError("OPENAI_TIMEOUT", "analysis timed out")

    def reflect_search_progress(
        self,
        jd_text: str,
        sourcing_preference_text: str,
        strategy: NormalizedQueryPayload,
        round_ledger: list[dict[str, object]],
        round_no: int,
        max_rounds: int,
        new_candidate_count: int,
        seen_candidate_count: int,
        model_version: str,
        prompt_version: str,
    ) -> SearchReflectionData:
        del (
            jd_text,
            sourcing_preference_text,
            round_ledger,
            round_no,
            max_rounds,
            new_candidate_count,
            seen_candidate_count,
            model_version,
            prompt_version,
        )
        return SearchReflectionData(
            prompt_text="中文相同策略反思",
            model_version="stub-1",
            prompt_version="agent-loop-v1",
            continue_search=True,
            reason="继续使用相同策略。",
            next_round_goal="继续补充候选。",
            next_round_query={
                "keyword": strategy["keyword"],
                "mustTerms": list(strategy["mustTerms"]),
                "shouldTerms": list(strategy["shouldTerms"]),
                "excludeTerms": list(strategy["excludeTerms"]),
                "structuredFilters": dict(strategy["structuredFilters"]),
            },
        )


class _ReflectionFailingLLM:
    def draft_keywords(self, jd_text: str, model_version: str, prompt_version: str):
        raise AssertionError("draft_keywords should not be called")

    def extract_agent_search_strategy(
        self,
        jd_text: str,
        sourcing_preference_text: str,
        model_version: str,
        prompt_version: str,
    ) -> AgentSearchStrategyData:
        del jd_text, sourcing_preference_text
        return AgentSearchStrategyData(
            prompt_text="中文首轮提取",
            model_version=model_version,
            prompt_version=prompt_version,
            must_requirements=["Python"],
            core_requirements=["Agent"],
            bonus_requirements=[],
            exclude_signals=[],
            round_1_query={
                "keyword": "Python Agent",
                "mustTerms": ["Python"],
                "shouldTerms": ["Agent"],
                "excludeTerms": [],
                "structuredFilters": {"page": 1, "pageSize": 10},
            },
            summary="使用默认的 Python Agent 首轮查询。",
        )

    def analyze_resume_match(
        self,
        jd_text: str,
        sourcing_preference_text: str,
        strategy: NormalizedQueryPayload,
        candidate: CandidateData,
        model_version: str,
        prompt_version: str,
    ) -> ResumeMatchData:
        del jd_text, sourcing_preference_text, strategy
        return ResumeMatchData(
            prompt_text="analyze",
            model_version=model_version,
            prompt_version=prompt_version,
            score=0.82,
            summary=f"Keep {candidate.name} in the shortlist.",
            evidence=[candidate.title],
            concerns=[],
        )

    def reflect_search_progress(
        self,
        jd_text: str,
        sourcing_preference_text: str,
        strategy: NormalizedQueryPayload,
        round_ledger: list[dict[str, object]],
        round_no: int,
        max_rounds: int,
        new_candidate_count: int,
        seen_candidate_count: int,
        model_version: str,
        prompt_version: str,
    ) -> SearchReflectionData:
        del (
            jd_text,
            sourcing_preference_text,
            strategy,
            round_ledger,
            round_no,
            max_rounds,
            new_candidate_count,
            seen_candidate_count,
            model_version,
            prompt_version,
        )
        raise TransientDependencyError("OPENAI_TIMEOUT", "reflection timed out")


class _StaticLLM(_ReflectionFailingLLM):
    def reflect_search_progress(
        self,
        jd_text: str,
        sourcing_preference_text: str,
        strategy: NormalizedQueryPayload,
        round_ledger: list[dict[str, object]],
        round_no: int,
        max_rounds: int,
        new_candidate_count: int,
        seen_candidate_count: int,
        model_version: str,
        prompt_version: str,
    ) -> SearchReflectionData:
        del (
            jd_text,
            sourcing_preference_text,
            round_ledger,
            new_candidate_count,
            seen_candidate_count,
            model_version,
            prompt_version,
        )
        return SearchReflectionData(
            prompt_text="中文反思",
            model_version="stub-1",
            prompt_version="agent-loop-v1",
            continue_search=round_no < max_rounds,
            reason="继续用当前紧凑查询搜下一轮。",
            next_round_goal="继续寻找更强候选。",
            next_round_query={
                "keyword": strategy["keyword"],
                "mustTerms": list(strategy["mustTerms"]),
                "shouldTerms": list(strategy["shouldTerms"]),
                "excludeTerms": list(strategy["excludeTerms"]),
                "structuredFilters": dict(strategy["structuredFilters"]),
            },
        )


def _create_run(service, *, idempotency_key: str = "agent-run-1", config: dict[str, object] | None = None) -> AgentRunRecord:
    return service.create_agent_run(
        jd_text="Need AI agent engineer with Python and workflows",
        sourcing_preference_text="Prefer search, eval, and recruiting-tool experience",
        model_version="stub-1",
        prompt_version="agent-loop-v1",
        idempotency_key=idempotency_key,
        config=config,
    )


def test_agent_run_create_normalizes_config_and_backfills_existing_workflow_id(tmp_path: Path) -> None:
    service, session, engine, _ = build_test_service(tmp_path)
    try:
        run = _create_run(
            service,
            idempotency_key="agent-config",
            config={"maxRounds": 3, "roundFetchSchedule": [2], "finalTopK": 2},
        )
        assert run.config["roundFetchSchedule"] == [2, 2, 2]

        run.workflow_id = None
        service.uow.agent_runs.save_run(run)
        service.uow.commit()

        replay = _create_run(service, idempotency_key="agent-config")
        assert replay.id == run.id
        assert replay.workflow_id == f"agent-run-{run.id}"
    finally:
        session.close()
        engine.dispose()


def test_agent_run_execute_uses_fallback_strategy_and_duplicate_strategy_stop(tmp_path: Path) -> None:
    resume_source = _SequenceResumeSource(
        [
            _search_page([_candidate(0)], page_no=1, page_size=1),
            _search_page([], page_no=2, page_size=1),
        ]
    )
    service, session, engine, _ = build_test_service(tmp_path, llm=_FallbackExerciseLLM(), resume_source=resume_source)
    try:
        run = _create_run(
            service,
            idempotency_key="agent-fallback",
            config={"maxRounds": 3, "roundFetchSchedule": [1, 1, 1], "finalTopK": 1},
        )
        completed = service.execute_agent_run(run.id)

        assert completed.status == "completed"
        assert completed.final_shortlist[0]["externalIdentityId"] == "cts_001"
        strategy_step = next(step for step in completed.steps if step["stepType"] == "strategy")
        assert strategy_step["payload"]["mustRequirements"]
        assert "round1Query" in strategy_step["payload"]
        assert any("首轮策略提取降级" in step["summary"] for step in completed.steps)
        assert any(step["stepType"] == "stop" for step in completed.steps)
        assert completed.final_shortlist[0]["reason"].startswith("AI 降级启发式匹配")
    finally:
        session.close()
        engine.dispose()


def test_agent_run_execute_uses_reflection_fallback_and_keeps_shortlist(tmp_path: Path) -> None:
    resume_source = _SequenceResumeSource(
        [
            _search_page([_candidate(4), _candidate(5)], page_no=1, page_size=2),
            _search_page([], page_no=2, page_size=2),
        ]
    )
    service, session, engine, _ = build_test_service(tmp_path, llm=_ReflectionFailingLLM(), resume_source=resume_source)
    try:
        run = _create_run(
            service,
            idempotency_key="agent-reflection",
            config={"maxRounds": 3, "roundFetchSchedule": [2, 2, 2], "finalTopK": 2},
        )
        completed = service.execute_agent_run(run.id)

        assert completed.status == "completed"
        assert len(completed.final_shortlist) == 2
        assert completed.current_round == 3
        assert any("反思步骤降级" in step["summary"] for step in completed.steps)
        reflection_step = next(
            step for step in completed.steps if step["stepType"] == "reflection" and step["roundNo"] == 2
        )
        assert reflection_step["payload"]["minimumRoundsOverrideApplied"] is True
        assert "queryDelta" in reflection_step["payload"]
    finally:
        session.close()
        engine.dispose()


def test_agent_run_failure_paths_cover_search_error_and_dispatch_failure(tmp_path: Path) -> None:
    resume_source = _SequenceResumeSource(
        [
            _search_page([], page_no=1, page_size=2, error_code="CTS_HTTP_ERROR", error_message="boom"),
        ]
    )
    service, session, engine, _ = build_test_service(tmp_path, llm=_StaticLLM(), resume_source=resume_source)
    try:
        run = _create_run(
            service,
            idempotency_key="agent-search-error",
            config={"maxRounds": 3, "roundFetchSchedule": [2, 2, 2], "finalTopK": 1},
        )
        failed = service.execute_agent_run(run.id)
        dispatch_failed = service.fail_agent_run_dispatch(run.id, "TEMPORAL_START_FAILED", "dispatch failed")

        assert failed.status == "failed"
        assert failed.error_code == "CTS_HTTP_ERROR"
        assert dispatch_failed.error_code == "TEMPORAL_START_FAILED"
    finally:
        session.close()
        engine.dispose()


def test_agent_run_trace_tree_groups_rounds_and_uses_compact_ledger(tmp_path: Path) -> None:
    tracer = _RecordingTracer()
    resume_source = _SequenceResumeSource(
        [
            _search_page([_candidate(0), _candidate(1)], page_no=1, page_size=2),
            _search_page([_candidate(0)], page_no=2, page_size=1),
            _search_page([], page_no=3, page_size=1),
        ]
    )
    service, session, engine, _ = build_test_service(
        tmp_path,
        llm=_StaticLLM(),
        resume_source=resume_source,
        agent_run_tracer=tracer,
    )
    try:
        run = _create_run(
            service,
            idempotency_key="agent-trace-tree",
            config={"maxRounds": 3, "roundFetchSchedule": [2, 1, 1], "finalTopK": 2},
        )
        completed = service.execute_agent_run(run.id)

        assert completed.status == "completed"
        root = tracer.handles[0].root
        root_child_names = [child.name for child in root.children]
        assert "extract-search-strategy" in root_child_names
        assert "round-1" in root_child_names
        assert "finalize" in root_child_names

        round_1 = next(child for child in root.children if child.name == "round-1")
        assert round_1.as_type == "chain"
        round_1_child_names = [child.name for child in round_1.children]
        assert round_1_child_names == [
            "cts-search-round-1",
            "dedupe-round-1",
            "analysis-round-1",
            "shortlist-round-1",
            "reflect-round-1",
        ]
        assert round_1.children[0].as_type == "tool"
        assert round_1.children[1].as_type == "span"
        assert round_1.children[2].as_type == "chain"
        assert round_1.children[3].as_type == "span"
        assert round_1.children[4].as_type == "generation"

        analysis_round_1 = round_1.children[2]
        assert len(analysis_round_1.children) == 2
        assert all(child.as_type == "generation" for child in analysis_round_1.children)
        assert isinstance(analysis_round_1.children[0].input, str)

        reflect_round_1 = round_1.children[4]
        assert isinstance(reflect_round_1.input, str)
        reflect_metadata = reflect_round_1.metadata
        assert isinstance(reflect_metadata, dict)
        compact_ledger = reflect_metadata["compactRoundLedger"]
        assert isinstance(compact_ledger, list)
        assert "resumeProjection" not in str(compact_ledger)

        round_3 = next(child for child in root.children if child.name == "round-3")
        assert any(child.name == "stop-round-3" for child in round_3.children)
    finally:
        session.close()
        engine.dispose()
