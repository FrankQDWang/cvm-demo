from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import cast

import yaml
from fastapi import FastAPI


CONTRACT_PATH = Path(__file__).resolve().parents[5] / "contracts/openapi/platform-api.openapi.yaml"


@lru_cache(maxsize=1)
def load_openapi_contract() -> dict[str, object]:
    payload = cast(object, yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8")))
    if not isinstance(payload, dict):
        raise ValueError(f"OpenAPI contract at {CONTRACT_PATH} did not contain a mapping.")
    return cast(dict[str, object], payload)


def bind_openapi_contract(application: FastAPI) -> None:
    def _openapi() -> dict[str, object]:
        if application.openapi_schema is None:
            application.openapi_schema = deepcopy(load_openapi_contract())
        return application.openapi_schema

    application.openapi = _openapi
