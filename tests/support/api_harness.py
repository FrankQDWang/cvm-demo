from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from datetime import UTC
from os import environ
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import sessionmaker

from cvm_platform.api.dependencies import service_dependency
from cvm_platform.application.agent_tracing import (
    AgentRunTracer,
    AgentTraceObservation,
    TraceObservationType,
    TracePromptReference,
)
from cvm_platform.application.dto import AgentRunRecord
from cvm_platform.application.service import PlatformService
from cvm_platform.domain.types import AgentRuntimeConfigPayload, JsonValue
from cvm_platform.domain.ports import ResumeSourcePort
from cvm_platform.infrastructure.db import Base
from cvm_platform.infrastructure.service_factory import build_runtime_config
from cvm_platform.infrastructure.sqlalchemy_uow import SqlAlchemyPlatformUnitOfWork
from cvm_platform.main import create_app
from cvm_platform.settings.config import Settings
from cvm_worker.execution import run_agent_run_locally


class FakeTemporalClient:
    def __init__(
        self,
        runtime_settings: Settings,
        *,
        session_factory,
        resume_source: ResumeSourcePort | None,
        agent_run_tracer: AgentRunTracer | None,
    ) -> None:
        self._runtime_settings = runtime_settings
        self._session_factory = session_factory
        self._resume_source = resume_source
        self._agent_run_tracer = agent_run_tracer

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
            await run_agent_run_locally(
                run_id,
                runtime_settings=self._runtime_settings,
                session_factory=self._session_factory,
                resume_source_factory=(lambda runtime_settings: self._resume_source)
                if self._resume_source is not None
                else None,
                agent_run_tracer_factory=(lambda runtime_settings: self._agent_run_tracer)
                if self._agent_run_tracer is not None
                else (lambda runtime_settings: _FakeAgentRunTracer()),
            )
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
        prompt: TracePromptReference | None = None,
        usage_details: dict[str, int] | None = None,
        cost_details: dict[str, float] | None = None,
        level: str | None = None,
        status_message: str | None = None,
    ) -> Iterator[AgentTraceObservation]:
        del (
            name,
            as_type,
            input,
            metadata,
            model,
            version,
            prompt,
            usage_details,
            cost_details,
            level,
            status_message,
        )
        yield _FakeTraceObservation()

    def update(
        self,
        *,
        input: JsonValue | None = None,
        output: JsonValue | None = None,
        metadata: JsonValue | None = None,
        model: str | None = None,
        version: str | None = None,
        prompt: TracePromptReference | None = None,
        usage_details: dict[str, int] | None = None,
        cost_details: dict[str, float] | None = None,
        level: str | None = None,
        status_message: str | None = None,
    ) -> None:
        del input, output, metadata, model, version, prompt, usage_details, cost_details, level, status_message


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
        prompt: TracePromptReference | None = None,
        usage_details: dict[str, int] | None = None,
        cost_details: dict[str, float] | None = None,
        level: str | None = None,
        status_message: str | None = None,
    ) -> Iterator[AgentTraceObservation]:
        del (
            name,
            as_type,
            input,
            metadata,
            model,
            version,
            prompt,
            usage_details,
            cost_details,
            level,
            status_message,
        )
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
        agent_runtime_config: AgentRuntimeConfigPayload,
    ) -> Iterator[_FakeTraceHandle]:
        del jd_text, sourcing_preference_text, model_version, prompt_version, agent_runtime_config
        yield _FakeTraceHandle(run_id)


class _PostgresTestDatabase:
    def __init__(self, *, admin_url: URL, database_url: URL, database_name: str) -> None:
        self.database_name = database_name
        self.database_url = database_url.render_as_string(hide_password=False)
        self._admin_engine = create_engine(
            admin_url.render_as_string(hide_password=False),
            future=True,
            isolation_level="AUTOCOMMIT",
        )
        self._engine = create_engine(self.database_url, future=True)

    @classmethod
    def create(cls, base_database_url: str) -> _PostgresTestDatabase:
        base_url = make_url(base_database_url)
        if base_url.get_backend_name() != "postgresql":
            raise RuntimeError(
                "PostgreSQL test harness requires CVM_DATABASE_URL to use the postgresql+psycopg driver."
            )
        database_name = f"cvm_test_{uuid4().hex}"
        admin_url = base_url.set(database="postgres")
        admin_engine = create_engine(
            admin_url.render_as_string(hide_password=False),
            future=True,
            isolation_level="AUTOCOMMIT",
        )
        try:
            with admin_engine.connect() as connection:
                connection.execute(text(f'CREATE DATABASE "{database_name}"'))
        finally:
            admin_engine.dispose()
        return cls(
            admin_url=admin_url,
            database_url=base_url.set(database=database_name),
            database_name=database_name,
        )

    @property
    def engine(self):
        return self._engine

    def dispose(self) -> None:
        self._engine.dispose()
        with self._admin_engine.connect() as connection:
            connection.execute(
                text(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = :database_name
                      AND pid <> pg_backend_pid()
                    """
                ),
                {"database_name": self.database_name},
            )
            connection.execute(text(f'DROP DATABASE IF EXISTS "{self.database_name}"'))
        self._admin_engine.dispose()


def _resolve_test_database_url() -> str:
    database_url = environ.get("CVM_TEST_DATABASE_URL") or environ.get("CVM_DATABASE_URL")
    if database_url:
        return database_url
    return Settings().database_url


def build_test_service(
    tmp_path: Path,
    *,
    resume_source: ResumeSourcePort | None = None,
    agent_run_tracer: AgentRunTracer | None = None,
    allow_sensitive_export: bool = False,
) -> tuple[PlatformService, object, object, Settings]:
    test_database = _PostgresTestDatabase.create(_resolve_test_database_url())
    SessionLocal = sessionmaker(bind=test_database.engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=test_database.engine)

    session = SessionLocal()
    settings = Settings(
        _env_file=None,
        database_url=test_database.database_url,
        allow_sensitive_export=allow_sensitive_export,
        exports_dir=tmp_path / "exports",
        temporal_namespace="default",
        temporal_task_queue="cvm-agent-runs",
        temporal_ui_base_url="http://127.0.0.1:8080",
        temporal_visibility_backend="opensearch",
        app_version="0.1.0",
        build_id="test-build",
        agent_profile="deterministic",
        agent_min_rounds=3,
        agent_max_rounds=5,
        agent_round_fetch_schedule="10,5,5",
        agent_final_top_k=5,
        resume_source_mode="mock" if resume_source is None else "cts",
    )
    runtime_config = build_runtime_config(settings)
    del agent_run_tracer
    service = PlatformService(uow=SqlAlchemyPlatformUnitOfWork(session), runtime_config=runtime_config)
    service.__dict__["_cvm_test_sessionmaker"] = SessionLocal
    return service, session, test_database, settings


def build_test_client(
    tmp_path: Path,
    monkeypatch,
    *,
    resume_source: ResumeSourcePort | None = None,
    agent_run_tracer: AgentRunTracer | None = None,
    temporal_connect: TemporalConnectFn | None = None,
    temporal_inspect: TemporalInspectFn | None = None,
    allow_sensitive_export: bool = False,
) -> TestClient:
    service, session, engine, settings = build_test_service(
        tmp_path,
        resume_source=resume_source,
        agent_run_tracer=agent_run_tracer,
        allow_sensitive_export=allow_sensitive_export,
    )
    app = create_app(initialize_db_on_startup=False)
    app.dependency_overrides[service_dependency] = lambda: service

    async def default_connect(*args, **kwargs) -> FakeTemporalClient:
        del args, kwargs
        return FakeTemporalClient(
            settings,
            session_factory=service.__dict__["_cvm_test_sessionmaker"],
            resume_source=resume_source,
            agent_run_tracer=agent_run_tracer,
        )

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
