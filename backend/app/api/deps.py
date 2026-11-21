"""Shared FastAPI dependencies. Tests override them via `app.dependency_overrides`."""

import datetime as dt
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openrouter import OpenRouterProvider
from pydantic_ai.settings import ModelSettings

from app.clock import today_in_warsaw
from app.config import LlmProvider, Settings, ThinkingLevel, get_settings
from app.engine import Params
from app.services.param_versions import ParamStore, active_params, open_param_store
from app.services.params import load_params
from app.services.sessions import SessionStore, open_session_store

KEY_NAMES: dict[LlmProvider, str] = {
    "openrouter": "OPENROUTER_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GEMINI_API_KEY",
}


def get_today() -> dt.date:
    return today_in_warsaw()


async def get_param_store(settings: Annotated[Settings, Depends(get_settings)]) -> ParamStore:
    return await open_param_store(settings.supabase_url, settings.supabase_secret_key)


async def get_params(
    store: Annotated[ParamStore, Depends(get_param_store)],
    today: Annotated[dt.date, Depends(get_today)],
) -> Params:
    """The parameters in force today: the newest admin version whose date has come, else the
    base file. The engine gets them as an argument and never reads the database itself."""
    return active_params(load_params(), await store.list(), today)


async def get_session_store(settings: Annotated[Settings, Depends(get_settings)]) -> SessionStore:
    return await open_session_store(settings.supabase_url, settings.supabase_secret_key)


def get_chat_model(settings: Annotated[Settings, Depends(get_settings)]) -> Model:
    if not settings.llm_api_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "Asystent AI jest wyłączony: brak klucza "
                f"{KEY_NAMES[settings.llm_provider]} w backend/.env."
            ),
        )
    return _chat_model(
        settings.llm_provider, settings.llm_model_name, settings.llm_api_key, settings.llm_thinking
    )


@lru_cache(maxsize=4)
def _chat_model(
    provider: LlmProvider, name: str, api_key: str, thinking: ThinkingLevel | None
) -> Model:
    model_settings = ModelSettings(cache=True)
    if thinking is not None:
        model_settings["thinking"] = thinking
    if provider == "google":
        return GoogleModel(name, provider=GoogleProvider(api_key=api_key), settings=model_settings)
    if provider == "openrouter":
        return OpenRouterModel(
            name, provider=OpenRouterProvider(api_key=api_key), settings=model_settings
        )
    return AnthropicModel(
        name, provider=AnthropicProvider(api_key=api_key), settings=model_settings
    )
