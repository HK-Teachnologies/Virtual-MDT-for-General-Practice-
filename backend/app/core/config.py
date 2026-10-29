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
    # Log OTP codes server-side (dev/demo use made-up addresses that never
    # receive mail). Set OTP_LOG_CODE=false in production to turn it off.
    otp_log_code: bool = True
    secret_key: str = "dev-only-change-me"
    access_token_expire_minutes: int = 60 * 24

    # Background jobs.
    redis_url: str = "redis://localhost:6379/0"
    celery_task_always_eager: bool = False

    # Public origin of the web app, used for links inside notification emails.
    frontend_url: str = "https://localhost"

    # LLM access goes through one OpenAI-compatible path (LiteLLM), so the
    # provider is swappable without touching MDT logic. META_API_KEY is kept
    # as a fallback because existing .env files already carry it.
    llm_provider: str = "echo"  # echo | litellm
    llm_api_key: str = ""
    meta_api_key: str = ""
    llm_api_base: str = "https://api.meta.ai/v1"
    llm_model: str = "openai/muse-spark-1.3"
    llm_vision_model: str = ""  # falls back to llm_model (must be multimodal)
    llm_transcribe_model: str = "muse-voice-transcribe-1.0"
    llm_embed_model: str = "text-embedding-3-small"
    # Must match the model server's embedding model (bge-base-en-v1.5 = 768).
    llm_embed_dim: int = 768
    llm_embed_batch: int = 128
    # Local embedding server (docker compose sets this). When set, embed()
    # calls it over HTTP so no patient text leaves the deployment; chat and
    # transcription still go through LiteLLM. Empty = use LiteLLM/echo.
    model_server_url: str = ""
    prompt_version: str = "v2"


settings = Settings()
