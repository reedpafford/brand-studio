"""Settings read from environment variables (prefix BS_). Never hard-code secrets."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

REPO_ROOT = Path(__file__).resolve().parents[2]
PLACEHOLDER = "change-me"  # the example value in deploy/.env.example


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
    # Launch brands' real screens, logos and style boards, imported on first setup
    # ("" to skip): <dir>/fomo/screens, <dir>/ironpaws/screens.
    brand_assets_dir: str = str(REPO_ROOT / "assets" / "brands")
    # Login throttling: this many failures within the window locks the email / IP out.
    login_max_failures: int = 5
    login_max_failures_per_ip: int = 20
    login_window_minutes: int = 15
    # Replicate. In the sandbox the network proxy adds credentials.
    replicate_base_url: str = "https://api.replicate.com/v1"
    # Deployed servers have no proxy: set REPLICATE_API_TOKEN there. Never logged.
    replicate_token: SecretStr = Field(SecretStr(""), validation_alias="REPLICATE_API_TOKEN")
    # Outputs are only downloaded over https from these hosts (and their subdomains).
    replicate_delivery_hosts: list[str] = ["replicate.delivery"]
    max_download_mb: int = 500
    # Claude: key from STUDIO_ANTHROPIC_KEY only (never in code or logs).
    anthropic_key: SecretStr = Field(SecretStr(""), validation_alias="STUDIO_ANTHROPIC_KEY")
    # Paid generation (Replicate, Claude). Off by default: the owner turns it on at deploy.
    generation_enabled: bool = False
    # Local runs only: stand-ins for Replicate and Claude (grey pictures, simple answers).
    # Nothing is sent or billed, and Generate works even with generation switched off.
    fake_providers: bool = False
    # Background worker
    worker_poll_seconds: float = 2.0
    # One-time secret needed to create the first owner (POST /auth/setup). Empty = disabled.
    setup_token: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


def check_production(settings: Settings) -> None:
    """Refuse to start a live server that still has example secrets from deploy/.env.example."""
    if settings.env != "production":
        return
    problems = []
    token = settings.setup_token
    if token and (token == PLACEHOLDER or len(token) < 24):
        problems.append(
            "BS_SETUP_TOKEN is the example value or under 24 characters: "
            "use `openssl rand -hex 32`, or remove the line once setup is done."
        )
    if make_url(settings.database_url).password == PLACEHOLDER:
        problems.append("POSTGRES_PASSWORD is the example value: use `openssl rand -hex 24`.")
    if settings.fake_providers:
        problems.append("BS_FAKE_PROVIDERS is on: it's for local runs only, remove the line.")
    if problems:
        raise RuntimeError("Not starting. Fix deploy/.env: " + " ".join(problems))
