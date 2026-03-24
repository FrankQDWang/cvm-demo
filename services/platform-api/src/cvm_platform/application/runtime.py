from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PlatformRuntimeConfig:
    temporal_namespace: str
    temporal_task_queue: str
    allow_sensitive_export: bool
    exports_dir: Path
    app_version: str
    build_id: str
    temporal_ui_base_url: str
    temporal_visibility_backend: str
    default_llm_model: str
    llm_mode: str
