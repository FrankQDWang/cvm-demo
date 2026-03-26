from __future__ import annotations

from typing import cast

from sqlalchemy.orm import Session

from cvm_platform.application.ports import PlatformUnitOfWork
from cvm_platform.application.runtime import PlatformRuntimeConfig
from cvm_platform.application.service import PlatformService
from cvm_platform.infrastructure.agent_tracing import build_agent_run_tracer
from cvm_platform.infrastructure.adapters import build_llm, build_resume_source
from cvm_platform.infrastructure.sqlalchemy_uow import SqlAlchemyPlatformUnitOfWork
from cvm_platform.settings.config import Settings


def build_runtime_config(settings: Settings) -> PlatformRuntimeConfig:
    round_fetch_schedule = [
        int(token.strip())
        for token in settings.agent_round_fetch_schedule.split(",")
        if token.strip()
    ] or [10, 5, 5]
    return PlatformRuntimeConfig(
        temporal_namespace=settings.temporal_namespace,
        temporal_task_queue=settings.temporal_task_queue,
        allow_sensitive_export=settings.allow_sensitive_export,
        exports_dir=settings.exports_dir,
        app_version=settings.app_version,
        build_id=settings.build_id,
        temporal_ui_base_url=settings.temporal_ui_base_url,
        temporal_visibility_backend=settings.temporal_visibility_backend,
        default_llm_model=settings.llm_model,
        default_agent_prompt_version=settings.agent_prompt_version,
        llm_mode=settings.llm_mode,
        default_agent_max_rounds=settings.agent_max_rounds,
        default_agent_round_fetch_schedule=round_fetch_schedule,
        default_agent_final_top_k=settings.agent_final_top_k,
    )


def build_platform_service(session: Session, settings: Settings) -> PlatformService:
    runtime_config = build_runtime_config(settings)
    uow = cast(PlatformUnitOfWork, cast(object, SqlAlchemyPlatformUnitOfWork(session)))
    return PlatformService(
        uow=uow,
        runtime_config=runtime_config,
        llm=build_llm(settings),
        resume_source=build_resume_source(settings),
        agent_run_tracer=build_agent_run_tracer(settings),
    )
