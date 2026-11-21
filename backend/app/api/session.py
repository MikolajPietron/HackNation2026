"""Session endpoints: restore a stored conversation, start one from the onboarding, forget it."""

import datetime as dt
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from app.api.chat import load_history
from app.api.deps import get_params, get_session_store, get_today
from app.assistant.transcript import to_chat_messages
from app.engine import Params, Scenario, ScenarioError, Timeline, build_timeline
from app.engine.plausibility import due_date_problem
from app.services.sessions import Session, SessionStore

router = APIRouter(prefix="/api", tags=["session"])


class SessionView(BaseModel):
    """What the UI needs to pick up where the parent left off."""

    messages: list[dict[str, Any]]
    timeline: Timeline | None


@router.get("/session/{session_id}")
async def get_session(
    session_id: UUID,
    store: Annotated[SessionStore, Depends(get_session_store)],
    params: Annotated[Params, Depends(get_params)],
    today: Annotated[dt.date, Depends(get_today)],
) -> SessionView:
    session = await store.load(session_id)
    timeline = None
    if session.scenario.due_date is not None:
        try:
            # Recalculated from the saved answers, so it always follows the current rules.
            timeline = build_timeline(session.scenario, params, today)
        except ScenarioError:
            timeline = None
    return SessionView(messages=to_chat_messages(load_history(session)), timeline=timeline)


class DueDate(BaseModel):
    due_date: dt.date


@router.put("/session/{session_id}/due-date")
async def start_with_due_date(
    session_id: UUID,
    body: DueDate,
    store: Annotated[SessionStore, Depends(get_session_store)],
    params: Annotated[Params, Depends(get_params)],
    today: Annotated[dt.date, Depends(get_today)],
) -> Timeline:
    """First answer of the interview, given in the onboarding instead of the chat.

    Starts the session from this date; the assistant then continues with the next question.
    """
    problem = due_date_problem(body.due_date, today)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    scenario = Scenario(due_date=body.due_date)
    timeline = build_timeline(scenario, params, today)
    await store.save(session_id, Session(scenario=scenario))
    return timeline


@router.delete("/session/{session_id}", status_code=204)
async def delete_session(
    session_id: UUID, store: Annotated[SessionStore, Depends(get_session_store)]
) -> Response:
    await store.delete(session_id)
    return Response(status_code=204)
