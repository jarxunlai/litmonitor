from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./data/litmonitor.db"
    ncbi_api_key: str = ""

    app_host: str = "127.0.0.1"
    app_port: int = 8000
    default_timezone: str = "America/Chicago"
    scheduler_enabled: bool = False

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False

    llm_enabled: bool = False
    llm_backend: str = "openai-compatible"
    llm_api_base: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 0
    llm_thinking_type: str = ""
    llm_reasoning_effort: str = ""
    llm_stream: bool = False
    llm_timeout_seconds: int = 60
    llm_force_json_mode: bool = True
    llm_retry_attempts: int = 3
    llm_retry_backoff_seconds: float = 10.0
    llm_fallback_backend: str = ""

    llm_cli_command: str = "codex"
    llm_cli_args: str = "exec --json"
    llm_cli_timeout_seconds: int = 120

    llm_max_papers_per_run: int = 20
    llm_min_relevance_score: float = 5
    llm_cache_enabled: bool = True
    digest_max_papers_per_run: int = 20

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
