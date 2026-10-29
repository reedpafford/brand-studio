"""Settings read from environment variables (prefix BS_). Never hard-code secrets."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

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
    # The test site shares live's address on another port, and cookies ignore ports.
    cookie_name: str = "bs_session"
    # Uploaded files (local disk for now; S3-compatible later)
    storage_dir: str = "./storage"
    max_upload_mb: int = 200
    # Launch brands' real screens, logos and style boards, imported on first setup
    # ("" to skip): <dir>/fomo/screens, <dir>/ironpaws/screens.
    brand_assets_dir: str = str(REPO_ROOT / "assets" / "brands")
    # Reference reels a brief can adapt: folders with BREAKDOWN.json (+ contact.jpg).
    references_dir: str = str(REPO_ROOT / "docs" / "references")
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
    # Suno through KIE (app/providers/kie.py). Off until Reed says so; key from KIE_API_KEY
    # only (never in code or logs). Songs download only over https from these hosts.
    kie_suno: bool = False
    kie_base_url: str = "https://api.kie.ai/api/v1"
    kie_api_key: SecretStr = Field(SecretStr(""), validation_alias="KIE_API_KEY")
    kie_delivery_hosts: list[str] = []  # set with the switch, from a real song link
    # Real songs stop before their spend would pass this (0: none). Each request counts at
    # this price until KIE's real one is known (music.py A4).
    kie_budget_usd: float = 0.0
    kie_usd_per_request: float = 0.1028
    # Real look samples on the test site (Reed, 2026-10-29): with the stand-ins on, a look's
    # sample (its still and 5 s clip) alone is made on Replicate, until the next one would
    # take their spend past this budget; after that a sample is a stand-in again.
    real_look_samples: bool = False
    look_samples_budget_usd: float = 0.0
    # Claude: key from STUDIO_ANTHROPIC_KEY only (never in code or logs).
    anthropic_key: SecretStr = Field(SecretStr(""), validation_alias="STUDIO_ANTHROPIC_KEY")
    # Paid generation (Replicate, Claude). Off by default: the owner turns it on at deploy.
    generation_enabled: bool = False
    # Local runs only: stand-ins for Replicate and Claude (grey pictures, simple answers).
    # Nothing is sent or billed, and Generate works even with generation switched off.
    fake_providers: bool = False
    # The advisory check on stills and takes (flows 1b, P4) costs real calls: off until the
    # Producer approves a real test; with the stand-ins on, it always runs (free).
    item_checks_paid: bool = False
    # Import from website (BR2): reading a real site. Off until the Producer approves a real
    # test; the stand-ins give a practice page, and with it off a read says so.
    site_read_real: bool = False
    # The music bed under a narration (N1) is a Claude call and a Stable Audio file: off until
    # the Producer approves a real test; with the stand-ins on, it always runs (free). Real
    # runs stop before their spend would pass the budget, each counted at its rough price.
    narration_music_paid: bool = False
    narration_music_budget_usd: float = 0.0
    narration_music_usd_per_run: float = 0.25  # the bed's $0.20 and the prompt's call
    # Which items are checked (Producer, 2026-10-29, to fit "a few cents a video"):
    # key_takes (default): takes of ★-product or speaking clips, one frame each; all_takes:
    # every take, one frame; everything: stills too, and three frames a take.
    item_check_scope: Literal["key_takes", "all_takes", "everything"] = "key_takes"
    # Background worker
    worker_poll_seconds: float = 2.0
    # Which providers' jobs this worker takes, e.g. ["local"] for a reel-prep worker; empty: all.
    worker_providers: list[str] = []
    # One-time secret needed to create the first owner (POST /auth/setup). Empty = disabled.
    setup_token: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


def check_production(settings: Settings) -> None:
    """Refuse to start a live server (or the test site, env "next") that still has example
    secrets from deploy/.env.example. Only the test site may run on the free stand-ins."""
    if settings.env not in ("production", "next"):
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
    if settings.fake_providers and settings.env == "production":
        problems.append("BS_FAKE_PROVIDERS is on: it's for local runs only, remove the line.")
    if problems:
        raise RuntimeError("Not starting. Fix deploy/.env: " + " ".join(problems))
