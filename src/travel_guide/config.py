from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str
    telegram_bot_token: str
    google_maps_api_key: str = ""

    # Haiku is the default for cost; switch to claude-sonnet-5-5 if plan quality suffers.
    claude_model: str = "claude-haiku-5-5"
    claude_effort: str = "low"
    max_tokens: int = 8000
    # Keep only the last N messages per user to bound cost.
    history_limit: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()
