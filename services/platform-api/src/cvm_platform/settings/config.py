from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CVM_", extra="ignore")

    app_name: str = "cvm-platform-api"
    app_version: str = "0.1.0"
    database_url: str = "postgresql+psycopg://cvm:cvm@localhost:5432/cvm"
    use_temporal: bool = False
    temporal_host: str = "localhost:7233"
    temporal_task_queue: str = "cvm-search-runs"
    allow_sensitive_export: bool = False
    exports_dir: Path = Path("var/exports")


settings = Settings()
