"""F23 "Sprawdzanie wniosku przed złożeniem".

POST /api/requests/check   a filled request → the problems found (`RequestCheckResult`)

The checks are deterministic (`app/request_check/checks.py`). With `phrase` the AI (Claude or
Gemini, `document_model.py`) rewords the problems it is given; it finds none and adds no rule,
and the answer says when it was used (`ai`). Nothing is stored.
"""

import datetime as dt
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_params, get_session_store, get_today
from app.api.document_model import ModelFactory, get_document_model_factory
from app.engine import Params, ScenarioError, Timeline, build_timeline
from app.request_check.checks import check
from app.request_check.models import RequestCheckRequest, RequestCheckResult
from app.request_check.phrasing import ModelPhraser, Phraser, apply_phrasing
from app.services.sessions import SessionStore

router = APIRouter(prefix="/api/requests", tags=["requests"])

PhraserFactory = Callable[[], Phraser]


def get_phraser_factory(
    models: Annotated[ModelFactory, Depends(get_document_model_factory)],
) -> PhraserFactory:
    return lambda: ModelPhraser(models())


@router.post("/check")
async def check_request(
    body: RequestCheckRequest,
    make_phraser: Annotated[PhraserFactory, Depends(get_phraser_factory)],
    store: Annotated[SessionStore, Depends(get_session_store)],
    params: Annotated[Params, Depends(get_params)],
    today: Annotated[dt.date, Depends(get_today)],
) -> RequestCheckResult:
    scenario = body.scenario
    if scenario is None and body.session_id is not None:
        scenario = (await store.load(body.session_id)).scenario
    timeline: Timeline | None = None
    if scenario is not None and scenario.anchor_date is not None:
        try:
            timeline = build_timeline(scenario, params, today)
        except ScenarioError:
            timeline = None
    result = check(body.request, params=params, today=today, scenario=scenario, timeline=timeline)
    if not body.phrase or not result.problems:
        return result
    try:
        phraser = make_phraser()
        phrased = await phraser.phrase(result.problems)
    except HTTPException as error:  # no key or a model that may not read documents
        result.ai_note = f"Bez przeredagowania przez AI: {error.detail}"
        return result
    except Exception:  # noqa: BLE001 — the model or the network failed
        result.ai_note = (
            "Nie udało się przeredagować komunikatów: pokazujemy je w wersji aplikacji."
        )
        return result
    result.problems = apply_phrasing(result.problems, phrased, params)
    result.ai = any(p.phrased for p in result.problems)
    if result.ai:
        result.ai_model = phraser.model_name
        result.ai_note = "Problemy znalazła aplikacja bez AI; model AI przeredagował ich opis."
    return result
