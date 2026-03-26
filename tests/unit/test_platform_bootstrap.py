from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from google.protobuf.timestamp_pb2 import Timestamp
from sqlalchemy.orm import Session
from temporalio.api.enums.v1 import WorkflowExecutionStatus

from cvm_platform.api import dependencies, openapi_contract
from cvm_platform import main as platform_main
from cvm_platform.infrastructure import db, service_factory, temporal_diagnostics
from cvm_platform.settings.config import Settings


def test_service_dependency_yields_platform_service(monkeypatch) -> None:
    fake_session = Session()
    fake_service = object()
    monkeypatch.setattr(dependencies, "get_session", lambda: iter([fake_session]))
    monkeypatch.setattr(dependencies, "build_platform_service", lambda session, settings: fake_service)

    try:
        assert list(dependencies.service_dependency()) == [fake_service]
    finally:
        fake_session.close()


def test_load_openapi_contract_and_bind_openapi() -> None:
    openapi_contract.load_openapi_contract.cache_clear()
    payload = openapi_contract.load_openapi_contract()
    assert payload["openapi"] == "3.1.0"

    app = FastAPI()
    openapi_contract.bind_openapi_contract(app)
    schema = app.openapi()
    assert schema["paths"]
    assert app.openapi() is schema


def test_initialize_database_requires_postgresql(monkeypatch) -> None:
    fake_engine = SimpleNamespace(dialect=SimpleNamespace(name="mysql"))
    monkeypatch.setattr(db, "engine", fake_engine)

    with pytest.raises(RuntimeError, match="Only PostgreSQL"):
        db.initialize_database()


def test_initialize_database_applies_schema_updates(monkeypatch) -> None:
    executed: list[str] = []

    class FakeConnection:
        def execute(self, statement) -> None:
            executed.append(str(statement))

    class FakeBegin:
        def __enter__(self):
            return FakeConnection()

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    class FakeMetadata:
        def create_all(self, *, bind) -> None:
            executed.append(f"create_all:{type(bind).__name__}")

    fake_engine = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"), begin=lambda: FakeBegin())
    fake_base = SimpleNamespace(metadata=FakeMetadata())
    monkeypatch.setattr(db, "engine", fake_engine)
    monkeypatch.setattr(db, "Base", fake_base)

    db.initialize_database()

    assert "create_all:FakeConnection" in executed
    assert any("pg_advisory_lock" in statement for statement in executed)
    assert any("pg_advisory_unlock" in statement for statement in executed)


def test_get_session_closes_session(monkeypatch) -> None:
    events: list[str] = []

    class FakeSession:
        def close(self) -> None:
            events.append("closed")

    monkeypatch.setattr(db, "SessionLocal", lambda: FakeSession())

    generator = db.get_session()
    session = next(generator)
    assert isinstance(session, FakeSession)
    with pytest.raises(StopIteration):
        next(generator)
    assert events == ["closed"]


def test_build_platform_service_wires_runtime_and_uow(monkeypatch) -> None:
    runtime_config = SimpleNamespace(name="runtime")
    monkeypatch.setattr(service_factory, "build_runtime_config", lambda settings: runtime_config)

    session = object()
    service = service_factory.build_platform_service(session=session, settings=Settings(_env_file=None))

    assert service.runtime_config is runtime_config
    assert service.uow.session is session


def test_settings_default_agent_runtime_is_live() -> None:
    settings = Settings(_env_file=None)

    assert settings.agent_profile == "live"
    assert settings.agent_min_rounds == 3
    assert settings.agent_max_rounds == 5
    assert settings.agent_round_fetch_schedule == "10,5,5"


def test_settings_reject_invalid_agent_round_window() -> None:
    with pytest.raises(ValueError, match="CVM_AGENT_MIN_ROUNDS"):
        Settings(_env_file=None, agent_profile="deterministic", agent_min_rounds=4, agent_max_rounds=3)


def test_create_app_requires_openai_api_key_for_live_startup(monkeypatch) -> None:
    monkeypatch.setattr(platform_main.settings, "agent_profile", "live")
    monkeypatch.setattr(platform_main.settings, "openai_api_key", "")

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is required when CVM_AGENT_PROFILE=live"):
        platform_main.create_app()


def test_temporal_timestamp_helpers() -> None:
    timestamp = Timestamp(seconds=1)
    assert temporal_diagnostics._format_timestamp(timestamp) is not None
    assert temporal_diagnostics._format_timestamp(Timestamp()) is None
    assert temporal_diagnostics._append_error(None, "first") == "first"
    assert temporal_diagnostics._append_error("first", "second") == "first; second"


def test_build_temporal_ui_url_encodes_query() -> None:
    settings = Settings(_env_file=None, temporal_ui_base_url="http://127.0.0.1:8080")
    url = temporal_diagnostics.build_temporal_ui_url(settings, "default", "agent-run-1")
    assert "WorkflowId%20%3D%20%27agent-run-1%27" in url


def test_inspect_agent_run_reports_execution_and_visibility(monkeypatch) -> None:
    start = Timestamp(seconds=10)
    close = Timestamp(seconds=20)
    info = SimpleNamespace(
        status=WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_COMPLETED,
        start_time=start,
        close_time=close,
    )
    description = SimpleNamespace(raw_description=SimpleNamespace(workflow_execution_info=info))

    class FakeHandle:
        async def describe(self):
            return description

    class FakeClient:
        def get_workflow_handle(self, workflow_id: str) -> FakeHandle:
            assert workflow_id == "agent-run-1"
            return FakeHandle()

        async def count_workflows(self, query: str):
            assert "agent-run-1" in query
            return SimpleNamespace(count=1)

    async def fake_connect(host: str, *, namespace: str) -> FakeClient:
        assert host == "127.0.0.1:7233"
        assert namespace == "default"
        return FakeClient()

    monkeypatch.setattr(temporal_diagnostics.Client, "connect", fake_connect)

    run = SimpleNamespace(
        id="run_1",
        workflow_id="agent-run-1",
        temporal_namespace="default",
        temporal_task_queue="cvm-agent-runs",
        status="completed",
        current_round=2,
        steps=[{"stepType": "stop", "summary": "Stopped because maxRounds was reached."}],
        final_shortlist=[{"externalIdentityId": "resume_1"}],
        error_code=None,
        error_message=None,
        langfuse_trace_url="http://127.0.0.1:4202/project/project-cvm-local/traces/abc",
        started_at=None,
        finished_at=None,
    )
    settings = Settings(_env_file=None, temporal_host="127.0.0.1:7233")

    diagnostic = asyncio.run(temporal_diagnostics.inspect_agent_run(run, settings))

    assert diagnostic["temporalExecutionFound"] is True
    assert diagnostic["visibilityIndexed"] is True
    assert diagnostic["temporalExecutionStatus"] == "WORKFLOW_EXECUTION_STATUS_COMPLETED"
    assert diagnostic["currentRound"] == 2
    assert diagnostic["finalShortlistCount"] == 1
    assert diagnostic["langfuseTraceUrl"] == "http://127.0.0.1:4202/project/project-cvm-local/traces/abc"


def test_inspect_agent_run_aggregates_failures(monkeypatch) -> None:
    class FakeHandle:
        async def describe(self):
            raise OSError("describe failed")

    class FakeClient:
        def get_workflow_handle(self, workflow_id: str) -> FakeHandle:
            return FakeHandle()

        async def count_workflows(self, query: str):
            raise OSError("visibility failed")

    async def fake_connect(host: str, *, namespace: str) -> FakeClient:
        return FakeClient()

    monkeypatch.setattr(temporal_diagnostics.Client, "connect", fake_connect)

    run = SimpleNamespace(
        id="run_2",
        workflow_id=None,
        temporal_namespace=None,
        temporal_task_queue=None,
        status="failed",
        current_round=1,
        steps=[],
        final_shortlist=[],
        error_code="OPENAI_TIMEOUT",
        error_message="reflection timed out",
        langfuse_trace_url=None,
        started_at=None,
        finished_at=None,
    )
    settings = Settings(_env_file=None, temporal_host="127.0.0.1:7233")

    diagnostic = asyncio.run(temporal_diagnostics.inspect_agent_run(run, settings))

    assert diagnostic["temporalExecutionFound"] is False
    assert diagnostic["visibilityIndexed"] is False
    assert "execution lookup failed" in diagnostic["error"]
    assert "visibility query failed" in diagnostic["error"]
    assert diagnostic["errorCode"] == "OPENAI_TIMEOUT"
