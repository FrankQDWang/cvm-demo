from __future__ import annotations

import asyncio

import pytest

from cvm_worker import main as worker_main
from cvm_worker import workflows
from cvm_worker.activities import (
    cts_search_candidates,
    load_agent_run_snapshot,
    persist_agent_run_patch,
    publish_langfuse_trace,
)
from cvm_worker.workflows import AgentRunWorkflow


def test_agent_run_workflow_delegates_to_execution_entrypoint(monkeypatch) -> None:
    captured: dict[str, object] = {}
    fake_bundle = object()

    async def fake_execute_agent_run_workflow(*, run_id: str, agents, runtime_settings) -> str:
        captured["run_id"] = run_id
        captured["agents"] = agents
        captured["runtime_settings"] = runtime_settings
        return "completed"

    monkeypatch.setattr(workflows, "AGENT_BUNDLE", fake_bundle)
    monkeypatch.setattr(workflows, "execute_agent_run_workflow", fake_execute_agent_run_workflow)

    result = asyncio.run(AgentRunWorkflow().run("agent_456"))

    assert result == "completed"
    assert captured["run_id"] == "agent_456"
    assert captured["agents"] is fake_bundle
    assert captured["runtime_settings"] is workflows.settings


def test_run_worker_requires_openai_api_key_for_live_profile(monkeypatch) -> None:
    monkeypatch.setattr("cvm_worker.main.initialize_database", lambda: None)
    monkeypatch.setattr(worker_main.settings, "agent_profile", "live")
    monkeypatch.setattr(worker_main.settings, "openai_api_key", "")

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is required when CVM_AGENT_PROFILE=live"):
        asyncio.run(worker_main.run_worker())


def test_run_worker_builds_temporal_worker_with_plugin(monkeypatch) -> None:
    calls: dict[str, object] = {}
    plugin = object()

    class FakeWorker:
        def __init__(
            self,
            client,
            *,
            task_queue,
            workflows,
            activities,
            activity_executor,
            plugins,
        ) -> None:
            calls["client"] = client
            calls["task_queue"] = task_queue
            calls["workflows"] = workflows
            calls["activities"] = activities
            calls["activity_executor"] = activity_executor
            calls["worker_plugins"] = plugins

        async def run(self) -> None:
            calls["ran"] = True

    class FakeClient:
        pass

    async def fake_connect(host: str, *, namespace: str, plugins) -> FakeClient:
        calls["temporal_host"] = host
        calls["namespace"] = namespace
        calls["client_plugins"] = plugins
        return FakeClient()

    monkeypatch.setattr("cvm_worker.main.initialize_database", lambda: calls.setdefault("initialized", True))
    monkeypatch.setattr("cvm_worker.main.PydanticAIPlugin", lambda: plugin)
    monkeypatch.setattr("cvm_worker.main.Client.connect", fake_connect)
    monkeypatch.setattr("cvm_worker.main.Worker", FakeWorker)
    monkeypatch.setattr(worker_main.settings, "agent_profile", "deterministic")
    monkeypatch.setattr(worker_main.settings, "openai_api_key", "")
    monkeypatch.setattr(worker_main.settings, "temporal_host", "127.0.0.1:7233")
    monkeypatch.setattr(worker_main.settings, "temporal_namespace", "default")
    monkeypatch.setattr(worker_main.settings, "temporal_task_queue", "cvm-agent-runs")

    asyncio.run(worker_main.run_worker())

    assert calls["initialized"] is True
    assert calls["ran"] is True
    assert calls["task_queue"] == "cvm-agent-runs"
    assert calls["temporal_host"] == "127.0.0.1:7233"
    assert calls["namespace"] == "default"
    assert calls["client_plugins"] == [plugin]
    assert calls["worker_plugins"] == [plugin]
    assert calls["workflows"] == [AgentRunWorkflow]
    assert calls["activities"] == [
        load_agent_run_snapshot,
        persist_agent_run_patch,
        cts_search_candidates,
        publish_langfuse_trace,
    ]


def test_worker_main_uses_asyncio_runner(monkeypatch) -> None:
    calls: dict[str, object] = {}

    def fake_basic_config(*, level) -> None:
        calls["level"] = level

    def fake_run(coro) -> None:
        calls["called"] = True
        coro.close()

    monkeypatch.setattr("cvm_worker.main.logging.basicConfig", fake_basic_config)
    monkeypatch.setattr("cvm_worker.main.asyncio.run", fake_run)

    worker_main.main()

    assert calls["called"] is True
