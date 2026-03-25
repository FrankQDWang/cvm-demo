from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from cvm_platform.api.dependencies import service_dependency
from cvm_platform.application.dto import SearchRunRecord
from cvm_platform.application.service import PlatformService
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
        del workflow_name, id, task_queue
        self._service.execute_search_run(run_id)


TemporalConnectFn = Callable[..., Awaitable[object]]
TemporalInspectFn = Callable[[SearchRunRecord, Settings], Awaitable[dict[str, object]]]


def build_test_service(
    tmp_path: Path,
    *,
    llm: LLMPort | None = None,
    resume_source: ResumeSourcePort | None = None,
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
        temporal_task_queue="cvm-search-runs",
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
    )
    return service, session, engine, settings


def build_test_client(
    tmp_path: Path,
    monkeypatch,
    *,
    llm: LLMPort | None = None,
    resume_source: ResumeSourcePort | None = None,
    temporal_connect: TemporalConnectFn | None = None,
    temporal_inspect: TemporalInspectFn | None = None,
    allow_sensitive_export: bool = False,
) -> TestClient:
    service, session, engine, settings = build_test_service(
        tmp_path,
        llm=llm,
        resume_source=resume_source,
        allow_sensitive_export=allow_sensitive_export,
    )
    app = create_app(initialize_db_on_startup=False)
    app.dependency_overrides[service_dependency] = lambda: service

    async def default_connect(*args, **kwargs) -> FakeTemporalClient:
        del args, kwargs
        return FakeTemporalClient(service)

    async def default_inspect_search_run(run: SearchRunRecord, runtime_settings: Settings) -> dict[str, object]:
        workflow_id = run.workflow_id or f"search-run-{run.id}"
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
            "temporalExecutionFound": True,
            "temporalExecutionStatus": "WORKFLOW_EXECUTION_STATUS_COMPLETED"
            if run.status == "completed"
            else "WORKFLOW_EXECUTION_STATUS_FAILED",
            "visibilityIndexed": True,
            "visibilityBackend": runtime_settings.temporal_visibility_backend,
            "startedAt": started_at.isoformat() if started_at else None,
            "closedAt": finished_at.isoformat() if finished_at else None,
            "error": run.error_message,
            "temporalUiUrl": f"{runtime_settings.temporal_ui_base_url.rstrip('/')}/namespaces/{runtime_settings.temporal_namespace}",
        }

    monkeypatch.setattr("cvm_platform.api.routes.Client.connect", temporal_connect or default_connect)
    monkeypatch.setattr(
        "cvm_platform.api.routes.inspect_search_run",
        temporal_inspect or default_inspect_search_run,
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
