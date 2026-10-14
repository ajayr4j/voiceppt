from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Backend configuration, loaded from environment / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = "sk-placeholder-replace-me"
    realtime_model: str = "gpt-realtime-2.1"
    realtime_voice: str = "marin"
    cors_allow_origins: str = "http://localhost:5173"


settings = Settings()
