from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from cvm_platform.api.routes import router
from cvm_platform.domain.errors import AppError
from cvm_platform.infrastructure.db import initialize_database
from cvm_platform.settings.config import settings


logger = logging.getLogger("uvicorn.error")


def create_app() -> FastAPI:
    initialize_database()
    application = FastAPI(title=settings.app_name, version=settings.app_version)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"code": exc.code, "message": exc.message})

    application.include_router(router)
    logger.info(
        "API runtime ready build_id=%s temporal_namespace=%s temporal_visibility_backend=%s temporal_task_queue=%s",
        settings.build_id,
        settings.temporal_namespace,
        settings.temporal_visibility_backend,
        settings.temporal_task_queue,
    )
    return application


def app() -> FastAPI:
    return create_app()
