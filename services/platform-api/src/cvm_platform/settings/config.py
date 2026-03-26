from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field
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
    llm_mode: str = "stub"
    llm_provider: str = "openai"
    llm_model: str = "gpt-5.4-mini"
    llm_api_key: str = Field(default="", validation_alias=AliasChoices("CVM_LLM_API_KEY", "OPENAI_API_KEY"))
    llm_base_url: str = Field(default="", validation_alias=AliasChoices("CVM_LLM_BASE_URL", "OPENAI_BASE_URL"))
    llm_timeout_seconds: int = 30
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
    agent_max_rounds: int = Field(default=3, ge=3, le=5)
    agent_round_fetch_schedule: str = "10,5,5"
    agent_final_top_k: int = 5
    agent_prompt_version: str = "agent-loop-v1"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
