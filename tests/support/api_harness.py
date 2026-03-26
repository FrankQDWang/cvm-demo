from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from datetime import UTC
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from cvm_platform.api.dependencies import service_dependency
from cvm_platform.application.agent_tracing import AgentRunTracer, AgentTraceObservation, TraceObservationType
from cvm_platform.application.dto import AgentRunRecord
from cvm_platform.application.service import PlatformService
from cvm_platform.domain.types import JsonValue
from cvm_platform.domain.ports import LLMPort, ResumeSourcePort
from cvm_platform.infrastructure.adapters import MockResumeSourceAdapter, StubLLMAdapter
from cvm_platform.infrastructure.db import Base
from cvm_platform.infrastructure.service_factory import build_runtime_config
from cvm_platform.infrastructure.sqlalchemy_uow import SqlAlchemyPlatformUnitOfWork
from cvm_platform.main import create_app
from cvm_platform.settings.config import Settings


class FakeTemporalClient:
    def __init__(self, service: PlatformService) -> None:
        self._service = service

    async def start_workflow(
        self,
        workflow_name: str,
        run_id: str,
        *,
        id: str | None = None,
        task_queue: str | None = None,
    ) -> None:
        del id, task_queue
        if workflow_name == "AgentRunWorkflow":
            self._service.execute_agent_run(run_id)
            return
        raise RuntimeError(f"Unsupported fake workflow: {workflow_name}")


TemporalConnectFn = Callable[..., Awaitable[object]]
TemporalInspectFn = Callable[[AgentRunRecord, Settings], Awaitable[dict[str, object]]]


class _FakeTraceObservation:
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
        del name, as_type, input, metadata, model, version, level, status_message
        yield _FakeTraceObservation()

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
        del input, output, metadata, model, version, level, status_message


class _FakeTraceHandle:
    def __init__(self, run_id: str) -> None:
        self.trace_id = f"trace-{run_id}"
        self.trace_url = f"http://127.0.0.1:4202/project/project-cvm-local/traces/{self.trace_id}"

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
        del name, as_type, input, metadata, model, version, level, status_message
        yield _FakeTraceObservation()

    def update_root(
        self,
        *,
        output: JsonValue | None = None,
        metadata: JsonValue | None = None,
        level: str | None = None,
        status_message: str | None = None,
    ) -> None:
        del output, metadata, level, status_message


class _FakeAgentRunTracer:
    @contextmanager
    def trace_run(
        self,
        *,
        run_id: str,
        jd_text: str,
        sourcing_preference_text: str,
        model_version: str,
        prompt_version: str,
    ) -> Iterator[_FakeTraceHandle]:
        del jd_text, sourcing_preference_text, model_version, prompt_version
        yield _FakeTraceHandle(run_id)


def build_test_service(
    tmp_path: Path,
    *,
    llm: LLMPort | None = None,
    resume_source: ResumeSourcePort | None = None,
    agent_run_tracer: AgentRunTracer | None = None,
    allow_sensitive_export: bool = False,
) -> tuple[PlatformService, object, object, Settings]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    settings = Settings(
        _env_file=None,
        allow_sensitive_export=allow_sensitive_export,
        exports_dir=tmp_path / "exports",
        temporal_namespace="default",
        temporal_task_queue="cvm-agent-runs",
        temporal_ui_base_url="http://127.0.0.1:8080",
        temporal_visibility_backend="opensearch",
        app_version="0.1.0",
        build_id="test-build",
    )
    runtime_config = build_runtime_config(settings)
    service = PlatformService(
        uow=SqlAlchemyPlatformUnitOfWork(session),
        runtime_config=runtime_config,
        llm=llm or StubLLMAdapter(),
        resume_source=resume_source or MockResumeSourceAdapter(),
        agent_run_tracer=agent_run_tracer or _FakeAgentRunTracer(),
    )
    return service, session, engine, settings


def build_test_client(
    tmp_path: Path,
    monkeypatch,
    *,
    llm: LLMPort | None = None,
    resume_source: ResumeSourcePort | None = None,
    agent_run_tracer: AgentRunTracer | None = None,
    temporal_connect: TemporalConnectFn | None = None,
    temporal_inspect: TemporalInspectFn | None = None,
    allow_sensitive_export: bool = False,
) -> TestClient:
    service, session, engine, settings = build_test_service(
        tmp_path,
        llm=llm,
        resume_source=resume_source,
        agent_run_tracer=agent_run_tracer,
        allow_sensitive_export=allow_sensitive_export,
    )
    app = create_app(initialize_db_on_startup=False)
    app.dependency_overrides[service_dependency] = lambda: service

    async def default_connect(*args, **kwargs) -> FakeTemporalClient:
        del args, kwargs
        return FakeTemporalClient(service)

    async def default_inspect_agent_run(run: AgentRunRecord, runtime_settings: Settings) -> dict[str, object]:
        workflow_id = run.workflow_id or f"agent-run-{run.id}"
        started_at = run.started_at
        finished_at = run.finished_at
        if started_at is not None and started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=UTC)
        if finished_at is not None and finished_at.tzinfo is None:
            finished_at = finished_at.replace(tzinfo=UTC)
        return {
            "runId": run.id,
            "workflowId": workflow_id,
            "namespace": run.temporal_namespace or runtime_settings.temporal_namespace,
            "taskQueue": run.temporal_task_queue or runtime_settings.temporal_task_queue,
            "appStatus": run.status,
            "currentRound": run.current_round,
            "stepCount": len(run.steps),
            "finalShortlistCount": len(run.final_shortlist),
            "temporalExecutionFound": True,
            "temporalExecutionStatus": "WORKFLOW_EXECUTION_STATUS_COMPLETED"
            if run.status == "completed"
            else "WORKFLOW_EXECUTION_STATUS_FAILED",
            "visibilityIndexed": True,
            "visibilityBackend": runtime_settings.temporal_visibility_backend,
            "startedAt": started_at.isoformat() if started_at else None,
            "closedAt": finished_at.isoformat() if finished_at else None,
            "error": run.error_message,
            "errorCode": run.error_code,
            "errorMessage": run.error_message,
            "stopReason": next(
                (step["summary"] for step in reversed(run.steps) if step["stepType"] == "stop"),
                None,
            ),
            "langfuseTraceUrl": run.langfuse_trace_url,
            "temporalUiUrl": f"{runtime_settings.temporal_ui_base_url.rstrip('/')}/namespaces/{runtime_settings.temporal_namespace}",
        }

    monkeypatch.setattr("cvm_platform.api.routes.Client.connect", temporal_connect or default_connect)
    monkeypatch.setattr(
        "cvm_platform.api.routes.inspect_agent_run",
        temporal_inspect or default_inspect_agent_run,
    )

    client = TestClient(app)
    client.__dict__["_cvm_test_session"] = session
    client.__dict__["_cvm_test_engine"] = engine
    client.__dict__["_cvm_test_settings"] = settings
    return client


def close_test_client(client: TestClient, monkeypatch: Any | None = None) -> None:
    client.close()
    client.__dict__["_cvm_test_session"].close()
    client.__dict__["_cvm_test_engine"].dispose()
    if monkeypatch is not None:
        monkeypatch.undo()
