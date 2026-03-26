from __future__ import annotations

from dataclasses import dataclass, field

from cvm_platform.infrastructure.agent_tracing import LangfuseAgentRunTracer, build_agent_run_tracer
from cvm_platform.settings.config import Settings


@dataclass
class _FakeObservation:
    name: str
    as_type: str
    input: object | None
    metadata: object | None
    model: str | None
    version: str | None
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
            level=kwargs.get("level") if isinstance(kwargs.get("level"), str) else None,
            status_message=kwargs.get("status_message")
            if isinstance(kwargs.get("status_message"), str)
            else None,
        )
        self.observations.append(observation)
        return observation

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
            ) as reflect_trace:
                reflect_trace.update(output={"continueSearch": True})
        handle.update_root(output={"status": "completed"}, metadata={"seenResumeCount": 5})

    fake_client = tracer._client  # pyright: ignore[reportPrivateUsage]
    assert len(fake_client.observations) == 1
    root_observation = fake_client.observations[0]
    assert root_observation.name == "agent-run"
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
    assert fake_client.init_kwargs["host"] == "http://langfuse-internal:3000"
    assert "base_url" not in fake_client.init_kwargs
    assert fake_client.flush_calls == 1
