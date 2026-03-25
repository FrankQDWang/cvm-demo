from __future__ import annotations

import json
from collections.abc import Mapping
from hashlib import sha1

from cvm_platform.application.runtime import PlatformRuntimeConfig
from cvm_platform.domain.types import JsonValue


PLACEHOLDER_MODEL_VERSIONS = {"", "default", "stub", "stub-1"}


def resolve_llm_model_version(requested_model: str, runtime_config: PlatformRuntimeConfig) -> str:
    model = requested_model.strip()
    if runtime_config.llm_mode.lower() == "stub":
        return model or "stub-1"
    return runtime_config.default_llm_model if model.lower() in PLACEHOLDER_MODEL_VERSIONS else model


def resume_hash(payload: Mapping[str, JsonValue]) -> str:
    return sha1(
        json.dumps(dict(payload), ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
