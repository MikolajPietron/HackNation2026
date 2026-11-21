"""Konfiguracja ze zmiennych środowiskowych (backend/.env, wzór w .env.example)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Supabase: klucz sekretny tylko po stronie backendu, nigdy we frontendzie.
    supabase_url: str = ""
    supabase_secret_key: str = ""

    # Claude: asystent z cytatami i odczyt skanów spraw.
    anthropic_api_key: str = ""
    llm_model: str = "claude-opus-5-5"

    # Adresy frontendu, które mogą wołać API.
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
