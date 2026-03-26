from __future__ import annotations

import os

import httpx
import pytest

from cvm_testkit import build_client, require_local_stack
from tests.support.api_harness import build_test_client, close_test_client


@pytest.fixture
def client(tmp_path, monkeypatch) -> httpx.Client:
    test_client = build_test_client(tmp_path, monkeypatch)
    try:
        yield test_client
    finally:
        close_test_client(test_client)


def pytest_configure(config: pytest.Config) -> None:
    os.environ["CVM_LANGFUSE_PUBLIC_KEY"] = ""
    os.environ["CVM_LANGFUSE_SECRET_KEY"] = ""
    os.environ["CVM_LANGFUSE_HOST"] = ""
    os.environ["CVM_LANGFUSE_BASE_URL"] = ""
    config.addinivalue_line("markers", "stack: requires the docker-compose-backed local stack")


@pytest.fixture(scope="session")
def stack_client() -> httpx.Client:
    require_local_stack()
    with build_client() as api_client:
        yield api_client
