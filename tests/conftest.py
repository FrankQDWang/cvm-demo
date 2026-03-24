from __future__ import annotations

import httpx
import pytest

from cvm_testkit import build_client, require_local_stack


@pytest.fixture(scope="session")
def client() -> httpx.Client:
    require_local_stack()
    with build_client() as api_client:
        yield api_client
