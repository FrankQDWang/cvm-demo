from __future__ import annotations

from typing import cast

from sqlalchemy.orm import Session

from cvm_platform.application.ports import PlatformUnitOfWork
from cvm_platform.application.runtime import PlatformRuntimeConfig
from cvm_platform.application.service import PlatformService
from cvm_platform.infrastructure.sqlalchemy_uow import SqlAlchemyPlatformUnitOfWork
from cvm_platform.settings.config import Settings


def _parse_round_fetch_schedule(raw_schedule: str) -> list[int]:
    schedule = [int(token.strip()) for token in raw_schedule.split(",") if token.strip()]
    if not schedule or any(fetch_size <= 0 for fetch_size in schedule):
        raise ValueError("CVM_AGENT_ROUND_FETCH_SCHEDULE must contain positive integers.")
    return schedule


def build_runtime_config(settings: Settings) -> PlatformRuntimeConfig:
    round_fetch_schedule = _parse_round_fetch_schedule(settings.agent_round_fetch_schedule)
    return PlatformRuntimeConfig(
        temporal_namespace=settings.temporal_namespace,
        temporal_task_queue=settings.temporal_task_queue,
        allow_sensitive_export=settings.allow_sensitive_export,
        exports_dir=settings.exports_dir,
        app_version=settings.app_version,
        build_id=settings.build_id,
        temporal_ui_base_url=settings.temporal_ui_base_url,
        temporal_visibility_backend=settings.temporal_visibility_backend,
        default_agent_model=settings.agent_model,
        default_agent_prompt_version=settings.agent_prompt_version,
        agent_profile=settings.agent_profile,
        default_agent_min_rounds=settings.agent_min_rounds,
        default_agent_max_rounds=settings.agent_max_rounds,
        default_agent_round_fetch_schedule=round_fetch_schedule,
        default_agent_final_top_k=settings.agent_final_top_k,
    )


def build_platform_service(session: Session, settings: Settings) -> PlatformService:
    runtime_config = build_runtime_config(settings)
    uow = cast(PlatformUnitOfWork, cast(object, SqlAlchemyPlatformUnitOfWork(session)))
    return PlatformService(uow=uow, runtime_config=runtime_config)
