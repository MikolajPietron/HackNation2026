"""Shared FastAPI dependencies. Tests override them via `app.dependency_overrides`."""

import datetime as dt
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel, AnthropicModelSettings
from pydantic_ai.providers.anthropic import AnthropicProvider

from app.clock import today_in_warsaw
from app.config import Settings, ThinkingLevel, get_settings
from app.engine import Params
from app.services.params import load_params


def get_params() -> Params:
    return load_params()


def get_today() -> dt.date:
    return today_in_warsaw()


def get_chat_model(settings: Annotated[Settings, Depends(get_settings)]) -> Model:
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="Asystent AI jest wyłączony: brak klucza ANTHROPIC_API_KEY w backend/.env.",
        )
    return _anthropic_model(settings.llm_model, settings.anthropic_api_key, settings.llm_thinking)


@lru_cache(maxsize=4)
def _anthropic_model(name: str, api_key: str, thinking: ThinkingLevel | None) -> Model:
    model_settings = AnthropicModelSettings(cache=True)
    if thinking is not None:
        model_settings["thinking"] = thinking
    provider = AnthropicProvider(api_key=api_key)
    return AnthropicModel(name, provider=provider, settings=model_settings)
