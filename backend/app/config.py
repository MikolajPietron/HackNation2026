"""Settings from environment variables (backend/.env, template in .env.example)."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ThinkingLevel = Literal["minimal", "low", "medium", "high", "xhigh", "max"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Supabase: the secret key stays in the backend, never in the frontend.
    supabase_url: str = ""
    supabase_secret_key: str = ""

    # Claude: chat assistant (Pydantic AI), later also reading case scans.
    anthropic_api_key: str = ""
    llm_model: str = "claude-opus-5-5"
    llm_thinking: ThinkingLevel | None = None
    """Thinking effort; unset = the model's default (adaptive thinking on Claude Opus 5.5)."""

    # Frontend origins allowed to call the API.
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
