from __future__ import annotations

import asyncio

from cvm_worker import main as worker_main
from cvm_worker.workflows import AgentRunWorkflow, execute_agent_run


def test_execute_agent_run_delegates_to_platform_service(monkeypatch) -> None:
    calls: dict[str, object] = {}

    class FakeSession:
        def close(self) -> None:
            calls["closed"] = True

    class FakeService:
        def execute_agent_run(self, run_id: str):
            calls["run_id"] = run_id
            return type("RunResult", (), {"status": "completed"})()

    monkeypatch.setattr("cvm_worker.workflows.SessionLocal", lambda: FakeSession())
    monkeypatch.setattr("cvm_worker.workflows.build_platform_service", lambda session, settings: FakeService())

    result = execute_agent_run("agent_123")

    assert result == "completed"
    assert calls == {"run_id": "agent_123", "closed": True}


def test_agent_run_workflow_invokes_activity(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_execute_activity(activity_fn, run_id: str, *, start_to_close_timeout) -> str:
        captured["activity_fn"] = activity_fn
        captured["run_id"] = run_id
        captured["timeout_seconds"] = int(start_to_close_timeout.total_seconds())
        return "completed"

    monkeypatch.setattr("cvm_worker.workflows.workflow.execute_activity", fake_execute_activity)

    result = asyncio.run(AgentRunWorkflow().run("agent_456"))

    assert result == "completed"
    assert captured["run_id"] == "agent_456"
    assert captured["timeout_seconds"] == 180


def test_run_worker_builds_and_runs_temporal_worker(monkeypatch) -> None:
    calls: dict[str, object] = {}

    class FakeWorker:
        def __init__(self, client, *, task_queue, workflows, activities, activity_executor) -> None:
            calls["task_queue"] = task_queue
            calls["workflows"] = workflows
            calls["activities"] = activities
            calls["activity_executor"] = activity_executor

        async def run(self) -> None:
            calls["ran"] = True

    class FakeClient:
        pass

    async def fake_connect(host: str, *, namespace: str) -> FakeClient:
        calls["temporal_host"] = host
        calls["namespace"] = namespace
        return FakeClient()

    monkeypatch.setattr("cvm_worker.main.initialize_database", lambda: calls.setdefault("initialized", True))
    monkeypatch.setattr("cvm_worker.main.Client.connect", fake_connect)
    monkeypatch.setattr("cvm_worker.main.Worker", FakeWorker)
    monkeypatch.setattr(worker_main.settings, "temporal_task_queue", "cvm-agent-runs")

    asyncio.run(worker_main.run_worker())

    assert calls["initialized"] is True
    assert calls["ran"] is True
    assert calls["task_queue"] == "cvm-agent-runs"
    assert calls["workflows"] == [AgentRunWorkflow]
    assert calls["activities"] == [execute_agent_run]


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
