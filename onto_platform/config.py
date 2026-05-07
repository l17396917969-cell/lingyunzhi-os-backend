from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ONTO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(...)
    secret_key: str = Field(..., min_length=44)

    bind_host: str = "0.0.0.0"
    bind_port: int = 8080
    log_level: str = "info"

    query_default_max_rows: int = 1000
    query_max_rows_cap: int = 10_000
    query_default_timeout_ms: int = 30_000
    query_timeout_ms_cap: int = 120_000

    ui_session_ttl_seconds: int = 43_200
    ui_cookie_secure: bool = True

    ingestion_data_dir: str = "var/ingestion"
    ingestion_max_concurrent: int = 2
    ingestion_max_upload_bytes: int = 25_000_000
    ingestion_max_files_per_job: int = 20
    ingestion_max_total_bytes_per_job: int = 100_000_000
    ingestion_job_wall_clock_timeout_s: int = 1_800

    llm_provider: str = "openai_compat"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_max_steps: int = 50
    llm_request_timeout_s: int = 120

    chat_session_orphan_after_s: int = 1800
    chat_turn_max_wall_clock_s: int = 1800
    chat_sse_heartbeat_s: int = 15
    chat_max_concurrent_sessions_per_token: int = 5
