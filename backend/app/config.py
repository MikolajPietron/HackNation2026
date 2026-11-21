"""Settings from environment variables (backend/.env, template in .env.example)."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ThinkingLevel = Literal["minimal", "low", "medium", "high", "xhigh", "max"]
LlmProvider = Literal["openrouter", "anthropic", "google"]

DEFAULT_MODELS: dict[LlmProvider, str] = {
    "openrouter": "anthropic/claude-opus-5.5",
    "anthropic": "claude-opus-5-5",
    # Fast, for the chat's many tool calls.
    "google": "gemini-flash-latest",
}
# The scans need the strongest reader of the provider.
DEFAULT_CASES_MODELS: dict[LlmProvider, str] = {
    **DEFAULT_MODELS,
    "google": "gemini-pro-latest",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Supabase: the secret key stays in the backend, never in the frontend.
    supabase_url: str = ""
    supabase_secret_key: str = ""

    # LLM for the chat assistant (Pydantic AI): OpenRouter by default, or Anthropic, or Google
    # (Gemini, with GEMINI_API_KEY).
    llm_provider: LlmProvider = "openrouter"
    openrouter_api_key: str = ""
    anthropic_api_key: str = ""
    llm_model: str = ""
    """Empty = the default model of the provider (Claude Opus 5.5)."""
    llm_thinking: ThinkingLevel | None = None
    """Thinking effort; unset = the model's default (adaptive thinking on Claude Opus 5.5)."""

    # Example cases from ZUS (scanned PDFs, confidential, never in git): the folder they are in,
    # and where the facts read from them are kept. Empty = docs/dokumentyZUS/sprawy.
    cases_dir: str = ""
    cases_cache_dir: str = ".cases_cache"
    cases_model: str = ""
    """The model that reads the scans: Claude or Gemini only (team decision, CLAUDE.md), whatever
    LLM_MODEL the chat uses. Empty = Claude Opus 5.5 of the provider; "gemini-…" = Google with
    GEMINI_API_KEY."""
    gemini_api_key: str = ""

    # Frontend origins allowed to call the API.
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @property
    def llm_api_key(self) -> str:
        return {
            "openrouter": self.openrouter_api_key,
            "anthropic": self.anthropic_api_key,
            "google": self.gemini_api_key,
        }[self.llm_provider]

    @property
    def llm_model_name(self) -> str:
        return self.llm_model or DEFAULT_MODELS[self.llm_provider]

    @property
    def cases_model_name(self) -> str:
        return self.cases_model or DEFAULT_CASES_MODELS[self.llm_provider]


@lru_cache
def get_settings() -> Settings:
    return Settings()
