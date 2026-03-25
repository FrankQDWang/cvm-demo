from __future__ import annotations

import httpx
import pytest

from cvm_testkit import build_client, require_local_stack


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "stack: requires the docker-compose-backed local stack")


@pytest.fixture(scope="session")
def client() -> httpx.Client:
    require_local_stack()
    with build_client() as api_client:
        yield api_client
