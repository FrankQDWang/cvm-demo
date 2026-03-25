from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import schemathesis
from _pytest.monkeypatch import MonkeyPatch
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from schemathesis.core.result import Ok

from tests.support.api_harness import build_test_client, close_test_client


CONTRACT_PATH = Path(__file__).resolve().parents[1] / "contracts/openapi/platform-api.openapi.yaml"
SCHEMA = schemathesis.openapi.from_path(CONTRACT_PATH)
OPERATIONS = [result.ok() for result in SCHEMA.get_all_operations() if isinstance(result, Ok)]


@pytest.mark.parametrize("operation", OPERATIONS, ids=[operation.label for operation in OPERATIONS])
@given(data=st.data())
@settings(
    max_examples=5,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_internal_openapi_contract(operation, data: st.DataObject) -> None:
    case: schemathesis.Case = data.draw(
        operation.as_strategy(generation_mode=schemathesis.GenerationMode.POSITIVE),
        label=operation.label,
    )
    with TemporaryDirectory() as tmpdir:
        monkeypatch = MonkeyPatch()
        client = build_test_client(Path(tmpdir), monkeypatch)
        try:
            request_kwargs = case.as_transport_kwargs(base_url="http://testserver")
            response = client.request(**request_kwargs)
            case.validate_response(response)
            assert response.status_code < 600
        finally:
            close_test_client(client, monkeypatch=monkeypatch)
