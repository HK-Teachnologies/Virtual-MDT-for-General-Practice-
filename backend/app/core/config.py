from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://mdt:changeme@db:5432/virtualmdt"
    secret_key: str = "dev-only-change-me"
    access_token_expire_minutes: int = 60 * 24


settings = Settings()
