"""Environment configuration. Values come from env vars / .env (see .env.example)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(REPO_DIR / ".env", BACKEND_DIR / ".env"), extra="ignore")

    app_mode: Literal["historical", "live"] = "historical"
    llm_mode: Literal["fake", "live", "replay"] = "fake"

    gemini_api_key: str | None = None
    gemini_api_key_backups: str | None = None   # comma-separated; used in order when a key's quota runs out
    gemini_model_deep: str = "gemini-4-argon"
    gemini_model_fast: str = "gemini-4-argon"  # Argon everywhere; Flash (gemini-3.8-flash) is the fallback

    eodhd_api_key: str | None = None
    finnhub_api_key: str | None = None
    alpaca_key_id: str | None = None
    alpaca_secret_key: str | None = None
    edgar_user_agent: str = "UclAgentVerse hackathon team (set EDGAR_USER_AGENT)"

    snapshot_dir: Path = BACKEND_DIR / "data" / "snapshot"
    state_db: Path = BACKEND_DIR / "state.sqlite"
    runs_dir: Path = BACKEND_DIR / "runs"
    recorded_run: Path | None = None  # optional immutable historical replay, loaded at startup
    static_dir: Path = BACKEND_DIR / "app" / "static"

    public_demo: bool = False
    demo_passcode: str | None = None
    task_secret: str | None = None
    daily_llm_budget_usd: float = 20.0
    rate_limit_per_minute: int = 30   # POSTs per visitor IP per minute in the public demo (#12)

    @model_validator(mode="after")
    def _public_demo_replays(self) -> Settings:
        # PUBLIC_DEMO=1 replays the recorded run by default: no Gemini calls unless LLM_MODE is set explicitly.
        if self.public_demo and "llm_mode" not in self.model_fields_set:
            self.llm_mode = "replay"
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
