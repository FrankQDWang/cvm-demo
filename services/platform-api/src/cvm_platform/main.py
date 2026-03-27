from __future__ import annotations

import logging
from typing import cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from cvm_platform.api.openapi_contract import bind_openapi_contract
from cvm_platform.api.routes import router
from cvm_platform.domain.errors import DomainError
from cvm_platform.infrastructure.db import initialize_database
from cvm_platform.settings.config import settings


logger = logging.getLogger("uvicorn.error")


def _ensure_allowed_agent_runtime() -> None:
    settings.assert_runtime_mode_allowed()


async def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "retryable": exc.retryable,
        },
    )


def _format_validation_error(error: object) -> str:
    if not isinstance(error, dict):
        return "Request body did not match the contract."
    error_map = cast(dict[str, object], error)
    loc_value = error_map.get("loc", ())
    if isinstance(loc_value, list):
        location = ".".join(str(part) for part in cast(list[object], loc_value))
    elif isinstance(loc_value, tuple):
        location = ".".join(str(part) for part in cast(tuple[object, ...], loc_value))
    elif loc_value:
        location = str(loc_value)
    else:
        location = ""
    message_value = error_map.get("msg", "Request body did not match the contract.")
    message = str(message_value)
    return f"{location}: {message}" if location else str(message)


async def handle_request_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = cast(list[object], exc.errors())
    details = "; ".join(_format_validation_error(error) for error in errors)
    return JSONResponse(
        status_code=400,
        content={
            "code": "INVALID_REQUEST",
            "message": details or "Request body did not match the contract.",
            "retryable": False,
        },
    )


def create_app(*, initialize_db_on_startup: bool = True) -> FastAPI:
    if initialize_db_on_startup:
        _ensure_allowed_agent_runtime()
        initialize_database()
    application = FastAPI(title=settings.app_name, version=settings.app_version)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.exception_handler(DomainError)(handle_domain_error)
    application.exception_handler(RequestValidationError)(handle_request_validation_error)
    bind_openapi_contract(application)
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
