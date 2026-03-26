from __future__ import annotations

from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CVM_", extra="ignore", env_file=".env", env_file_encoding="utf-8")

    app_name: str = "cvm-platform-api"
    app_version: str = "0.1.0"
    build_id: str = "local-dev"
    database_url: str = "postgresql+psycopg://cvm:cvm@localhost:5432/cvm"
    temporal_host: str = "localhost:7233"
    temporal_task_queue: str = "cvm-agent-runs"
    temporal_namespace: str = "default"
    temporal_visibility_backend: str = "opensearch"
    temporal_ui_base_url: str = "http://127.0.0.1:8080"
    agent_profile: str = "live"
    agent_model: str = "gpt-5.4-mini"
    agent_model_timeout_seconds: int = 30
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="", validation_alias="OPENAI_BASE_URL")
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    langfuse_base_url: str = ""
    langfuse_environment: str = "local"
    resume_source_mode: str = "mock"
    cts_base_url: str = "https://link.hewa.cn"
    cts_tenant_key: str = ""
    cts_tenant_secret: str = ""
    cts_timeout_seconds: int = 20
    allow_sensitive_export: bool = False
    exports_dir: Path = Path("var/exports")
    cors_origins: str = "http://localhost:4200"
    agent_min_rounds: int = Field(default=3, ge=3, le=5)
    agent_max_rounds: int = Field(default=5, ge=3, le=5)
    agent_round_fetch_schedule: str = "10,5,5"
    agent_final_top_k: int = 5
    agent_prompt_version: str = "agent-loop-v1"

    @model_validator(mode="after")
    def validate_agent_runtime(self) -> "Settings":
        normalized_profile = self.agent_profile.strip().lower()
        if normalized_profile not in {"live", "deterministic"}:
            raise ValueError("CVM_AGENT_PROFILE must be either 'live' or 'deterministic'.")
        if self.agent_min_rounds > self.agent_max_rounds:
            raise ValueError("CVM_AGENT_MIN_ROUNDS must be less than or equal to CVM_AGENT_MAX_ROUNDS.")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
