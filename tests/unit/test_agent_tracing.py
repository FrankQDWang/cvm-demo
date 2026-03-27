from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass, field
from typing import cast

from cvm_platform.application.agent_tracing import TracePromptReference
from cvm_platform.application.agent_runs import effective_agent_runtime_config
from cvm_platform.application.dto import AgentRunRecord
from cvm_platform.domain.types import to_json_object
from cvm_platform.infrastructure.agent_tracing import LangfuseAgentRunTracer, build_agent_run_tracer
from cvm_platform.settings.config import Settings
from cvm_worker.activities import _replay_trace
from cvm_worker.models import AgentRunStepModel, ObservationTraceFactModel, TracePromptReferenceModel


@dataclass
class _FakePrompt:
    name: str
    version: int
    prompt: str
    labels: list[str] = field(default_factory=list)


@dataclass
class _FakeObservation:
    name: str
    as_type: str
    input: object | None
    metadata: object | None
    model: str | None
    version: str | None
    prompt: _FakePrompt | None = None
    usage_details: dict[str, int] | None = None
    cost_details: dict[str, float] | None = None
    level: str | None = None
    status_message: str | None = None
    updates: list[dict[str, object]] = field(default_factory=list)
    children: list["_FakeObservation"] = field(default_factory=list)

    def __enter__(self) -> "_FakeObservation":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def start_as_current_observation(self, **kwargs: object) -> "_FakeObservation":
        observation = _FakeObservation(
            name=str(kwargs["name"]),
            as_type=str(kwargs["as_type"]),
            input=kwargs.get("input"),
            metadata=kwargs.get("metadata"),
            model=kwargs.get("model"),
            version=kwargs.get("version"),
            prompt=kwargs.get("prompt") if isinstance(kwargs.get("prompt"), _FakePrompt) else None,
            usage_details=cast(dict[str, int] | None, kwargs.get("usage_details")),
            cost_details=cast(dict[str, float] | None, kwargs.get("cost_details")),
            level=kwargs.get("level") if isinstance(kwargs.get("level"), str) else None,
            status_message=kwargs.get("status_message")
            if isinstance(kwargs.get("status_message"), str)
            else None,
        )
        self.children.append(observation)
        return observation

    def update(self, **kwargs: object) -> None:
        self.updates.append(kwargs)


class _FakeLangfuseClient:
    def __init__(self, **kwargs: object) -> None:
        self.init_kwargs = kwargs
        self.observations: list[_FakeObservation] = []
        self.flush_calls = 0
        self.prompts: dict[str, list[_FakePrompt]] = {}

    def create_trace_id(self, *, seed: str) -> str:
        return f"trace-{seed}"

    def get_trace_url(self, *, trace_id: str) -> str:
        return f"http://langfuse-internal:3000/project/project_123/traces/{trace_id}"

    def start_as_current_observation(self, **kwargs: object) -> _FakeObservation:
        observation = _FakeObservation(
            name=str(kwargs["name"]),
            as_type=str(kwargs["as_type"]),
            input=kwargs.get("input"),
            metadata=kwargs.get("metadata"),
            model=kwargs.get("model"),
            version=kwargs.get("version"),
            prompt=kwargs.get("prompt") if isinstance(kwargs.get("prompt"), _FakePrompt) else None,
            usage_details=cast(dict[str, int] | None, kwargs.get("usage_details")),
            cost_details=cast(dict[str, float] | None, kwargs.get("cost_details")),
            level=kwargs.get("level") if isinstance(kwargs.get("level"), str) else None,
            status_message=kwargs.get("status_message")
            if isinstance(kwargs.get("status_message"), str)
            else None,
        )
        self.observations.append(observation)
        return observation

    def get_prompt(
        self,
        name: str,
        *,
        version: int | None = None,
        label: str | None = None,
        type: str = "text",
    ) -> _FakePrompt:
        del type
        for prompt in self.prompts.get(name, []):
            if version is not None and prompt.version != version:
                continue
            if label is not None and label not in prompt.labels:
                continue
            return prompt
        raise RuntimeError(f"Prompt {name!r} not found.")

    def create_prompt(
        self,
        *,
        name: str,
        prompt: str | list[dict[str, object]],
        labels: list[str],
        type: str = "text",
    ) -> _FakePrompt:
        del type
        if not isinstance(prompt, str):
            raise TypeError("Test prompt fixture only supports text prompts.")
        version = len(self.prompts.get(name, [])) + 1
        created = _FakePrompt(name=name, version=version, prompt=prompt, labels=list(labels))
        self.prompts.setdefault(name, []).append(created)
        return created

    def update_prompt(self, *, name: str, version: int, new_labels: list[str]) -> _FakePrompt:
        prompts = self.prompts.get(name, [])
        for prompt in prompts:
            prompt.labels = [label for label in prompt.labels if label not in new_labels]
        for prompt in prompts:
            if prompt.version == version:
                prompt.labels = list(new_labels)
                return prompt
        raise RuntimeError(f"Prompt {name!r} version {version} not found.")

    def flush(self) -> None:
        self.flush_calls += 1


def test_build_agent_run_tracer_returns_noop_without_keys(monkeypatch) -> None:
    monkeypatch.setattr("cvm_platform.infrastructure.agent_tracing.Langfuse", _FakeLangfuseClient)
    tracer = build_agent_run_tracer(Settings(_env_file=None, langfuse_public_key="", langfuse_secret_key=""))

    with tracer.trace_run(
        run_id="agent_1",
        jd_text="jd",
        sourcing_preference_text="pref",
        model_version="deterministic",
        prompt_version="agent-loop-v1",
        agent_runtime_config=effective_agent_runtime_config(
            None,
            fallback_model_version="deterministic",
        ),
    ) as handle:
        assert handle.trace_id is None
        assert handle.trace_url is None


def test_langfuse_agent_run_tracer_records_root_and_nested_observations(monkeypatch) -> None:
    monkeypatch.setattr("cvm_platform.infrastructure.agent_tracing.Langfuse", _FakeLangfuseClient)
    tracer = build_agent_run_tracer(
        Settings(
            _env_file=None,
            langfuse_public_key="pk",
            langfuse_secret_key="sk",
            langfuse_host="http://langfuse-internal:3000",
            langfuse_base_url="http://127.0.0.1:4202",
            langfuse_environment="test",
        )
    )

    assert isinstance(tracer, LangfuseAgentRunTracer)

    with tracer.trace_run(
        run_id="agent_2",
        jd_text="Need Python",
        sourcing_preference_text="Prefer agent experience",
        model_version="gpt-5.4-mini",
        prompt_version="agent-loop-v1",
        agent_runtime_config=effective_agent_runtime_config(
            {
                "strategyExtractor": {"modelVersion": "gpt-5.4-mini", "thinkingEffort": "low"},
                "resumeMatcher": {"modelVersion": "gpt-5.4-mini", "thinkingEffort": "low"},
                "searchReflector": {"modelVersion": "gpt-5.4", "thinkingEffort": "medium"},
            },
            fallback_model_version="gpt-5.4-mini",
        ),
    ) as handle:
        assert handle.trace_id == "trace-agent_2"
        assert handle.trace_url == "http://127.0.0.1:4202/project/project_123/traces/trace-agent_2"
        with handle.start_observation(
            name="round-1",
            as_type="chain",
            input={"roundNo": 1},
            metadata={"phase": "round"},
        ) as round_trace:
            with round_trace.start_observation(
                name="cts-search-round-1",
                as_type="tool",
                input={"pageNo": 1},
                metadata={"tool": "cts.search_candidates"},
            ) as search_trace:
                search_trace.update(output={"candidateIds": ["cts_001"]})
            with round_trace.start_observation(
                name="reflect-round-1",
                as_type="generation",
                input="中文反思 prompt",
                model="gpt-5.4-mini",
                version="agent-loop-v1",
                prompt=TracePromptReference(
                    name="cvm.search-reflector",
                    label="agent-loop-v1",
                    prompt_text="中文反思 prompt",
                ),
                usage_details={"prompt_tokens": 18, "completion_tokens": 7, "total_tokens": 25},
            ) as reflect_trace:
                reflect_trace.update(
                    output={"continueSearch": True},
                    usage_details={"prompt_tokens": 18, "completion_tokens": 7, "total_tokens": 25},
                )
        handle.update_root(output={"status": "completed"}, metadata={"seenResumeCount": 5})

    fake_client = tracer._client  # pyright: ignore[reportPrivateUsage]
    assert len(fake_client.observations) == 1
    root_observation = fake_client.observations[0]
    assert root_observation.name == "agent-run"
    assert root_observation.metadata["agentRuntimeConfig"]["searchReflector"]["modelVersion"] == "gpt-5.4"
    assert root_observation.updates[-1]["output"] == {"status": "completed"}
    assert len(root_observation.children) == 1
    round_observation = root_observation.children[0]
    assert round_observation.name == "round-1"
    assert round_observation.as_type == "chain"
    assert [child.name for child in round_observation.children] == ["cts-search-round-1", "reflect-round-1"]
    assert round_observation.children[0].as_type == "tool"
    assert round_observation.children[0].updates[-1]["output"] == {"candidateIds": ["cts_001"]}
    assert round_observation.children[1].as_type == "generation"
    assert round_observation.children[1].input == "中文反思 prompt"
    assert round_observation.children[1].updates[-1]["output"] == {"continueSearch": True}
    assert round_observation.children[1].prompt is not None
    assert round_observation.children[1].prompt.name == "cvm.search-reflector"
    assert round_observation.children[1].prompt.labels == ["agent-loop-v1"]
    assert round_observation.children[1].usage_details == {
        "prompt_tokens": 18,
        "completion_tokens": 7,
        "total_tokens": 25,
    }
    assert round_observation.children[1].updates[-1]["usage_details"] == {
        "prompt_tokens": 18,
        "completion_tokens": 7,
        "total_tokens": 25,
    }
    assert fake_client.init_kwargs["host"] == "http://langfuse-internal:3000"
    assert "base_url" not in fake_client.init_kwargs
    assert fake_client.flush_calls == 1


def test_replay_trace_rehydrates_prompt_links_and_usage_details(monkeypatch) -> None:
    monkeypatch.setattr("cvm_platform.infrastructure.agent_tracing.Langfuse", _FakeLangfuseClient)
    tracer = build_agent_run_tracer(
        Settings(
            _env_file=None,
            langfuse_public_key="pk",
            langfuse_secret_key="sk",
            langfuse_host="http://langfuse-internal:3000",
            langfuse_base_url="http://127.0.0.1:4202",
            langfuse_environment="test",
            agent_min_rounds=3,
            agent_max_rounds=5,
            agent_round_fetch_schedule="10,5,5",
            agent_final_top_k=5,
        )
    )

    strategy_trace = ObservationTraceFactModel(
        observationType="generation",
        input=to_json_object({"promptText": "策略 prompt", "messageHistory": [{"kind": "request"}]}),
        output=to_json_object({"structuredOutput": {"summary": "策略完成"}, "response": {"kind": "response"}}),
        metadata=to_json_object({"stepType": "strategy"}),
        prompt=TracePromptReferenceModel(
            name="cvm.strategy-extractor",
            label="agent-loop-v1",
            text="策略 prompt",
        ),
        model="openai-responses:gpt-5.4-mini",
        version="agent-loop-v1",
        usageDetails={"prompt_tokens": 31, "completion_tokens": 9, "total_tokens": 40},
    )
    search_trace = ObservationTraceFactModel(
        observationType="tool",
        input=to_json_object(
            {
                "searchRequest": {"pageNo": 1, "pageSize": 10},
                "upstreamRequest": {"page": 1, "pageSize": 10},
            }
        ),
        output=to_json_object(
            {
                "returnedCount": 1,
                "candidateIds": ["resume_001"],
                "upstreamResponse": {"candidateIds": ["resume_001"]},
            }
        ),
        metadata=to_json_object({"tool": "cts.search_candidates"}),
    )
    analysis_trace = ObservationTraceFactModel(
        observationType="span",
        input=to_json_object({"summary": "analysis", "analyzedCount": 1}),
        output=to_json_object({"analyzedCount": 1, "candidateIds": ["resume_001"]}),
        metadata=to_json_object({"stepType": "analysis"}),
    )
    resume_trace = ObservationTraceFactModel(
        observationType="generation",
        input=to_json_object({"promptText": "分析 prompt", "messageHistory": [{"kind": "request"}]}),
        output=to_json_object({"structuredOutput": {"summary": "强匹配"}, "response": {"kind": "response"}}),
        metadata=to_json_object({"candidateId": "cand_resume_001"}),
        prompt=TracePromptReferenceModel(
            name="cvm.resume-matcher",
            label="agent-loop-v1",
            text="分析 prompt",
        ),
        model="openai-responses:gpt-5.4-mini",
        version="agent-loop-v1",
        usageDetails={"prompt_tokens": 19, "completion_tokens": 7, "total_tokens": 26},
    )
    finalize_trace = ObservationTraceFactModel(
        observationType="span",
        input=to_json_object({"currentRound": 1}),
        output=to_json_object({"stopReason": "enough", "finalShortlist": []}),
        metadata=to_json_object({"stepType": "finalize"}),
    )
    steps = [
        AgentRunStepModel(
            stepNo=1,
            roundNo=None,
            stepType="strategy",
            title="Strategy",
            status="completed",
            summary="策略完成",
            payload={"promptText": "策略 prompt", "trace": strategy_trace.model_dump(mode="json")},
            occurredAt="2026-03-27T09:00:00+00:00",
        ),
        AgentRunStepModel(
            stepNo=2,
            roundNo=1,
            stepType="search",
            title="Search",
            status="completed",
            summary="search",
            payload={"trace": search_trace.model_dump(mode="json")},
            occurredAt="2026-03-27T09:01:00+00:00",
        ),
        AgentRunStepModel(
            stepNo=3,
            roundNo=1,
            stepType="analysis",
            title="Analysis",
            status="completed",
            summary="analysis",
            payload={
                "analyses": [
                    {
                        "candidateId": "cand_resume_001",
                        "externalIdentityId": "resume_001",
                        "name": "Ada",
                        "trace": resume_trace.model_dump(mode="json"),
                    }
                ],
                "trace": analysis_trace.model_dump(mode="json"),
            },
            occurredAt="2026-03-27T09:02:00+00:00",
        ),
        AgentRunStepModel(
            stepNo=4,
            roundNo=1,
            stepType="finalize",
            title="Finalize",
            status="completed",
            summary="finalize",
            payload={"trace": finalize_trace.model_dump(mode="json")},
            occurredAt="2026-03-27T09:03:00+00:00",
        ),
    ]
    run = AgentRunRecord(
        id="agent_3",
        case_id="case_3",
        status="completed",
        jd_text="Need Python",
        sourcing_preference_text="Prefer agent experience",
        idempotency_key="idem_3",
        config={"maxRounds": 5, "roundFetchSchedule": [10, 5, 5, 5, 5], "finalTopK": 5},
        current_round=1,
        model_version="gpt-5.4-mini",
        prompt_version="agent-loop-v1",
        agent_runtime_config={
            "strategyExtractor": {"modelVersion": "gpt-5.4-mini", "thinkingEffort": "low"},
            "resumeMatcher": {"modelVersion": "gpt-5.4-mini", "thinkingEffort": "low"},
            "searchReflector": {"modelVersion": "gpt-5.4", "thinkingEffort": "medium"},
        },
        workflow_id="agent-run-agent_3",
        temporal_namespace="default",
        temporal_task_queue="cvm-agent-runs",
        langfuse_trace_id=None,
        langfuse_trace_url=None,
        steps=[step.to_payload() for step in steps],
        final_shortlist=[],
        seen_resume_ids=["resume_001"],
        error_code=None,
        error_message=None,
        created_at=datetime(2026, 3, 27, 9, 0, 0),
        started_at=datetime(2026, 3, 27, 9, 0, 0),
        finished_at=datetime(2026, 3, 27, 9, 5, 0),
    )

    with tracer.trace_run(
        run_id=run.id,
        jd_text=run.jd_text,
        sourcing_preference_text=run.sourcing_preference_text,
        model_version=run.model_version,
        prompt_version=run.prompt_version,
        agent_runtime_config=effective_agent_runtime_config(
            run.agent_runtime_config,
            fallback_model_version=run.model_version,
        ),
    ) as handle:
        _replay_trace(run, handle, Settings(_env_file=None, agent_round_fetch_schedule="10,5,5"))

    fake_client = tracer._client  # pyright: ignore[reportPrivateUsage]
    root_observation = fake_client.observations[0]
    round_observation = next(child for child in root_observation.children if child.name == "round-1")
    strategy_observation = next(child for child in root_observation.children if child.name == "extract-search-strategy")
    search_observation = next(child for child in round_observation.children if child.name == "cts-search")
    analysis_observation = next(child for child in round_observation.children if child.name == "analysis")
    resume_observation = analysis_observation.children[0]

    assert strategy_observation.input == {"promptText": "策略 prompt", "messageHistory": [{"kind": "request"}]}
    assert strategy_observation.updates[-1]["output"] == {
        "structuredOutput": {"summary": "策略完成"},
        "response": {"kind": "response"},
    }
    assert strategy_observation.prompt is not None
    assert strategy_observation.prompt.name == "cvm.strategy-extractor"
    assert strategy_observation.usage_details == {
        "prompt_tokens": 31,
        "completion_tokens": 9,
        "total_tokens": 40,
    }
    assert search_observation.input == {
        "searchRequest": {"pageNo": 1, "pageSize": 10},
        "upstreamRequest": {"page": 1, "pageSize": 10},
    }
    assert search_observation.updates[-1]["output"]["upstreamResponse"] == {"candidateIds": ["resume_001"]}
    assert resume_observation.prompt is not None
    assert resume_observation.prompt.name == "cvm.resume-matcher"
    assert resume_observation.input == {
        "promptText": "分析 prompt",
        "messageHistory": [{"kind": "request"}],
    }
    assert resume_observation.updates[-1]["output"]["structuredOutput"]["summary"] == "强匹配"
    assert resume_observation.usage_details == {
        "prompt_tokens": 19,
        "completion_tokens": 7,
        "total_tokens": 26,
    }
