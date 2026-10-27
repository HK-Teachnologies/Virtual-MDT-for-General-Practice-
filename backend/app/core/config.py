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


settings = Settings()
