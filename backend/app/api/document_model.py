"""The model for documents people upload or fill in: a letter from ZUS (F24) and the wording of a
request check (F23). The same rule as the case reader: Claude or Gemini only (team decision,
CLAUDE.md "Dane i poufność"), from CASES_MODEL, never the chat's model of another vendor. The
model is made only when it is needed, so a request without AI needs no key. Tests replace
`get_document_model_factory` with a scripted model."""

from collections.abc import Callable
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException
from pydantic_ai.models import Model
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from app.api.deps import KEY_NAMES, _chat_model
from app.config import Settings, get_settings

ModelFactory = Callable[[], Model]

NOT_ALLOWED = (
    "Pisma i wnioski czyta tylko Claude albo Gemini (decyzja zespołu): ustaw CASES_MODEL "
    "w backend/.env."
)


def allowed(name: str) -> bool:
    """Claude (directly or through OpenRouter) or Gemini; nothing else gets the documents."""
    lowered = name.lower()
    return lowered.startswith("gemini") or "claude" in lowered


def get_document_model_factory(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ModelFactory:
    def make() -> Model:
        name = settings.cases_model_name
        if not allowed(name):
            raise HTTPException(503, NOT_ALLOWED)
        if name.startswith("gemini"):
            if not settings.gemini_api_key:
                raise HTTPException(503, "Gemini wymaga klucza GEMINI_API_KEY w backend/.env.")
            return _gemini_model(name, settings.gemini_api_key)
        provider = settings.llm_provider
        if provider == "google":
            # Claude is never reached through Google: only with its own key.
            provider = "anthropic"
        key = settings.anthropic_api_key if provider == "anthropic" else settings.llm_api_key
        if not key:
            raise HTTPException(
                503, f"Odczyt przez AI jest wyłączony: brak klucza {KEY_NAMES[provider]}."
            )
        return _chat_model(provider, name, key, None)

    return make


@lru_cache(maxsize=2)
def _gemini_model(name: str, api_key: str) -> Model:
    return GoogleModel(name, provider=GoogleProvider(api_key=api_key))
