"""Settings read from environment variables (prefix BS_). Never hard-code secrets."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BS_", env_file=".env", extra="ignore")

    env: str = "dev"
    database_url: str = "sqlite:///./dev.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
