"""Settings read from environment variables (prefix BS_). Never hard-code secrets."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BS_", env_file=".env", extra="ignore")

    env: str = "dev"
    database_url: str = "sqlite:///./dev.db"
    # Login sessions
    session_days: int = 30
    invite_days: int = 7
    cookie_secure: bool = True  # set BS_COOKIE_SECURE=false only for local http
    # Uploaded files (local disk for now; S3-compatible later)
    storage_dir: str = "./storage"
    max_upload_mb: int = 200
    # Folder of fomo UI screens imported on first setup (optional)
    fomo_screens_dir: str = ""
    # Login throttling: this many failures within the window locks the email / IP out.
    login_max_failures: int = 5
    login_max_failures_per_ip: int = 20
    login_window_minutes: int = 15
    # Claude: key from STUDIO_ANTHROPIC_KEY only (never in code or logs).
    anthropic_key: SecretStr = Field(SecretStr(""), validation_alias="STUDIO_ANTHROPIC_KEY")
    # Background worker
    worker_poll_seconds: float = 2.0
    # One-time secret needed to create the first owner (POST /auth/setup). Empty = disabled.
    setup_token: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
