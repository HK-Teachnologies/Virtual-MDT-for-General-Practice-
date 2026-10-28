from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://mdt:changeme@db:5432/virtualmdt"
    upload_dir: str = "uploads"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "Virtual MDT <noreply@example.com>"
    otp_expire_minutes: int = 10
    otp_max_attempts: int = 5
    secret_key: str = "dev-only-change-me"
    access_token_expire_minutes: int = 60 * 24

    # Background jobs.
    redis_url: str = "redis://localhost:6379/0"
    celery_task_always_eager: bool = False

    # LLM access goes through one OpenAI-compatible path (LiteLLM), so the
    # provider is swappable without touching MDT logic. META_API_KEY is kept
    # as a fallback because existing .env files already carry it.
    llm_provider: str = "echo"  # echo | litellm
    llm_api_key: str = ""
    meta_api_key: str = ""
    llm_api_base: str = ""  # e.g. a self-hosted LiteLLM proxy URL
    llm_model: str = "gpt-4o-mini"
    llm_vision_model: str = ""  # falls back to llm_model (must be multimodal)
    llm_transcribe_model: str = "whisper-1"
    llm_embed_model: str = "text-embedding-3-small"
    # Must match the model server's embedding model (bge-base-en-v1.5 = 768).
    llm_embed_dim: int = 768
    llm_embed_batch: int = 128
    # Local embedding server (docker compose sets this). When set, embed()
    # calls it over HTTP so no patient text leaves the deployment; chat and
    # transcription still go through LiteLLM. Empty = use LiteLLM/echo.
    model_server_url: str = ""
    prompt_version: str = "v1"


settings = Settings()
