from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from cvm_platform.api.routes import router
from cvm_platform.domain.errors import AppError
from cvm_platform.infrastructure.db import Base, engine
from cvm_platform.settings.config import settings


def create_app() -> FastAPI:
    Base.metadata.create_all(bind=engine)
    application = FastAPI(title=settings.app_name, version=settings.app_version)

    @application.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"code": exc.code, "message": exc.message})

    application.include_router(router)
    return application


def app() -> FastAPI:
    return create_app()
