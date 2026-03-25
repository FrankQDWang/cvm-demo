from __future__ import annotations

import asyncio
import json

import pytest
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

from cvm_platform.domain.errors import TransientDependencyError
from cvm_platform import main as main_module


def _request() -> Request:
    return Request({"type": "http", "headers": [], "method": "GET", "path": "/"})


def test_format_validation_error_handles_multiple_location_shapes() -> None:
    assert main_module._format_validation_error({"loc": ["query", "pageNo"], "msg": "invalid"}) == "query.pageNo: invalid"
    assert main_module._format_validation_error({"loc": ("body", "ownerTeamId"), "msg": "required"}) == "body.ownerTeamId: required"
    assert main_module._format_validation_error({"loc": "body", "msg": "invalid"}) == "body: invalid"
    assert main_module._format_validation_error("bad payload") == "Request body did not match the contract."


def test_error_handlers_return_contract_envelopes() -> None:
    domain_response = asyncio.run(
        main_module.handle_domain_error(
            _request(),
            TransientDependencyError("TEMPORAL_START_FAILED", "Temporal workflow dispatch failed."),
        )
    )
    assert domain_response.status_code == 503
    assert json.loads(domain_response.body) == {
        "code": "TEMPORAL_START_FAILED",
        "message": "Temporal workflow dispatch failed.",
        "retryable": True,
    }

    validation_response = asyncio.run(
        main_module.handle_request_validation_error(
            _request(),
            RequestValidationError(
                [
                    {"loc": ("body", "ownerTeamId"), "msg": "String should have at least 1 character"},
                    {"loc": ["query", "pageNo"], "msg": "Input should be a valid integer"},
                ]
            ),
        )
    )
    assert validation_response.status_code == 400
    body = json.loads(validation_response.body)
    assert body["code"] == "INVALID_REQUEST"
    assert "body.ownerTeamId" in body["message"]
    assert "query.pageNo" in body["message"]
    assert body["retryable"] is False


def test_create_app_registers_handlers_and_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []

    monkeypatch.setattr(main_module, "initialize_database", lambda: events.append("db"))
    monkeypatch.setattr(main_module, "bind_openapi_contract", lambda app: events.append(f"bind:{app.title}"))
    monkeypatch.setattr(main_module.logger, "info", lambda *args, **kwargs: events.append("log"))

    application = main_module.create_app(initialize_db_on_startup=True)

    assert isinstance(application, FastAPI)
    assert "db" in events
    assert any(event.startswith("bind:") for event in events)
    assert "log" in events
    assert RequestValidationError in application.exception_handlers
    assert main_module.DomainError in application.exception_handlers


def test_app_wrapper_delegates_to_create_app(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel = FastAPI()
    monkeypatch.setattr(main_module, "create_app", lambda: sentinel)
    assert main_module.app() is sentinel
