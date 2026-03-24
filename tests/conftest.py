from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


TEST_DB = Path(__file__).resolve().parent / "test.sqlite3"
os.environ.setdefault("CVM_DATABASE_URL", f"sqlite+pysqlite:///{TEST_DB}")
os.environ.setdefault("CVM_USE_TEMPORAL", "false")

from cvm_platform.infrastructure.db import Base, engine  # noqa: E402
from cvm_platform.main import create_app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(create_app()) as test_client:
        yield test_client
